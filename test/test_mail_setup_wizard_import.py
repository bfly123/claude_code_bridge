from __future__ import annotations

import importlib


def test_mail_setup_wizard_module_imports() -> None:
    module = importlib.import_module("mail_tui.wizard")
    assert hasattr(module, "run_wizard")
    assert hasattr(module, "run_simple_wizard")
