from __future__ import annotations

from pathlib import Path


def resolve_socket_ref(socket_name: str | None) -> tuple[str | None, str | None]:
    text = str(socket_name or '').strip()
    if not text:
        return None, None
    if '/' in text or '\\' in text:
        try:
            return None, str(Path(text).expanduser())
        except Exception:
            return None, text
    return text, None


def build_backend(backend_factory, *, socket_name: str | None):
    resolved_socket_name, resolved_socket_path = resolve_socket_ref(socket_name)
    for kwargs in _backend_call_variants(
        socket_name=resolved_socket_name,
        socket_path=resolved_socket_path,
    ):
        backend, should_continue = _call_backend_factory(backend_factory, kwargs=kwargs)
        if backend is not None or not should_continue:
            return backend
    return None


def _backend_call_variants(*, socket_name: str | None, socket_path: str | None) -> tuple[dict[str, str | None], ...]:
    variants: list[dict[str, str | None]] = [
        {'socket_name': socket_name, 'socket_path': socket_path},
    ]
    if socket_path is not None:
        variants.append({'socket_path': socket_path})
    if socket_name is not None:
        variants.append({'socket_name': socket_name})
    variants.append({})
    return tuple(variants)


def _call_backend_factory(backend_factory, *, kwargs: dict[str, str | None]) -> tuple[object | None, bool]:
    try:
        return backend_factory(**kwargs), False
    except TypeError:
        return None, True
    except Exception:
        return None, False


__all__ = ['build_backend', 'resolve_socket_ref']
