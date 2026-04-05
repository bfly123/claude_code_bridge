from __future__ import annotations

from ccbd.socket_client import CcbdClient


def test_ccbd_client_uses_stable_default_timeout(tmp_path) -> None:
    client = CcbdClient(tmp_path / "ccbd.sock")
    assert client._timeout_s == 3.0


def test_ccbd_client_reads_timeout_from_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CCB_CCBD_CLIENT_TIMEOUT_S", "4.5")
    client = CcbdClient(tmp_path / "ccbd.sock")
    assert client._timeout_s == 4.5


def test_ccbd_client_explicit_timeout_overrides_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CCB_CCBD_CLIENT_TIMEOUT_S", "4.5")
    client = CcbdClient(tmp_path / "ccbd.sock", timeout_s=0.2)
    assert client._timeout_s == 0.2
