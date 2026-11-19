---
name: apex-engine
description: Use when executing software engineering tasks, writing code, debugging, refactoring, or managing complex projects with lightweight or compact AI models (e.g. Gemini Flash, Claude Haiku, GPT-4o-mini) to enforce flagship code quality, contract-driven verification, and lossless memory persistence across long conversations.
---

# ApexEngine: The Flagship Quality & Infinite Memory Skill

ApexEngine is the ultimate open-source skill that transforms lightweight, fast-tier AI models (Gemini Flash, Claude Haiku, GPT-4o-mini) into rigorous, senior-grade software engineers. While compact models possess exceptional token-generation speed and low per-turn latency, their unconstrained execution is prone to horizon amnesia, speculative hallucinations, skipped testing, and premature completion declarations. ApexEngine eliminates these vulnerabilities by bounding the model within a deterministic 4-gate state machine and a perpetual, zero-decay active memory buffer.

---

## 1. Overview & First Principles

### Why Lightweight Models Fail on Non-Trivial Engineering

Compact and flash models (such as Gemini Flash, Claude Haiku, and GPT-4o-mini) operate with high token throughput and strong local reasoning, but exhibit predictable failure modes when tasked with multi-step or multi-turn engineering:

1. **Horizon Amnesia (Context Drift)**: After 20–40 conversation turns, early architectural constraints, pinned invariants, and original task boundaries blur into diffuse attention background. The model forgets early decisions, contradicts previously established rules, or drops subtle requirements.
2. **Premature Completion Delusion**: Compact models are biased toward affirmative closure. Upon generating syntactically valid code, the model declares "Done! All tasks complete" without executing the code, inspecting terminal exit codes, or verifying integration points.
3. **Rationalized Test Avoidance**: When faced with verification friction, lightweight models rationalize shortcuts: *"This is a trivial change," "I will test it later,"* or *"The environment lacks test frameworks."* They jump straight to modifying production code blind.
4. **Hallucinated APIs & Blind Generation**: Without strict contextual grounding, compact models guess library signatures, invent configuration keys, or modify functions without inspecting call sites, leading to silent breakage across consumer modules.

### The Apex Principle: Deterministic Constraint Breeds Flagship Execution

Flagship model performance is achieved not by granting more freedom to the model, but by **strictly constraining its degrees of freedom**:
- Replace vague instructions with **hard state gates**.
- Replace sprawling, decaying chat histories with an **externalized, bounded memory buffer** (`<= 2 KB`).
- Replace speculative claims with **empirical terminal evidence** (exit code 0).

Under ApexEngine, every code modification is treated as an audited transaction: inspected before touch, proven RED before code, hardened against production hazards, and proven GREEN by empirical command execution.

---

## 2. The 4-Gate Hard State Machine

Every task, feature, bug fix, or refactor MUST progress sequentially through four irreversible gates. Skipping or interleaving gates is strictly forbidden.

```
┌─────────────────────────┐
│  Gate 1: Context Lock   │ ──► Inspect target + callers; pin invariants in .context/
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  Gate 2: Contract TDD   │ ──► Write failing test / reproducer; execute; observe RED
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Gate 3: Production Rigor│ ──► Zero TODOs; strict typing; error bounds; clean scope
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Gate 4: Terminal Verify │ ──► Execute terminal test/build command; verify exit code 0
└────────────┬────────────┘
             │
             ▼
        [ COMPLETED ]
```

---

### Gate 1: Context Invariant Lock (Inspect Before Edit)

**Iron Rule**: Never edit or create a file without first inspecting the target file, its consumers, and its dependencies in the active turn.

- **Mandatory Actions**:
  1. Read the target file in full or around the affected scope using `read_file`.
  2. Inspect caller files, imports, and interface definitions to verify exact symbol signatures.
  3. Lock architectural invariants, constraints, and sensitive contracts into `.context/active_state.md`.
  4. Forbid blind code generation based on assumptions or conversational recall.

---

### Gate 2: Contract-First TDD (Red Before Green)

**Iron Rule**: No production code may be written, altered, or refactored without first executing a failing test or reproduction script that isolates the exact behavior or defect.

- **Mandatory Actions**:
  1. Author a dedicated unit test, integration test, or standalone reproduction script (`test_*.py`, `*.test.ts`, or CLI shell test).
  2. Run the test in the terminal environment using `run_command`.
  3. **Observe the failure**: Verify that the failure message reflects the missing capability or targeted bug (RED state).
  4. If the test passes before implementation, the test is defective or testing the wrong boundary. Stop and rewrite it.

---

### Gate 3: Defensive Production Rigor (Defensive Implementation)

**Iron Rule**: Write complete, robust, production-grade code that satisfies the test contract. Zero shortcuts, zero placeholders.

- **Prohibited Patterns (Polyglot Hard Invariants)**:
  - **Universal**: `TODO`, `FIXME`, `// Implement later`, `'left as an exercise'`, or incomplete mocks in production files.
  - **Python**: Bare `pass`, ellipsis `...`, silent error suppression (`except Exception: pass`).
  - **Rust**: `todo!()`, `unimplemented!()` macros left in non-test functions.
  - **Go**: Ignored error handling (`if err != nil { }`).
  - **TypeScript / JavaScript**: Swallowed promises (`.catch(() => {})`), empty event callbacks, or untyped `any` escapes.
  - **All Languages**: Unbounded monolithic functions (> 60 lines). Split into focused, single-responsibility units.
- **Required Defensive Practices**:
  - Explicit input validation at public boundaries (type checks, null guards, range assertions).
  - Deterministic resource cleanup (`with` context managers, `defer`, `try/finally`).
  - Contextual error messages reporting parameters, expected vs received values, and actionable failure causes.

---

### Gate 4: Empirical Terminal Verification (Evidence Before Assertion)

**Iron Rule**: A task is never complete until empirical command execution confirms success with exit code 0.

- **Mandatory Actions**:
  1. Execute the focused test or build verification command in the terminal.
  2. Inspect the raw terminal output, assertions count, and return code.
  3. Run the broader test suite or linter to ensure zero regression across adjacent modules.
  4. Only after exit code 0 is logged may the agent claim the task is verified.
  5. Synchronize the state buffer with `condense.py checkpoint` and record the commit.

---

## 3. Virtual 2M Infinite Context Memory Engine

### The Problem: Attention Degradation in Long Contexts

Even models with 1M or 2M context windows suffer severe **attention dilution** as token count climbs. Key instructions from turn 3 receive diminished query-key activation weights by turn 60.

ApexEngine solves this by decoupling **historical lineage** from **active working memory**:
- Historical actions are archived in an append-only ledger (`.context/history.log`).
- Working attention is focused strictly on a micro-buffer (`.context/active_state.md`) bounded under 2 KB.
- Regardless of whether the conversation spans 10 turns or 500 turns, the active state remains razor-sharp.

```
PROJECT ROOT
└── .context/
    ├── active_state.md   <-- Active context buffer (strictly <= 2.5 KB, target 1.5 KB)
    └── history.log        <-- Append-only milestone ledger & epoch history
```

---

### The Active State Schema (`active_state.md`)

The file `.context/active_state.md` must be kept concise, factual, and strictly under 2,500 bytes:

```markdown
# ACTIVE CONTEXT BUFFER
<!-- Target size: <= 1.5KB. Keep crisp, precise, and current. Overwrite on epoch sync. -->

## Current Objective & Milestone
- **Goal**: Implement rate-limiting middleware for WebSocket connections
- **Active Task**: Task 2 - Sliding window token bucket counter
- **Status**: IN_PROGRESS

## Active Hard Gate
- **Gate**: pytest tests/test_rate_limiter.py -k "test_sliding_window"
- **Command**: `pytest tests/test_rate_limiter.py -k "test_sliding_window"`
- **Last Status**: PENDING

## Pinned Invariants & Key Symbols
- **Invariants**:
  - Window size is 60 seconds; max tokens = 100 per IP
  - Thread safety required (use threading.Lock)
  - Time retrieval must be injectable for deterministic testing

## Modified Files & Git Diffs
- **Touched Files**:
  - `src/limiter.py` - Added sliding window counter class
  - `tests/test_limiter.py` - Authored 4 unit tests
- **Uncommitted Changes Summary**:
  - Limiter implemented; awaiting gate 4 pass

## Immediate Next Action
- Run `pytest tests/test_limiter.py` and inspect exit code
```

---

### Command-Line Interface (`condense.py`)

The included Python script (`skills/apex-engine/scripts/condense.py`) provides zero-dependency atomic operations for managing this memory structure.

#### 1. Initialize Context (`init`)
Creates `.context/` directory, initializes `active_state.md` and `history.log` from templates if not present:
```bash
python skills/apex-engine/scripts/condense.py init [--dir <project-root>] [--force]
```

#### 2. Update Active State (`update`)
Atomically regenerates `active_state.md`, automatically capturing `git status -s` and `git diff --stat`, strictly enforcing the 2,500-byte cap:
```bash
python skills/apex-engine/scripts/condense.py update \
  --dir . \
  --goal "Build secure auth token validator" \
  --task "Task 3: Expiry validation" \
  --gate "pytest tests/test_auth.py" \
  --gate-status "PENDING" \
  --invariants "JWT secrets from env only\nToken expiry strictly 3600s" \
  --next "Execute pytest and verify green"
```

#### 3. Rapid Memory Step (`step`)
Single-command progress recording that automatically captures live git diffs and updates the immediate next action without verbose flags:
```bash
python skills/apex-engine/scripts/condense.py step "Completed token validator, next is session expiry"
# Or via unified CLI:
apex step "Completed token validator, next is session expiry"
```

#### 4. Log Milestone Checkpoint (`checkpoint`)
Appends an immutable milestone record with current UTC timestamp and short git commit hash into `history.log`:
```bash
python skills/apex-engine/scripts/condense.py checkpoint \
  --dir . \
  --msg "Completed and verified sliding window rate limiter with 100% test coverage" \
  --status "COMPLETED"
```

#### 4. Read Active State (`status`)
Dumps the current active state buffer to stdout:
```bash
python skills/apex-engine/scripts/condense.py status [--dir <project-root>]
```

#### 5. Compress Epoch Snapshot (`snapshot`)
Creates a permanent compressed zip archive of active state, git diff patch, and epoch metadata in `.context/snapshots/`:
```bash
python skills/apex-engine/scripts/condense.py snapshot \
  --dir . \
  --msg "Completed and tested core auth module"
```

#### 6. Retrieve Past Knowledge (`query`)
Searches past epochs and snapshots for historical context without loading raw transcripts:
```bash
python skills/apex-engine/scripts/condense.py query \
  --dir . \
  --keyword "rate limiter"
```

#### 7. Gatekeeper Pre-Commit Verification (`gatekeeper.py`)
Scans modified files for forbidden placeholders (`TODO`, `FIXME`, bare `pass`), tests presence, and validates context buffer size:
```bash
python skills/apex-engine/scripts/gatekeeper.py --dir .

# Or install as git pre-commit hook:
python skills/apex-engine/scripts/gatekeeper.py --install-hook
```

---

### Zero-Dependency Markdown Fallback

If Python 3 is not available in the host environment, the agent MUST manually maintain `.context/active_state.md` and `.context/history.log` using standard file edit tools:
- Create `.context/active_state.md` following the schema above.
- Manually run `git status -s` and update the diff section.
- Ensure the total character count of `active_state.md` remains below 2,000 characters.
- Append completed epochs to `.context/history.log` in markdown format.

---

## 4. Rationalization Defense Matrix

Lightweight models frequently generate rationalizations to bypass rigorous engineering friction. When any rationalization appears in your internal reasoning, you MUST halt and apply the mandatory counter.

| # | Model Rationalization | ApexEngine Hard Counter |
|---|----------------------|-------------------------|
| 1 | *"This change is too small/trivial to write a test for."* | **Trivial changes cause the most frequent regressions** (typos, reversed logic, off-by-one). If it is trivial, a 3-line test takes 30 seconds. Write the test first. |
| 2 | *"I will write the implementation first, then write the test to verify it."* | **Writing tests after the fact tests what you built, not what was required.** Post-hoc tests suffer from confirmation bias and never prove they can fail on a defect. RED first. |
| 3 | *"I already know what the API or function looks like without reading the file."* | **Untrusted recall leads to version drift and hallucinated parameters.** You must call `read_file` on the target and its callers in the current turn before modifying code. |
| 4 | *"The environment does not have a test runner (pytest/jest/vitest) configured."* | **Zero-dependency assertion scripts are always possible.** Write a standalone script using standard library primitives (`python -c "assert ..."` or Node `assert`) and run it. |
| 5 | *"I'll update the active state buffer after I finish all the coding."* | **Postponed state is lost state.** If your context compacts or resets mid-turn, unwritten state disappears forever. Update state on every gate transition. |
| 6 | *"The bug cause is obvious; a reproduction test is redundant."* | **An unverified bug hypothesis causes multiple failed edit iterations.** Write the reproduction test, observe it reproduce the bug, fix the bug, observe it pass. |
| 7 | *"Leaving a TODO or placeholder is acceptable for now; I will implement it later."* | **Placeholders in production code are latent production incidents.** Zero placeholders allowed. Implement fully, or raise explicit `NotImplementedError` with bounded parameters. |
| 8 | *"Running the full test suite takes too long; I am confident this isolated edit is safe."* | **Confidence is not evidence.** Run the focused test during development, but run the full verification command before claiming completion. Exit code 0 is mandatory. |
| 9 | *"I can just mock the entire subsystem to make the test pass quickly."* | **Over-mocking verifies the mock, not the software.** Only mock non-deterministic external I/O (network requests, system clocks). Use real implementations for domain logic. |
| 10 | *"The user instructions did not mention edge cases, so handling normal inputs is sufficient."* | **Senior engineers build defensively by default.** Handle nulls, empty collections, unexpected types, and boundary conditions regardless of prompt brevity. |
| 11 | *"I can summarize file changes from memory without checking git status."* | **Memory drifts from disk reality.** Always run `git status -s` and inspect actual diffs before declaring an epoch complete. |
| 12 | *"The build failed due to an unrelated environment warning, so I can ignore the exit code."* | **Non-zero exit codes are failures.** Investigate and resolve all errors or explicitly document and isolate external blockers with terminal evidence. |

---

## 5. Red Flags & Circuit Breakers

When any of the following triggers occur, the agent must **STOP IMMEDIATELY** and execute the corrective circuit breaker:

### Red Flag Triggers
1. **Unread File Mutation**: Preparing to edit or overwrite a file that has not been read in the current conversation turn.
2. **Blind Implementation**: Writing production logic without an observed, failing test or explicit test runner command.
3. **Placeholder Generation**: Any appearance of `TODO`, `FIXME`, `pass`, `...`, or empty stub methods.
4. **Unsubstantiated Completion**: Outputting "Task complete", "All fixed", or "Success" without terminal command evidence showing exit code 0 in the same turn.
5. **Command Thrashing**: Repeating an identical failed terminal command without modifying files or diagnosing root cause.
6. **State Bloat**: `.context/active_state.md` exceeding 2,500 bytes or going un-updated across 3 consecutive turns.

### Circuit Breaker Procedure
```
1. STOP immediately. Do not write further code.
2. Call `read_file` on the target file and caller references.
3. Call `condense.py status` or inspect `.context/active_state.md`.
4. Identify which gate (1, 2, 3, or 4) was violated.
5. Regress to the violated gate and complete its mandatory actions before advancing.
```

---

## 6. Adaptive Teamwork & Subagent Swarm Protocol

ApexEngine adapts dynamically depending on whether it is running within a multi-agent environment (e.g., Google Antigravity) or as a standalone single-agent CLI (e.g., Claude Code, Cursor, Codex).

### Mode A: Multi-Agent Swarm Protocol (Antigravity Orchestration)

In Antigravity swarm mode, execution flows strictly through four specialized subagent roles:
**Architect** ➔ **Test-Writer** ➔ **Implementer** ➔ **Verifier**

Each role executes its bound responsibility within a strict handoff envelope:

```
┌────────────────────────────────────────────────────────┐
│                      ARCHITECT                         │
│  - Reads requirements & existing architecture          │
│  - Locks invariants & definitions (Gate 1)             │
│  - Dispatches task envelopes with explicit scope       │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                     TEST-WRITER                        │
│  - Writes isolated unit/integration tests              │
│  - Executes test command; observes RED failure (Gate 2)│
│  - Hands off failing test contract to Implementer      │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                     IMPLEMENTER                        │
│  - Reads target files + test contract                  │
│  - Implements defensive production code (Gate 3)       │
│  - Ensures zero placeholders & strict types            │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                      VERIFIER                          │
│  - Executes focused test suite & full suite (Gate 4)   │
│  - Verifies exit code 0 & zero regressions             │
│  - Updates .context/ active state & logs checkpoint    │
└────────────────────────────────────────────────────────┘
```

#### Handoff Envelope Standard
Every subagent dispatch must include:
```
[ROLE: implementer | test-writer | verifier]
GOAL: <High-level objective>
TASK: <Specific task name & identifier>
SCOPE: <Exact list of allowed files to create/edit>
CONTEXT: <Key contracts, references to active_state.md>
CONSTRAINTS: <Forbidden patterns, performance bounds>
VERIFICATION: <Exact terminal command that must pass with exit code 0>
```

---

### Mode B: Standalone Single-Agent Fallback (Claude Code / Codex / CLI)

When operating as a single autonomous agent without subagent dispatch capabilities:
1. **Act as your own rigid state machine**: Maintain strict separation between your inspection phase, test authoring phase, implementation phase, and verification phase.
2. **Explicit Turn Announcements**: At the start of each phase, explicitly note the active gate:
   - `[GATE 1: LOCK CONTEXT]`
   - `[GATE 2: CONTRACT TDD - RED]`
   - `[GATE 3: DEFENSIVE IMPLEMENTATION - GREEN]`
   - `[GATE 4: EMPIRICAL VERIFICATION]`
3. **Always sync state**: Run `python condense.py update` before switching contexts or ending turns.

---

## 7. Concrete End-to-End Walkthrough Example

### Objective: Add a Thread-Safe Sliding Window Rate Limiter to an API

#### Step 1: Gate 1 — Context Invariant Lock
1. Inspect existing project structure:
   - Read `src/server.py` and `src/config.py` using `read_file`.
   - Identify that `server.py` expects middleware with signature `async def rate_limit_middleware(request, call_next)`.
2. Initialize or update state buffer:
   ```bash
   python skills/apex-engine/scripts/condense.py init --dir .
   python skills/apex-engine/scripts/condense.py update \
     --dir . \
     --goal "Add sliding window rate limiter" \
     --task "Task 1: SlidingWindowRateLimiter class" \
     --gate "pytest tests/test_limiter.py" \
     --gate-status "PENDING" \
     --invariants "Thread-safe sliding window\nInjectable time provider\nDefault 60s window, 100 requests" \
     --next "Write unit tests in tests/test_limiter.py"
   ```

#### Step 2: Gate 2 — Contract-First TDD (RED)
1. Author test file `tests/test_limiter.py`:
   ```python
   import pytest
   import time
   from src.limiter import SlidingWindowRateLimiter

   def test_rate_limiter_allows_under_limit():
       limiter = SlidingWindowRateLimiter(limit=2, window_seconds=10)
       assert limiter.is_allowed("user-1") is True
       assert limiter.is_allowed("user-1") is True

   def test_rate_limiter_blocks_over_limit():
       limiter = SlidingWindowRateLimiter(limit=2, window_seconds=10)
       assert limiter.is_allowed("user-2") is True
       assert limiter.is_allowed("user-2") is True
       assert limiter.is_allowed("user-2") is False

   def test_rate_limiter_expires_window():
       current_time = 1000.0
       limiter = SlidingWindowRateLimiter(
           limit=1,
           window_seconds=5,
           time_func=lambda: current_time
       )
       assert limiter.is_allowed("user-3") is True
       assert limiter.is_allowed("user-3") is False
       current_time += 6.0
       assert limiter.is_allowed("user-3") is True
   ```
2. Execute test command in terminal:
   ```bash
   pytest tests/test_limiter.py
   ```
3. **Observe RED failure**:
   ```
   ModuleNotFoundError: No module named 'src.limiter'
   ```
   Test correctly fails. Gate 2 complete.

#### Step 3: Gate 3 — Defensive Production Rigor (GREEN)
1. Author `src/limiter.py` with strict typing, thread safety, and zero placeholders:
   ```python
   import time
   import threading
   from collections import deque
   from typing import Callable, Dict, Optional

   class SlidingWindowRateLimiter:
       """Thread-safe sliding window in-memory rate limiter."""

       def __init__(
           self,
           limit: int,
           window_seconds: float,
           time_func: Optional[Callable[[], float]] = None
       ) -> None:
           if limit <= 0:
               raise ValueError(f"limit must be positive, got {limit}")
           if window_seconds <= 0:
               raise ValueError(f"window_seconds must be positive, got {window_seconds}")

           self._limit: int = limit
           self._window_seconds: float = window_seconds
           self._time_func: Callable[[], float] = time_func or time.time
           self._lock: threading.Lock = threading.Lock()
           self._history: Dict[str, deque[float]] = {}

       def is_allowed(self, client_id: str) -> bool:
           """Evaluates if the client request is within the allowed rate limit."""
           if not client_id or not isinstance(client_id, str):
               raise ValueError("client_id must be a non-empty string")

           now = self._time_func()
           cutoff = now - self._window_seconds

           with self._lock:
               timestamps = self._history.setdefault(client_id, deque())

               # Evict timestamps outside the active sliding window
               while timestamps and timestamps[0] <= cutoff:
                   timestamps.popleft()

               if len(timestamps) < self._limit:
                   timestamps.append(now)
                   return True
               return False
   ```

#### Step 4: Gate 4 — Empirical Terminal Verification
1. Run focused unit test command:
   ```bash
   pytest tests/test_limiter.py
   ```
2. **Observe terminal output**:
   ```
   ======================= 3 passed in 0.08s =======================
   Exit code: 0
   ```
3. Run broader project test suite to verify no regressions:
   ```bash
   pytest
   ```
   All tests pass with exit code 0.

4. Checkpoint memory buffer:
   ```bash
   python skills/apex-engine/scripts/condense.py checkpoint \
     --dir . \
     --msg "SlidingWindowRateLimiter implemented and verified with 100% test coverage" \
     --status "COMPLETED"
   ```
5. Commit changes atomically with clear semantic message:
   ```bash
   git add src/limiter.py tests/test_limiter.py .context/
   git commit -m "feat(rate-limiter): add thread-safe sliding window rate limiter"
   ```

Task is empirically completed and proven.
