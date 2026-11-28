#!/usr/bin/env python3
"""
ApexEngine Interactive Architecture Visualizer (diagram_generator.py)
Generates standalone, zero-dependency dark-mode HTML/SVG architecture HUDs.
Extracts module dependency graphs, state machines, and invariant contracts
and renders them directly to disk (docs/architecture.html) to prevent
context memory bloat (0 extra chat tokens consumed).
Zero external dependencies: Python 3.8+ standard library only.
"""

import os
import sys
import re
import ast
import json
import argparse
import webbrowser
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple


def _parse_ast_node(node: ast.AST, imports: List[str], classes: List[str], functions: List[str]) -> None:
    """Extracts symbols from a single AST node."""
    if isinstance(node, ast.Import):
        for alias in node.names:
            imports.append(alias.name)
    elif isinstance(node, ast.ImportFrom):
        mod = node.module or ""
        for alias in node.names:
            sym = f"{mod}.{alias.name}" if mod else alias.name
            imports.append(sym)
    elif isinstance(node, ast.ClassDef):
        classes.append(node.name)
    elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
        functions.append(node.name)


def _regex_fallback_metadata(file_path: str) -> Dict[str, List[str]]:
    """Lightweight regex parser fallback when ast.parse fails."""
    imports: List[str] = []
    classes: List[str] = []
    functions: List[str] = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                imp = re.match(r"^\s*(?:from|import)\s+([a-zA-Z0-9_\.]+)", line)
                if imp:
                    imports.append(imp.group(1))
                fn = re.match(r"^\s*def\s+([a-zA-Z0-9_]+)", line)
                if fn:
                    functions.append(fn.group(1))
                cls_m = re.match(r"^\s*class\s+([a-zA-Z0-9_]+)", line)
                if cls_m:
                    classes.append(cls_m.group(1))
    except (OSError, UnicodeDecodeError):
        return {"imports": [], "classes": [], "functions": []}
    return {"imports": imports, "classes": classes, "functions": functions}


def extract_python_metadata(file_path: str) -> Dict[str, Any]:
    """Extracts imports, classes, and top-level functions using AST with regex fallback."""
    imports: List[str] = []
    classes: List[str] = []
    functions: List[str] = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content, filename=file_path)
        for node in ast.walk(tree):
            _parse_ast_node(node, imports, classes, functions)
    except (SyntaxError, UnicodeDecodeError, OSError):
        return _regex_fallback_metadata(file_path)

    return {
        "imports": sorted(list(set(imports))),
        "classes": sorted(list(set(classes))),
        "functions": sorted(list(set(functions))),
    }


def _discover_source_modules(target_path: Path) -> List[Dict[str, Any]]:
    """Discovers code modules in workspace directory."""
    modules: List[Dict[str, Any]] = []
    ignored = {".git", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache", "dist", "build"}

    for root, dirs, files in os.walk(target_path):
        dirs[:] = [d for d in dirs if d not in ignored and not d.startswith(".")]
        for file in files:
            if file.endswith((".py", ".ts", ".js", ".go", ".rs")):
                full = os.path.join(root, file)
                rel = os.path.relpath(full, target_path).replace("\\", "/")
                meta = extract_python_metadata(full) if file.endswith(".py") else {"imports": [], "classes": [], "functions": []}
                modules.append({
                    "name": rel,
                    "filename": file,
                    "path": full,
                    "imports": meta["imports"],
                    "classes": meta["classes"],
                    "functions": meta["functions"],
                })
    return modules


def _match_import_target(imp: str, file_map: Dict[str, str], stem_map: Dict[str, str], current_mod: str) -> Optional[str]:
    """Resolves target module name from import symbol."""
    imp_parts = imp.split(".")
    base_candidate = imp_parts[-1] + ".py"
    first_candidate = imp_parts[0] + ".py"

    target = file_map.get(base_candidate)
    if target is not None and target != current_mod:
        return target

    target = file_map.get(first_candidate)
    if target is not None and target != current_mod:
        return target

    for part in imp_parts:
        target = stem_map.get(part)
        if target is not None and target != current_mod:
            return target
    return None


def _resolve_dependency_edges(modules: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Resolves directional dependencies between discovered modules."""
    file_map = {m["filename"]: m["name"] for m in modules}
    stem_map = {Path(m["name"]).stem: m["name"] for m in modules}
    unique_deps: List[Dict[str, str]] = []
    seen_deps: Dict[Tuple[str, str], bool] = {}

    for mod in modules:
        for imp in mod["imports"]:
            target_match = _match_import_target(imp, file_map, stem_map, mod["name"])
            if target_match:
                key = (mod["name"], target_match)
                if seen_deps.get(key) is None:
                    seen_deps[key] = True
                    unique_deps.append({"from": mod["name"], "to": target_match, "symbol": imp})
    return unique_deps


def _load_invariants(target_path: Path) -> List[Dict[str, Any]]:
    """Loads cryptographic invariants from .context/invariants.json."""
    invariants: List[Dict[str, Any]] = []
    inv_file = target_path / ".context" / "invariants.json"
    if inv_file.is_file():
        try:
            with open(inv_file, "r", encoding="utf-8") as f:
                inv_data = json.load(f)
                for name, details in inv_data.get("invariants", {}).items():
                    invariants.append({
                        "name": name,
                        "value": details.get("value"),
                        "type": details.get("type"),
                        "monotonic": details.get("monotonic", False),
                        "desc": details.get("desc", ""),
                    })
        except (json.JSONDecodeError, OSError):
            return []
    return invariants


def build_diagram_model(target_dir: str) -> Dict[str, Any]:
    """Builds the structural graph model of the workspace."""
    target_path = Path(target_dir).resolve()
    modules = _discover_source_modules(target_path)
    dependencies = _resolve_dependency_edges(modules)
    invariants = _load_invariants(target_path)

    states = [
        {"id": "G1", "name": "Gate 1: Context Lock", "desc": "Read target files & callers before touching code", "status": "active"},
        {"id": "G2", "name": "Gate 2: Contract TDD", "desc": "Executable test reproduces RED before implementation", "status": "active"},
        {"id": "G3", "name": "Gate 3: Production Rigor", "desc": "Zero placeholders, SAST security, CC <= 10", "status": "active"},
        {"id": "G4", "name": "Gate 4: Empirical Verify", "desc": "Terminal execution with Exit Code 0", "status": "active"},
    ]

    return {
        "workspace": str(target_path),
        "modules": modules,
        "dependencies": dependencies,
        "states": states,
        "invariants": invariants,
    }


def _render_svg_edges(dependencies: List[Dict[str, str]], coords: Dict[str, Tuple[int, int]]) -> str:
    """Renders curved SVG arrows between connected modules."""
    lines: List[str] = []
    for dep in dependencies:
        c1 = coords.get(dep["from"])
        c2 = coords.get(dep["to"])
        if c1 is not None and c2 is not None:
            cx1, cy1 = c1[0] + 120, c1[1] + 45
            cx2, cy2 = c2[0] + 120, c2[1] + 45
            lines.append(
                f'<path d="M {cx1} {cy1} Q {(cx1+cx2)//2} {(cy1+cy2)//2 - 20} {cx2} {cy2}" '
                f'stroke="#58a6ff" stroke-width="2" fill="none" stroke-dasharray="4,4" opacity="0.75" '
                f'marker-end="url(#arrow)" />'
            )
    return "".join(lines)


def _render_svg_nodes(modules: List[Dict[str, Any]], coords: Dict[str, Tuple[int, int]]) -> str:
    """Renders SVG node rectangles for modules."""
    nodes: List[str] = []
    for mod in modules:
        pt = coords.get(mod["name"], (50, 100))
        badge = f"{len(mod['classes'])}C · {len(mod['functions'])}F · {len(mod['imports'])}I"
        nodes.append(f"""
        <g class="module-node" transform="translate({pt[0]}, {pt[1]})">
            <rect width="250" height="90" rx="8" ry="8" fill="#161b22" stroke="#30363d" stroke-width="1.5" />
            <rect width="250" height="26" rx="8" ry="8" fill="#21262d" />
            <text x="12" y="18" fill="#58a6ff" font-family="sans-serif" font-size="12" font-weight="600">{mod["name"]}</text>
            <text x="12" y="48" fill="#8b949e" font-family="monospace" font-size="11">{mod["filename"]}</text>
            <text x="12" y="70" fill="#7ee787" font-family="monospace" font-size="10">{badge}</text>
        </g>
        """)
    return "".join(nodes)


def _build_svg_diagram(modules: List[Dict[str, Any]], deps: List[Dict[str, str]]) -> Tuple[str, int, int]:
    """Calculates grid layout and generates SVG canvas markup."""
    coords: Dict[str, Tuple[int, int]] = {}
    cols, col_w, row_h = 3, 300, 140
    start_x, start_y = 50, 60

    for idx, mod in enumerate(modules):
        col, row = idx % cols, idx // cols
        coords[mod["name"]] = (start_x + col * col_w, start_y + row * row_h)

    svg_w = max(960, start_x * 2 + cols * col_w)
    total_rows = (len(modules) + cols - 1) // cols if modules else 1
    svg_h = max(450, start_y + total_rows * row_h + 60)

    edges_svg = _render_svg_edges(deps, coords)
    nodes_svg = _render_svg_nodes(modules, coords)

    svg_body = f"""<svg width="{svg_w}" height="{svg_h}" viewBox="0 0 {svg_w} {svg_h}" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#58a6ff" />
            </marker>
        </defs>
        <g id="edges">{edges_svg}</g>
        <g id="nodes">{nodes_svg}</g>
    </svg>"""
    return svg_body, svg_w, svg_h


def _render_state_cards(states: List[Dict[str, Any]]) -> str:
    """Renders HTML cards for 4-Gate invariant state lifecycle."""
    cards = []
    for s in states:
        cards.append(f"""
        <div class="state-card">
            <div class="state-id">{s["id"]}</div>
            <div class="state-title">{s["name"]}</div>
            <div class="state-desc">{s["desc"]}</div>
        </div>
        """)
    return "".join(cards)


def _render_invariant_items(invariants: List[Dict[str, Any]]) -> str:
    """Renders HTML list of locked invariants."""
    if not invariants:
        return '<div class="inv-empty">No invariants bound in .context/invariants.json. Use <code>apex bind</code> to pin.</div>'
    items = []
    for inv in invariants:
        tag = "MONOTONIC" if inv.get("monotonic") else "IMMUTABLE"
        items.append(f"""
        <div class="inv-item">
            <span class="inv-name">{inv["name"]}</span>
            <span class="inv-val">{inv["value"]}</span>
            <span class="inv-tag">{tag}</span>
        </div>
        """)
    return "".join(items)


CSS_STYLES = """
:root {
    --bg: #0d1117; --surface: #161b22; --border: #30363d;
    --text-main: #c9d1d9; --text-muted: #8b949e; --accent: #58a6ff;
    --success: #2ea043; --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    --font-mono: ui-monospace, Menlo, Consolas, monospace;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text-main); font-family: var(--font-sans); padding: 24px; line-height: 1.5; }
header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 16px; margin-bottom: 24px; }
h1 { font-size: 20px; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 10px; }
.badge { background: rgba(88,166,255,0.15); color: var(--accent); border: 1px solid var(--accent); font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 12px; }
.meta-bar { font-size: 12px; color: var(--text-muted); font-family: var(--font-mono); }
.section-title { font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); margin-bottom: 12px; }
.state-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 24px; }
.state-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 14px; }
.state-id { font-size: 11px; font-weight: 700; color: var(--accent); font-family: var(--font-mono); margin-bottom: 4px; }
.state-title { font-size: 13px; font-weight: 600; color: #fff; margin-bottom: 6px; }
.state-desc { font-size: 11px; color: var(--text-muted); }
.diagram-container { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: auto; margin-bottom: 24px; padding: 16px; }
svg { display: block; margin: 0 auto; }
.inv-container { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin-bottom: 24px; }
.inv-item { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border-bottom: 1px solid var(--border); font-family: var(--font-mono); font-size: 12px; }
.inv-name { color: var(--accent); font-weight: 600; }
.inv-tag { background: rgba(46,160,67,0.2); color: var(--success); padding: 2px 6px; border-radius: 4px; font-size: 10px; }
.inv-empty { font-size: 12px; color: var(--text-muted); font-style: italic; }
footer { border-top: 1px solid var(--border); padding-top: 16px; font-size: 11px; color: var(--text-muted); text-align: center; }
"""


def generate_architecture_html(target_dir: str, out_path: Optional[str] = None) -> str:
    """Renders standalone, zero-dependency HTML5 with embedded SVG architecture HUD."""
    model = build_diagram_model(target_dir)
    out_file = Path(out_path or os.path.join(target_dir, "docs", "architecture.html")).resolve()
    os.makedirs(out_file.parent, exist_ok=True)

    svg_markup, _, _ = _build_svg_diagram(model["modules"], model["dependencies"])
    state_cards = _render_state_cards(model["states"])
    inv_items = _render_invariant_items(model["invariants"])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ApexEngine Architecture HUD</title>
    <style>{CSS_STYLES}</style>
</head>
<body>
    <header>
        <h1>ApexEngine Architecture HUD <span class="badge">v3.2.0</span></h1>
        <div class="meta-bar">Modules: {len(model["modules"])} · Dependencies: {len(model["dependencies"])} · Invariants: {len(model["invariants"])}</div>
    </header>
    <div class="section-title">Enforced Invariant State Lifecycle</div>
    <div class="state-grid">{state_cards}</div>
    <div class="section-title">Component & Dependency Graph</div>
    <div class="diagram-container">{svg_markup}</div>
    <div class="section-title">Cryptographic Invariant Registry</div>
    <div class="inv-container">{inv_items}</div>
    <footer>Standalone Artifact generated by <code>apex diagram</code> · 0 chat tokens consumed · Disk-only visual artifact</footer>
</body>
</html>"""

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html)
    return str(out_file)


def main(argv: Optional[List[str]] = None) -> int:
    """CLI Entrypoint for diagram generator."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="ApexEngine Architecture HTML & SVG Visualizer")
    parser.add_argument("--dir", default=".", help="Target workspace directory (default: current dir)")
    parser.add_argument("--out", help="Output file path (default: docs/architecture.html)")
    parser.add_argument("--open", action="store_true", help="Automatically open generated HTML in default browser")
    parser.add_argument("--json", action="store_true", help="Output structural model as JSON instead of HTML")

    args = parser.parse_args(argv)

    if args.json:
        print(json.dumps(build_diagram_model(args.dir), indent=2))
        return 0

    res_path = generate_architecture_html(args.dir, out_path=args.out)
    print(f"Architecture HUD generated successfully:\n  file:///{res_path.replace(os.sep, '/')}")
    if args.open:
        webbrowser.open(f"file:///{res_path.replace(os.sep, '/')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
