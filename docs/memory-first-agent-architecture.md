# Memory-First AI Agent Architecture

A comprehensive design for AI agent systems where memory becomes the core and models become replaceable executors.

## 1. Core Philosophy

### Paradigm Shift

| Dimension | Traditional | Memory-First |
|-----------|-------------|--------------|
| **Core** | Model (capability-bound) | Memory (knowledge-bound) |
| **Model Role** | Brain | Replaceable "compute unit" |
| **Memory Role** | Auxiliary tool | First-class citizen, identity carrier |
| **Migration Cost** | Switch model = start over | Switch model = change executor |

### Design Principles

- **Memory = Kernel**: Not a cache attached to the model, but the system's core
- **Models = CPU**: Stateless execution units, plug-and-play
- **Database = Motherboard**: Connects perception, memory, and execution

## 2. Three-Role Architecture (A/B/C Model)

### Role Definitions

| Role | Name | Responsibility | Characteristics |
|------|------|----------------|-----------------|
| **A** | Memory Keeper | Global memory maintenance | Long-term, persistent, cross-session |
| **B** | Context Builder | Short-term memory + context assembly | Real-time, session-scoped, orchestrator |
| **C** | Executor | Task execution | Stateless, pure function, focused execution |

### Optional Extension: Add a Mid-Term "Task Memory" Role (T)

When tasks span multiple context windows, introduce a mid-term memory layer to track plan and progress without polluting long-term facts.

| Role | Name | Responsibility | Characteristics |
|------|------|----------------|-----------------|
| **T** | Task Tracker (Mid-term Memory) | Task plan/progress state (plan → todo → step execution → done) | Cross-window, task-scoped, structured, recoverable |

Mapping to the `tp/tr` workflow:

- `/tp` creates and persists plan artifacts (e.g. `todo.md`, `state.json`, `plan_log.md`) → this is the canonical mid-term memory for a task.
- `/tr` advances `state.json.current` and updates todo/logs per step → this is mid-term memory mutation.
- Long-term memory is only updated by extracting stable outcomes from the task (not the in-progress state).

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Memory System                                │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    A: Memory Keeper                          │   │
│  │                                                              │   │
│  │  Responsibilities:                                           │   │
│  │  - Maintain long-term memory (project knowledge, decisions)  │   │
│  │  - Process write requests from B                             │   │
│  │  - Respond to retrieval requests from B                      │   │
│  │  - Periodic cleanup, merge, compress old memories            │   │
│  │                                                              │   │
│  │  Storage: Vector DB + Structured DB + File System            │   │
│  └──────────────────────────┬───────────────────────────────────┘   │
│                             │                                       │
│                    Retrieve ↑   ↓ Write                             │
│                             │                                       │
│  ┌──────────────────────────┴───────────────────────────────────┐   │
│  │                    B: Context Builder                         │   │
│  │                                                              │   │
│  │  Responsibilities:                                           │   │
│  │  1. Maintain session short-term memory                       │   │
│  │  2. Receive user task → analyze intent                       │   │
│  │  3. Retrieve relevant global memory from A                   │   │
│  │  4. Assemble C's input (short-term + global + current task)  │   │
│  │  5. Call C for execution                                     │   │
│  │  6. Process C's output (extract key information)             │   │
│  │  7. Update short-term memory + notify A for persistence      │   │
│  │                                                              │   │
│  │  Storage: Memory / Redis (session-level)                     │   │
│  └──────────────────────────┬───────────────────────────────────┘   │
│                             │                                       │
│                    Input ↓   ↑ Output                               │
│                             │                                       │
│  ┌──────────────────────────┴───────────────────────────────────┐   │
│  │                    C: Executor                                │   │
│  │                                                              │   │
│  │  Responsibilities:                                           │   │
│  │  - Receive assembled context                                 │   │
│  │  - Execute task (write code, answer questions, analyze)      │   │
│  │  - Return results                                            │   │
│  │                                                              │   │
│  │  Characteristics: Stateless, f(input) → output               │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 3. Memory Storage Architecture

### Three-Tier Storage (Hot-Warm-Cold)

| Tier | Data Type | Technology Stack | Design Pattern |
|------|-----------|------------------|----------------|
| **L1: Hot** | Current session, temp variables, tool outputs | Redis / Memcached | Sliding window + priority queue, millisecond R/W |
| **L2: Warm** | Task state and entity relations | SQLite / Postgres + (optional) graph DB | Task state machine + knowledge graph |
| **L3: Cold** | Historical logs, document chunks, code snippets | Pgvector / Chroma / LanceDB | Semantic index + timestamp, hybrid search |

Notes:

- In many implementations, "L2" is best split into two concerns:
  - **Mid-term task memory**: strongly structured, task-scoped (`task_id`) artifacts like `state.json` + `todo.md` + `plan_log.md`.
  - **Entity/relationship memory**: optional graph layer for cross-task reasoning.

### Database Selection

| Memory Type | Storage Solution | Rationale |
|-------------|------------------|-----------|
| Long-term Memory | ChromaDB/Qdrant + SQLite | Vector retrieval + structured metadata |
| Short-term Memory | Redis / In-memory | Fast R/W, TTL auto-expiration |
| File Index | Neo4j / SQLite + Embeddings | Dependency graph + semantic search |
| Execution State | SQLite | Transactional, rollback support |

## 4. Context Assembly Strategy

### Two-Layer Memory Model

```
┌─────────────────────────────────────────────────────────────────┐
│                    Global Memory                                 │
│                                                                 │
│   Cross-session, cross-model persistent memory                  │
│   - Project knowledge, user preferences, historical decisions   │
│   - Storage: File system / Vector DB / Database                 │
└─────────────────────────────────────────────────────────────────┘
                              ↑↓ Sync
┌─────────────────────────────────────────────────────────────────┐
│                    Local Memory                                  │
│                                                                 │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│   │ Claude  │  │ Codex   │  │ Gemini  │  │OpenCode │           │
│   │ Context │  │ Context │  │ Context │  │ Context │           │
│   └─────────┘  └─────────┘  └─────────┘  └─────────┘           │
│                                                                 │
│   Each model's context = efficient local memory                 │
└─────────────────────────────────────────────────────────────────┘
```

### Core Principle: Local Memory First

| Memory Type | Retrieval Cost | Latency | Coherence | Use Case |
|-------------|----------------|---------|-----------|----------|
| **Local Memory** | Zero | Zero | Very High | Continuous tasks, iterative development |
| **Global Memory** | High | High | Medium | Cross-session, new task startup |

### Three-Layer Context Structure

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: System Prompt (Fixed)                 ~5% budget  │
│  - Role definition, rule constraints                        │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Injected Memory                    ~30-40% budget │
│  - Retrieved from global memory                             │
│  - Project background, historical decisions, related code   │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: Local Context                      ~50-60% budget │
│  - Current session dialogue history                         │
│  - Recent task chain, iteration process                     │
└─────────────────────────────────────────────────────────────┘
```

## 5. Memory Retrieval Strategy

### Add Task-Scoped Retrieval (Mid-term First)

If a task is active, retrieval should prioritize mid-term task artifacts before global long-term memory:

1) Task state (`state.json`): current step, attempts, blocked reason, done conditions
2) Task todo (`todo.md`): remaining work and completion markers
3) Task log (`plan_log.md`): key decisions and rationale
4) Global long-term memory: stable facts/preferences/constraints

This avoids wasting context budget re-deriving "what we were doing" after a context window reset.

### Multi-Path Retrieval Flow

```
User Input
    │
    ↓
┌─────────────────────────────────────────┐
│  Step 1: Intent Recognition              │
│  - Intent: bug_fix / new_feature / etc.  │
│  - Domain: auth / payment / etc.         │
│  - Keywords: extracted from query        │
└─────────────────────────────────────────┘
    │
    ↓
┌─────────────────────────────────────────┐
│  Step 2: Hybrid Retrieval                │
│  - Vector Search (semantic)              │
│  - Keyword Search (BM25)                 │
│  - Graph Traversal (structured)          │
└─────────────────────────────────────────┘
    │
    ↓
┌─────────────────────────────────────────┐
│  Step 3: Ranking                         │
│  - Semantic similarity (0.4)             │
│  - Time decay (0.2)                      │
│  - Type matching (0.2)                   │
│  - Reference frequency (0.2)             │
└─────────────────────────────────────────┘
    │
    ↓
┌─────────────────────────────────────────┐
│  Step 4: Budget Allocation               │
│  - Must-have: 30%                        │
│  - Should-have: 50%                      │
│  - Nice-to-have: 20%                     │
└─────────────────────────────────────────┘
```

### Task-Type Based Retrieval Priority

| Task Type | Priority Order |
|-----------|----------------|
| Bug Fix | Error history > Related code > Architecture decisions |
| New Feature | Architecture decisions > User preferences > Related code |
| Refactoring | Architecture decisions > Code structure > Change history |
| Q&A | Project knowledge > Historical dialogue > Documentation |

## 6. Context Optimization

### Layered Caching Strategy

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 0: Base Context (Session-level cache)                │
│  - System Prompt, Project background, Code structure        │
│  - Update: Only on project changes                          │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Task Context (Task-level cache)                   │
│  - Task-related code files, Related decisions               │
│  - Update: On task switch                                   │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Delta Context (No cache)                          │
│  - Current task description, Last execution result          │
│  - Update: Every round                                      │
└─────────────────────────────────────────────────────────────┘
```

### Efficiency Gains

```
Round 1: Initial assembly
- L0: Generate + cache (30K)
- L1: Retrieve + cache (30K)
- L2: Generate (20K)
- Total cost: 80K generation

Round 2+: Same task chain
- L0: Reuse cache ✓ (0 cost)
- L1: Reuse cache ✓ (0 cost)
- L2: Update delta only (20K)
- Total cost: 20K generation, 60K reused
- Efficiency improvement: ~70%
```

### B's Context Management

**Problem**: B assembling 80K context each time causes context bloat

**Solution**: B keeps only "metadata", not "full content"

| Information Type | Storage Location | B Retains |
|------------------|------------------|-----------|
| Assembled context | Temp variable (discard after use) | "Assembled 75K, contains X/Y/Z" |
| C's code output | File system | "Generated src/auth/token.py" |
| Retrieved memories | A's memory store | "Retrieved 3 auth-related items" |
| Execution results | File system / logs | "Success/failure, reason..." |

## 7. Global Memory Maintenance

### Maintenance Modes

| Mode | Maintainer | Trigger | Pros/Cons |
|------|------------|---------|-----------|
| **Synchronous** | Current executor | Immediately on task completion | Real-time but adds latency |
| **Asynchronous** | Dedicated Memory Agent | Background periodic cleanup | Non-blocking but may lag |
| **Hybrid** | Critical sync + details async | Tiered triggers | Balance efficiency and completeness |

### Practical Triggers for Maintenance

Long-term memory should not be rewritten on every turn. Prefer append-only candidate writes during execution, and run consolidation/compaction on explicit lifecycle events:

- **Explicit**: user invokes a CLI command such as `memory clear`
- **Implicit**: session end / restart (`on_session_end` hook)
- **Milestone**: task finalize / step completion (write candidates; merge async)

To preserve online retrieval quality while long-term updates are periodic, use a two-source retrieval strategy:

- **Real-time layer**: recent candidates produced in the current/nearby sessions (TTL)
- **Long-term layer**: consolidated facts + indexed chunks

Query both and merge results.

### Recommended: Hybrid Mode

```
During Task Execution
    │
    ├─→ Critical decisions/errors ──→ Sync write (immediate)
    │   - Important architecture decisions
    │   - Failed attempts (prevent repetition)
    │   - Explicit user preferences
    │
    └─→ Regular information ──→ Mark pending ──→ Async cleanup
        - Dialogue details
        - Intermediate processes
        - Code change records

During Idle / Session End
    │
    └─→ Memory Agent activates
        - Process pending information
        - Merge duplicate memories
        - Compress/summarize old memories
        - Clean expired information
```

## 8. Potential Issues and Solutions

### Known Risks

| Risk | Description | Solution |
|------|-------------|----------|
| **Retrieval Drift** | Summaries dominate future retrieval → semantic shift | Hybrid retrieval (semantic + keyword + time decay) |
| **Self-Reinforcement** | Incorrect memory gets restated → becomes "truth" | Periodic "reflection" scans for contradictions |
| **Over-Compression** | Summarization loses constraints → subtle task errors | Store both raw and summarized; include raw when confidence low |
| **Memory Spam** | Writes on every turn → storage bloat, noisy retrieval | Selective writing, importance scoring |
| **Deadlock** | Memory LLM waits for Task LLM; Task LLM waits for Memory | Deterministic orchestrator with timeouts |
| **Privacy Leaks** | Sensitive data stored without governance | Strict redaction rules, allowlist fields |
| **Version Skew** | Two LLMs see different system prompts | Centralized prompt management |

### The Recursion Problem: "Who manages Memory Model's memory?"

**Solution: Layering and Freezing**

- **System Prompt**: Memory LLM's "meta-memory", immutable hardcoded rules
- **Working Memory**: Only maintain a very short sliding window (e.g., last 5 rounds)
- Memory LLM doesn't need to remember "what I processed yesterday", only "what I'm processing now"

## 9. Implementation Recommendations

### Phased Approach

| Phase | Content |
|-------|---------|
| Step 1 | Deterministic orchestrator + embedding store + strict schema (facts/preferences/constraints/tasks) |
| Step 2 | Large model only for write-time consolidation and conflict checks; retrieval stays cheap |
| Step 3 | Add memory "review" batch jobs to clean/merge memories |
| Step 4 | Introduce second LLM for memory only when single-LLM baseline proves insufficient |
| Step 5 | Implement guardrails: versioning, "source of truth" tags, confidence scores, delete/forget pathways |

### CCB Environment Mapping

| Role | CCB Implementation |
|------|-------------------|
| **A (Memory Keeper)** | Claude / Codex / Dedicated Memory Agent |
| **B (Context Builder)** | Claude Code (current session) - natural orchestrator |
| **C (Executor)** | Codex / Gemini / OpenCode / Claude API |

## 10. Key Insights

### From Multi-Model Analysis

| Source | Core Insight |
|--------|--------------|
| **Claude** | Recursion problem is the core bug; need fixed rules to break infinite regression |
| **Codex** | Technically feasible; needs evaluation system and guardrails |
| **OpenCode** | Progressive introduction; large model only for critical memory operations |
| **Gemini** | Dual-brain architecture is optimal; tiered storage + reflection mechanism solves drift |

### Final Principle

> **Don't let the model "remember" - let the model "query"**
>
> Build a powerful retrieval engine that understands code structure, correlates historical dialogue, and updates file state in real-time. The model is just a natural language interface and decision-maker for this engine.

## References

- [MemGPT](https://memgpt.ai/) - OS-like memory management for LLMs
- [MemGPT Paper](https://arxiv.org/abs/2310.08560)
- [Generative Agents (Stanford)](https://arxiv.org/abs/2304.03442) - Reflection mechanism
- [MetaGPT](https://github.com/geekan/MetaGPT) - Multi-agent collaboration
- [LangChain Memory](https://python.langchain.com/docs/modules/memory/)
- [LlamaIndex](https://www.llamaindex.ai/) - RAG and memory indexing
