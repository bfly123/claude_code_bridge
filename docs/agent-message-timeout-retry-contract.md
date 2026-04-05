# Agent Message Timeout And Retry Contract

This document defines the runtime/message contract for ask-driven agent delivery.

## 1. Startup Failure Must Not Leave A Silent Running Job

If a provider job cannot bind to a usable runtime at start time, the execution path must not leave the job in a silent `running` state.

Rules:

- missing runtime context, missing provider session, backend binding failure, and equivalent bootstrap failures must surface as terminal execution failure signals
- these failures must be eligible for normal retry policy evaluation
- the system must not park such jobs in a passive state that never produces a terminal decision

## 2. Timeout Means Inspect, Not Blind Failure

When a running attempt reaches the completion timeout without a confirmed terminal reply:

- the job status becomes `incomplete`
- the caller receives a standard inspection notice reply
- the notice must tell the caller that the task may still be running in the target agent session
- the notice must direct the caller/operator to inspect the live agent state before deciding to continue or retry

Timeout is not treated as an automatic provider/API failure.

## 3. Retry Must Preserve Context When Context Already Exists

Automatic or manual retry creates a new attempt in the same logical message lineage.

Retry body policy:

- if the prior attempt already entered provider context, retry sends `continue`
- if the prior attempt never entered provider context, retry replays the original request body

Provider-context entry is determined from prior terminal evidence such as:

- `anchor_seen`
- `reply_started`
- prior retry lineage already marked as `continue`

## 4. Timeout Does Not Auto-Retry By Default

Timeout alone does not automatically resubmit the task body.

Reason:

- some agent executions are legitimately long-running
- blind retry wastes work and may fork the target session incorrectly

The first system response on timeout is an inspection notice, not an automatic replay.
