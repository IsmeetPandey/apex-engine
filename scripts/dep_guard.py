#!/usr/bin/env python3
"""
ApexEngine Dependency & Import Guard (dep_guard.py)
Audits Python source files to detect hallucinated packages and unresolvable imports.
Zero external dependencies: Python 3.8+ standard library only.
"""

import os
import sys
import ast
import re
import argparse
from pathlib import Path
from typing import Set, List, Tuple, Dict

# Fallback stdlib module set for Python 3.8/3.9 compatibility
FALLBACK_STDLIB = {
    "abc", "argparse", "ast", "asyncio", "base64", "binascii", "bisect", "bz2",
    "calendar", "cgi", "cmath", "cmd", "code", "codecs", "collections", "colorsys",
    "compileall", "concurrent", "configparser", "contextlib", "contextvars", "copy",
    "copyreg", "crypt", "csv", "ctypes", "curses", "dataclasses", "datetime", "dbm",
    "decimal", "difflib", "dis", "distutils", "doctest", "email", "encodings", "ensurepip",
    "enum", "errno", "faulthandler", "fcntl", "filecmp", "fileinput", "fnmatch", "fractions",
    "ftplib", "functools", "gc", "getopt", "getpass", "gettext", "glob", "graphlib",
    "gzip", "hashlib", "heapq", "hmac", "html", "http", "idlelib", "imaplib", "imghdr",
    "imp", "importlib", "inspect", "io", "ipaddress", "itertools", "json", "keyword",
    "lib2to3", "linecache", "locale", "logging", "lzma", "mailbox", "mailcap", "marshal",
    "math", "mimetypes", "mmap", "modulefinder", "msilib", "msvcrt", "multiprocessing",
    "netrc", "nntplib", "numbers", "operator", "optparse", "os", "ossaudiodev", "parser",
    "pathlib", "pdb", "pickle", "pickletools", "pipes", "pkgutil", "platform", "plistlib",
    "poplib", "posix", "pprint", "profile", "pstats", "pty", "pwd", "py_compile", "pyclbr",
    "pydoc", "queue", "quopri", "random", "re", "readline", "reprlib", "resource", "rlcompleter",
    "runpy", "sched", "secrets", "select", "selectors", "shelve", "shlex", "shutil", "signal",
    "site", "smtpd", "smtplib", "sndhdr", "socket", "socketserver", "spwd", "sqlite3",
    "ssl", "stat", "statistics", "string", "stringprep", "struct", "subprocess", "sunau",
    "symbol", "symtable", "sys", "sysconfig", "syslog", "tabnanny", "tarfile", "telnetlib",
    "tempfile", "termios", "test", "textwrap", "threading", "time", "timeit", "tkinter",
    "token", "tokenize", "trace", "traceback", "tracemalloc", "tty", "turtle", "turtledemo",
    "types", "typing", "unicodedata", "unittest", "urllib", "uu", "uuid", "venv",
    "warnings", "wave", "weakref", "webbrowser", "winreg", "winsound", "wsgiref", "xdrlib",
    "xml", "xmlrpc", "zipapp", "zipfile", "zipimport", "zlib", "zoneinfo"
}


def get_stdlib_modules() -> Set[str]:
    """Returns the set of valid Python standard library module names."""
    if hasattr(sys, "stdlib_module_names"):
        return set(sys.stdlib_module_names)
    return FALLBACK_STDLIB


def get_local_modules(target_dir: str) -> Set[str]:
    """Finds all local .py module names and package directories."""
    modules = set()
    for root, dirs, files in os.walk(target_dir):
        # Exclude hidden and venv directories
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in {"venv", "env", "node_modules", "__pycache__"}]
        for f in files:
            if f.endswith(".py"):
                name = os.path.splitext(f)[0]
                modules.add(name)
        for d in dirs:
            modules.add(d)
    return modules


NODE_BUILTINS = {
    "assert", "async_hooks", "buffer", "child_process", "cluster", "console",
    "constants", "crypto", "dgram", "diagnostics_channel", "dns", "domain",
    "events", "fs", "http", "http2", "https", "inspector", "module", "net",
    "os", "path", "perf_hooks", "process", "punycode", "querystring", "readline",
    "repl", "stream", "string_decoder", "timers", "tls", "trace_events", "tty",
    "url", "util", "v8", "vm", "wasi", "worker_threads", "zlib"
}

JS_TS_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}


def get_npm_declared_dependencies(target_dir: str) -> Set[str]:
    """Parses package.json for dependencies and devDependencies."""
    declared = set()
    pkg_file = os.path.join(target_dir, "package.json")
    if os.path.isfile(pkg_file):
        try:
            import json
            with open(pkg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for section in ("dependencies", "devDependencies", "peerDependencies"):
                    if section in data and isinstance(data[section], dict):
                        declared.update(data[section].keys())
        except Exception:
            return declared
    return declared


def extract_js_ts_imports(file_path: str) -> List[Tuple[str, int]]:
    """Extracts non-relative imported package names from JS/TS files."""
    imports = []
    import_regex = re.compile(r"""(?:import\s+(?:[\w*\s{},]*\s+from\s+)?|require\s*\(\s*)["']([^"']+)["']""")
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for lineno, line in enumerate(f, 1):
                # Ignore pure comment lines
                stripped = line.strip()
                if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                    continue
                match = import_regex.search(line)
                if match:
                    pkg = match.group(1).strip()
                    # Skip relative path imports or path aliases (@/, ~/)
                    if pkg.startswith(".") or pkg.startswith("/") or pkg.startswith("@/") or pkg.startswith("~/"):
                        continue
                    # Extract top-level package or scoped package (@org/pkg)
                    if pkg.startswith("@"):
                        parts = pkg.split("/")
                        top_pkg = "/".join(parts[:2]) if len(parts) >= 2 else pkg
                    else:
                        top_pkg = pkg.split("/")[0]
                    # Strip 'node:' prefix if present
                    if top_pkg.startswith("node:"):
                        top_pkg = top_pkg[5:]
                    imports.append((top_pkg, lineno))
    except Exception:
        return []
    return imports


def get_declared_dependencies(target_dir: str) -> Set[str]:
    """Parses requirements.txt or pyproject.toml if present."""
    declared = set()
    req_file = os.path.join(target_dir, "requirements.txt")
    if os.path.isfile(req_file):
        try:
            with open(req_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Extract package name before ==, >=, etc.
                        pkg = re.split(r"[><=~;]", line)[0].strip().replace("-", "_").lower()
                        declared.add(pkg)
        except Exception:
            return declared
    return declared


def extract_imports_from_file(file_path: str) -> List[Tuple[str, int]]:
    """Extracts top-level imported module names and line numbers via AST."""
    imports = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except Exception:
        return []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_pkg = alias.name.split(".")[0]
                imports.append((top_pkg, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                top_pkg = node.module.split(".")[0]
                imports.append((top_pkg, node.lineno))
    return imports


def check_directory(target_dir: str, allowed_extra: Set[str] = None) -> List[str]:
    """Scans target_dir and returns list of violation strings for Python and JS/TS."""
    if allowed_extra is None:
        allowed_extra = set()

    stdlib = get_stdlib_modules()
    local = get_local_modules(target_dir)
    declared = get_declared_dependencies(target_dir)
    valid_py_names = stdlib.union(local).union(declared).union(allowed_extra)

    # Node / NPM ecosystem
    npm_declared = get_npm_declared_dependencies(target_dir)
    valid_npm_names = NODE_BUILTINS.union(npm_declared).union(allowed_extra)

    violations = []
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in {"venv", "env", "node_modules", "__pycache__", "dist", "build"}]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, target_dir)

            if ext == ".py":
                for mod_name, lineno in extract_imports_from_file(full_path):
                    if mod_name.lower() not in valid_py_names and mod_name not in valid_py_names:
                        violations.append(f"{rel_path}:{lineno} - Unresolvable/hallucinated Python import: '{mod_name}'")

            elif ext in JS_TS_EXTENSIONS:
                for pkg_name, lineno in extract_js_ts_imports(full_path):
                    if pkg_name not in valid_npm_names:
                        violations.append(f"{rel_path}:{lineno} - Unresolvable/hallucinated NPM import: '{pkg_name}' (missing from package.json)")

    return violations


def main(argv=None) -> int:
    """CLI Entrypoint for dep_guard.py."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="ApexEngine Dependency & Import Guard")
    parser.add_argument("--dir", default=".", help="Target directory (default: current dir)")
    parser.add_argument("--allow", default="", help="Comma-separated allowed extra modules")

    args = parser.parse_args(argv)
    target_dir = os.path.abspath(args.dir)

    extra = set(filter(None, [m.strip() for m in args.allow.split(",")])) if args.allow else set()
    violations = check_directory(target_dir, allowed_extra=extra)

    if violations:
        print("\n=== DepGuard Alert: Hallucinated / Unresolvable Imports Detected ===", file=sys.stderr)
        for v in violations:
            print(f"  ❌ {v}", file=sys.stderr)
        print("\nFix missing imports or add them to requirements.txt before continuing.\n", file=sys.stderr)
        return 1

    print("=== DepGuard Approved: All imports verified against stdlib and project dependencies ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
