from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import API_VERSION


@dataclass(frozen=True)
class RpcRequest:
    op: str
    request: dict[str, Any] = field(default_factory=dict)
    api_version: int = API_VERSION

    def __post_init__(self) -> None:
        if self.api_version != API_VERSION:
            raise ValueError(f"api_version must be {API_VERSION}")
        if not (self.op or "").strip():
            raise ValueError("op cannot be empty")
        object.__setattr__(self, "request", dict(self.request))

    def to_record(self) -> dict[str, Any]:
        return {
            "api_version": self.api_version,
            "op": self.op,
            "request": dict(self.request),
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "RpcRequest":
        api_version = record.get("api_version")
        if api_version != API_VERSION:
            raise ValueError(f"unsupported api_version: {api_version!r}")
        payload = record.get("request", {})
        if not isinstance(payload, dict):
            raise ValueError("request must be an object")
        return cls(op=str(record.get("op") or ""), request=payload, api_version=api_version)


@dataclass(frozen=True)
class RpcResponse:
    ok: bool
    payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    api_version: int = API_VERSION

    def __post_init__(self) -> None:
        if self.api_version != API_VERSION:
            raise ValueError(f"api_version must be {API_VERSION}")
        object.__setattr__(self, "payload", dict(self.payload))
        if not self.ok and not (self.error or "").strip():
            raise ValueError("error response requires a message")

    def to_record(self) -> dict[str, Any]:
        record = {"api_version": self.api_version, "ok": self.ok}
        if self.ok:
            record.update(self.payload)
        else:
            record["error"] = self.error
        return record

    @classmethod
    def success(cls, payload: dict[str, Any] | None = None) -> "RpcResponse":
        return cls(ok=True, payload=payload or {})

    @classmethod
    def failure(cls, error: str, *, payload: dict[str, Any] | None = None) -> "RpcResponse":
        return cls(ok=False, payload=payload or {}, error=error)

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "RpcResponse":
        api_version = record.get("api_version")
        if api_version != API_VERSION:
            raise ValueError(f"unsupported api_version: {api_version!r}")
        ok = bool(record.get("ok"))
        if ok:
            payload = dict(record)
            payload.pop("api_version", None)
            payload.pop("ok", None)
            return cls(ok=True, payload=payload, api_version=api_version)
        return cls(ok=False, error=str(record.get("error") or ""), api_version=api_version)


__all__ = ["RpcRequest", "RpcResponse"]
