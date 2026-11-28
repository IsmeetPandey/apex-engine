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
import blast_analyzer
import invariant_store
import ste_engine
import diagram_generator


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
    gate_parser.add_argument("--strict-tests", action="store_true", default=True, help="Fail if code changed without test")
    gate_parser.add_argument("--allow-no-tests", action="store_true", help="Allow committing without companion tests")
    gate_parser.add_argument("--json", action="store_true", help="Output violations as JSON")

    # 7b. blast: Blast Radius & Dependency Analyzer
    blast_parser = subparsers.add_parser("blast", help="Analyze blast radius and downstream consumers")
    blast_parser.add_argument("--dir", default=".", help="Target directory (default: current dir)")
    blast_parser.add_argument("--files", nargs="*", help="Specific files to analyze")
    blast_parser.add_argument("--json", action="store_true", help="Output results as JSON")

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

    # 12. step: Rapid Active Memory Step
    step_parser = subparsers.add_parser("step", help="Quick one-line active memory progress update")
    step_parser.add_argument("message", help="Brief progress and immediate next step")
    step_parser.add_argument("--dir", default=".", help="Target directory (default: current dir)")

    # 13. benchmark: Empirical Benchmark Suite
    bench_parser = subparsers.add_parser("benchmark", help="Run empirical memory and head-to-head benchmarks")
    bench_parser.add_argument("--memory-only", action="store_true", help="Run only memory context benchmark")

    # 14. bind: Invariant State Variable Binder
    bind_parser = subparsers.add_parser("bind", help="Bind an invariant variable into .context/invariants.json")
    bind_parser.add_argument("name", help="Symbol name (e.g., PORT, BASELINE_SCORE)")
    bind_parser.add_argument("value", help="Literal value to store")
    bind_parser.add_argument("--dir", default=".", help="Target project directory")
    bind_parser.add_argument("--type", dest="val_type", choices=["int", "float", "string", "bool", "list", "dict"], help="Explicit primitive type")
    bind_parser.add_argument("--immutable", action="store_true", default=True, help="Register as immutable (default: True)")
    bind_parser.add_argument("--monotonic", action="store_true", help="Register as monotonic state variable")
    bind_parser.add_argument("--transitions", help="JSON map of allowed transitions for monotonic state")
    bind_parser.add_argument("--bounds", help="Bounds specification (e.g. min:max or json)")
    bind_parser.add_argument("--desc", default="", help="Description of invariant purpose")

    # 15. check-invariants: Invariant AST & Integrity Verifier
    cinv_parser = subparsers.add_parser("check-invariants", help="Verify codebase and active state against .context/invariants.json")
    cinv_parser.add_argument("--dir", default=".", help="Target directory (default: current dir)")
    cinv_parser.add_argument("--json", action="store_true", help="Output violations in JSON format")

    # 16. ste: ASD-STE100 Precision Linter & Step Normalizer
    ste_parser = subparsers.add_parser("ste", help="Lint specification/prompts with 80%% ASD-STE100 precision or normalize steps")
    ste_parser.add_argument("--file", help="File to lint")
    ste_parser.add_argument("--text", help="Text string to lint")
    ste_parser.add_argument("--step", help="Format a noisy procedural step into an active imperative command")
    ste_parser.add_argument("--check", action="store_true", help="Exit code 1 if violations found")
    ste_parser.add_argument("--json", action="store_true", help="Output violations as JSON")

    # 17. diagram: Standalone HTML/SVG Architecture Visualizer
    diag_parser = subparsers.add_parser("diagram", help="Generate standalone dark-mode HTML/SVG architecture HUD")
    diag_parser.add_argument("--dir", default=".", help="Target directory (default: current dir)")
    diag_parser.add_argument("--out", help="Output HTML file path (default: docs/architecture.html)")
    diag_parser.add_argument("--open", action="store_true", help="Automatically open generated HTML in browser")
    diag_parser.add_argument("--json", action="store_true", help="Output structural model as JSON")

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

    elif args.subcommand in {"init", "update", "checkpoint", "snapshot", "query", "status", "step"}:
        return condense.main(argv)

    elif args.subcommand == "gate":
        sub_argv = ["--dir", args.dir]
        if args.install_hook:
            sub_argv.append("--install-hook")
        if args.allow_no_tests:
            sub_argv.append("--allow-no-tests")
        if args.json:
            sub_argv.append("--json")
        return gatekeeper.main(sub_argv)

    elif args.subcommand == "blast":
        sub_argv = ["--dir", args.dir]
        if args.files:
            sub_argv.extend(["--files"] + args.files)
        if args.json:
            sub_argv.append("--json")
        return blast_analyzer.main(sub_argv)

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

    elif args.subcommand == "bind":
        sub_argv = ["bind", args.name, args.value, "--dir", args.dir]
        if args.val_type:
            sub_argv.extend(["--type", args.val_type])
        if args.monotonic:
            sub_argv.append("--monotonic")
        if args.transitions:
            sub_argv.extend(["--transitions", args.transitions])
        if args.bounds:
            sub_argv.extend(["--bounds", args.bounds])
        if args.desc:
            sub_argv.extend(["--desc", args.desc])
        return invariant_store.main(sub_argv)

    elif args.subcommand == "check-invariants":
        sub_argv = ["--dir", args.dir, "--check-invariants"]
        if args.json:
            sub_argv.append("--json")
        return gatekeeper.main(sub_argv)

    elif args.subcommand == "ste":
        sub_argv = []
        if args.file:
            sub_argv.extend(["--file", args.file])
        if args.text:
            sub_argv.extend(["--text", args.text])
        if args.step:
            sub_argv.extend(["--step", args.step])
        if args.check:
            sub_argv.append("--check")
        if args.json:
            sub_argv.append("--json")
        return ste_engine.main(sub_argv)

    elif args.subcommand == "diagram":
        sub_argv = ["--dir", args.dir]
        if args.out:
            sub_argv.extend(["--out", args.out])
        if args.open:
            sub_argv.append("--open")
        if args.json:
            sub_argv.append("--json")
        return diagram_generator.main(sub_argv)

    return 0


if __name__ == "__main__":
    sys.exit(main())
