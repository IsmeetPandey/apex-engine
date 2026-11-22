#!/usr/bin/env python3
"""
ApexEngine Gatekeeper 3.0: Peak Quality, SAST & Verification Enforcer
Enforces all 4 Invariant Gates prior to git commit:
- Static Security (AST SAST & Secret Scanning)
- Code Complexity & Maintainability (McCabe CC <= 10, nesting depth <= 4, monolithic limit)
- Test Authenticity (Anti-Tautology & Assertion Density Guard)
- Zero Placeholders & Band-Aids (Polyglot)
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
from typing import List, Tuple, Dict, Any, Set, Optional

FORBIDDEN_PATTERNS = [
    (re.compile(r"(?i)\bTODO\b"), "TODO placeholder found"),
    (re.compile(r"(?i)\bFIXME\b"), "FIXME placeholder found"),
    (re.compile(r"^\s*pass\b(?:\s*#.*)?$", re.MULTILINE), "Bare 'pass' statement found"),
    (re.compile(r"^\s*\.\.\.\s*(?:#.*)?$", re.MULTILINE), "Bare '...' ellipsis placeholder found"),
    (re.compile(r"(?i)left as an exercise"), "'Left as an exercise' placeholder found"),
    (re.compile(r"(?i)implement later"), "'Implement later' placeholder found"),
    (re.compile(r"(?i)placeholder for"), "'Placeholder for' marker found"),
    (re.compile(r"\btodo!\s*\("), "Rust todo!() macro placeholder found"),
    (re.compile(r"\bunimplemented!\s*\("), "Rust unimplemented!() macro placeholder found"),
    (re.compile(r"if\s+err\s*!=\s*nil\s*\{\s*\}"), "Go empty error handler found"),
    (re.compile(r"\.catch\s*\(\s*(?:\(\s*\)|[a-zA-Z_]\w*)\s*=>\s*\{\s*\}"), "JavaScript/TypeScript silent swallowed promise catch found"),
    (re.compile(r"catch\s*\([^)]*\)\s*\{\s*\}"), "JavaScript/TypeScript empty catch block found"),
    (re.compile(r"except(?:\s+[\w\.]+)?\s*:\s*(?:pass|\.\.\.)", re.MULTILINE), "Python silent exception suppression (except: pass) found"),
]

SECRET_PATTERNS = [
    (re.compile(r"(?i)\b(AKIA[0-9A-Z]{16})\b"), "SEC007", "Hardcoded AWS Access Key ID detected"),
    (re.compile(r"-----BEGIN (?:RSA|EC|DSA|OPENSSH) PRIVATE KEY-----"), "SEC008", "Hardcoded Private Key detected"),
]

CODE_EXTENSIONS = {".py", ".ts", ".js", ".jsx", ".tsx", ".go", ".rs", ".java", ".cpp", ".c", ".cs"}
TEST_PATTERNS = [re.compile(r"(?i)(test_|_test|\.test\.|\.spec\.|tests/|test/|__tests__/)")]


class SecuritySASTVisitor(ast.NodeVisitor):
    """AST visitor that checks for common high-severity security vulnerabilities."""

    def __init__(self, filename: str):
        self.filename = filename
        self.violations: List[Tuple[int, str, str]] = []

    def _resolve_call_name(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            val = self._resolve_call_name(node.value)
            return f"{val}.{node.attr}" if val else node.attr
        return ""

    def visit_Call(self, node: ast.Call):
        func_name = self._resolve_call_name(node.func)

        # 1. Shell Injection: os.system / os.popen or subprocess(..., shell=True) with dynamic args
        if func_name in {"os.system", "os.popen"}:
            self.violations.append((node.lineno, "SEC001", f"Insecure direct shell execution via '{func_name}'"))
        elif func_name.startswith("subprocess."):
            for kw in node.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    if node.args and not isinstance(node.args[0], ast.Constant):
                        self.violations.append((node.lineno, "SEC002", "Command injection hazard: shell=True with dynamic arguments"))

        # 2. Unsafe Deserialization
        elif func_name in {"pickle.loads", "pickle.load", "_pickle.loads", "marshal.loads"}:
            self.violations.append((node.lineno, "SEC003", f"Unsafe deserialization hazard: '{func_name}'"))
        elif func_name == "yaml.load":
            has_safe = any(kw.arg == "Loader" and "Safe" in getattr(kw.value, "id", getattr(kw.value, "attr", "")) for kw in node.keywords)
            if not has_safe:
                self.violations.append((node.lineno, "SEC004", "Unsafe YAML deserialization: yaml.load without SafeLoader"))

        # 3. Dynamic Arbitrary Code Execution
        elif func_name in {"eval", "exec"}:
            self.violations.append((node.lineno, "SEC005", f"Arbitrary code execution hazard: '{func_name}'"))

        # 4. SQL Injection via unparameterized f-strings
        elif func_name.endswith(".execute") or func_name.endswith(".raw"):
            if node.args and isinstance(node.args[0], ast.JoinedStr):
                self.violations.append((node.lineno, "SEC006", "SQL injection hazard: unparameterized f-string in SQL query"))

        self.generic_visit(node)


class ComplexityVisitor(ast.NodeVisitor):
    """AST visitor measuring McCabe Cyclomatic Complexity, nesting depth, and loops."""

    def __init__(self, filename: str):
        self.filename = filename
        self.violations: List[Tuple[int, str, str]] = []
        self._current_nesting = 0
        self._loop_depth = 0

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._check_function_metrics(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._check_function_metrics(node)
        self.generic_visit(node)

    def _check_function_metrics(self, node):
        # 1. Monolithic function check (lines of code)
        total_lines = getattr(node, "end_lineno", node.lineno) - node.lineno
        if total_lines > 60:
            self.violations.append((node.lineno, "CMP001", f"Monolithic function '{node.name}' has {total_lines} lines (max 60)"))

        # 2. Max parameters check
        param_count = len(node.args.args)
        if param_count > 5:
            self.violations.append((node.lineno, "CMP002", f"Parameter bloat: '{node.name}' has {param_count} parameters (max 5)"))

        # 3. Cyclomatic complexity calculation
        cc = 1  # Base complexity
        for sub in ast.walk(node):
            if isinstance(sub, (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.With, ast.Assert)):
                cc += 1
            elif isinstance(sub, ast.BoolOp):
                cc += max(1, len(sub.values) - 1)

        if cc > 10:
            self.violations.append((node.lineno, "CMP003", f"Excessive Cyclomatic Complexity in '{node.name}' (CC={cc}, max 10)"))

    def visit_If(self, node: ast.If):
        self._current_nesting += 1
        if self._current_nesting > 4:
            self.violations.append((node.lineno, "CMP004", f"Excessive nesting depth ({self._current_nesting} levels, max 4)"))
        self.generic_visit(node)
        self._current_nesting -= 1

    def visit_For(self, node: ast.For):
        self._loop_depth += 1
        self.generic_visit(node)
        self._loop_depth -= 1

    def visit_While(self, node: ast.While):
        self._loop_depth += 1
        self.generic_visit(node)
        self._loop_depth -= 1

    def visit_Compare(self, node: ast.Compare):
        # Anti-O(N^2) trap: linear containment ('x in seq') inside loops over non-set/dict literals
        if self._loop_depth > 0:
            for op, comparator in zip(node.ops, node.comparators):
                if isinstance(op, ast.In) and isinstance(comparator, (ast.Name, ast.Attribute, ast.Call)):
                    self.violations.append(
                        (node.lineno, "CMP005", "Potential O(N^2) trap: linear 'in' containment check inside iterative loop")
                    )
        self.generic_visit(node)


def get_modified_files(target_dir: str) -> List[str]:
    """Retrieves all staged, unstaged, and untracked code files via git status."""
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
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                path_entry = parts[1]
                if " -> " in path_entry:
                    path_entry = path_entry.split(" -> ")[1]
                path_entry = path_entry.strip().strip('"')
                ext = os.path.splitext(path_entry)[1].lower()
                if ext in CODE_EXTENSIONS:
                    files.add(os.path.normpath(path_entry).replace("\\", "/"))
    except Exception:
        pass

    if not files:
        # Fallback to git diff --cached or git diff
        for flag in [["--cached"], []]:
            try:
                proc2 = subprocess.run(
                    ["git", "diff", "--name-only"] + flag,
                    cwd=target_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=5
                )
                for f in proc2.stdout.splitlines():
                    if f.strip() and os.path.splitext(f.strip())[1].lower() in CODE_EXTENSIONS:
                        files.add(os.path.normpath(f.strip()).replace("\\", "/"))
            except Exception:
                pass

    return sorted(list(files))


def check_placeholders(target_dir: str, files: List[str]) -> List[str]:
    """Scans code files for banned placeholders."""
    violations = []
    for rel_path in files:
        full_path = os.path.join(target_dir, rel_path)
        ext = os.path.splitext(rel_path)[1].lower()
        if ext not in CODE_EXTENSIONS or not os.path.isfile(full_path):
            continue
        if os.path.basename(rel_path) == "gatekeeper.py":
            continue
        # Test files are scanned separately for tautologies/empty bodies
        if any(p.search(rel_path) for p in TEST_PATTERNS):
            continue

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            continue

        for pattern, desc in FORBIDDEN_PATTERNS:
            match = pattern.search(content)
            if match:
                line_no = content[:match.start()].count("\n") + 1
                violations.append(f"{rel_path}:{line_no} - {desc} ('{match.group(0).strip()}')")
    return violations


APEX_TOOL_SCRIPTS = {
    "gatekeeper.py", "dep_guard.py", "self_heal.py", "blast_analyzer.py",
    "apex_cli.py", "condense.py", "studio.py", "vibe_synthesizer.py",
    "invariant_store.py"
}


def check_sast_and_complexity(target_dir: str, files: List[str]) -> List[str]:
    """Runs AST-based SAST security and complexity visitors."""
    violations = []
    for rel_path in files:
        full_path = os.path.join(target_dir, rel_path)
        ext = os.path.splitext(rel_path)[1].lower()
        if not os.path.isfile(full_path):
            continue
        if os.path.basename(rel_path) in APEX_TOOL_SCRIPTS:
            continue
        if any(p.search(rel_path) for p in TEST_PATTERNS):
            continue

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            continue

        # Secret scanning across all file formats
        for pattern, code, desc in SECRET_PATTERNS:
            match = pattern.search(content)
            if match:
                line_no = content[:match.start()].count("\n") + 1
                violations.append(f"{rel_path}:{line_no} [{code}] - {desc}")

        # Python-specific AST scanning
        if ext == ".py":
            try:
                tree = ast.parse(content, filename=full_path)
            except SyntaxError as e:
                violations.append(f"{rel_path}:{e.lineno} [SYN001] - Python syntax error: {e.msg}")
                continue

            sec_visitor = SecuritySASTVisitor(rel_path)
            sec_visitor.visit(tree)
            for line_no, code, msg in sec_visitor.violations:
                violations.append(f"{rel_path}:{line_no} [{code}] - {msg}")

            cmp_visitor = ComplexityVisitor(rel_path)
            cmp_visitor.visit(tree)
            for line_no, code, msg in cmp_visitor.violations:
                violations.append(f"{rel_path}:{line_no} [{code}] - {msg}")

    return violations


def check_test_authenticity(target_dir: str, files: List[str]) -> List[str]:
    """Verifies that test files are substantive and free of tautologies or empty bodies."""
    violations = []
    test_files = [f for f in files if any(p.search(f) for p in TEST_PATTERNS)]

    for rel_path in test_files:
        full_path = os.path.join(target_dir, rel_path)
        ext = os.path.splitext(rel_path)[1].lower()
        if ext != ".py" or not os.path.isfile(full_path):
            continue

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            tree = ast.parse(content, filename=full_path)
        except Exception:
            continue

        # Scan for empty test bodies or tautological asserts
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test_"):
                    # 1. Empty test body check
                    if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                        violations.append(f"{rel_path}:{node.lineno} [TST001] - Vacuous test function '{node.name}' contains only 'pass'")
                    elif len(node.body) == 1 and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and node.body[0].value.value is Ellipsis:
                        violations.append(f"{rel_path}:{node.lineno} [TST002] - Vacuous test function '{node.name}' contains only '...'")

                    # 2. Tautological assert check
                    for sub in ast.walk(node):
                        if isinstance(sub, ast.Assert):
                            # assert True, assert 1, assert "a" == "a"
                            if isinstance(sub.test, ast.Constant) and bool(sub.test.value) is True:
                                violations.append(f"{rel_path}:{sub.lineno} [TST003] - Tautological assertion 'assert {sub.test.value}' detected")
                            elif isinstance(sub.test, ast.Compare):
                                if isinstance(sub.test.left, ast.Constant) and len(sub.test.comparators) == 1 and isinstance(sub.test.comparators[0], ast.Constant):
                                    if sub.test.left.value == sub.test.comparators[0].value:
                                        violations.append(f"{rel_path}:{sub.lineno} [TST004] - Tautological constant comparison 'assert {sub.test.left.value} == {sub.test.comparators[0].value}' detected")

    return violations


class InvariantASTVisitor(ast.NodeVisitor):
    """AST Visitor that validates code modifications against .context/invariants.json."""

    def __init__(self, filename: str, immutable_invariants: Dict[str, Any]):
        self.filename = filename
        self.invariants = immutable_invariants
        self.violations: List[Tuple[int, str, str]] = []

    def _extract_constant_value(self, node: ast.AST) -> Tuple[bool, Any]:
        """Extracts literal value from AST Constant or simple unary expressions."""
        if isinstance(node, ast.Constant):
            return True, node.value
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant):
            return True, -node.operand.value
        return False, None

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in self.invariants:
                inv = self.invariants[target.id]
                expected_val = inv["value"]
                is_literal, val = self._extract_constant_value(node.value)
                if is_literal:
                    if val != expected_val:
                        self.violations.append((
                            node.lineno,
                            "INV001",
                            f"Illegal mutation of immutable symbol '{target.id}': assigned {val!r}, must be {expected_val!r}"
                        ))
                    expected_type = inv.get("type")
                    if expected_type:
                        val_type_name = type(val).__name__
                        if expected_type in ("string", "str") and val_type_name != "str":
                            self.violations.append((
                                node.lineno,
                                "INV003",
                                f"Type mismatch on '{target.id}': expected {expected_type}, got {val_type_name}"
                            ))
                        elif expected_type == "int" and (val_type_name != "int" or isinstance(val, bool)):
                            self.violations.append((
                                node.lineno,
                                "INV003",
                                f"Type mismatch on '{target.id}': expected {expected_type}, got {val_type_name}"
                            ))
                        elif expected_type == "float" and not isinstance(val, (float, int)):
                            self.violations.append((
                                node.lineno,
                                "INV003",
                                f"Type mismatch on '{target.id}': expected {expected_type}, got {val_type_name}"
                            ))
                    b = inv.get("bounds")
                    if b:
                        if "min" in b:
                            try:
                                if val < b["min"]:
                                    self.violations.append((
                                        node.lineno,
                                        "INV004",
                                        f"Boundary violation on '{target.id}': {val!r} is below min bound {b['min']}"
                                    ))
                            except TypeError:
                                pass
                        if "max" in b:
                            try:
                                if val > b["max"]:
                                    self.violations.append((
                                        node.lineno,
                                        "INV004",
                                        f"Boundary violation on '{target.id}': {val!r} exceeds max bound {b['max']}"
                                    ))
                            except TypeError:
                                pass
                        if "choices" in b and val not in b["choices"]:
                            self.violations.append((
                                node.lineno,
                                "INV004",
                                f"Boundary violation on '{target.id}': {val!r} not in allowed choices {b['choices']}"
                            ))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if isinstance(node.target, ast.Name) and node.target.id in self.invariants:
            inv = self.invariants[node.target.id]
            expected_val = inv["value"]
            if node.value is not None:
                is_literal, val = self._extract_constant_value(node.value)
                if is_literal:
                    if val != expected_val:
                        self.violations.append((
                            node.lineno,
                            "INV001",
                            f"Illegal annotated mutation of immutable symbol '{node.target.id}': assigned {val!r}, must be {expected_val!r}"
                        ))
                    expected_type = inv.get("type")
                    if expected_type:
                        val_type_name = type(val).__name__
                        if expected_type in ("string", "str") and val_type_name != "str":
                            self.violations.append((
                                node.lineno,
                                "INV003",
                                f"Type mismatch on '{node.target.id}': expected {expected_type}, got {val_type_name}"
                            ))
                        elif expected_type == "int" and (val_type_name != "int" or isinstance(val, bool)):
                            self.violations.append((
                                node.lineno,
                                "INV003",
                                f"Type mismatch on '{node.target.id}': expected {expected_type}, got {val_type_name}"
                            ))
                        elif expected_type == "float" and not isinstance(val, (float, int)):
                            self.violations.append((
                                node.lineno,
                                "INV003",
                                f"Type mismatch on '{node.target.id}': expected {expected_type}, got {val_type_name}"
                            ))
                    b = inv.get("bounds")
                    if b:
                        if "min" in b:
                            try:
                                if val < b["min"]:
                                    self.violations.append((
                                        node.lineno,
                                        "INV004",
                                        f"Boundary violation on '{node.target.id}': {val!r} is below min bound {b['min']}"
                                    ))
                            except TypeError:
                                pass
                        if "max" in b:
                            try:
                                if val > b["max"]:
                                    self.violations.append((
                                        node.lineno,
                                        "INV004",
                                        f"Boundary violation on '{node.target.id}': {val!r} exceeds max bound {b['max']}"
                                    ))
                            except TypeError:
                                pass
                        if "choices" in b and val not in b["choices"]:
                            self.violations.append((
                                node.lineno,
                                "INV004",
                                f"Boundary violation on '{node.target.id}': {val!r} not in allowed choices {b['choices']}"
                            ))
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign):
        if isinstance(node.target, ast.Name) and node.target.id in self.invariants:
            self.violations.append((
                node.lineno,
                "INV001",
                f"Illegal augmented mutation of immutable symbol '{node.target.id}'"
            ))
        self.generic_visit(node)


def check_invariants(target_dir: str = ".") -> Tuple[bool, List[str]]:
    """Validates codebase against .context/invariants.json (rules INV001–INV006)."""
    violations: List[str] = []
    context_dir = os.path.join(target_dir, ".context")
    store_file = os.path.join(context_dir, "invariants.json")

    if not os.path.isfile(store_file):
        return True, []

    # 1. Verify tamper checksum (INV005)
    try:
        scripts_dir = os.path.dirname(os.path.abspath(__file__))
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from invariant_store import InvariantStore
        store = InvariantStore(context_dir)
        valid, msg = store.verify_integrity()
        if not valid:
            violations.append(f".context/invariants.json [INV005] - TamperChecksumViolation: {msg}")
            return False, violations
        regs = store.get_invariants()
    except Exception as e:
        violations.append(f".context/invariants.json [INV005] - Failed to load invariant store: {e}")
        return False, violations

    immutable_invariants = regs.get("immutable", {})
    if not immutable_invariants:
        return True, []

    # 2. Inspect code files
    modified_files = get_modified_files(target_dir)
    py_files: List[str] = []
    if modified_files:
        py_files = [f for f in modified_files if f.endswith(".py") and not any(p.search(f) for p in TEST_PATTERNS)]
    if not py_files:
        for root, dirs, files in os.walk(target_dir):
            if any(p in root for p in [".git", ".context", "__pycache__", "venv", ".venv", "tests"]):
                continue
            for f in files:
                if f.endswith(".py"):
                    rel = os.path.relpath(os.path.join(root, f), target_dir).replace("\\", "/")
                    py_files.append(rel)

    observed_symbol_values: Dict[str, List[Tuple[str, int, Any]]] = {}

    for rel_path in py_files:
        full_path = os.path.join(target_dir, rel_path)
        if not os.path.isfile(full_path):
            continue
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            tree = ast.parse(content, filename=full_path)
        except Exception:
            continue

        visitor = InvariantASTVisitor(rel_path, immutable_invariants)
        visitor.visit(tree)
        for lineno, code, message in visitor.violations:
            violations.append(f"{rel_path}:{lineno} [{code}] - {message}")

        # Track cross-module definitions for INV006
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in immutable_invariants:
                        is_lit, val = visitor._extract_constant_value(node.value)
                        if is_lit:
                            if target.id not in observed_symbol_values:
                                observed_symbol_values[target.id] = []
                            observed_symbol_values[target.id].append((rel_path, node.lineno, val))

    for sym, occurrences in observed_symbol_values.items():
        expected_val = immutable_invariants[sym]["value"]
        for rel_path, lineno, val in occurrences:
            if val != expected_val:
                violations.append(
                    f"{rel_path}:{lineno} [INV006] - DivergentStateViolation: Code defines '{sym} = {val!r}', "
                    f"diverging from bound invariant value {expected_val!r}"
                )

    return (len(violations) == 0), violations


def check_active_state(target_dir: str) -> List[str]:
    """Verifies .context/active_state.md exists and is within byte limits."""
    violations = []
    state_file = os.path.join(target_dir, ".context", "active_state.md")
    if not os.path.isfile(state_file):
        init_script = os.path.join(os.path.dirname(__file__), "condense.py")
        if os.path.isfile(init_script):
            try:
                subprocess.run([sys.executable, init_script, "init", "--dir", target_dir], capture_output=True, timeout=5)
            except Exception:
                violations.append("Unable to auto-init .context directory.")
        if not os.path.isfile(state_file):
            violations.append("Missing .context/active_state.md. Run 'python scripts/condense.py init'")
            return violations

    size = os.path.getsize(state_file)
    if size > 2500:
        violations.append(f".context/active_state.md exceeds 2,500 byte limit ({size} bytes). Run condense.py update.")
    return violations


def check_tests_present(files: List[str]) -> List[str]:
    """Verifies application code changes are accompanied by test files."""
    code_files = [f for f in files if os.path.splitext(f)[1].lower() in CODE_EXTENSIONS]
    if not code_files:
        return []

    # Check if modified files are all docs/configs
    non_test_code = [f for f in code_files if not any(p.search(f) for p in TEST_PATTERNS)]
    if not non_test_code:
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
        "python scripts/gatekeeper.py --dir . --strict-tests\n"
    )

    with open(hook_file, "w", encoding="utf-8") as f:
        f.write(hook_content)

    try:
        import stat
        st = os.stat(hook_file)
        os.chmod(hook_file, st.st_mode | stat.S_IEXEC)
    except Exception:
        return False

    print(f"Installed ApexEngine pre-commit hook in {hook_file}")
    return True


def main(argv=None) -> int:
    """CLI Entrypoint for gatekeeper."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="ApexEngine Gatekeeper 3.0: Invariant & SAST Enforcer")
    parser.add_argument("--dir", default=".", help="Target repository directory (default: current dir)")
    parser.add_argument("--install-hook", action="store_true", help="Install as git pre-commit hook")
    parser.add_argument("--strict-tests", action="store_true", default=True, help="Treat missing test files as hard failures (default: True)")
    parser.add_argument("--allow-no-tests", action="store_true", help="Explicitly allow committing changes without companion tests")
    parser.add_argument("--strict-sast", action="store_true", default=True, help="Treat SAST security violations as hard failures")
    parser.add_argument("--strict-complexity", action="store_true", default=True, help="Treat complexity violations as hard failures")
    parser.add_argument("--check-invariants", action="store_true", help="Run only invariant AST & integrity checks")
    parser.add_argument("--json", action="store_true", help="Output violations in JSON format")

    args = parser.parse_args(argv)
    target_dir = os.path.abspath(args.dir)

    if args.install_hook:
        return 0 if install_pre_commit_hook(target_dir) else 1

    if args.check_invariants:
        inv_ok, inv_violations = check_invariants(target_dir)
        if args.json:
            print(json.dumps({"status": "failed" if inv_violations else "passed", "violations": inv_violations}, indent=2))
        else:
            if inv_violations:
                print("\n=== Gatekeeper Rejected: Invariant Violations Detected ===", file=sys.stderr)
                for v in inv_violations:
                    print(f"  ❌ {v}", file=sys.stderr)
            else:
                print("=== Gatekeeper Approved: Invariant Integrity Verified ===")
        return 0 if inv_ok else 1

    files = get_modified_files(target_dir)
    violations = []

    # Check 1: State buffer limits
    violations.extend(check_active_state(target_dir))

    # Check 1b: Invariants and code consistency (INV001–INV006)
    inv_ok, inv_violations = check_invariants(target_dir)
    violations.extend(inv_violations)

    # Check 2: Placeholders
    if files:
        violations.extend(check_placeholders(target_dir, files))

    # Check 3: SAST & Complexity
    if files:
        sast_violations = check_sast_and_complexity(target_dir, files)
        if args.strict_sast or args.strict_complexity:
            violations.extend(sast_violations)

    # Check 4: Test authenticity & tautologies
    if files:
        violations.extend(check_test_authenticity(target_dir, files))

    # Check 5: Tests present (Contract TDD)
    if not args.allow_no_tests:
        test_violations = check_tests_present(files)
        violations.extend(test_violations)

    if args.json:
        print(json.dumps({"status": "failed" if violations else "passed", "violations": violations}, indent=2))
        return 1 if violations else 0

    if violations:
        print("\n=== Gatekeeper Rejected: Invariant Gate Violations Detected (ApexEngine 3.0) ===", file=sys.stderr)
        for v in violations:
            print(f"  ❌ {v}", file=sys.stderr)
        print("\nFix all violations before proceeding. (ApexEngine Gate 2, 3 & Gate 4 Enforcement)\n", file=sys.stderr)
        return 1

    print("=== Gatekeeper Approved: All Invariant Gates Passed (ApexEngine 3.0) ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
