#!/usr/bin/env python3
"""
ApexEngine Master Unified CLI (apex_cli.py)
A single unified command-line orchestrator for vibe synthesis, context distillation,
import verification, gatekeeper pre-commit checks, error self-healing, and live studio.
Zero external dependencies: Python 3.8+ standard library only.
"""

import os
import sys
import argparse
import subprocess

# Add scripts directory to sys.path
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import condense
import gatekeeper
import vibe_synthesizer
import dep_guard
import self_heal
import studio


def main(argv=None) -> int:
    """Master CLI Entrypoint."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="apex",
        description="ApexEngine Master CLI: Flagship Quality & Infinite Memory for Compact AI Models"
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # 1. vibe: Vibe Synthesizer
    vibe_parser = subparsers.add_parser("vibe", help="Synthesize casual vibe prompt into contract spec & active memory")
    vibe_parser.add_argument("prompt", help="Natural language vibe prompt")
    vibe_parser.add_argument("--dir", default=".", help="Target directory (default: current dir)")
    vibe_parser.add_argument("--out", help="Output file path for generated Markdown spec")
    vibe_parser.add_argument("--json", action="store_true", help="Output specification as JSON")

    # 2. init: Context Initializer
    init_parser = subparsers.add_parser("init", help="Initialize .context directory and templates")
    init_parser.add_argument("--dir", default=".", help="Target directory (default: current dir)")
    init_parser.add_argument("--force", action="store_true", help="Force overwrite active_state.md")

    # 3. update: Active State Distiller
    update_parser = subparsers.add_parser("update", help="Update active_state.md with live diffs (< 2,500 bytes)")
    update_parser.add_argument("--dir", default=".", help="Target directory (default: current dir)")
    update_parser.add_argument("--goal", required=True, help="Current goal / objective")
    update_parser.add_argument("--gate", required=True, help="Active gate / verification command")
    update_parser.add_argument("--gate-status", default="PENDING", help="Status (PENDING, PASSED, FAILED)")
    update_parser.add_argument("--invariants", default="", help="Pinned invariants / constraints")
    update_parser.add_argument("--next", required=True, dest="next_action", help="Immediate next action")
    update_parser.add_argument("--task", default="Active Task", help="Current task identifier")
    update_parser.add_argument("--status", default="IN_PROGRESS", help="Current task status")

    # 4. checkpoint: Epoch Logger
    cp_parser = subparsers.add_parser("checkpoint", help="Append milestone epoch record to history.log")
    cp_parser.add_argument("--dir", default=".", help="Target directory (default: current dir)")
    cp_parser.add_argument("--msg", required=True, help="Checkpoint summary message")
    cp_parser.add_argument("--status", default="COMPLETED", help="Status (default: COMPLETED)")

    # 5. snapshot: Compressed Zip Archive
    snap_parser = subparsers.add_parser("snapshot", help="Create compressed zip archive of current epoch state")
    snap_parser.add_argument("--dir", default=".", help="Target directory (default: current dir)")
    snap_parser.add_argument("--msg", default="", help="Snapshot description")

    # 6. query: Historical Milestone Query
    query_parser = subparsers.add_parser("query", help="Query past milestones by keyword")
    query_parser.add_argument("--dir", default=".", help="Target directory (default: current dir)")
    query_parser.add_argument("--keyword", required=True, help="Keyword to search")

    # 7. gate: Gatekeeper Pre-Commit Enforcer
    gate_parser = subparsers.add_parser("gate", help="Run Gatekeeper invariant pre-commit checks")
    gate_parser.add_argument("--dir", default=".", help="Target directory (default: current dir)")
    gate_parser.add_argument("--install-hook", action="store_true", help="Install as git pre-commit hook")
    gate_parser.add_argument("--strict-tests", action="store_true", help="Fail if code changed without test")

    # 8. deps: Dependency & Import Guard
    deps_parser = subparsers.add_parser("deps", help="Verify imports and catch hallucinated packages")
    deps_parser.add_argument("--dir", default=".", help="Target directory (default: current dir)")
    deps_parser.add_argument("--allow", default="", help="Comma-separated allowed extra modules")

    # 9. heal: Diagnostic Error Parser
    heal_parser = subparsers.add_parser("heal", help="Parse compiler/test error and isolate root cause")
    heal_parser.add_argument("--error", help="Error text or log string (or pipe via stdin)")
    heal_parser.add_argument("--dir", default=".", help="Target directory (default: current dir)")
    heal_parser.add_argument("--json", action="store_true", help="Output diagnostic report as JSON")
    heal_parser.add_argument("--apply", action="store_true", help="Apply targeted remediation to active state")

    # 10. studio: Web Visualizer HUD
    studio_parser = subparsers.add_parser("studio", help="Launch live dark-mode web dashboard")
    studio_parser.add_argument("--port", type=int, default=8765, help="Port to bind (default: 8765)")
    studio_parser.add_argument("--dir", default=".", help="Target directory (default: current dir)")

    # 11. status: Active Memory Buffer
    status_parser = subparsers.add_parser("status", help="Print active_state.md buffer to stdout")
    status_parser.add_argument("--dir", default=".", help="Target directory (default: current dir)")

    # 12. benchmark: Empirical Benchmark Suite
    bench_parser = subparsers.add_parser("benchmark", help="Run empirical memory and head-to-head benchmarks")
    bench_parser.add_argument("--memory-only", action="store_true", help="Run only memory context benchmark")

    args = parser.parse_args(argv)

    if args.subcommand == "vibe":
        target_dir = os.path.abspath(args.dir)
        condense.init_context(target_dir, force=False)
        sub_argv = [args.prompt, "--dir", args.dir, "--apply-context"]
        if args.out:
            sub_argv.extend(["--out", args.out])
        if args.json:
            sub_argv.append("--json")
        return vibe_synthesizer.main(sub_argv)

    elif args.subcommand in {"init", "update", "checkpoint", "snapshot", "query", "status"}:
        return condense.main(argv)

    elif args.subcommand == "gate":
        sub_argv = ["--dir", args.dir]
        if args.install_hook:
            sub_argv.append("--install-hook")
        if args.strict_tests:
            sub_argv.append("--strict-tests")
        return gatekeeper.main(sub_argv)

    elif args.subcommand == "deps":
        sub_argv = ["--dir", args.dir]
        if args.allow:
            sub_argv.extend(["--allow", args.allow])
        return dep_guard.main(sub_argv)

    elif args.subcommand == "heal":
        sub_argv = ["--dir", args.dir]
        if args.error:
            sub_argv.extend(["--error", args.error])
        if args.json:
            sub_argv.append("--json")
        if args.apply:
            sub_argv.append("--apply")
        return self_heal.main(sub_argv)

    elif args.subcommand == "studio":
        return studio.main(["--port", str(args.port), "--dir", args.dir])

    elif args.subcommand == "benchmark":
        benchmarks_dir = os.path.abspath(os.path.join(SCRIPTS_DIR, "..", "benchmarks"))
        if args.memory_only:
            script = os.path.join(benchmarks_dir, "benchmark_memory.py")
        else:
            script = os.path.join(benchmarks_dir, "run_all.py")
        return subprocess.run([sys.executable, script]).returncode

    return 0


if __name__ == "__main__":
    sys.exit(main())
