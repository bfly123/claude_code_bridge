## Opencode Completion Contract

This document defines the authoritative completion contract for the `opencode`
provider in `ccb_source`.

### Authority

- `CCB_REQ_ID` is a request-binding marker only.
- `CCB_DONE` is not part of the `opencode` completion authority.
- The authoritative runtime evidence comes from `opencode` structured storage:
  session records, message records, part records, and assistant timestamps.

### Request Binding

- A managed `opencode` job writes `CCB_REQ_ID: <job_id>` into the user prompt.
- The reply belongs to that job only when the observed assistant message points
  to the user message through `parentID` or `parent_id`, and the parent prompt
  resolves back to the same `CCB_REQ_ID`.
- Session identity and `session_id_filter` scope the storage reader, but they do
  not replace request binding.

### Completion

- An `opencode` assistant reply becomes complete only when the matched assistant
  message has `time.completed`.
- Before `time.completed`, reply text may be surfaced as an in-progress preview,
  but it must not finalize the job.
- The execution adapter emits a `TURN_BOUNDARY` with reason
  `assistant_completed` when a matched assistant reaches completion.

### No-Wrap Mode

- `no_wrap` intentionally skips managed request binding.
- In `no_wrap`, `opencode` may still surface reply previews and completed
  replies from the bound session, but the result is degraded because it is not
  anchored by `CCB_REQ_ID`.

### Non-Goals

- Quiet terminal periods are not completion authority for `opencode`.
- `CCB_DONE`, terminal idle time, or pane text markers must not be reintroduced
  as the primary completion path for `opencode`.
