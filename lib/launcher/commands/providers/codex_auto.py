from __future__ import annotations

from pathlib import Path


def ensure_codex_auto_approval() -> None:
    import re

    codex_config = Path.home() / ".codex" / "config.toml"
    if not codex_config.exists():
        return

    def _toml_unescape_basic_string(value: str) -> str:
        try:
            return (
                (value or "")
                .replace("\\\\", "\\")
                .replace('\\"', '"')
                .replace("\\t", "\t")
                .replace("\\n", "\n")
                .replace("\\r", "\r")
            )
        except Exception:
            return value or ""

    def _toml_escape_basic_string(value: str) -> str:
        return (value or "").replace("\\", "\\\\").replace('"', '\\"')

    cwd = str(Path.cwd())
    section_header = f'[projects."{_toml_escape_basic_string(cwd)}"]'
    ccb_begin = "# CCB_AUTO_APPROVAL_BEGIN"
    ccb_end = "# CCB_AUTO_APPROVAL_END"
    desired = [
        'trust_level = "trusted"',
        'approval_policy = "never"',
        'sandbox_mode = "danger-full-access"',
    ]

    def _dedupe_duplicate_project_tables(content: str) -> tuple[str, bool]:
        lines = content.splitlines()
        out: list[str] = []
        seen_project_headers: set[str] = set()
        skip_block = False
        deduped = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('[projects."') and stripped.endswith('"]'):
                header = stripped
                if header in seen_project_headers:
                    skip_block = True
                    deduped = True
                    continue
                seen_project_headers.add(header)
                skip_block = False
            elif stripped.startswith("[") and stripped.endswith("]"):
                skip_block = False
            if not skip_block:
                out.append(line)
        return "\n".join(out) + ("\n" if content.endswith("\n") else ""), deduped

    def _ensure_block(section: str) -> tuple[str, bool]:
        changed = False
        if ccb_begin in section and ccb_end in section:
            start = section.index(ccb_begin)
            end = section.index(ccb_end) + len(ccb_end)
            before = section[:start]
            after = section[end:]
            block = "\n".join([ccb_begin, *desired, ccb_end])
            updated = before + block + after
            if updated != section:
                changed = True
            return updated, changed
        lines = section.rstrip().splitlines()
        block = [ccb_begin, *desired, ccb_end]
        updated = "\n".join([*lines, *block]) + "\n"
        return updated, True

    try:
        content = codex_config.read_text(encoding="utf-8")
        changed_any = False
        deduped = False
        migrated = False

        content, deduped = _dedupe_duplicate_project_tables(content)

        escaped_cwd = re.escape(cwd)
        exact_header = re.compile(rf'^\[projects\."{escaped_cwd}"\]\s*$', re.MULTILINE)
        match = exact_header.search(content)

        if not match:
            path_headers = list(re.finditer(r'^\[projects\."(?P<path>.+?)"\]\s*$', content, re.MULTILINE))
            for header_match in path_headers:
                raw_path = header_match.group("path")
                if _toml_unescape_basic_string(raw_path) != cwd:
                    continue
                section_start = header_match.start()
                next_match = next((item for item in path_headers if item.start() > section_start), None)
                section_end = next_match.start() if next_match else len(content)
                section = content[section_start:section_end]
                updated_section = section.replace(header_match.group(0), section_header, 1)
                if updated_section != section:
                    content = content[:section_start] + updated_section + content[section_end:]
                    migrated = True
                match = exact_header.search(content)
                break

        if match:
            start = match.start()
            next_header = re.search(r"^\[", content[match.end():], re.MULTILINE)
            end = match.end() + next_header.start() if next_header else len(content)
            section = content[start:end]
            updated_section, changed = _ensure_block(section)
            if changed:
                content = content[:start] + updated_section + content[end:]
                changed_any = True
        else:
            entry = "\n".join([section_header, ccb_begin, *desired, ccb_end]) + "\n"
            content = content.rstrip() + "\n\n" + entry
            changed_any = True

        content, deduped_after = _dedupe_duplicate_project_tables(content)
        deduped = deduped or deduped_after or migrated
        if changed_any or deduped:
            codex_config.write_text(content, encoding="utf-8")
            print(f"✅ Codex auto-approval configured for: {cwd}")
    except Exception as exc:
        print(f"⚠️ Failed to configure codex auto-approval: {exc}")
