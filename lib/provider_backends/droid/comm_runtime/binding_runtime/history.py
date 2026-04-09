from __future__ import annotations

import time
from pathlib import Path


def record_previous_binding(
    data: dict[str, object],
    *,
    old_path: str,
    old_id: str,
    new_path: str,
    new_id: str,
    binding_changed: bool,
) -> None:
    _record_old_session_id(data, old_id=old_id, new_id=new_id)
    _record_old_session_path(
        data,
        old_path=old_path,
        new_path=new_path,
        old_id=old_id,
        new_id=new_id,
    )
    _record_old_binding_timestamp(
        data,
        old_path=old_path,
        old_id=old_id,
        binding_changed=binding_changed,
    )


def maybe_transfer_previous_binding(
    data: dict[str, object],
    *,
    old_path: str,
    old_id: str,
    binding_changed: bool,
) -> None:
    if not _should_transfer_previous_binding(
        old_path=old_path,
        old_id=old_id,
        binding_changed=binding_changed,
    ):
        return
    try:
        from memory.transfer_runtime import maybe_auto_transfer

        maybe_auto_transfer(
            provider='droid',
            work_dir=_work_dir_from_data(data),
            session_path=_previous_session_path(old_path),
            session_id=_optional_text(old_id),
        )
    except Exception:
        pass


def _record_old_session_id(data: dict[str, object], *, old_id: str, new_id: str) -> None:
    if old_id and old_id != new_id:
        data['old_droid_session_id'] = old_id


def _record_old_session_path(
    data: dict[str, object],
    *,
    old_path: str,
    new_path: str,
    old_id: str,
    new_id: str,
) -> None:
    if old_path and _path_history_changed(
        old_path=old_path,
        new_path=new_path,
        old_id=old_id,
        new_id=new_id,
    ):
        data['old_droid_session_path'] = old_path


def _path_history_changed(*, old_path: str, new_path: str, old_id: str, new_id: str) -> bool:
    if old_path != new_path:
        return True
    return bool(old_id and old_id != new_id)


def _record_old_binding_timestamp(
    data: dict[str, object],
    *,
    old_path: str,
    old_id: str,
    binding_changed: bool,
) -> None:
    if (old_path or old_id) and binding_changed:
        data['old_updated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')


def _should_transfer_previous_binding(*, old_path: str, old_id: str, binding_changed: bool) -> bool:
    return binding_changed and bool(old_path or old_id)


def _work_dir_from_data(data: dict[str, object]) -> Path:
    wd = data.get('work_dir')
    return Path(wd) if isinstance(wd, str) and wd else Path.cwd()


def _previous_session_path(old_path: str) -> Path | None:
    if not old_path:
        return None
    try:
        return Path(old_path).expanduser()
    except Exception:
        return None


def _optional_text(value: str) -> str | None:
    text = str(value or '').strip()
    return text or None


__all__ = ['maybe_transfer_previous_binding', 'record_previous_binding']
