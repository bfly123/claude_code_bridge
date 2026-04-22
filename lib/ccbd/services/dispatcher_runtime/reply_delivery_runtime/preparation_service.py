from __future__ import annotations

import collections
import logging
import time

from mailbox_kernel import InboundEventStatus, InboundEventType
from message_bureau.reply_payloads import reply_id_from_payload

from . import cmd_body_store
from .cmd_delivery_telemetry import (
    record_header_only_dispatch,
    record_long_reply_fallback,
    record_phase2_failure,
)
from .cmd_transport_planner import plan_cmd_delivery
from .common import head_reply_id, project_id_for_agent
from .preparation_head import resolve_existing_delivery_job
from .preparation_message import build_reply_delivery_job
from .repair import repair_reply_delivery_heads

_logger = logging.getLogger(__name__)

_CMD_PANE_CACHE_TTL = 30.0
# In-memory LRU of reply_ids already injected into the cmd pane. Prevents
# re-injecting the same reply on every tick while the head still waits for
# `client.ack('cmd')` from the cmd user. Bounded so long-lived daemons do
# not leak memory; if a reply ages out of the cache it will be re-injected
# on the next tick, which is visually annoying but never unsafe (cmd text
# inject is an at-least-once delivery, not exactly-once).
_CMD_INJECTED_CACHE_MAX = 256


def prepare_reply_deliveries(dispatcher):
    control = getattr(dispatcher, '_message_bureau_control', None)
    bureau = getattr(dispatcher, '_message_bureau', None)
    if control is None or bureau is None:
        return ()

    repair_reply_delivery_heads(dispatcher)
    created = []
    for agent_name in dispatcher._config.agents:
        job = prepare_agent_reply_delivery(dispatcher, agent_name)
        if job is not None:
            created.append(job)

    if bool(getattr(dispatcher._config, 'cmd_enabled', False)):
        _deliver_cmd_replies(dispatcher)

    return tuple(created)


def _deliver_cmd_replies(dispatcher):
    """Side-effect-only cmd delivery: inject pane text, leave head for human ack.

    CCB contract: `client.ack('cmd')` is the human-driven consumer of the cmd
    mailbox head. This function's job is to surface replies in the tmux pane,
    NOT to burn the inbox head. Any claim/consume/abandon here would race
    against the user's ack call (and was the root cause of the reply-loss
    finding from codex structural review 2026-04-22).

    Idempotency: reply_ids already injected are cached in an LRU on the
    dispatcher so we don't spam the pane on every tick while the user
    hasn't acked yet. Environmental failures (no pane, dead backend) return
    silently and let the next tick retry once the environment recovers.
    """
    control = getattr(dispatcher, '_message_bureau_control', None)
    if control is None:
        return

    kernel = getattr(control, '_mailbox_kernel', None)
    if kernel is None:
        return

    head = kernel.head_pending_event('cmd')
    if head is None or head.event_type is not InboundEventType.TASK_REPLY:
        return

    # Only act on fresh heads. If the head is DELIVERING, an older flow did
    # claim it — we leave it for the legacy stale-repair path (or the ack
    # handler) rather than re-acting. CONSUMED/ABANDONED/SUPERSEDED are
    # already filtered out by head_pending_event.
    if head.status not in (InboundEventStatus.CREATED, InboundEventStatus.QUEUED):
        return

    reply_id = reply_id_from_payload(head.payload_ref)
    if not reply_id:
        # Malformed payload. We can't look up the reply, and there's no
        # point re-scanning the same head forever. Leaving it QUEUED would
        # stall the cmd mailbox. This is a true permanent failure — abandon.
        try:
            kernel.abandon('cmd', head.inbound_event_id, finished_at=dispatcher._clock())
        except Exception:
            _logger.debug('cmd head abandon (malformed payload) failed', exc_info=True)
        return

    injected_cache = _get_injected_cache(dispatcher)
    if reply_id in injected_cache:
        # Already handed this reply to the pane; waiting on human ack.
        return

    reply_store = getattr(control, '_reply_store', None)
    if reply_store is None:
        return
    reply = reply_store.get_latest(reply_id)
    if reply is None:
        # Rare race with a concurrent reply writer; try again next tick.
        return

    project_root = _resolve_project_root(dispatcher)

    cmd_pane_id = _discover_cmd_pane_id(dispatcher)
    if not cmd_pane_id:
        _logger.debug('cmd pane not discoverable; leaving head queued for next tick')
        return

    backend = _get_tmux_backend(dispatcher)
    if backend is None:
        _logger.debug('cmd tmux backend unavailable; leaving head queued for next tick')
        return

    try:
        if not backend.is_alive(cmd_pane_id):
            _invalidate_cmd_pane_cache(dispatcher)
            _logger.debug('cmd pane %s not alive; leaving head queued for next tick', cmd_pane_id)
            return
    except Exception:
        _invalidate_cmd_pane_cache(dispatcher)
        _logger.debug('cmd pane liveness check raised; leaving head queued', exc_info=True)
        return

    body_char_count = len(reply.reply or '')

    try:
        plan, fallback = plan_cmd_delivery(
            dispatcher,
            reply,
            project_root=project_root,
            body_store=cmd_body_store,
        )
    except Exception:
        _logger.warning(
            'cmd reply %s planning failed; leaving head queued for next tick',
            reply_id, exc_info=True,
        )
        record_phase2_failure(
            project_root,
            reply_id=reply.reply_id,
            stage='plan',
            reason='exception',
            body_char_count=body_char_count,
            failed_at=dispatcher._clock(),
        )
        return

    if fallback is not None:
        record_long_reply_fallback(
            project_root,
            reply_id=reply.reply_id,
            reason=fallback.reason,
            body_char_count=fallback.body_char_count,
            dispatched_at=dispatcher._clock(),
        )

    try:
        backend.send_text_to_pane(cmd_pane_id, plan.body)
    except Exception:
        _logger.warning(
            'cmd reply %s pane injection failed; leaving head queued for next tick',
            reply_id, exc_info=True,
        )
        _invalidate_cmd_pane_cache(dispatcher)
        record_phase2_failure(
            project_root,
            reply_id=reply.reply_id,
            stage='send',
            reason='exception',
            body_char_count=body_char_count,
            failed_at=dispatcher._clock(),
        )
        return

    if plan.header_only and plan.body_file is not None and project_root is not None:
        record_header_only_dispatch(
            project_root,
            reply_id=reply.reply_id,
            body_file=plan.body_file,
            dispatched_at=dispatcher._clock(),
            body_char_count=body_char_count,
        )

    # Mark as injected so subsequent ticks don't re-inject before the user
    # calls ack. Added AFTER the inject succeeds so a transient send failure
    # triggers retry on the next tick.
    injected_cache[reply_id] = None  # OrderedDict used as LRU set
    while len(injected_cache) > _CMD_INJECTED_CACHE_MAX:
        injected_cache.popitem(last=False)


def _get_injected_cache(dispatcher):
    cache = getattr(dispatcher, '_cmd_injected_replies', None)
    if cache is None:
        cache = collections.OrderedDict()
        try:
            dispatcher._cmd_injected_replies = cache
        except AttributeError:
            # Attribute assignment failed (e.g., dispatcher uses __slots__)
            # — fall back to a throwaway cache so inject still works; the
            # tradeoff is we may re-inject more often than necessary.
            return collections.OrderedDict()
    return cache


# Fix #3: TTL-based cache instead of permanent.
def _discover_cmd_pane_id(dispatcher) -> str | None:
    cache = getattr(dispatcher, '_cmd_pane_cache', None)
    now = time.monotonic()

    if cache is not None:
        cached_id, cached_at = cache
        if (now - cached_at) < _CMD_PANE_CACHE_TTL:
            return cached_id if cached_id else None

    layout = getattr(dispatcher, '_layout', None)
    if layout is None:
        return None

    pane_id = _lookup_cmd_pane_id(dispatcher, layout)

    if pane_id is not None:
        try:
            dispatcher._cmd_pane_cache = (pane_id, now)
        except AttributeError:
            pass

    return pane_id


def _invalidate_cmd_pane_cache(dispatcher):
    try:
        dispatcher._cmd_pane_cache = None
    except AttributeError:
        pass


def _resolve_project_root(dispatcher):
    layout = getattr(dispatcher, '_layout', None)
    if layout is None:
        return None
    root = getattr(layout, 'project_root', None)
    return root


def _resolve_project_id(dispatcher, layout) -> str | None:
    runtime_service = getattr(dispatcher, '_runtime_service', None)
    project_id = str(getattr(runtime_service, '_project_id', '') or '').strip()
    if project_id:
        return project_id
    try:
        from project.ids import compute_project_id
        return compute_project_id(layout.project_root)
    except Exception:
        pass
    try:
        from storage.paths_ccbd import compute_project_id
        return compute_project_id(layout.project_root)
    except Exception:
        return None


def _lookup_cmd_pane_id(dispatcher, layout) -> str | None:
    try:
        from ccbd.services.project_namespace import ProjectNamespaceController
        from ccbd.services.project_namespace_runtime.backend import build_backend

        project_id = _resolve_project_id(dispatcher, layout)
        if not project_id:
            return None
        controller = ProjectNamespaceController(layout, project_id)
        namespace = controller.load()
        if namespace is None:
            return None

        socket_path = str(getattr(namespace, 'tmux_socket_path', None) or '').strip()
        if not socket_path:
            return None

        backend = build_backend(controller._backend_factory, socket_path=socket_path)
        project_id_str = str(project_id)

        runner = getattr(backend, '_tmux_run', None)
        if not callable(runner):
            return None

        try:
            cp = runner(
                ['list-panes', '-a', '-F',
                 '#{pane_id}\t#{@ccb_role}\t#{@ccb_slot}\t#{@ccb_project_id}'],
                capture=True,
                check=True,
            )
        except Exception:
            return None

        stdout = getattr(cp, 'stdout', '') or ''
        for line in stdout.splitlines():
            parts = line.strip().split('\t')
            if len(parts) < 4:
                continue
            pane_id, role, slot, pane_project = parts[0], parts[1], parts[2], parts[3]
            if (role == 'cmd' and slot == 'cmd'
                    and pane_project == project_id_str
                    and pane_id.startswith('%')):
                return pane_id
    except Exception:
        _logger.debug('cmd pane discovery failed', exc_info=True)

    return None


def _get_tmux_backend(dispatcher):
    try:
        from ccbd.services.project_namespace import ProjectNamespaceController
        from ccbd.services.project_namespace_runtime.backend import build_backend

        layout = dispatcher._layout
        project_id = _resolve_project_id(dispatcher, layout)
        if not project_id:
            return None
        controller = ProjectNamespaceController(layout, project_id)
        namespace = controller.load()
        if namespace is None:
            return None
        socket_path = str(getattr(namespace, 'tmux_socket_path', None) or '').strip()
        if not socket_path:
            return None
        return build_backend(controller._backend_factory, socket_path=socket_path)
    except Exception:
        _logger.debug('tmux backend construction failed', exc_info=True)
        return None


def prepare_agent_reply_delivery(dispatcher, agent_name: str):
    from .common import head_reply_event

    head = head_reply_event(dispatcher, agent_name)
    if head is None:
        return None
    reply_id = head_reply_id(head)
    if not reply_id:
        return None

    head = resolve_existing_delivery_job(
        dispatcher,
        agent_name,
        head,
        reply_id=reply_id,
    )
    if head is None or head is False:
        return None

    reply = dispatcher._message_bureau_control._reply_store.get_latest(reply_id)
    if reply is None:
        return None

    accepted_at = dispatcher._clock()
    project_id = project_id_for_agent(dispatcher, agent_name)
    if not project_id:
        return None
    return build_reply_delivery_job(
        dispatcher,
        agent_name=agent_name,
        head=head,
        reply=reply,
        accepted_at=accepted_at,
        project_id=project_id,
    )


__all__ = ['prepare_reply_deliveries']
