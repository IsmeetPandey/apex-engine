# ACTIVE CONTEXT BUFFER
<!-- Target size: <= 1.5KB. Keep crisp, precise, and current. Overwrite on epoch sync. -->

## Current Objective & Milestone
- **Goal**: [Brief description of current overarching goal]
- **Active Task**: [Task identifier & name currently being executed]
- **Milestone / Phase**: [Milestone or Wave number]
- **Status**: [IN_PROGRESS | BLOCKED | AWAITING_VERIFICATION]

## Active Hard Gate
- **Gate**: [Verification criteria that must pass before proceeding]
- **Command**: `[e.g., pytest / npm test / build command]`
- **Last Status**: [PENDING | PASSED | FAILED]

## Pinned Invariants & Key Symbols
- **Invariants**:
  - [Critical constraint or architectural invariant 1]
  - [Critical constraint or architectural invariant 2]
- **Key Symbols & Contracts**:
  - `[FunctionNameOrClass]`: [Brief contract or expected behavior]
  - `[ConfigOrEnvKey]`: [Definition or usage]

### 🔒 Pinned Invariant Register
| Symbol | Type | Value | Reg | Constraint |
|:-------|:-----|:------|:----|:-----------|
| `PORT` | int | `8080` | IMMUTABLE | `8000..9000` |
| `STAGE` | state | `GATE_1_LOCK` | MONOTONIC | forward DAG |

## Modified Files & Git Diffs
- **Touched Files**:
  - `[path/to/file1]` - [Brief change summary]
  - `[path/to/file2]` - [Brief change summary]
- **Uncommitted Changes Summary**:
  - [1-2 line summary of working tree state]

## Immediate Next Action
- [Next atomic action or step to execute right now]
