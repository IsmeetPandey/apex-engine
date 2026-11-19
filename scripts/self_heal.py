#!/usr/bin/env python3
"""
ApexEngine Self-Healing Diagnostic Engine (self_heal.py)
Parses compiler, linter, and runtime test errors, isolates root cause,
and generates targeted atomic remediation directives in .context/active_state.md.
Zero external dependencies: Python 3.8+ standard library only.
"""

import os
import sys
import re
import json
import argparse
import subprocess
from typing import Dict, Any, Optional


def parse_error_log(error_text: str) -> Dict[str, Any]:
    """Extracts failing file, line, exception type, and message from error logs."""
    # Pattern 1: Python traceback "File '...', line X, in ..."
    file_matches = list(re.finditer(r'File\s+["\']([^"\']+)["\'],\s+line\s+(\d+)(?:,\s+in\s+([^\n]+))?', error_text))
    failing_file = "unknown"
    line_no = 0
    function_name = ""

    if file_matches:
        # Last frame is usually the culprit in Python tracebacks
        last_match = file_matches[-1]
        failing_file = last_match.group(1)
        line_no = int(last_match.group(2))
        function_name = last_match.group(3) or ""

    # Pattern 2: Error class and message
    error_type = "RuntimeError"
    error_msg = ""
    err_match = re.search(r'([A-Za-z0-9_]+(?:Error|Exception|Failure)):\s*([^\n]+)', error_text)
    if err_match:
        error_type = err_match.group(1)
        error_msg = err_match.group(2).strip()
    else:
        # Check for pytest FAILURES block
        fail_match = re.search(r'FAILED\s+([^\s:]+)::([^\s]+)\s*-\s*([^\n]+)', error_text)
        if fail_match:
            failing_file = fail_match.group(1)
            error_type = "TestFailure"
            error_msg = fail_match.group(3).strip()

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
        print(f"  Action:  {diagnostic['remediation']}")

    if args.apply:
        condense_script = os.path.join(os.path.dirname(__file__), "condense.py")
        if os.path.isfile(condense_script):
            next_action = f"Fix {diagnostic['failing_file']}:{diagnostic['line_number']} ({diagnostic['error_type']}: {diagnostic['error_message']})"
            cmd = [
                sys.executable,
                condense_script,
                "update",
                "--dir", target_dir,
                "--goal", "Resolve Test / Runtime Failure",
                "--gate", "VERIFY",
                "--gate-status", "FAILED",
                "--invariants", f"Target file: {diagnostic['failing_file']}; Issue: {diagnostic['error_type']}",
                "--next", next_action,
                "--task", f"Debug {diagnostic['error_type']}"
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            print("Updated .context/active_state.md with diagnostic remediation.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
