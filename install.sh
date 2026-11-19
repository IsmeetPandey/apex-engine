#!/usr/bin/env bash
set -euo pipefail

echo "=================================================="
echo "          Installing ApexEngine v2.2.0            "
echo "=================================================="

# Check Python 3
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 is required to install ApexEngine." >&2
    exit 1
fi

PYTHON_BIN=$(command -v python3)
TARGET_DIR=""

# Detect platform / environment
if [ -d "$HOME/.gemini/config/skills" ]; then
    TARGET_DIR="$HOME/.gemini/config/skills/apex-engine"
    echo "Detected Google Antigravity environment: $TARGET_DIR"
elif [ -d "$HOME/.claude/skills" ]; then
    TARGET_DIR="$HOME/.claude/skills/apex-engine"
    echo "Detected Claude Code environment: $TARGET_DIR"
else
    TARGET_DIR="$HOME/.apex-engine"
    echo "Installing to user home: $TARGET_DIR"
fi

mkdir -p "$TARGET_DIR"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -r "$SCRIPT_DIR/SKILL.md" "$TARGET_DIR/"
cp -r "$SCRIPT_DIR/scripts" "$TARGET_DIR/"
cp -r "$SCRIPT_DIR/templates" "$TARGET_DIR/"

echo "ApexEngine successfully installed to $TARGET_DIR"
echo "Run 'python3 $TARGET_DIR/scripts/condense.py init' in any repository to begin."
