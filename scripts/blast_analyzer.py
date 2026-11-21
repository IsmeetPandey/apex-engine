#!/usr/bin/env python3
"""
ApexEngine Blast Radius Analyzer: Cross-Module Dependency & Impact Engine
Analyzes workspace import graphs, call paths, and downstream consumers
to identify the exact regression verification matrix before commits.
Zero external dependencies: Python 3.8+ standard library only.
"""

import os
import sys
import re
import ast
import json
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any

CODE_EXTENSIONS = {".py", ".ts", ".js", ".tsx", ".jsx", ".go", ".rs"}
TEST_PATTERNS = [re.compile(r"(?i)(test_|_test|\.test\.|\.spec\.|tests/|test/|__tests__/)")]


def get_git_modified_files(target_dir: str) -> List[str]:
    """Retrieves all staged, unstaged, and untracked code files."""
    files = set()
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=target_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5
        )
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            # Format: ' M file.py', 'M  file.py', '?? file.py', 'R  old -> new'
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                path_entry = parts[1]
                if " -> " in path_entry:
                    path_entry = path_entry.split(" -> ")[1]
                path_entry = path_entry.strip().strip('"')
                ext = os.path.splitext(path_entry)[1].lower()
                if ext in CODE_EXTENSIONS:
                    files.add(os.path.normpath(path_entry).replace("\\", "/"))
    except (subprocess.SubprocessError, OSError):
        return []
    return sorted(list(files))


def parse_python_imports(file_path: str) -> Set[str]:
    """Extracts imported module names and paths from a Python file."""
    imports = set()
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except Exception:
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def parse_js_ts_imports(file_path: str) -> Set[str]:
    """Extracts import targets from JS/TS files via regex."""
    imports = set()
    pattern = re.compile(r"""(?:import\s+(?:[\w*\s{},]*\s+from\s+)?|require\s*\()\s*['"]([^'"]+)['"]""")
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                for match in pattern.finditer(line):
                    imports.add(match.group(1))
    except (OSError, UnicodeDecodeError):
        return imports
    return imports


def build_dependency_graph(target_dir: str) -> Dict[str, Set[str]]:
    """
    Builds a reverse dependency graph: target_file -> set of consumer_files
    """
    consumers: Dict[str, Set[str]] = {}
    all_code_files = []

    for root, dirs, files in os.walk(target_dir):
        # Skip git, venv, caches
        dirs[:] = [d for d in dirs if d not in {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in CODE_EXTENSIONS:
                rel = os.path.relpath(os.path.join(root, f), target_dir).replace("\\", "/")
                all_code_files.append(rel)
                consumers[rel] = set()

    for rel_path in all_code_files:
        full_path = os.path.join(target_dir, rel_path)
        ext = os.path.splitext(rel_path)[1].lower()

        if ext == ".py":
            imported = parse_python_imports(full_path)
            # Match module names against other workspace files
            for imp in imported:
                imp_path_candidate = imp.replace(".", "/")
                for other in all_code_files:
                    if other == rel_path:
                        continue
                    other_no_ext = os.path.splitext(other)[0]
                    if other_no_ext.endswith(imp_path_candidate) or imp_path_candidate.endswith(other_no_ext):
                        consumers.setdefault(other, set()).add(rel_path)
        elif ext in {".ts", ".tsx", ".js", ".jsx"}:
            imported = parse_js_ts_imports(full_path)
            curr_dir = os.path.dirname(rel_path)
            for imp in imported:
                if imp.startswith("."):
                    resolved = os.path.normpath(os.path.join(curr_dir, imp)).replace("\\", "/")
                    for other in all_code_files:
                        if other == rel_path:
                            continue
                        other_no_ext = os.path.splitext(other)[0]
                        if other_no_ext == resolved or other == resolved:
                            consumers.setdefault(other, set()).add(rel_path)

    return consumers


def calculate_blast_radius(target_dir: str, modified_files: List[str]) -> Dict[str, Any]:
    """Calculates impacted downstream modules and required verification tests."""
    consumers_graph = build_dependency_graph(target_dir)

    direct_consumers = set()
    indirect_consumers = set()
    to_visit = list(modified_files)
    visited = set(modified_files)

    # Breadth-first traversal of consumer graph
    depth = 0
    while to_visit and depth < 3:
        depth += 1
        next_visit = []
        for f in to_visit:
            downstream = consumers_graph.get(f, set())
            for c in downstream:
                if c not in visited:
                    visited.add(c)
                    if depth == 1:
                        direct_consumers.add(c)
                    else:
                        indirect_consumers.add(c)
                    next_visit.append(c)
        to_visit = next_visit

    all_impacted = sorted(list(visited))
    
    # Identify required test suites
    required_tests = set()
    for imp in all_impacted:
        if any(p.search(imp) for p in TEST_PATTERNS):
            required_tests.add(imp)
        else:
            # Look for companion test files (e.g. src/auth.py -> tests/test_auth.py)
            basename = os.path.splitext(os.path.basename(imp))[0]
            for candidate in consumers_graph.keys():
                if any(p.search(candidate) for p in TEST_PATTERNS):
                    if basename in candidate:
                        required_tests.add(candidate)

    return {
        "modified_files": modified_files,
        "direct_consumers": sorted(list(direct_consumers)),
        "indirect_consumers": sorted(list(indirect_consumers)),
        "all_impacted_count": len(all_impacted),
        "required_tests": sorted(list(required_tests)),
    }


def main(argv=None) -> int:
    """CLI entry point for blast radius analyzer."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="ApexEngine Blast Radius Analyzer")
    parser.add_argument("--dir", default=".", help="Target repository directory")
    parser.add_argument("--files", nargs="*", help="Specific modified files to analyze")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args(argv)
    target_dir = os.path.abspath(args.dir)

    files = args.files or get_git_modified_files(target_dir)

    report = calculate_blast_radius(target_dir, files)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("=== ApexEngine Blast Radius Analysis ===")
        print(f"  Modified Files:     {len(report['modified_files'])}")
        for f in report['modified_files']:
            print(f"    - {f}")
        print(f"  Direct Consumers:   {len(report['direct_consumers'])}")
        for c in report['direct_consumers']:
            print(f"    - {c}")
        if report['indirect_consumers']:
            print(f"  Indirect Consumers: {len(report['indirect_consumers'])}")
            for ic in report['indirect_consumers']:
                print(f"    - {ic}")
        print(f"  Required Tests:     {len(report['required_tests'])}")
        for t in report['required_tests']:
            print(f"    - {t}")
        if not report['required_tests'] and report['modified_files']:
            print("  ⚠️ Warning: No automated test files detected for impacted scope (Gate 2 contract risk).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
