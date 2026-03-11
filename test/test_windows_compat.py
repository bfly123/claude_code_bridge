"""Tests for Windows compatibility fixes in bin/ask (issue #127)."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ASK_SCRIPT = REPO_ROOT / "bin" / "ask"


def _read_ask_source() -> str:
    return ASK_SCRIPT.read_text(encoding="utf-8")


def _extract_windows_block(source: str) -> str:
    """Extract the main Windows (os.name == 'nt') block that generates the PowerShell script.

    There are multiple ``os.name == "nt"`` checks in the source.  The one we
    care about is the large block inside ``main()`` that writes the .ps1
    script.  We identify it by looking for the block that contains
    'PowerShell' or 'script_content' so we skip the small helper guard in
    ``_maybe_start_unified_daemon``.
    """
    lines = source.splitlines()
    blocks: list[list[str]] = []
    in_block = False
    block_lines: list[str] = []
    indent_level: int | None = None

    for line in lines:
        if ('os.name == "nt"' in line or "os.name == 'nt'" in line) and not in_block:
            in_block = True
            indent_level = len(line) - len(line.lstrip())
            block_lines = [line]
            continue
        if in_block:
            if line.strip() == "" or len(line) - len(line.lstrip()) > indent_level:
                block_lines.append(line)
            elif line.strip().startswith("else:"):
                blocks.append(block_lines)
                in_block = False
                block_lines = []
            else:
                block_lines.append(line)

    if in_block and block_lines:
        blocks.append(block_lines)

    # Return the block that contains the PowerShell script generation
    for block in blocks:
        text = "\n".join(block)
        if "script_content" in text or "PowerShell" in text or ".ps1" in text:
            return text

    # Fallback: return all blocks concatenated
    return "\n".join(line for block in blocks for line in block)


class TestWindowsPowerShellScript:
    """Verify the Windows PowerShell script template includes required settings."""

    def setup_method(self):
        self.source = _read_ask_source()
        self.win_block = _extract_windows_block(self.source)

    def test_ccb_run_dir_in_windows_block(self):
        """CCB_RUN_DIR must be passed to PowerShell script (issue #127)."""
        assert "CCB_RUN_DIR" in self.win_block, (
            "Windows block must include CCB_RUN_DIR env var"
        )

    def test_utf8_output_encoding(self):
        """$OutputEncoding must be set for proper pipe encoding."""
        assert "$OutputEncoding" in self.win_block

    def test_utf8_input_encoding(self):
        """Console InputEncoding must be set for Chinese chars."""
        assert "InputEncoding" in self.win_block

    def test_pythonioencoding(self):
        """PYTHONIOENCODING must be set for Python subprocess UTF-8."""
        assert "PYTHONIOENCODING" in self.win_block

    def test_console_output_encoding(self):
        """Console OutputEncoding must still be present."""
        assert "[Console]::OutputEncoding" in self.win_block

    def test_email_env_vars_in_windows_block(self):
        """CCB_EMAIL_* env vars must be handled in Windows block."""
        assert "CCB_EMAIL" in self.win_block or "email_env_lines" in self.win_block

    def test_unix_block_still_has_run_dir(self):
        """Unix block must still include CCB_RUN_DIR (no regression)."""
        # Find the else/Unix block
        assert 'export CCB_RUN_DIR' in self.source


class TestWindowsUnixParity:
    """Verify Windows and Unix script generation have feature parity."""

    def setup_method(self):
        self.source = _read_ask_source()

    def test_both_blocks_set_req_id(self):
        """Both Windows and Unix set CCB_REQ_ID."""
        assert '$env:CCB_REQ_ID' in self.source  # Windows
        assert 'export CCB_REQ_ID' in self.source  # Unix

    def test_both_blocks_set_caller(self):
        """Both Windows and Unix set CCB_CALLER."""
        assert '$env:CCB_CALLER' in self.source  # Windows
        assert 'export CCB_CALLER' in self.source  # Unix

    def test_both_blocks_set_work_dir(self):
        """Both Windows and Unix set CCB_WORK_DIR."""
        assert '$env:CCB_WORK_DIR' in self.source  # Windows
        assert 'export CCB_WORK_DIR' in self.source  # Unix
