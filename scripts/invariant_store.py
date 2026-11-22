#!/usr/bin/env python3
"""
ApexEngine Invariant Store Engine (invariant_store.py)
Authoritative state register ensuring zero variable amnesia and zero state drift.
Maintains .context/invariants.json with SHA-256 cryptographic tamper verification.
Zero external dependencies: Python 3.8+ standard library only.
"""

import os
import sys
import json
import hashlib
import datetime
import argparse
from typing import Any, Dict, List, Optional, Tuple


class InvariantStore:
    """Authoritative store for immutable constants, monotonic states, and ephemeral variables."""

    SCHEMA_VERSION = "1.0.0"

    def __init__(self, context_dir: str):
        self.context_dir = os.path.abspath(context_dir)
        self.store_path = os.path.join(self.context_dir, "invariants.json")
        self._ensure_store()

    def _ensure_store(self) -> None:
        os.makedirs(self.context_dir, exist_ok=True)
        if not os.path.isfile(self.store_path):
            initial_data = {
                "version": self.SCHEMA_VERSION,
                "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "checksum": "",
                "registers": {
                    "immutable": {},
                    "monotonic": {},
                    "ephemeral": {}
                }
            }
            initial_data["checksum"] = self._compute_checksum(initial_data["registers"])
            self._save_raw(initial_data)

    def _compute_checksum(self, registers: Dict[str, Any]) -> str:
        """Computes SHA-256 digest over canonical JSON serialization."""
        serialized = json.dumps(registers, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _load_raw(self) -> Dict[str, Any]:
        with open(self.store_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data

    def _save_raw(self, data: Dict[str, Any]) -> None:
        data["last_updated"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        data["checksum"] = self._compute_checksum(data["registers"])
        temp_path = self.store_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, self.store_path)

    def verify_integrity(self) -> Tuple[bool, str]:
        """Validates that .context/invariants.json has not been tampered with out-of-band."""
        if not os.path.isfile(self.store_path):
            return False, "Store file missing (.context/invariants.json)"
        try:
            data = self._load_raw()
        except Exception as e:
            return False, f"JSON parse failure: {e}"

        expected = self._compute_checksum(data.get("registers", {}))
        actual = data.get("checksum", "")
        if actual != expected:
            return False, f"Checksum mismatch: expected {expected[:12]}, found {actual[:12]} (INV005: TamperChecksumViolation)"
        return True, "Integrity verified"

    def bind_immutable(
        self,
        name: str,
        value: Any,
        val_type: Optional[str] = None,
        bounds: Optional[Dict[str, Any]] = None,
        desc: str = "",
        source: str = "user"
    ) -> None:
        """
        Binds a variable to the immutable register. Write-once, read-forever.
        Raises ValueError (INV001, INV003, INV004) if violated.
        """
        valid, msg = self.verify_integrity()
        if not valid:
            raise ValueError(f"Cannot bind to tampered store: {msg}")

        data = self._load_raw()
        immutable = data["registers"]["immutable"]

        # If already registered, ensure exact value matches (idempotency)
        if name in immutable:
            existing = immutable[name]
            if existing["value"] != value:
                raise ValueError(
                    f"INV001: ImmutableMutationViolation: Cannot mutate immutable symbol '{name}' "
                    f"from {existing['value']!r} to {value!r}"
                )
            return

        # Infer type if not specified
        if val_type is None:
            if isinstance(value, bool):
                val_type = "bool"
            elif isinstance(value, int):
                val_type = "int"
            elif isinstance(value, float):
                val_type = "float"
            elif isinstance(value, str):
                val_type = "string"
            elif isinstance(value, list):
                val_type = "list"
            elif isinstance(value, dict):
                val_type = "dict"
            else:
                val_type = type(value).__name__

        # Validate type correctness
        type_checks = {
            "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "float": lambda v: isinstance(v, (float, int)) and not isinstance(v, bool),
            "string": lambda v: isinstance(v, str),
            "str": lambda v: isinstance(v, str),
            "bool": lambda v: isinstance(v, bool),
            "list": lambda v: isinstance(v, list),
            "dict": lambda v: isinstance(v, dict),
        }
        if val_type in type_checks and not type_checks[val_type](value):
            raise ValueError(
                f"INV003: TypeMismatchViolation: Value {value!r} does not match declared type '{val_type}'"
            )

        # Validate bounds
        if bounds:
            if "min" in bounds and value < bounds["min"]:
                raise ValueError(
                    f"INV004: BoundaryConditionViolation: Value {value!r} for '{name}' is below min bound {bounds['min']}"
                )
            if "max" in bounds and value > bounds["max"]:
                raise ValueError(
                    f"INV004: BoundaryConditionViolation: Value {value!r} for '{name}' exceeds max bound {bounds['max']}"
                )
            if "choices" in bounds and value not in bounds["choices"]:
                raise ValueError(
                    f"INV004: BoundaryConditionViolation: Value {value!r} for '{name}' not in allowed choices {bounds['choices']}"
                )
            if "regex" in bounds and isinstance(value, str):
                import re
                if not re.search(bounds["regex"], value):
                    raise ValueError(
                        f"INV004: BoundaryConditionViolation: Value {value!r} for '{name}' does not match regex '{bounds['regex']}'"
                    )

        immutable[name] = {
            "type": val_type,
            "value": value,
            "locked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "source": source,
            "description": desc,
            "bounds": bounds or {}
        }
        self._save_raw(data)

    def bind_monotonic(
        self,
        name: str,
        initial_value: str,
        allowed_transitions: Dict[str, List[str]],
        desc: str = ""
    ) -> None:
        """
        Binds a state variable with directed monotonic transitions (DAG).
        Prohibits state regression.
        """
        valid, msg = self.verify_integrity()
        if not valid:
            raise ValueError(f"Cannot bind to tampered store: {msg}")

        data = self._load_raw()
        monotonic = data["registers"]["monotonic"]
        if name in monotonic:
            existing = monotonic[name]
            if existing["current_value"] == initial_value:
                return  # Idempotent re-declaration
            raise ValueError(f"Monotonic variable '{name}' already declared with state '{existing['current_value']}'")

        monotonic[name] = {
            "type": "string",
            "current_value": initial_value,
            "allowed_transitions": allowed_transitions,
            "description": desc,
            "history": [
                {
                    "from": None,
                    "to": initial_value,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }
            ]
        }
        self._save_raw(data)

    def transition_monotonic(self, name: str, to_value: str) -> None:
        """Executes a validated forward transition on a monotonic state variable."""
        valid, msg = self.verify_integrity()
        if not valid:
            raise ValueError(f"Cannot transition in tampered store: {msg}")

        data = self._load_raw()
        monotonic = data["registers"]["monotonic"]
        if name not in monotonic:
            raise KeyError(f"Monotonic variable '{name}' not found in store")

        record = monotonic[name]
        current = record["current_value"]
        if current == to_value:
            return  # Idempotent forward stay

        allowed = record.get("allowed_transitions", {}).get(current, [])
        if to_value not in allowed:
            raise ValueError(
                f"INV002: MonotonicRegressionViolation: Transition for '{name}' from '{current}' to '{to_value}' "
                f"is prohibited. Permitted transitions: {allowed}"
            )

        record["current_value"] = to_value
        record["history"].append({
            "from": current,
            "to": to_value,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        })
        self._save_raw(data)

    def bind_ephemeral(self, name: str, value: Any, val_type: Optional[str] = None, expires_on_checkpoint: bool = True) -> None:
        """Binds a task-scoped variable cleared on milestone checkpoint."""
        valid, msg = self.verify_integrity()
        if not valid:
            raise ValueError(f"Cannot bind to tampered store: {msg}")

        data = self._load_raw()
        if val_type is None:
            val_type = type(value).__name__

        data["registers"]["ephemeral"][name] = {
            "type": val_type,
            "value": value,
            "expires_on_checkpoint": expires_on_checkpoint,
            "bound_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        self._save_raw(data)

    def clear_ephemeral(self) -> None:
        """Prunes all ephemeral registers upon milestone completion."""
        data = self._load_raw()
        data["registers"]["ephemeral"] = {}
        self._save_raw(data)

    def get_invariants(self) -> Dict[str, Any]:
        """Returns all registered invariants."""
        data = self._load_raw()
        return data.get("registers", {})

    def render_markdown_table(self, max_bytes: int = 600) -> str:
        """
        Renders the active invariants as a formatted Markdown table for suffix recency injection.
        Guarantees strict size <= max_bytes (default 600 bytes).
        """
        regs = self.get_invariants()
        lines = [
            "## 🔒 Pinned Invariant Register",
            "| Symbol | Type | Value | Reg | Constraint |",
            "|:-------|:-----|:------|:----|:-----------|"
        ]

        # Immutable constants
        for name, item in sorted(regs.get("immutable", {}).items()):
            b_str = "exact"
            if item.get("bounds"):
                b = item["bounds"]
                if "min" in b and "max" in b:
                    b_str = f"[{b['min']}..{b['max']}]"
                elif "choices" in b:
                    b_str = f"in {b['choices']}"
                elif "regex" in b:
                    b_str = f"pattern: {b['regex']}"
            val = str(item.get("value"))
            if len(val) > 20:
                val = val[:17] + "..."
            lines.append(f"| `{name}` | {item.get('type')} | `{val}` | IMMUTABLE | {b_str} |")

        # Monotonic state variables
        for name, item in sorted(regs.get("monotonic", {}).items()):
            lines.append(f"| `{name}` | state | `{item.get('current_value')}` | MONOTONIC | forward DAG |")

        table = "\n".join(lines)
        encoded = table.encode("utf-8")
        if len(encoded) > max_bytes:
            ellipsis = "| ... | ... | ... | ... | ... |"
            rows = lines[:3]
            for row in lines[3:]:
                # Ensure that adding this row PLUS the ellipsis row will not exceed max_bytes
                candidate_with_ellipsis = "\n".join(rows + [row, ellipsis])
                if len(candidate_with_ellipsis.encode("utf-8")) <= max_bytes:
                    rows.append(row)
                else:
                    rows.append(ellipsis)
                    break
            else:
                # If loop completed without break but still exceeds, append ellipsis if needed
                if rows and rows[-1] != ellipsis:
                    rows.append(ellipsis)
            table = "\n".join(rows)

            # Defensive guard: if table still exceeds (e.g. max_bytes is very small), pop rows until <= max_bytes
            while len(table.encode("utf-8")) > max_bytes and len(rows) > 3:
                if len(rows) > 4:
                    rows.pop(-2)  # Remove last data row before ellipsis
                else:
                    rows.pop()    # Remove ellipsis if even header + ellipsis exceeds
                table = "\n".join(rows)

        return table


def main(argv=None) -> int:
    """CLI helper for invariant operations."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="ApexEngine Invariant Store Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bind_p = subparsers.add_parser("bind", help="Bind an invariant variable")
    bind_p.add_argument("name", help="Symbol name (e.g., PORT, BASELINE_SCORE)")
    bind_p.add_argument("value", help="Literal value to store")
    bind_p.add_argument("--dir", default=".", help="Target project directory")
    bind_p.add_argument("--type", dest="val_type", choices=["int", "float", "string", "bool", "list", "dict"], help="Explicit primitive type")
    bind_p.add_argument("--immutable", action="store_true", default=True, help="Register as immutable (default: True)")
    bind_p.add_argument("--monotonic", action="store_true", help="Register as monotonic state variable")
    bind_p.add_argument("--transitions", help="JSON map of allowed transitions for monotonic state")
    bind_p.add_argument("--bounds", help="Bounds specification (e.g. min:max or json)")
    bind_p.add_argument("--desc", default="", help="Description of invariant purpose")

    verify_p = subparsers.add_parser("verify", help="Verify integrity of .context/invariants.json")
    verify_p.add_argument("--dir", default=".", help="Target project directory")

    table_p = subparsers.add_parser("table", help="Render Markdown invariant table")
    table_p.add_argument("--dir", default=".", help="Target project directory")
    table_p.add_argument("--max-bytes", type=int, default=600, help="Maximum byte budget (default: 600)")

    args = parser.parse_args(argv)
    target_dir = os.path.abspath(args.dir)
    context_dir = os.path.join(target_dir, ".context")
    store = InvariantStore(context_dir)

    if args.command == "verify":
        ok, msg = store.verify_integrity()
        if ok:
            print(f"=== Invariant Integrity Approved: {msg} ===")
            return 0
        else:
            print(f"❌ Invariant Integrity Violation: {msg}", file=sys.stderr)
            return 1

    elif args.command == "table":
        print(store.render_markdown_table(max_bytes=args.max_bytes))
        return 0

    elif args.command == "bind":
        # Parse value type
        raw_val = args.value
        parsed_val: Any = raw_val
        val_type = args.val_type

        if val_type == "int":
            parsed_val = int(raw_val)
        elif val_type == "float":
            parsed_val = float(raw_val)
        elif val_type == "bool":
            parsed_val = raw_val.lower() in ("true", "1", "yes")
        elif val_type in ("list", "dict"):
            parsed_val = json.loads(raw_val)
        else:
            # Try auto-inference if type not explicitly specified
            try:
                if raw_val.isdigit() or (raw_val.startswith("-") and raw_val[1:].isdigit()):
                    parsed_val = int(raw_val)
                    val_type = "int"
                elif "." in raw_val:
                    parsed_val = float(raw_val)
                    val_type = "float"
                elif raw_val.lower() in ("true", "false"):
                    parsed_val = raw_val.lower() == "true"
                    val_type = "bool"
                else:
                    parsed_val = raw_val
                    val_type = "string"
            except Exception:
                parsed_val = raw_val
                val_type = "string"

        # Parse bounds
        bounds_dict = None
        if args.bounds:
            try:
                bounds_dict = json.loads(args.bounds)
            except Exception:
                if ":" in args.bounds:
                    parts = args.bounds.split(":")
                    bounds_dict = {}
                    if parts[0]:
                        bounds_dict["min"] = float(parts[0]) if "." in parts[0] else int(parts[0])
                    if parts[1]:
                        bounds_dict["max"] = float(parts[1]) if "." in parts[1] else int(parts[1])

        if args.monotonic:
            transitions = {}
            if args.transitions:
                transitions = json.loads(args.transitions)
            store.bind_monotonic(args.name, str(parsed_val), transitions, desc=args.desc)
            print(f"=== Monotonic State Registered: '{args.name}' = '{parsed_val}' ===")
        else:
            store.bind_immutable(args.name, parsed_val, val_type=val_type, bounds=bounds_dict, desc=args.desc)
            print(f"=== Immutable Invariant Registered: '{args.name}' = {parsed_val!r} ({val_type}) ===")

        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
