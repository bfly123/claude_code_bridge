---
name: ask
description: Submit a request via `ccb ask` to a named CCB agent. Default async; on async receipt end the turn immediately. Use wait only when the user explicitly asks for the reply in the same turn.
metadata:
  short-description: Ask agent
---

# Ask Target

Send the user's request to another CCB agent via the canonical `ccb ask` command.

## CCB Context

- `ccb` is the project control plane. This skill assumes the current working directory is inside a CCB-managed project with a `.ccb/ccb.config`.
- `ccb ask` uses the current CCB workspace to infer sender identity. Do not manually reimplement sender resolution in the skill.
- If the current cwd is an agent workspace such as `.ccb/workspaces/agent1`, sender is inferred as `agent1`.
- If the current cwd is not an agent workspace, sender falls back to `user`.
- `ccb ask all` is broadcast. When sender is an agent, broadcast excludes that sender agent itself. When sender is `user`, broadcast goes to all alive agents.
- Bare `ask` is only a compatibility alias for `ccb ask`.
- `--silence` only hides successful completion body in the caller mailbox. Failed, incomplete, or cancelled outcomes still return their normal reply body.

## Usage

The skill signature is exactly:

```text
/ask <target> <message...>
```

Parse arguments exactly once:

- `TARGET` = the first whitespace-delimited token after `/ask`
- `MESSAGE` = the exact raw remainder after `TARGET`

Everything after `TARGET` belongs to `MESSAGE` and must be forwarded verbatim to the target agent.
Do not parse `from`, `--wait`, `--async`, `--silence`, quotes, or any later token as extra skill syntax.
Sender is inferred by `ccb ask` itself from the current CCB workspace.

If the user provides only a target and no remaining message, stop and report a brief usage error.

The message MUST be provided via stdin (heredoc or pipe), not as CLI arguments, to avoid shell globbing issues.

## Execution (MANDATORY)

Default async submit:

```bash
command ccb ask "$TARGET" <<'EOF'
$MESSAGE
EOF
```

This returns only an acceptance receipt in the current turn.
The reply is not echoed into the same command stdout.
To fetch the same-turn reply, use the explicit wait form below.
Successful async submit also prints a protocol marker like:

```text
[CCB_ASYNC_SUBMITTED ...]
```

That marker means the async handoff is complete for this turn.

Silent-on-success submit, only if the user explicitly asks for silent success mail:

```bash
command ccb ask --silence "$TARGET" <<'EOF'
$MESSAGE
EOF
```

Only if the user explicitly asks to wait for the reply in the same turn:

```bash
command ccb ask --wait "$TARGET" <<'EOF'
$MESSAGE
EOF
```

Only if the user explicitly asks for both waiting and silent-on-success behavior:

```bash
command ccb ask --wait --silence "$TARGET" <<'EOF'
$MESSAGE
EOF
```

## Rules

- Execute exactly one snippet above, then stop, unless the user explicitly asked to wait.
- If async output contains `[CCB_ASYNC_SUBMITTED ...]`, end the turn immediately. Do not inspect, summarize follow-up state, or poll for replies in the same turn.
- Do not run deprecated wrapper aliases, `pend`, `ping`, retries, or other follow-up commands unless the user explicitly asks.
- Do not add extra filler like "processing...". The command output is the result.
- Do not rewrite target names. `cmd` is reserved as the control pane name and must not be used as an agent target or mailbox target.
- Do not reinterpret any part of `MESSAGE` as sender override syntax. This skill does not accept a sender argument.
- Use canonical `ccb ask`. Do not use bare `ask` here unless the user is explicitly testing alias compatibility.
- Keep stdin/heredoc form; do not pass the raw message as CLI arguments.
- Forward `MESSAGE` verbatim. Do not summarize, translate, or paraphrase it before sending.
- If the user asks for broadcast, use `TARGET=all`. Do not try to expand the agent list yourself.

## Examples

- `/ask agent1 1+1=?`
- `/ask agent2 Summarize this diff`
- `/ask all 请同步检查当前方案`
- `/ask agent1 联网查询一下 superpowers 是什么开源项目`
- `command ccb ask --silence "agent3" <<'EOF'`
  `做完后只回完成通知，不要回正文`
  `EOF`
- `command ccb ask --wait "agent1" <<'EOF'`
  `1+1=?`
  `EOF`

## Notes

- If submit fails, report the command failure output and stop. Only diagnose in a later turn if the user asks.
- Successful `--silence` replies look like `CCB_COMPLETE ... result=hidden`.
- Successful async submit is complete as soon as `[CCB_ASYNC_SUBMITTED ...]` appears.
