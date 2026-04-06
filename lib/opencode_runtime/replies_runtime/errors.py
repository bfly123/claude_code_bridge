from __future__ import annotations


def is_aborted_error(error_obj: object) -> bool:
    if not isinstance(error_obj, dict):
        return False
    name = error_obj.get('name')
    if isinstance(name, str) and 'aborted' in name.lower():
        return True
    data = error_obj.get('data')
    if isinstance(data, dict):
        message = data.get('message')
        if isinstance(message, str) and ('aborted' in message.lower() or 'cancel' in message.lower()):
            return True
    return False


__all__ = ['is_aborted_error']
