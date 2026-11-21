#!/usr/bin/env python3
"""
ApexEngine Self-Healing Diagnostic Engine (self_heal.py)
Parses compiler, linter, runtime, and Gatekeeper errors, isolates root cause,
enforces the Anti-Band-Aid Protocol (Origin vs Manifestation site),
and preserves context invariants in .context/active_state.md.
Zero external dependencies: Python 3.8+ standard library only.
"""

import os
import sys
import re
import json
import argparse
import subprocess
from typing import Dict, Any, Optional

MANIFESTATION_EXCEPTIONS = {
    "AttributeError", "TypeError", "KeyError", "IndexError",
    "NullPointerException", "ZeroDivisionError", "UnboundLocalError"
}


def parse_error_log(error_text: str) -> Dict[str, Any]:
    """Extracts failing file, line, exception type, and message from error logs."""
    failing_file = "unknown"
    line_no = 0
    function_name = ""
    error_type = "RuntimeError"
    error_msg = ""
    is_manifestation = False

    # Check 0: Gatekeeper 3.0 violation: "file.py:14 [SEC001] - message" or "file.py:10 - desc"
    gk_match = re.search(r'([a-zA-Z0-9_\-\./\\]+\.(?:py|ts|tsx|js|jsx|go|rs)):(\d+)\s*(?:\[([A-Z0-9_]+)\])?\s*-\s*([^\n]+)', error_text)
    if gk_match:
        failing_file = gk_match.group(1)
        line_no = int(gk_match.group(2))
        error_type = gk_match.group(3) or "GatekeeperViolation"
        error_msg = gk_match.group(4).strip()

    # Check 1: TypeScript / JavaScript tsc error: "src/App.tsx(14,5): error TS2322: ..." or "src/App.tsx:14:5 - error TS2322: ..."
    elif re.search(r'([a-zA-Z0-9_\-\./\\]+\.(?:ts|tsx|js|jsx))(?:\((\d+),\d+\)|:(\d+):\d+)\s*(?:-\s*error\s*|:\s*error\s*)(TS\d+)?:?\s*([^\n]+)', error_text):
        ts_match = re.search(r'([a-zA-Z0-9_\-\./\\]+\.(?:ts|tsx|js|jsx))(?:\((\d+),\d+\)|:(\d+):\d+)\s*(?:-\s*error\s*|:\s*error\s*)(TS\d+)?:?\s*([^\n]+)', error_text)
        if ts_match:
            failing_file = ts_match.group(1)
            line_no = int(ts_match.group(2) or ts_match.group(3))
            error_type = ts_match.group(4) or "TypeScriptError"
            error_msg = ts_match.group(5).strip()

    # Check 2: Rust rustc/cargo error: "error[E0425]: ... --> src/main.rs:18:5"
    elif "-->" in error_text and ".rs:" in error_text:
        rs_loc_match = re.search(r'-->\s*([a-zA-Z0-9_\-\./\\]+\.rs):(\d+):(\d+)', error_text)
        rs_err_match = re.search(r'error(?:\[(E\d+)\])?:\s*([^\n]+)', error_text)
        if rs_loc_match:
            failing_file = rs_loc_match.group(1)
            line_no = int(rs_loc_match.group(2))
        if rs_err_match:
            error_type = rs_err_match.group(1) or "RustcError"
            error_msg = rs_err_match.group(2).strip()

    # Check 3: Go build/test error: "main.go:14:2: undefined: myFunction"
    elif re.search(r'([a-zA-Z0-9_\-\./\\]+\.go):(\d+):(?:\d+:)?\s*(.+)', error_text):
        go_match = re.search(r'([a-zA-Z0-9_\-\./\\]+\.go):(\d+):(?:\d+:)?\s*(.+)', error_text)
        if go_match:
            failing_file = go_match.group(1)
            line_no = int(go_match.group(2))
            error_type = "GoCompilerError"
            error_msg = go_match.group(3).strip()

    # Check 4: Python traceback "File '...', line X, in ..."
    elif re.search(r'File\s+["\']([^"\']+)["\'],\s+line\s+(\d+)', error_text):
        file_matches = list(re.finditer(r'File\s+["\']([^"\']+)["\'],\s+line\s+(\d+)(?:,\s+in\s+([^\n]+))?', error_text))
        if file_matches:
            last_match = file_matches[-1]
            failing_file = last_match.group(1)
            line_no = int(last_match.group(2))
            function_name = last_match.group(3) or ""

        err_match = re.search(r'([A-Za-z0-9_]+(?:Error|Exception|Failure)):\s*([^\n]+)', error_text)
        if err_match:
            error_type = err_match.group(1)
            error_msg = err_match.group(2).strip()

    # Check 5: Pytest FAILURES block
    elif "FAILURES" in error_text or "FAILED" in error_text:
        fail_match = re.search(r'FAILED\s+([^\s:]+)(?:::([^\s]+))?\s*-\s*([^\n]+)', error_text)
        if fail_match:
            failing_file = fail_match.group(1)
            function_name = fail_match.group(2) or ""
            error_type = "TestFailure"
            error_msg = fail_match.group(3).strip()

    # Determine Anti-Band-Aid classification
    if error_type in MANIFESTATION_EXCEPTIONS:
        is_manifestation = True
        remediation = (
            f"ANTI-BAND-AID PROTOCOL: {error_type} at {failing_file}:{line_no} is a manifestation site. "
            "DO NOT slap a null guard (e.g., 'if obj is None: return' or 'obj?.x'). "
            "Trace upstream producer/factory where invalid state originated and fix at source."
        )
    else:
        remediation = (
            f"Inspect {failing_file}:{line_no} and resolve {error_type}: '{error_msg}'. "
            "Apply minimal targeted fix without altering unaffected contracts."
        )

    return {
        "failing_file": failing_file,
        "line_number": line_no,
        "function": function_name,
        "error_type": error_type,
        "error_message": error_msg,
        "is_manifestation_site": is_manifestation,
        "remediation": remediation
    }


def main(argv=None) -> int:
    """CLI Entrypoint for self_heal.py."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="ApexEngine Self-Healing Diagnostic Engine")
    parser.add_argument("--error", help="Error text or log string (or read from stdin)")
    parser.add_argument("--dir", default=".", help="Target workspace directory (default: current dir)")
    parser.add_argument("--json", action="store_true", help="Output diagnostic report as JSON")
    parser.add_argument("--apply", action="store_true", help="Update .context/active_state.md with remediation")

    args = parser.parse_args(argv)
    target_dir = os.path.abspath(args.dir)

    error_text = args.error
    if not error_text and not sys.stdin.isatty():
        error_text = sys.stdin.read()

    if not error_text:
        print("Error: No error log provided via --error or stdin.", file=sys.stderr)
        return 2

    diagnostic = parse_error_log(error_text)

    if args.json:
        sys.stdout.write(json.dumps(diagnostic, indent=2) + "\n")
    else:
        print("=== ApexEngine Diagnostic Report ===")
        print(f"  Culprit: {diagnostic['failing_file']}:{diagnostic['line_number']}")
        print(f"  Error:   {diagnostic['error_type']} - {diagnostic['error_message']}")
        print(f"  Site:    {'Manifestation (Upstream Check Required)' if diagnostic['is_manifestation_site'] else 'Direct Site'}")
        print(f"  Action:  {diagnostic['remediation']}")

    if args.apply:
        condense_script = os.path.join(os.path.dirname(__file__), "condense.py")
        if os.path.isfile(condense_script):
            state_file = os.path.join(target_dir, ".context", "active_state.md")
            current_goal = "Resolve Diagnostic Failure"
            current_invariants = f"Target: {diagnostic['failing_file']}; Issue: {diagnostic['error_type']}"
            current_gate = "VERIFY"

            # Non-destructive preservation of existing state
            if os.path.isfile(state_file):
                try:
                    with open(state_file, "r", encoding="utf-8") as f:
                        existing = f.read()
                    g_match = re.search(r"\*\*Goal\*\*:\s*([^\n]+)", existing)
                    if g_match:
                        current_goal = g_match.group(1).strip()
                    inv_match = re.search(r"## Pinned Invariants & Key Symbols\s*\n-\s*\*\*Invariants\*\*:\s*\n((?:\s*-\s*[^\n]+\n*)*)", existing)
                    if inv_match and inv_match.group(1).strip():
                        # Append diagnostic constraint without wiping original invariants
                        old_invs = inv_match.group(1).strip().lstrip("- ")
                        current_invariants = f"{old_invs}\n  - Diagnostic Invariant: {diagnostic['remediation']}"
                    gate_match = re.search(r"\*\*Gate\*\*:\s*([^\n]+)", existing)
                    if gate_match:
                        current_gate = gate_match.group(1).strip()
                except (OSError, UnicodeDecodeError):
                    current_invariants = f"Target: {diagnostic['failing_file']}; Issue: {diagnostic['error_type']}"

            next_action = f"Fix {diagnostic['failing_file']}:{diagnostic['line_number']} ({diagnostic['error_type']})"
            cmd = [
                sys.executable,
                condense_script,
                "update",
                "--dir", target_dir,
                "--goal", current_goal,
                "--gate", current_gate,
                "--gate-status", "FAILED",
                "--invariants", current_invariants,
                "--next", next_action,
                "--task", f"Debug {diagnostic['error_type']}"
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            print("Updated .context/active_state.md with diagnostic remediation (invariants preserved).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
