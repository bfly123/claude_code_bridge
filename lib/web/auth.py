"""
Authentication middleware for CCB Web Controller.
"""

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional


security = HTTPBearer(auto_error=False)


async def verify_local_access(request: Request) -> bool:
    """Verify request is from localhost."""
    client_host = request.client.host if request.client else None

    local_hosts = ["127.0.0.1", "localhost", "::1"]
    if client_host in local_hosts:
        return True

    return False


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """
    Authenticate the request.

    - Local requests: No auth required
    - Remote requests: Bearer token required
    """
    app = request.app

    # Check if local-only mode
    if app.state.local_only:
        if await verify_local_access(request):
            return {"type": "local", "authenticated": True}
        raise HTTPException(
            status_code=403,
            detail="Remote access not allowed in local-only mode",
        )

    # Remote access - require token
    if await verify_local_access(request):
        return {"type": "local", "authenticated": True}

    # Check bearer token
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if credentials.credentials != app.state.auth_token:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token",
        )

    return {"type": "token", "authenticated": True}


def require_auth(user: dict = Depends(get_current_user)) -> dict:
    """Dependency to require authentication."""
    if not user.get("authenticated"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
