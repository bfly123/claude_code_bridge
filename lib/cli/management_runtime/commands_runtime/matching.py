from __future__ import annotations


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in str(version or "").split(".") if part.isdigit())


def find_matching_version(target: str, versions: list[str]) -> str | None:
    target_parts = target.split(".")

    matching = []
    for version in versions:
        version_parts = version.split(".")
        if len(version_parts) >= len(target_parts) and version_parts[: len(target_parts)] == target_parts:
            matching.append(version)
    if not matching:
        return None
    matching.sort(key=version_key, reverse=True)
    return matching[0]


def latest_version(versions: list[str]) -> str | None:
    ordered = sorted({str(version) for version in versions if str(version).strip()}, key=version_key, reverse=True)
    return ordered[0] if ordered else None


def is_newer_version(candidate: str, current: str) -> bool:
    return version_key(candidate) > version_key(current)


__all__ = ['find_matching_version', 'is_newer_version', 'latest_version', 'version_key']
