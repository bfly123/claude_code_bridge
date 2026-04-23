from __future__ import annotations

from pathlib import Path

from storage.atomic import atomic_write_text

# cmd-only reply body persistence.
# Keeps long reply bodies out of cmd transcript by writing them to disk; the
# cmd pane gets a header-only pointer. Intentionally isolated from the shared
# transfer namespace (.ccb/history/) to avoid filename collisions with
# ctx-transfer artifacts.
#
# Must only be called from phase 2 (post-claim) of _deliver_cmd_replies.
# Writing in phase 1 (validate) would orphan files on validate-retry loops.

_SUBDIR = ('replies', 'cmd')


def reply_body_dir(project_root: Path) -> Path:
    return Path(project_root) / '.ccb' / _SUBDIR[0] / _SUBDIR[1]


def body_file_path(project_root: Path, reply_id: str) -> Path:
    safe = reply_id.replace('/', '_').replace('\\', '_')
    return reply_body_dir(project_root) / f'{safe}.md'


def write_reply_body(project_root: Path, reply_id: str, body: str) -> Path:
    target = body_file_path(project_root, reply_id)
    atomic_write_text(target, body)
    return target


__all__ = ['reply_body_dir', 'body_file_path', 'write_reply_body']
