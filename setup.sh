#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup.sh  —  One-shot setup for the Git Memory System
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
VENV_DIR="$REPO_ROOT/.venv"

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Git Memory System — Setup"
echo "═══════════════════════════════════════════════════════"
echo ""

# ── 1. Python virtual environment ─────────────────────────────────────────────
if [[ ! -d "$VENV_DIR" ]]; then
    echo "▶ Creating virtual environment at .venv …"
    python3 -m venv "$VENV_DIR"
else
    echo "▶ Virtual environment already exists."
fi

source "$VENV_DIR/bin/activate"
echo "▶ Installing dependencies …"
pip install --quiet --upgrade pip
pip install --quiet -r "$REPO_ROOT/requirements.txt"

# ── 2. Git hook ────────────────────────────────────────────────────────────────
HOOK_PATH="$REPO_ROOT/.git/hooks/post-commit"
if [[ -f "$HOOK_PATH" && -x "$HOOK_PATH" ]]; then
    echo "▶ post-commit hook already installed and executable."
else
    echo "▶ Installing post-commit hook …"
    cp "$REPO_ROOT/.git/hooks/post-commit" "$HOOK_PATH" 2>/dev/null || true
    chmod +x "$HOOK_PATH"
fi

# Inject the venv python path into the hook so it always uses the right env
PYTHON_PATH="$VENV_DIR/bin/python"
if ! grep -q "GIT_MEMORY_PYTHON" "$HOOK_PATH"; then
    sed -i.bak "1a\\
export GIT_MEMORY_PYTHON=\"$PYTHON_PATH\"" "$HOOK_PATH"
    rm -f "$HOOK_PATH.bak"
fi

# ── 3. Bulk index existing history ────────────────────────────────────────────
echo ""
read -rp "▶ Bootstrap memory from existing Git history? [Y/n] " ANSWER
ANSWER="${ANSWER:-Y}"

if [[ "$ANSWER" =~ ^[Yy]$ ]]; then
    read -rp "  Max commits to index (blank = all): " LIMIT_INPUT
    LIMIT_ARG=""
    if [[ -n "$LIMIT_INPUT" ]]; then
        LIMIT_ARG="--limit $LIMIT_INPUT"
    fi

    echo "  Indexing… (this may take a while for large repos)"
    # shellcheck disable=SC2086
    "$PYTHON_PATH" "$REPO_ROOT/scripts/git_memory_indexer.py" \
        --repo-path "$REPO_ROOT" \
        $LIMIT_ARG
fi

# ── 4. Claude Code MCP registration ───────────────────────────────────────────
CLAUDE_CONFIG="$HOME/.claude/claude_desktop_config.json"
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  MCP Server Registration"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "  Add the following to $CLAUDE_CONFIG:"
echo ""
cat <<EOF
  "mcpServers": {
    "git-memory": {
      "command": "$PYTHON_PATH",
      "args": ["$REPO_ROOT/ai/git_memory_mcp_server.py"],
      "env": {
        "GIT_MEMORY_REPO_PATH": "$REPO_ROOT",
        "GIT_MEMORY_USER_ID": "git_memory_system"
      }
    }
  }
EOF
echo ""
echo "  Then restart Claude Code to pick up the new MCP server."
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Setup complete!"
echo "═══════════════════════════════════════════════════════"
