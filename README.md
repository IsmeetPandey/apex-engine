# ApexEngine: Flagship Code Quality & Infinite Context for Compact AI Models

[![Test Suite](https://img.shields.io/badge/tests-27%2F27%20passing-brightgreen.svg)]()
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)]()
[![Dependencies](https://img.shields.io/badge/dependencies-0%20(stdlib%20only)-orange.svg)]()
[![Platform](https://img.shields.io/badge/platform-Antigravity%20%7C%20Claude%20Code%20%7C%20Codex%20%7C%20CLI-purple.svg)]()

ApexEngine is an open-source cognitive operating system and memory distillation harness that compels economical AI models (Gemini Flash, Claude Haiku, GPT-4o-mini, Qwen, DeepSeek Coder) to write production code rivaling flagship models (Claude 3.7 Sonnet, GPT-4o) while retaining context across hundreds of turns without amnesia.

---

## The Problem: Why Compact Models Write "Cheap" Code

Compact models possess vast syntactic knowledge, but fail under real development pressures due to two vulnerabilities:

1. **Horizon Amnesia & Context Dilution:** As conversations exceed 20 turns, attention degrades. The model loses track of early architectural invariants, invents conflicting dependencies, and duplicates logic.
2. **Premature Completion & Rationalization:** Smaller models exhibit urgency to conclude turns. They skip reading dependent files, omit unit tests, leave `// TODO` placeholders, and claim tasks are "done" without running compilers or test runners.

---

## The Solution: Two Autonomous Engines

ApexEngine solves both root causes with two interconnected systems:

```text
+-----------------------------------------------------------------------------------------+
|                                    APEX ENGINE SYSTEM                                   |
+-----------------------------------------------------------------------------------------+
|                                                                                         |
|  [COGNITIVE STATE PROTOCOL (SKILL.md)]     [VIRTUAL 2M CONTEXT DISTILLATION ENGINE]     |
|                                                                                         |
|  * Gate 1: Context Invariant Lock          * Zero-dependency CLI (condense.py)          |
|    (Read file & callers before edit)       * Ultra-dense buffer: .context/active_state.md|
|  * Gate 2: Contract-First TDD                (Strictly bounded < 2,500 bytes / ~500 tok)|
|    (RED failure verified in terminal)      * Append-only ledger: .context/history.log   |
|  * Gate 3: Defensive Production Rigor        (Monotonic epoch tracking [001], [002]...) |
|    (No placeholders, no TODOs, strict)     * Live git diff & uncommitted status capture |
|  * Gate 4: Empirical Terminal Verify                                                    |
|    (Exit code 0 mandatory before done)                                                  |
|                                                                                         |
|  [ADAPTIVE TEAMWORK ORCHESTRATION]                                                      |
|  * Antigravity Swarm: Architect -> Test-Writer -> Implementer -> Independent Verifier   |
|  * Standalone Fallback: Rigid sequential single-agent self-enforcing phase loops        |
+-----------------------------------------------------------------------------------------+
```

### 1. The 4-Gate Hard State Machine
- **Gate 1 (Context Lock):** Target files and calling references MUST be inspected with `read_file` before touching code.
- **Gate 2 (Contract-First TDD):** An executable test or reproducer MUST fail in the terminal before writing application logic.
- **Gate 3 (Production Rigor):** Forbids `TODO`, `pass`, empty handlers, and functions over 60 lines. Mandates strict typing and input guards.
- **Gate 4 (Terminal Verify):** Forbids declaring completion without executing a terminal test command and obtaining exit code 0.

### 2. The Virtual 2M Memory Engine
- Maintains `.context/active_state.md` (bounded strictly under 2,500 bytes / ~500 tokens).
- Automatically captures `git status -s` and `git diff --stat`.
- Flushes finished milestones to `.context/history.log` (`Epoch [001]`, `Epoch [002]`).
- Even across 300 conversation turns, the agent reads only the 500-token active buffer, eliminating context rot and slashing token costs by up to 90%.

---

## Quickstart & Installation

### Option A: Install into Google Antigravity
Clone or copy the skill directory into your personal Antigravity skills folder:
```bash
# Global installation
git clone https://github.com/your-username/apex-engine.git ~/.gemini/config/skills/apex-engine

# Or inside any individual project workspace:
git clone https://github.com/your-username/apex-engine.git .agents/skills/apex-engine
```

### Option B: Use with Claude Code / OpenAI Codex / Terminal Agents
Drop `SKILL.md` and `scripts/condense.py` into your repository:
```bash
mkdir -p .agents/skills/apex-engine
cp -r apex-engine/* .agents/skills/apex-engine/
```

---

## Daily Usage

### 1. Initialize Context in Any Repo
```bash
python scripts/condense.py init
```
This generates `.context/active_state.md` and `.context/history.log`.

### 2. Update Memory During Development
```bash
python scripts/condense.py update \
  --goal "Build OAuth token revocation" \
  --gate CONTRACT \
  --gate-status PENDING \
  --invariants "Revocation must be idempotent; TTL 3600s" \
  --next "Write failing test in tests/test_oauth.py"
```

### 3. Checkpoint Milestones
```bash
python scripts/condense.py checkpoint \
  --msg "Completed token revocation endpoint with 100% test coverage" \
  --status COMPLETED
```

---

## Verification & Test Suite

ApexEngine requires standard Python 3.8+ with **zero third-party dependencies**.

Run the complete test suite:
```bash
python -m unittest discover -s tests
```
```text
Ran 27 tests in 10.9s
OK
```

- `test_templates.py`: Verifies buffer byte boundaries and template structure.
- `test_condenser.py`: Verifies CLI commands, atomic temp-file replace, and git diff capture.
- `test_skill_purity.py`: Verifies frontmatter CSO trigger rules, AST code execution, and tool purity.
- `test_e2e_simulation.py`: Simulates full 4-gate developer lifecycle in a live temporary git repo under high-churn diff stress.

---

## Project Structure

```text
apex-engine/
├── SKILL.md                          # Master cognitive protocol & agent contract
├── scripts/
│   └── condense.py                   # Zero-dependency memory distillation engine
├── templates/
│   ├── active_state_template.md      # Active buffer template (< 1.5 KB)
│   └── epoch_log_template.md         # Milestone history log template
├── tests/
│   ├── test_templates.py
│   ├── test_condenser.py
│   ├── test_skill_purity.py
│   └── test_e2e_simulation.py
└── README.md
```

---

## Contributing & License

Contributions, feedback, and issue reports are welcome. Released under the [MIT License](LICENSE).
