"""
Provider status API routes.
"""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from web.auth import require_auth

router = APIRouter()


class ProviderStatus(BaseModel):
    """Provider status response."""
    name: str
    available: bool
    session_active: bool = False
    error: Optional[str] = None


class PingResult(BaseModel):
    """Ping result response."""
    provider: str
    success: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None


KNOWN_PROVIDERS = ["claude", "codex", "gemini", "opencode", "droid", "copilot", "codebuddy", "qwen"]


def check_provider_available(provider: str) -> ProviderStatus:
    """Check if a provider is available."""
    try:
        # Check if provider adapter exists
        from askd.registry import ProviderRegistry
        registry = ProviderRegistry()

        # Try to get adapter
        adapter = registry.get(provider)
        if adapter:
            return ProviderStatus(name=provider, available=True)
    except Exception as e:
        return ProviderStatus(name=provider, available=False, error=str(e))

    return ProviderStatus(name=provider, available=False)


@router.get("")
async def list_providers(user: dict = Depends(require_auth)) -> List[ProviderStatus]:
    """List all provider statuses."""
    statuses = []
    for provider in KNOWN_PROVIDERS:
        statuses.append(check_provider_available(provider))
    return statuses


@router.get("/{name}")
async def get_provider(name: str, user: dict = Depends(require_auth)) -> ProviderStatus:
    """Get specific provider status."""
    if name not in KNOWN_PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {name}")
    return check_provider_available(name)


@router.post("/{name}/ping")
async def ping_provider(name: str, user: dict = Depends(require_auth)) -> PingResult:
    """Ping a provider to check connectivity."""
    if name not in KNOWN_PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {name}")

    import time

    try:
        from askd_client import try_daemon_request
        import os

        start = time.time()
        reply, exit_code = try_daemon_request(
            provider=name,
            message="ping",
            work_dir=os.getcwd(),
            timeout_s=10,
        )
        latency = (time.time() - start) * 1000

        if exit_code == 0 and reply:
            return PingResult(
                provider=name,
                success=True,
                latency_ms=latency,
            )
        else:
            return PingResult(
                provider=name,
                success=False,
                error=f"Exit code: {exit_code}",
            )
    except Exception as e:
        return PingResult(
            provider=name,
            success=False,
            error=str(e),
        )
