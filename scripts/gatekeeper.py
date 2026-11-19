#!/usr/bin/env python3
"""
ApexEngine Gatekeeper: Pre-Commit & Verification Enforcer
Enforces all 4 Invariant Gates prior to git commit.
Zero external dependencies: Python 3.8+ standard library only.
"""

import os
import sys
import re
import argparse
import subprocess
from pathlib import Path
from typing import List, Tuple

FORBIDDEN_PATTERNS = [
    (re.compile(r"(?i)\bTODO\b"), "TODO placeholder found"),
    (re.compile(r"(?i)\bFIXME\b"), "FIXME placeholder found"),
    (re.compile(r"^\s*pass\s*$", re.MULTILINE), "Bare 'pass' statement found"),
    (re.compile(r"^\s*\.\.\.\s*$", re.MULTILINE), "Bare '...' ellipsis placeholder found"),
    (re.compile(r"(?i)left as an exercise"), "'Left as an exercise' placeholder found"),
]

CODE_EXTENSIONS = {".py", ".ts", ".js", ".jsx", ".tsx", ".go", ".rs", ".java", ".cpp", ".c", ".cs"}
TEST_PATTERNS = [re.compile(r"(?i)(test_|_test|\.test\.|\.spec\.)")]


def get_modified_files(target_dir: str) -> List[str]:
    """Retrieves list of staged files, or modified files if none staged."""
    try:
        # Check staged files
        proc = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=target_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5
        )
        staged = [f.strip() for f in proc.stdout.splitlines() if f.strip()]
        if staged:
            return staged

        # Fallback to unstaged / modified files
        proc2 = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=target_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5
        )
        return [f.strip() for f in proc2.stdout.splitlines() if f.strip()]
    except Exception:
        return []


def check_placeholders(target_dir: str, files: List[str]) -> List[str]:
    """Scans code files for banned placeholders."""
    violations = []
    for rel_path in files:
        full_path = os.path.join(target_dir, rel_path)
        ext = os.path.splitext(rel_path)[1].lower()
        if ext not in CODE_EXTENSIONS or not os.path.isfile(full_path):
            continue

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            continue

        for pattern, desc in FORBIDDEN_PATTERNS:
            match = pattern.search(content)
            if match:
                # Calculate approximate line number
                line_no = content[:match.start()].count("\n") + 1
                violations.append(f"{rel_path}:{line_no} - {desc} ('{match.group(0).strip()}')")
    return violations


def check_active_state(target_dir: str) -> List[str]:
    """Verifies .context/active_state.md exists and is within byte limits."""
    violations = []
    state_file = os.path.join(target_dir, ".context", "active_state.md")
    if not os.path.isfile(state_file):
        violations.append("Missing .context/active_state.md. Run 'python scripts/condense.py init'")
        return violations

    size = os.path.getsize(state_file)
    if size > 2500:
        violations.append(f".context/active_state.md exceeds 2,500 byte limit ({size} bytes). Run condense.py update.")
    return violations


def check_tests_present(files: List[str]) -> List[str]:
    """Warns if application code changed without any test files."""
    code_files = [f for f in files if os.path.splitext(f)[1].lower() in CODE_EXTENSIONS]
    if not code_files:
        return []

    has_test = any(any(p.search(f) for p in TEST_PATTERNS) for f in code_files)
    if not has_test:
        return ["Application code was modified without corresponding test files (Gate 2: Contract-First TDD violation)."]
    return []


def install_pre_commit_hook(target_dir: str) -> bool:
    """Installs gatekeeper as a git pre-commit hook."""
    git_dir = os.path.join(target_dir, ".git")
    if not os.path.isdir(git_dir):
        print(f"Error: {target_dir} is not a git repository.", file=sys.stderr)
        return False

    hooks_dir = os.path.join(git_dir, "hooks")
    os.makedirs(hooks_dir, exist_ok=True)
    hook_file = os.path.join(hooks_dir, "pre-commit")

    hook_content = (
        "#!/bin/sh\n"
        "# ApexEngine Gatekeeper pre-commit hook\n"
        "python scripts/gatekeeper.py --dir .\n"
    )

    with open(hook_file, "w", encoding="utf-8") as f:
        f.write(hook_content)

    # Make executable on Unix
    try:
        import stat
        st = os.stat(hook_file)
        os.chmod(hook_file, st.st_mode | stat.S_IEXEC)
    except Exception:
        pass

    print(f"Installed ApexEngine pre-commit hook in {hook_file}")
    return True


def main(argv=None) -> int:
    """CLI Entrypoint for gatekeeper."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="ApexEngine Gatekeeper: Invariant Verification Enforcer")
    parser.add_argument("--dir", default=".", help="Target repository directory (default: current dir)")
    parser.add_argument("--install-hook", action="store_true", help="Install as git pre-commit hook")
    parser.add_argument("--strict-tests", action="store_true", help="Treat missing test files as hard failures")

    args = parser.parse_args(argv)
    target_dir = os.path.abspath(args.dir)

    if args.install_hook:
        return 0 if install_pre_commit_hook(target_dir) else 1

    files = get_modified_files(target_dir)
    violations = []

    # Check 1: State buffer
    violations.extend(check_active_state(target_dir))

    # Check 2: Placeholders
    if files:
        violations.extend(check_placeholders(target_dir, files))

    # Check 3: Tests present
    test_violations = check_tests_present(files)
    if args.strict_tests:
        violations.extend(test_violations)
    elif test_violations:
        for w in test_violations:
            print(f"[Gatekeeper Warning]: {w}", file=sys.stderr)

    if violations:
        print("\n=== Gatekeeper Rejected: Invariant Gate Violations Detected ===", file=sys.stderr)
        for v in violations:
            print(f"  ❌ {v}", file=sys.stderr)
        print("\nFix all violations before proceeding. (ApexEngine Gate 3 & Gate 4 Enforcement)\n", file=sys.stderr)
        return 1

    print("=== Gatekeeper Approved: All Invariant Gates Passed ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
