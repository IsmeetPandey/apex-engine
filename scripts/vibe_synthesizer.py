#!/usr/bin/env python3
"""
ApexEngine Vibe Synthesizer (vibe_synthesizer.py)
Decomposes casual, high-level vibe coding prompts into rigid, contract-driven specifications
and test verification plans before code generation begins.
Zero external dependencies: Python 3.8+ standard library only.
"""

import os
import sys
import re
import json
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Any

try:
    import ste_engine
except ImportError:
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import ste_engine
    except ImportError:
        ste_engine = None


def extract_keywords(prompt: str) -> List[str]:
    """Tokenizes and cleans keywords from prompt."""
    tokens = re.findall(r"[A-Za-z0-9_\-]+", prompt.lower())
    stop_words = {"a", "an", "the", "in", "with", "and", "or", "for", "of", "to", "i", "want", "build", "create", "make"}
    return [t for t in tokens if t not in stop_words]


def synthesize_spec(prompt: str) -> Dict[str, Any]:
    """Transforms a natural language vibe prompt into a contract specification."""
    keywords = extract_keywords(prompt)
    clean_title = " ".join(prompt.split()[:6]).title()
    if not clean_title:
        clean_title = "Application Feature"

    # Identify domain clues
    has_auth = any(k in prompt.lower() for k in ["auth", "jwt", "login", "user", "password", "session"])
    has_storage = any(k in prompt.lower() for k in ["storage", "db", "database", "save", "redis", "persist", "sqlite"])
    has_api = any(k in prompt.lower() for k in ["api", "endpoint", "rest", "service", "route"])
    has_ui = any(k in prompt.lower() for k in ["ui", "editor", "view", "dashboard", "component", "frontend", "react", "nextjs", "vue"])

    # Detect language/stack
    prompt_lower = prompt.lower()
    is_ts = any(k in prompt_lower for k in ["typescript", "ts", "react", "next.js", "nextjs", "node", "javascript", "js", "frontend", "component"])
    is_go = any(k in prompt_lower for k in ["go", "golang"])
    is_rust = any(k in prompt_lower for k in ["rust", "cargo"])

    raw_objectives = [
        f"Implement core logic for: {prompt.strip()}",
        "Enforce strict input validation and boundary condition handling.",
        "Provide automated contract verification test suite with 100% pass guarantee."
    ]
    if ste_engine is not None:
        objectives = [ste_engine.format_ste_step(obj) for obj in raw_objectives]
    else:
        objectives = raw_objectives

    files = []
    slug = re.sub(r"[^a-z0-9]+", "_", clean_title.lower()).strip("_")
    if not slug:
        slug = "feature_core"

    if is_ts:
        ext = "tsx" if has_ui else "ts"
        files.append({
            "path": f"src/{slug}.{ext}",
            "responsibility": "Core TypeScript implementation and typed contract interfaces."
        })
        files.append({
            "path": f"tests/{slug}.test.ts",
            "responsibility": "Automated Vitest/Jest unit & contract test suite."
        })
        test_runner = "npm test"
    elif is_go:
        files.append({
            "path": f"{slug}.go",
            "responsibility": "Core Go package implementation and struct methods."
        })
        files.append({
            "path": f"{slug}_test.go",
            "responsibility": "Standard Go test suite verifying package invariants."
        })
        test_runner = "go test -v ./..."
    elif is_rust:
        files.append({
            "path": f"src/{slug}.rs",
            "responsibility": "Rust module implementation with strong ownership guarantees."
        })
        files.append({
            "path": f"tests/test_{slug}.rs",
            "responsibility": "Integration test suite verifying crate public interfaces."
        })
        test_runner = "cargo test"
    else:
        files.append({
            "path": f"src/{slug}_service.py",
            "responsibility": "Core domain logic and interface contract implementation."
        })
        files.append({
            "path": f"tests/test_{slug}.py",
            "responsibility": "Unit and contract test suite asserting all requirements."
        })
        test_runner = "python -m unittest discover -s tests"

    if has_storage:
        ext = "ts" if is_ts else ("go" if is_go else ("rs" if is_rust else "py"))
        files.append({
            "path": f"src/{slug}_storage.{ext}",
            "responsibility": "Data persistence layer and serialization logic."
        })
    if has_ui and not is_ts:
        files.append({
            "path": f"src/{slug}_ui.py",
            "responsibility": "Presentation layer, display rendering, or state dispatch."
        })

    test_plan = [
        f"Step 1 (Red): Author tests verifying primary functional requirements.",
        f"Step 2: Run test suite via '{test_runner}' to verify contract failure prior to implementation.",
        "Step 3 (Green): Implement minimal defensive logic to turn tests green.",
        "Step 4: Run Gatekeeper self-check to ensure zero incomplete placeholders remain."
    ]

    invariants = [
        "Zero external dependencies outside standard library unless explicitly approved.",
        "All functions must be strictly bounded (<60 lines) with complete type hints.",
        "Error paths must raise explicit, structured exceptions rather than silent failure."
    ]

    return {
        "title": clean_title,
        "prompt": prompt,
        "objectives": objectives,
        "files": files,
        "test_plan": test_plan,
        "invariants": invariants
    }


def format_markdown_spec(spec: Dict[str, Any]) -> str:
    """Formats the synthesized specification as a clean Markdown document."""
    lines = [
        f"# Technical Specification: {spec['title']}",
        f"\n**Original Vibe Prompt:** *\"{spec['prompt']}\"*\n",
        "## 1. Functional Objectives",
    ]
    for i, obj in enumerate(spec["objectives"], 1):
        lines.append(f"{i}. {obj}")

    lines.append("\n## 2. Component Architecture & File Ownership")
    lines.append("| File Path | Responsibility |")
    lines.append("| :--- | :--- |")
    for f in spec["files"]:
        lines.append(f"| `{f['path']}` | {f['responsibility']} |")

    lines.append("\n## 3. Contract-Driven Test Plan")
    for step in spec["test_plan"]:
        lines.append(f"- [ ] {step}")

    lines.append("\n## 4. Locked Invariants")
    for inv in spec["invariants"]:
        lines.append(f"- **Invariant**: {inv}")

    lines.append("\n---\n*Generated by ApexEngine Vibe Synthesizer (v2.0)*\n")
    return "\n".join(lines)


def main(argv=None) -> int:
    """CLI Entrypoint for vibe_synthesizer.py."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="ApexEngine Vibe Synthesizer")
    parser.add_argument("prompt", help="Natural language vibe prompt")
    parser.add_argument("--dir", default=".", help="Target workspace directory (default: current dir)")
    parser.add_argument("--out", help="Output file path for generated Markdown specification")
    parser.add_argument("--json", action="store_true", help="Output specification as JSON to stdout")
    parser.add_argument("--apply-context", action="store_true", help="Automatically update .context/active_state.md")

    args = parser.parse_args(argv)
    target_dir = os.path.abspath(args.dir)

    spec = synthesize_spec(args.prompt)

    if args.json:
        sys.stdout.write(json.dumps(spec, indent=2) + "\n")

    md_content = format_markdown_spec(spec)

    if args.out:
        out_path = os.path.abspath(args.out)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"Generated specification: {out_path}")

    if not args.json and not args.out:
        sys.stdout.write(md_content + "\n")

    if args.apply_context:
        condense_script = os.path.join(os.path.dirname(__file__), "condense.py")
        if os.path.isfile(condense_script):
            invariants_str = "; ".join(spec["invariants"])
            cmd = [
                sys.executable,
                condense_script,
                "update",
                "--dir", target_dir,
                "--goal", spec["title"],
                "--gate", "INSPECT",
                "--gate-status", "PASSED",
                "--invariants", invariants_str,
                "--next", spec["test_plan"][0],
                "--task", "Task 1: Contract authoring"
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"Updated .context/active_state.md with synthesized specification.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
