from __future__ import annotations


def find_matching_version(target: str, versions: list[str]) -> str | None:
    target_parts = target.split(".")

    def version_key(version: str):
        parts = version.split(".")
        return tuple(int(part) for part in parts if part.isdigit())

    matching = []
    for version in versions:
        version_parts = version.split(".")
        if len(version_parts) >= len(target_parts) and version_parts[: len(target_parts)] == target_parts:
            matching.append(version)
    if not matching:
        return None
    matching.sort(key=version_key, reverse=True)
    return matching[0]


__all__ = ['find_matching_version']
