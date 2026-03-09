# Custom Config Overrides

CCB ships with default config templates in `config/`. These templates define:

- **Role assignments** (which AI handles which role)
- **Review framework** (peer review rules and rubrics)
- **Collaboration rules** (async guardrails, inspiration consultation)

By default, `ccb update` downloads the latest version and overwrites these
templates. If you customize roles or review rules, your changes are lost.

## Local Overrides

The `config/local/` directory lets you persist custom configurations across
updates. Files placed here take priority over the upstream defaults.

### Supported override files

| File | Injected into | Controls |
|------|--------------|----------|
| `claude-md-ccb.md` | `~/.claude/CLAUDE.md` | Role table, review framework, collaboration rules |
| `agents-md-ccb.md` | `AGENTS.md` | Role table, review rubrics for Codex |
| `clinerules-ccb.md` | `.clinerules` | Role table for Cline/Roo |

### Quick start

```bash
# Initialize local overrides from current upstream templates
ccb config init

# Edit a specific override
ccb config edit claude-md-ccb.md

# Apply changes
ccb reinstall

# Check which overrides are active
ccb config show

# Remove a local override (revert to upstream)
ccb config reset claude-md-ccb.md
```

### Example: Custom role assignments

1. Initialize the override:
   ```bash
   ccb config init claude-md-ccb.md
   ```

2. Edit `config/local/claude-md-ccb.md` and change the role table:
   ```markdown
   | Role | Provider | Description |
   |------|----------|-------------|
   | `architect` | `claude` | Primary planner, orchestrator, final acceptance |
   | `executor` | `codex` | Code implementation, testing, bug fixing |
   | `reviewer` | `gemini` | Code review, quality assessment |
   ```

3. Apply:
   ```bash
   ccb reinstall
   ```

4. Future `ccb update` commands will preserve your `config/local/` directory
   and continue using your custom role assignments.

## How it works

- `copy_project()` in `install.sh` saves and restores `config/local/` during
  updates, so the directory survives even full version upgrades.
- `install_*_config()` functions check for a local override before falling
  back to the upstream default template.
- The `ccb config` CLI provides convenient management commands.

## Important notes

- Local overrides replace the **entire** template file, not individual
  sections. If upstream adds new sections, you may need to merge them
  manually. Run `ccb config show` after updates to check.
- To see what changed upstream, compare your override with the default:
  ```bash
  diff config/local/claude-md-ccb.md config/claude-md-ccb.md
  ```
