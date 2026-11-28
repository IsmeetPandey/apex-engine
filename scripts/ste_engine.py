#!/usr/bin/env python3
"""
ApexEngine ASD-STE100 Precision Engine (ste_engine.py)
Implements 80% Simplified Technical English (ASD-STE100) validation:
- Eliminates conversational AI padding/slop
- Detects passive voice constructs and flags them for active imperative conversion
- Enforces sentence length limits (<= 25 words) for procedural instructions
- Preserves technical software engineering vocabulary without vocabulary choking
- Formats noisy procedural steps into crisp, imperative actions
Zero external dependencies: Python 3.8+ standard library only.
"""

import os
import sys
import re
import json
import argparse
from typing import List, Dict, Any, Optional, Tuple


class STEViolation:
    """Represents a single ASD-STE100 style violation."""

    def __init__(self, rule_code: str, message: str, line: int = 1, text: str = ""):
        self.rule_code = rule_code
        self.message = message
        self.line = line
        self.text = text

    def __repr__(self) -> str:
        return f"STEViolation(code={self.rule_code}, line={self.line}, msg='{self.message}')"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_code": self.rule_code,
            "message": self.message,
            "line": self.line,
            "text": self.text,
        }


SLOP_PATTERNS = [
    (re.compile(r"(?i)\bcertainly\b!?", re.MULTILINE), "Conversational filler 'Certainly!'"),
    (re.compile(r"(?i)\bi('d| would be| am) (very )?happy to (assist|help)\b"), "AI assistant fluff 'happy to help/assist'"),
    (re.compile(r"(?i)\bas an ai\b"), "Self-referential AI persona statement"),
    (re.compile(r"(?i)\bas a language model\b"), "Self-referential language model statement"),
    (re.compile(r"(?i)\bsure thing\b"), "Conversational filler 'Sure thing'"),
    (re.compile(r"(?i)\bgreat question\b"), "Conversational filler 'Great question'"),
    (re.compile(r"(?i)\bfeel free to\b"), "Conversational padding 'feel free to'"),
    (re.compile(r"(?i)\bhope this helps\b"), "Conversational closing 'hope this helps'"),
    (re.compile(r"(?i)\blet's dive in\b"), "Conversational filler 'let's dive in'"),
    (re.compile(r"(?i)\bwithout further ado\b"), "Conversational filler 'without further ado'"),
]

PASSIVE_PATTERNS = [
    (re.compile(r"(?i)\b(is|are|was|were|be|been|being)\s+([a-zA-Z]+ed|[a-zA-Z]+en)\s+by\b"), "Passive voice with agent ('be [verb] by')"),
    (re.compile(r"(?i)\b(should|must|can|could|will|would|may|might)\s+be\s+([a-zA-Z]+ed|[a-zA-Z]+en)\b"), "Modal passive voice ('should be [verb]')"),
]

MAX_SENTENCE_WORDS = 25


def _check_line_slop(clean_line: str, line_idx: int) -> List[STEViolation]:
    """Detects AI conversational padding patterns on a single line."""
    violations: List[STEViolation] = []
    for pattern, desc in SLOP_PATTERNS:
        match = pattern.search(clean_line)
        if match:
            violations.append(
                STEViolation(
                    rule_code="STE-SLOP-001",
                    message=f"{desc} detected: '{match.group(0)}'",
                    line=line_idx,
                    text=clean_line,
                )
            )
    return violations


def _check_line_passive(clean_line: str, line_idx: int) -> List[STEViolation]:
    """Detects passive voice patterns on a single line."""
    violations: List[STEViolation] = []
    for pattern, desc in PASSIVE_PATTERNS:
        match = pattern.search(clean_line)
        if match:
            violations.append(
                STEViolation(
                    rule_code="STE-PASSIVE-002",
                    message=f"{desc} detected: '{match.group(0)}'. Convert to active imperative.",
                    line=line_idx,
                    text=clean_line,
                )
            )
    return violations


def _check_sentence_lengths(text: str) -> List[STEViolation]:
    """Splits text into sentences and flags procedural sentences exceeding MAX_SENTENCE_WORDS."""
    violations: List[STEViolation] = []
    sentence_chunks = re.split(r"(?<=[.!?])\s+", text)
    for chunk in sentence_chunks:
        trimmed = chunk.strip()
        if not trimmed:
            continue
        words = [w for w in re.split(r"\s+", trimmed) if re.search(r"[a-zA-Z0-9]", w)]
        if len(words) > MAX_SENTENCE_WORDS:
            snippet = " ".join(words[:8]) + " ... " + " ".join(words[-4:])
            violations.append(
                STEViolation(
                    rule_code="STE-LENGTH-003",
                    message=f"Sentence length exceeds {MAX_SENTENCE_WORDS} words ({len(words)} words): '{snippet}'. Split into atomic steps.",
                    line=1,
                    text=trimmed[:120],
                )
            )
    return violations


def lint_ste(text: str) -> List[STEViolation]:
    """
    Lints input text against 80% ASD-STE100 rules.
    Flags conversational slop, passive voice, and run-on procedural sentences.
    Preserves all technical programming vocabulary without false positives.
    """
    if not text or not text.strip():
        return []

    violations: List[STEViolation] = []
    lines = text.splitlines()

    for line_idx, line in enumerate(lines, start=1):
        clean_line = line.strip()
        if not clean_line or clean_line.startswith("#") or clean_line.startswith("//"):
            continue
        violations.extend(_check_line_slop(clean_line, line_idx))
        violations.extend(_check_line_passive(clean_line, line_idx))

    violations.extend(_check_sentence_lengths(text))
    return violations


def format_ste_step(raw_step: str) -> str:
    """
    Transforms verbose or passive procedural steps into clean, active imperative STE commands.
    Example: 'You need to make sure that the port is set to 8000.' -> 'Set port to 8000.'
    """
    step = raw_step.strip()
    if not step:
        return ""

    fluff_prefixes = [
        r"(?i)^(please\s+)?(you\s+(need\s+to|must|should)\s+)?(make\s+sure(\s+that)?|ensure(\s+that)?)\s+",
        r"(?i)^you\s+(need\s+to|should|must)\s+",
        r"(?i)^we\s+(need\s+to|should|must)\s+",
        r"(?i)^it\s+is\s+(important|necessary|required)\s+to\s+",
        r"(?i)^please\s+",
    ]
    for pref in fluff_prefixes:
        step = re.sub(pref, "", step).strip()

    step_clean = step.rstrip(".")
    set_match = re.match(r"(?i)^(?:that\s+)?(?:the\s+)?([a-zA-Z0-9_\-\s]+?)\s+is\s+set\s+to\s+(.+)$", step_clean)
    if set_match:
        param = set_match.group(1).strip()
        val = set_match.group(2).strip()
        return f"Set {param} to {val}."

    if step:
        return step[0].upper() + step[1:]
    return ""


def _handle_step_cli(step_arg: str, is_json: bool) -> int:
    """Handles --step CLI command."""
    formatted = format_ste_step(step_arg)
    if is_json:
        print(json.dumps({"original": step_arg, "formatted": formatted}))
    else:
        print(formatted)
    return 0


def _read_target_content(args: argparse.Namespace) -> Tuple[str, bool]:
    """Reads target content from file, argument, or stdin."""
    if args.file:
        if not os.path.isfile(args.file):
            print(f"Error: File not found '{args.file}'", file=sys.stderr)
            return "", False
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                return f.read(), True
        except (OSError, UnicodeDecodeError) as e:
            print(f"Error reading file '{args.file}': {e}", file=sys.stderr)
            return "", False
    if args.text:
        return args.text, True
    if not sys.stdin.isatty():
        return sys.stdin.read(), True
    return "", False


def _emit_violations_output(violations: List[STEViolation], is_json: bool) -> None:
    """Prints violations report in JSON or terminal human-readable format."""
    if is_json:
        result = {
            "status": "failed" if violations else "passed",
            "violation_count": len(violations),
            "violations": [v.to_dict() for v in violations],
        }
        print(json.dumps(result, indent=2))
        return

    if violations:
        print(f"\n=== ASD-STE100 Precision Violations Detected ({len(violations)}) ===", file=sys.stderr)
        for v in violations:
            print(f"  Line {v.line} [{v.rule_code}]: {v.message}", file=sys.stderr)
    else:
        print("=== ASD-STE100 Precision Check Passed: 0 Violations ===")


def main(argv: Optional[List[str]] = None) -> int:
    """CLI Entrypoint for ASD-STE100 precision linter."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="ApexEngine ASD-STE100 Precision Linter & Step Normalizer")
    parser.add_argument("--file", help="Path to specification or documentation file to lint")
    parser.add_argument("--text", help="Raw string text to lint")
    parser.add_argument("--step", help="Format a single messy step into active imperative STE")
    parser.add_argument("--check", action="store_true", help="Exit with code 1 if any violations are detected")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args(argv)

    if args.step:
        return _handle_step_cli(args.step, args.json)

    content, ok = _read_target_content(args)
    if not ok:
        if not args.file and not args.text:
            parser.print_help()
            return 0
        return 1

    violations = lint_ste(content)
    _emit_violations_output(violations, args.json)

    if args.check and violations:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
