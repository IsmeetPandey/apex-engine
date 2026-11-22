#!/usr/bin/env python3
"""
ApexEngine Memory Distillation Engine (condense.py)
Zero external dependencies: Python 3.8+ standard library only.
"""

import os
import sys
import re
import json
import shutil
import zipfile
import tempfile
import argparse
import datetime
import subprocess
from pathlib import Path
from typing import Tuple, List, Dict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

FALLBACK_ACTIVE_STATE = """# ACTIVE CONTEXT BUFFER
<!-- Target size: <= 1.5KB. Keep crisp, precise, and current. Overwrite on epoch sync. -->

## Current Objective & Milestone
- **Goal**: [Brief description of current overarching goal]
- **Active Task**: [Task identifier & name currently being executed]
- **Status**: IN_PROGRESS

## Active Hard Gate
- **Gate**: [Verification criteria that must pass before proceeding]
- **Command**: `[test command]`
- **Last Status**: PENDING

## Pinned Invariants & Key Symbols
- **Invariants**:
  - [Constraint 1]

### 🔒 Pinned Invariant Register
| Symbol | Type | Value | Reg | Constraint |
|:-------|:-----|:------|:----|:-----------|
| `PORT` | int | `8080` | IMMUTABLE | `8000..9000` |

## Modified Files & Git Diffs
- **Touched Files**:
  - (clean)
- **Uncommitted Changes Summary**:
  - Working tree clean

## Immediate Next Action
- [Next action]
"""

FALLBACK_EPOCH_LOG = """# APEX EPOCH HISTORY LOG
<!-- Append-only ledger of completed tasks, checkpoints, and epoch condensations. -->
"""

MAX_ACTIVE_STATE_BYTES = 2500


def get_short_commit(target_dir: str) -> str:
    """Retrieve short git commit hash or return N/A."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=target_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except Exception:
        return "N/A"
    return "N/A"


def get_git_diff_summary(target_dir: str) -> str:
    """Gathers git status -s and git diff --stat from target_dir."""
    try:
        status_proc = subprocess.run(
            ["git", "status", "-s"],
            cwd=target_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5
        )
        if status_proc.returncode != 0:
            return "- **Touched Files**:\n  - (clean / not a git repo)\n- **Uncommitted Changes Summary**:\n  - Clean or untracked directory"

        status_out = status_proc.stdout.strip()
        if not status_out:
            return "- **Touched Files**:\n  - (clean)\n- **Uncommitted Changes Summary**:\n  - Clean working tree (no uncommitted changes)"

        diff_proc = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=target_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5
        )
        diff_out = diff_proc.stdout.strip() if diff_proc.returncode == 0 else ""

        parts = ["- **Status**:\n```\n" + status_out + "\n```"]
        if diff_out:
            parts.append("- **Diff Stat**:\n```\n" + diff_out + "\n```")
        return "\n".join(parts)
    except Exception:
        return "- **Touched Files**:\n  - (clean)\n- **Uncommitted Changes Summary**:\n  - Clean or untracked directory"


def build_active_state_content(
    goal: str,
    gate: str,
    next_action: str,
    invariants: str = "",
    task: str = "Active Task",
    status: str = "IN_PROGRESS",
    gate_status: str = "PENDING",
    git_summary: str = "",
    invariant_table: str = ""
) -> str:
    """Builds active state markdown content strictly bounded < 2,500 bytes."""
    if invariants:
        inv_lines = "\n".join(f"  - {line.strip()}" for line in invariants.splitlines() if line.strip())
    else:
        inv_lines = "  - (none)"

    inv_block = f"- **Invariants**:\n{inv_lines}"
    if invariant_table:
        inv_block = f"{inv_block}\n\n{invariant_table}"

    template = (
        "# ACTIVE CONTEXT BUFFER\n"
        "<!-- Target size: <= 1.5KB. Keep crisp, precise, and current. Overwrite on epoch sync. -->\n\n"
        "## Current Objective & Milestone\n"
        f"- **Goal**: {goal}\n"
        f"- **Active Task**: {task}\n"
        f"- **Status**: {status}\n\n"
        "## Active Hard Gate\n"
        f"- **Gate**: {gate}\n"
        f"- **Command**: `{gate}`\n"
        f"- **Last Status**: {gate_status}\n\n"
        "## Pinned Invariants & Key Symbols\n"
        f"{inv_block}\n\n"
        "## Immediate Next Action\n"
        f"- {next_action}\n\n"
        "## Modified Files & Git Diffs\n"
        "{GIT_PLACEHOLDER}\n"
    )

    base_without_git = template.replace("{GIT_PLACEHOLDER}", "")
    base_bytes = len(base_without_git.encode("utf-8"))
    safety_margin = 100
    target_max = MAX_ACTIVE_STATE_BYTES - safety_margin

    if not git_summary:
        git_summary = "- **Touched Files**:\n  - (clean)\n- **Uncommitted Changes Summary**:\n  - Clean working tree"

    git_bytes = len(git_summary.encode("utf-8"))
    if base_bytes + git_bytes > target_max:
        allowed_git = max(50, target_max - base_bytes - len(b"\n... (truncated)"))
        truncated_git = git_summary.encode("utf-8")[:allowed_git].decode("utf-8", errors="ignore")
        git_summary = truncated_git + "\n... (truncated)"

    content = template.replace("{GIT_PLACEHOLDER}", git_summary)

    # Double check total byte limit
    encoded = content.encode("utf-8")
    if len(encoded) >= MAX_ACTIVE_STATE_BYTES:
        cutoff = MAX_ACTIVE_STATE_BYTES - 50
        content = encoded[:cutoff].decode("utf-8", errors="ignore") + "\n... (truncated)\n"

    return content


def init_context(target_dir: str, force: bool = False) -> None:
    """Initializes .context directory and template files."""
    context_dir = os.path.join(target_dir, ".context")
    os.makedirs(context_dir, exist_ok=True)

    active_path = os.path.join(context_dir, "active_state.md")
    history_path = os.path.join(context_dir, "history.log")

    try:
        from invariant_store import InvariantStore
        InvariantStore(context_dir)
    except (ImportError, OSError, ValueError) as err:
        sys.stderr.write(f"Notice: Invariant store init bypassed: {err}\n")

    if not os.path.isfile(active_path) or force:
        src_active = os.path.join(TEMPLATES_DIR, "active_state_template.md")
        if os.path.isfile(src_active):
            shutil.copyfile(src_active, active_path)
        else:
            with open(active_path, "w", encoding="utf-8") as f:
                f.write(FALLBACK_ACTIVE_STATE)

    if not os.path.isfile(history_path) or force:
        src_history = os.path.join(TEMPLATES_DIR, "epoch_log_template.md")
        if os.path.isfile(src_history):
            shutil.copyfile(src_history, history_path)
        else:
            with open(history_path, "w", encoding="utf-8") as f:
                f.write(FALLBACK_EPOCH_LOG)


def update_active_state(
    target_dir: str,
    goal: str,
    gate: str,
    next_action: str,
    invariants: str = "",
    task: str = "Active Task",
    status: str = "IN_PROGRESS",
    gate_status: str = "PENDING"
) -> str:
    """Atomically updates active_state.md with git status and diffs."""
    context_dir = os.path.join(target_dir, ".context")
    os.makedirs(context_dir, exist_ok=True)
    state_file = os.path.join(context_dir, "active_state.md")

    inv_table = ""
    try:
        from invariant_store import InvariantStore
        store = InvariantStore(context_dir)
        regs = store.get_invariants()
        if regs.get("immutable") or regs.get("monotonic"):
            inv_table = store.render_markdown_table(max_bytes=600)
    except (ImportError, OSError, ValueError) as err:
        sys.stderr.write(f"Notice: Invariant table render bypassed: {err}\n")

    git_summary = get_git_diff_summary(target_dir)
    content = build_active_state_content(
        goal=goal,
        gate=gate,
        next_action=next_action,
        invariants=invariants,
        task=task,
        status=status,
        gate_status=gate_status,
        git_summary=git_summary,
        invariant_table=inv_table
    )

    temp_fd, temp_path = tempfile.mkstemp(
        prefix="active_state.md.tmp",
        dir=context_dir,
        text=True
    )
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, state_file)
    except Exception:
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError as cleanup_err:
                sys.stderr.write(f"Warning: could not unlink {temp_path}: {cleanup_err}\n")
        raise

    return content


def quick_step(target_dir: str, message: str) -> str:
    """Convenience helper to record a rapid progress step into active_state.md."""
    context_dir = os.path.join(target_dir, ".context")
    state_file = os.path.join(context_dir, "active_state.md")

    current_goal = "Active Feature Development"
    current_invariants = "Production quality invariants locked"
    current_gate = "VERIFY"
    current_gate_status = "IN_PROGRESS"

    if os.path.isfile(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                existing = f.read()
            g_match = re.search(r"\*\*Goal\*\*:\s*([^\n]+)", existing)
            if g_match:
                current_goal = g_match.group(1).strip()
            inv_match = re.search(r"## Pinned Invariants & Key Symbols\s*\n-\s*\*\*Invariants\*\*:\s*\n((?:\s*-\s*[^\n]+\n*)*)", existing)
            if inv_match and inv_match.group(1).strip():
                current_invariants = inv_match.group(1).strip().lstrip("- ")
            gate_match = re.search(r"\*\*Gate\*\*:\s*([^\n]+)", existing)
            if gate_match:
                current_gate = gate_match.group(1).strip()
            status_match = re.search(r"\*\*Last Status\*\*:\s*([^\n]+)", existing)
            if status_match:
                current_gate_status = status_match.group(1).strip()
        except Exception:
            return ""

    return update_active_state(
        target_dir=target_dir,
        goal=current_goal,
        gate=current_gate,
        next_action=message,
        invariants=current_invariants,
        task="Progress Step",
        status="IN_PROGRESS",
        gate_status=current_gate_status
    )


def get_next_epoch_number(history_file: str) -> int:
    """Calculates next monotonic epoch number from history.log."""
    if not os.path.isfile(history_file):
        return 1
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            content = f.read()
        matches = re.findall(r"^## Epoch \[(\d+)\]", content, flags=re.MULTILINE)
        if matches:
            return max(int(m) for m in matches) + 1
    except Exception:
        return 1
    return 1


def checkpoint(target_dir: str, msg: str, status: str = "COMPLETED") -> str:
    """Appends an epoch checkpoint record to history.log."""
    context_dir = os.path.join(target_dir, ".context")
    os.makedirs(context_dir, exist_ok=True)
    history_file = os.path.join(context_dir, "history.log")

    epoch_idx = get_next_epoch_number(history_file)
    epoch_str = f"{epoch_idx:03d}"
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    commit_hash = get_short_commit(target_dir)

    entry = (
        f"\n## Epoch [{epoch_str}]: {msg}\n"
        f"- **Timestamp**: {timestamp}\n"
        f"- **Commit**: `{commit_hash}`\n"
        f"- **Status**: {status}\n"
        f"- **Summary**:\n"
        f"  - {msg}\n"
        "---\n"
    )

    with open(history_file, "a", encoding="utf-8") as f:
        f.write(entry)

    return entry


def get_status(target_dir: str) -> Tuple[str, bool]:
    """Reads active_state.md or returns an error tuple."""
    state_file = os.path.join(target_dir, ".context", "active_state.md")
    if not os.path.isfile(state_file):
        return (f"Error: active_state.md not found in {os.path.join(target_dir, '.context')}", False)
    with open(state_file, "r", encoding="utf-8") as f:
        return (f.read(), True)


def create_snapshot(target_dir: str, msg: str = "") -> str:
    """Creates a compressed zip archive of current active state, diffs, and metadata."""
    context_dir = os.path.join(target_dir, ".context")
    snapshots_dir = os.path.join(context_dir, "snapshots")
    os.makedirs(snapshots_dir, exist_ok=True)

    history_file = os.path.join(context_dir, "history.log")
    next_epoch = get_next_epoch_number(history_file)
    epoch_str = f"{next_epoch:03d}"
    now = datetime.datetime.now(datetime.timezone.utc)
    ts_label = now.strftime("%Y%m%dT%H%M%SZ")
    zip_name = f"snapshot_epoch_{epoch_str}_{ts_label}.zip"
    zip_path = os.path.join(snapshots_dir, zip_name)

    active_state_path = os.path.join(context_dir, "active_state.md")
    active_content = ""
    if os.path.isfile(active_state_path):
        with open(active_state_path, "r", encoding="utf-8") as f:
            active_content = f.read()

    # Capture patch
    diff_patch = ""
    try:
        proc = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=target_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5
        )
        if proc.returncode == 0:
            diff_patch = proc.stdout
    except Exception:
        diff_patch = ""

    meta = {
        "epoch": next_epoch,
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": get_short_commit(target_dir),
        "message": msg or "Epoch milestone snapshot",
        "has_active_state": bool(active_content),
        "patch_bytes": len(diff_patch.encode("utf-8"))
    }

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if active_content:
            zf.writestr("active_state.md", active_content)
        if diff_patch:
            zf.writestr("git_diff.patch", diff_patch)
        zf.writestr("snapshot_meta.json", json.dumps(meta, indent=2))
        if os.path.isfile(history_file):
            zf.write(history_file, arcname="history.log")

    return zip_path


def query_history(target_dir: str, keyword: str) -> Tuple[str, bool]:
    """Searches history.log and snapshots for milestones matching keyword."""
    context_dir = os.path.join(target_dir, ".context")
    history_file = os.path.join(context_dir, "history.log")
    if not os.path.isfile(history_file):
        return ("No history.log found in context.", False)

    with open(history_file, "r", encoding="utf-8") as f:
        content = f.read()

    epochs = re.split(r"\n(?=## Epoch \[)", content)
    matches = [ep.strip() for ep in epochs if keyword.lower() in ep.lower() and ep.strip()]

    if not matches:
        return (f"No milestones found matching '{keyword}'.", False)

    snapshots_dir = os.path.join(context_dir, "snapshots")
    available_zips = []
    if os.path.isdir(snapshots_dir):
        available_zips = [f for f in os.listdir(snapshots_dir) if f.endswith(".zip")]

    out = [f"=== Found {len(matches)} matching milestone(s) for '{keyword}' ===\n"]
    for m in matches:
        out.append(m)
        out.append("")

    if available_zips:
        out.append(f"Available Compressed Snapshots ({len(available_zips)}):")
        for z in available_zips[:5]:
            out.append(f"  - .context/snapshots/{z}")
        if len(available_zips) > 5:
            out.append(f"  ... and {len(available_zips) - 5} more.")

    return ("\n".join(out), True)


def main(argv=None) -> int:
    """CLI Entrypoint for condense.py."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="ApexEngine Memory Distillation Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    init_parser = subparsers.add_parser("init", help="Initialize .context directory and templates")
    init_parser.add_argument("--dir", default=".", help="Target directory (default: current dir)")
    init_parser.add_argument("--force", action="store_true", help="Force overwrite existing active_state.md and history.log")

    # update
    update_parser = subparsers.add_parser("update", help="Update active_state.md with bounded context")
    update_parser.add_argument("--dir", default=".", help="Target directory (default: current dir)")
    update_parser.add_argument("--goal", required=True, help="Current goal / objective")
    update_parser.add_argument("--gate", required=True, help="Verification gate / command")
    update_parser.add_argument("--gate-status", default="PENDING", help="Status of the gate (PENDING, PASSED, FAILED)")
    update_parser.add_argument("--invariants", default="", help="Pinned invariants / key symbols")
    update_parser.add_argument("--next", required=True, dest="next_action", help="Immediate next action")
    update_parser.add_argument("--task", default="Active Task", help="Current active task name or ID")
    update_parser.add_argument("--status", default="IN_PROGRESS", help="Current task status")

    # checkpoint
    cp_parser = subparsers.add_parser("checkpoint", help="Append an epoch record to history.log")
    cp_parser.add_argument("--dir", default=".", help="Target directory (default: current dir)")
    cp_parser.add_argument("--msg", required=True, help="Checkpoint summary message")
    cp_parser.add_argument("--status", default="COMPLETED", help="Epoch status (default: COMPLETED)")

    # snapshot
    snap_parser = subparsers.add_parser("snapshot", help="Create a compressed zip snapshot of current epoch")
    snap_parser.add_argument("--dir", default=".", help="Target directory (default: current dir)")
    snap_parser.add_argument("--msg", default="", help="Snapshot description or milestone summary")

    # query
    query_parser = subparsers.add_parser("query", help="Query past milestones and snapshots by keyword")
    query_parser.add_argument("--dir", default=".", help="Target directory (default: current dir)")
    query_parser.add_argument("--keyword", required=True, help="Keyword to search in past epochs")

    # status
    status_parser = subparsers.add_parser("status", help="Print active_state.md to stdout")
    status_parser.add_argument("--dir", default=".", help="Target directory (default: current dir)")

    # step (rapid single-argument progress update)
    step_parser = subparsers.add_parser("step", help="Quick one-line active memory progress update")
    step_parser.add_argument("message", help="Brief progress and immediate next step")
    step_parser.add_argument("--dir", default=".", help="Target directory (default: current dir)")

    args = parser.parse_args(argv)
    target_dir = os.path.abspath(args.dir)

    if args.command == "init":
        init_context(target_dir, force=args.force)
        print(f"Initialized .context in {target_dir}")
        return 0
    elif args.command == "update":
        update_active_state(
            target_dir=target_dir,
            goal=args.goal,
            gate=args.gate,
            next_action=args.next_action,
            invariants=args.invariants,
            task=args.task,
            status=args.status,
            gate_status=args.gate_status
        )
        print(f"Updated active_state.md in {target_dir}")
        return 0
    elif args.command == "checkpoint":
        checkpoint(target_dir, msg=args.msg, status=args.status)
        print(f"Logged checkpoint in {target_dir}")
        return 0
    elif args.command == "snapshot":
        path = create_snapshot(target_dir, msg=args.msg)
        print(f"Created snapshot: {path}")
        return 0
    elif args.command == "query":
        res, ok = query_history(target_dir, args.keyword)
        if ok:
            print(res)
            return 0
        else:
            print(res, file=sys.stderr)
            return 1
    elif args.command == "status":
        output, ok = get_status(target_dir)
        if ok:
            sys.stdout.write(output)
            return 0
        else:
            sys.stderr.write(output + "\n")
            return 1
    elif args.command == "step":
        quick_step(target_dir, args.message)
        print(f"Recorded step in {target_dir}")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
