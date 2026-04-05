# FileOpsREQ Templates

Templates for common /tr operations. Each template has a `_meta` section documenting placeholders.

## Usage

### Direct use (no placeholders)
```
/file-op <template content>
```

### With overrides
Replace placeholders before sending:

1. Copy template
2. Replace `{{placeholder}}` with actual values
3. Remove `_meta` section (optional, Codex ignores it)
4. Send via /file-op

### Placeholder Sources

| Placeholder | Source |
|-------------|--------|
| stepIndex | FileOpsRES.data.state.current.stepIndex |
| substeps | step design output.proposedSubsteps |
| verification | /review output.finalDecision.reason |
| changedFiles | FileOpsRES.changedFiles |
| stepTitle | current step title |
| taskName | state.json.task |
| reportContent | Claude-generated markdown |
| steps | Claude design (1-2 titles) |

## Templates

| Template | Purpose | Placeholders |
|----------|---------|--------------|
| preflight.json | Read state, validate step | None |
| split.json | Apply substep split | stepIndex, substeps |
| finalize.json | Mark step done, auto-commit, trigger autoloop | verification, changedFiles, stepIndex, stepTitle |
| final-report.json | Write task summary | taskName, reportContent |
| append-steps.json | Add fix steps | steps |
