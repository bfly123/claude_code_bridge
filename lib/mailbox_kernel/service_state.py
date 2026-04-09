from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MailboxKernelRuntimeState:
    layout: object
    clock: object
    mailbox_store: object
    inbound_store: object
    lease_store: object
    normalize_agent_name: object
    terminal_event_states: object
    claimable_event_states: object
    mailbox_record_cls: object
    delivery_lease_cls: object
    reply_event_type: object
    lease_state_acquired: object
    mailbox_state_delivering: object
    mailbox_state_blocked: object
    mailbox_state_idle: object
    status_delivering: object
    status_consumed: object


class MailboxKernelStateMixin:
    @property
    def _layout(self):
        return self._runtime_state.layout

    @property
    def _clock(self):
        return self._runtime_state.clock

    @property
    def _mailbox_store(self):
        return self._runtime_state.mailbox_store

    @property
    def _inbound_store(self):
        return self._runtime_state.inbound_store

    @property
    def _lease_store(self):
        return self._runtime_state.lease_store

    @property
    def _normalize_agent_name(self):
        return self._runtime_state.normalize_agent_name

    @property
    def _terminal_event_states(self):
        return self._runtime_state.terminal_event_states

    @property
    def _claimable_event_states(self):
        return self._runtime_state.claimable_event_states

    @property
    def _mailbox_record_cls(self):
        return self._runtime_state.mailbox_record_cls

    @property
    def _delivery_lease_cls(self):
        return self._runtime_state.delivery_lease_cls

    @property
    def _reply_event_type(self):
        return self._runtime_state.reply_event_type

    @property
    def _lease_state_acquired(self):
        return self._runtime_state.lease_state_acquired

    @property
    def _mailbox_state_delivering(self):
        return self._runtime_state.mailbox_state_delivering

    @property
    def _mailbox_state_blocked(self):
        return self._runtime_state.mailbox_state_blocked

    @property
    def _mailbox_state_idle(self):
        return self._runtime_state.mailbox_state_idle

    @property
    def _status_delivering(self):
        return self._runtime_state.status_delivering

    @property
    def _status_consumed(self):
        return self._runtime_state.status_consumed


__all__ = [
    'MailboxKernelRuntimeState',
    'MailboxKernelStateMixin',
]
