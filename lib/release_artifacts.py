from __future__ import annotations


def normalize_arch(raw_arch: str) -> str:
    text = str(raw_arch or "").strip().lower()
    mapping = {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "aarch64": "aarch64",
        "arm64": "aarch64",
    }
    return mapping.get(text, text or "unknown")


def normalize_release_platform(raw_system: str) -> str | None:
    text = str(raw_system or "").strip()
    mapping = {
        "Linux": "linux",
        "Darwin": "macos",
        "linux": "linux",
        "macos": "macos",
    }
    return mapping.get(text)


def release_build_arch(platform_name: str, *, machine: str) -> str | None:
    platform_name = normalize_release_platform(platform_name)
    if platform_name == "linux":
        return normalize_arch(machine)
    if platform_name == "macos":
        return "universal"
    return None


def release_artifact_basename(platform_name: str, *, machine: str) -> str | None:
    platform_name = normalize_release_platform(platform_name)
    if platform_name == "linux":
        arch = normalize_arch(machine)
        return f"ccb-linux-{arch}" if arch else None
    if platform_name == "macos":
        return "ccb-macos-universal"
    return None


def release_artifact_name(platform_name: str, *, machine: str) -> str | None:
    basename = release_artifact_basename(platform_name, machine=machine)
    if not basename:
        return None
    return f"{basename}.tar.gz"
