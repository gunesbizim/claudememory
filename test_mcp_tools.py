#!/usr/bin/env python3
"""
Quick smoke-test for all MCP tools against the lokumcu index.
Run: source .venv/bin/activate && python test_mcp_tools.py
"""

import os, sys, json
os.environ["CLAUDE_MEMORY_REPO_PATH"] = "../lokumcu"
os.environ["CLAUDE_MEMORY_USER_ID"]   = "lokumcu"

# Import tools directly from the MCP server module
sys.path.insert(0, "ai")
from claude_memory_mcp_server import (
    search_git_history,
    latest_commits,
    commits_touching_file,
    bug_fix_history,
    architecture_decisions,
)

SEP = "─" * 60

def show(label, results):
    print(f"\n{SEP}")
    print(f"  {label}")
    print(SEP)
    for r in results:
        if "error" in r or "message" in r:
            print(" ", r)
            continue
        score = r.get("relevance_score", "")
        score_str = f"  [score={score}]" if score else ""
        print(f"  [{r.get('short_hash','?')}] {r.get('date','')[:10]}  {r.get('category','').upper():<12}{score_str}")
        # Print first line of summary
        summary_first = r.get("summary","").splitlines()[0] if r.get("summary") else ""
        if summary_first:
            print(f"         {summary_first[:80]}")
        files = r.get("files_changed", [])
        if files:
            print(f"         Files: {', '.join(files[:3])}{'…' if len(files)>3 else ''}")
    print()

# ── Test 1 ─────────────────────────────────────────────────────────────────
show(
    "search_git_history('payment 3DS fix')",
    search_git_history("payment 3DS fix", limit=5)
)

# ── Test 2 ─────────────────────────────────────────────────────────────────
show(
    "latest_commits(5)",
    latest_commits(5)
)

# ── Test 3 ─────────────────────────────────────────────────────────────────
show(
    "commits_touching_file('routes')",
    commits_touching_file("routes", limit=5)
)

# ── Test 4 ─────────────────────────────────────────────────────────────────
show(
    "bug_fix_history('payments')",
    bug_fix_history("payments", limit=5)
)

# ── Test 5 ─────────────────────────────────────────────────────────────────
show(
    "architecture_decisions('auth')",
    architecture_decisions("auth", limit=5)
)

# ── Test 6: category filter ────────────────────────────────────────────────
show(
    "search_git_history('discount', category='fix')",
    search_git_history("discount", limit=5, category="fix")
)
