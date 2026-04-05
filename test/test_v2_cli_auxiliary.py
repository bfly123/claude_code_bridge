from __future__ import annotations

import subprocess
import sys
from types import SimpleNamespace

import pytest

from cli import auxiliary


def test_extract_tool_name_prefers_known_keys() -> None:
    assert auxiliary.extract_tool_name({"id": "tool-1"}) == "tool-1"
    assert auxiliary.extract_tool_name({"name": "tool-2"}) == "tool-2"
    assert auxiliary.extract_tool_name({"toolName": "tool-3"}) == "tool-3"
    assert auxiliary.extract_tool_name({"other": "x"}) == ""


def test_cmd_droid_test_delegation_detects_required_tools(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    payload = [
        {"name": "ccb_ask_agent"},
        {"name": "ccb_pend_agent"},
        {"name": "ccb_ping_agent"},
    ]

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=__import__("json").dumps(payload), stderr=""),
    )

    assert auxiliary.cmd_droid_test_delegation(SimpleNamespace()) == 0
    assert "MCP delegation tools detected" in capsys.readouterr().out


def test_cmd_droid_subcommand_routes_setup(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    calls: list[bool] = []

    def fake_setup(args, *, script_root):
        calls.append(args.force)
        assert script_root == tmp_path
        return 9

    monkeypatch.setattr(auxiliary, "cmd_droid_setup_delegation", fake_setup)
    assert auxiliary.cmd_droid_subcommand(["setup-delegation", "--force"], script_root=tmp_path) == 9
    assert calls == [True]
