"""
claude-memory CLI — entry points for pip-installed commands.

Commands:
    claude-memory index    Bulk-index a repository's commit history
    claude-memory serve    Start the MCP server
    claude-memory store    Store a single commit (used by post-commit hook)
    claude-memory install  Install the Claude Code plugin (skills + MCP config)
    claude-memory status   Show index statistics for a repository
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).parent.parent


# ── index ─────────────────────────────────────────────────────────────────────

def index_cmd(argv=None):
    """Bulk-index a Git repository into ChromaDB + Mem0."""
    from claude_memory.indexer import main
    main()


# ── serve ─────────────────────────────────────────────────────────────────────

def serve_cmd(argv=None):
    """Start the MCP server (stdio transport for Claude Code)."""
    from claude_memory.mcp_server import mcp
    mcp.run()


# ── store ─────────────────────────────────────────────────────────────────────

def store_cmd(argv=None):
    """Store a single commit — called by the post-commit hook."""
    from claude_memory.store import main
    main()


# ── status ────────────────────────────────────────────────────────────────────

def status_cmd(argv=None):
    """Show index statistics for a repository."""
    parser = argparse.ArgumentParser(description="Show claude-memory index stats.")
    parser.add_argument("--repo-path", default=".", help="Repository path")
    parser.add_argument("--user-id", default="claude_memory_system")
    args = parser.parse_args(argv)

    from claude_memory.chroma_index import ChromaCommitIndex

    chroma = ChromaCommitIndex()
    count  = chroma.count()

    try:
        import git
        repo = git.Repo(args.repo_path, search_parent_directories=True)
        total_commits = sum(1 for _ in repo.iter_commits())
        repo_name = Path(repo.working_dir).name
    except Exception:
        total_commits = "?"
        repo_name = args.repo_path

    print(f"\n── claude-memory status ──────────────────────────")
    print(f"  Repo          : {repo_name}")
    print(f"  Chroma docs   : {count}")
    print(f"  Total commits : {total_commits}")
    if isinstance(total_commits, int) and total_commits > 0:
        pct = round(count / total_commits * 100)
        print(f"  Coverage      : {pct}%")
    print()


# ── install ───────────────────────────────────────────────────────────────────

CLAUDE_MD_MARKER_START = "<!-- claude-memory:start -->"
CLAUDE_MD_MARKER_END   = "<!-- claude-memory:end -->"

CLAUDE_MD_BLOCK = """\
<!-- claude-memory:start -->

# Claude Memory System

This project uses **claudememory** — a dual-layer semantic index over Git commit history for Claude Code.

## Always Start Here

When beginning any task in this repository:

1. Call `latest_commits(5)` to understand what changed recently
2. Call `search_git_history(<relevant topic>)` before touching any module with history
3. After fixing a bug, call `bug_fix_history(<component>)` to check for prior regressions

## Available Skills

| Task | Skill |
|------|-------|
| Search commit history for a topic | `/claude-memory-search` |
| Index a new repository | `/claude-memory-index` |
| Debug why a component behaves a certain way | `/claude-memory-debug` |
| Check what's currently indexed | `/claude-memory-status` |

## MCP Tools Reference

| Tool | What it gives you | When to use |
|------|-------------------|-------------|
| `search_git_history(query, limit, category)` | Commits semantically related to a topic | Before editing any significant module |
| `latest_commits(limit)` | N most-recent indexed commits | Session start, before investigating regressions |
| `commits_touching_file(filename, limit)` | All commits that modified a file | Before editing a file — understand its history |
| `bug_fix_history(component, include_security)` | Bug/security fixes for a component | Before adding new code near known bug areas |
| `architecture_decisions(topic, limit)` | Refactors, migrations, design decisions | Understanding why code is structured a certain way |

## Proactive Usage Rules

**Always call before editing:**
```
commits_touching_file("PaymentService.php")  # know what's broken here before
bug_fix_history("auth")                       # avoid re-introducing fixed bugs
```

**Always call at session start:**
```
latest_commits(10)   # what changed while you were away?
```

**Always call when confused about design:**
```
architecture_decisions("state machine")  # why was this abstraction introduced?
search_git_history("why was X removed")
```

## Category Filter Values

Use `category=` in `search_git_history()` to narrow results:

| Category | Matches |
|----------|---------|
| `fix`    | Bug fixes, hotfixes, patches |
| `feat`   | New features |
| `security` | Security-related changes |
| `refactor` | Code refactors |
| `migration` | Database/schema migrations |
| `arch`   | Architecture decisions |
| `perf`   | Performance improvements |

<!-- claude-memory:end -->"""


def _install_claude_md(repo_path: str):
    """Add the claude-memory block to CLAUDE.md, preserving existing content."""
    claude_md_path = Path(repo_path) / "CLAUDE.md"

    if claude_md_path.exists():
        existing = claude_md_path.read_text()

        # Already has our block — replace it in-place
        if CLAUDE_MD_MARKER_START in existing and CLAUDE_MD_MARKER_END in existing:
            import re
            pattern = re.escape(CLAUDE_MD_MARKER_START) + r".*?" + re.escape(CLAUDE_MD_MARKER_END)
            updated = re.sub(pattern, CLAUDE_MD_BLOCK, existing, flags=re.DOTALL)
            claude_md_path.write_text(updated)
            print(f"✓ Updated claude-memory block in {claude_md_path}")
            return

        # Exists but no marker — prepend our block
        claude_md_path.write_text(CLAUDE_MD_BLOCK + "\n\n" + existing)
        print(f"✓ Prepended claude-memory block to {claude_md_path}")
    else:
        # No CLAUDE.md — create it
        claude_md_path.write_text(CLAUDE_MD_BLOCK + "\n")
        print(f"✓ Created {claude_md_path}")


def _find_skills_dir() -> Path:
    """Locate the skills directory, checking package data first, then source tree."""
    # Package data (works when installed via pip/pipx)
    pkg_skills = Path(__file__).parent / "skills"
    if pkg_skills.is_dir():
        return pkg_skills
    # Source tree fallback (editable / dev installs)
    src_skills = PACKAGE_ROOT / "skills"
    if src_skills.is_dir():
        return src_skills
    raise FileNotFoundError(
        "Skills directory not found. Reinstall claudememory: pip install claudememory"
    )


def _find_claude_memory_bin() -> str:
    """Find the installed claude-memory CLI executable."""
    cm = shutil.which("claude-memory")
    if cm:
        return cm
    # Fallback: run via python -m
    return sys.executable


def install_cmd(argv=None):
    """
    Install the Claude Code plugin:
      1. Copy skill files to ~/.claude/skills/
      2. Configure MCP server in .claude.json (project-level)
      3. Auto-index the repository
    """
    parser = argparse.ArgumentParser(description="Install claude-memory Claude Code plugin.")
    parser.add_argument("--repo-path", default=".", help="Target repo to configure MCP for")
    parser.add_argument("--user-id", default="claude_memory_system")
    parser.add_argument("--skills-only", action="store_true")
    parser.add_argument("--mcp-only",    action="store_true")
    parser.add_argument("--no-index",    action="store_true", help="Skip auto-indexing")
    args = parser.parse_args(argv)

    repo_abs = str(Path(args.repo_path).resolve())

    # Verify we're in a git repo
    try:
        import git
        repo = git.Repo(repo_abs, search_parent_directories=True)
        repo_abs = repo.working_dir  # use the actual repo root
    except Exception:
        print(f"Error: {repo_abs} is not inside a Git repository.")
        print("Run this command from within a Git repository, or pass --repo-path.")
        sys.exit(1)

    claude_dir   = Path.home() / ".claude"
    skills_dst   = claude_dir / "skills"

    # ── Skills ────────────────────────────────────────────────────────────────
    if not args.mcp_only:
        try:
            skills_src = _find_skills_dir()
        except FileNotFoundError as e:
            print(f"Warning: {e}")
            skills_src = None

        if skills_src:
            skills_dst.mkdir(parents=True, exist_ok=True)
            installed = []
            for skill_dir in skills_src.iterdir():
                if not skill_dir.is_dir():
                    continue
                dst = skills_dst / skill_dir.name
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(skill_dir, dst)
                installed.append(skill_dir.name)
            print(f"✓ Installed {len(installed)} skills to {skills_dst}:")
            for s in installed:
                print(f"    /{s}")

    # ── MCP config ────────────────────────────────────────────────────────────
    if not args.skills_only:
        cm_bin = _find_claude_memory_bin()
        if cm_bin == sys.executable:
            mcp_command = cm_bin
            mcp_args = ["-m", "claude_memory.cli", "serve"]
        else:
            mcp_command = cm_bin
            mcp_args = ["serve"]

        mcp_entry = {
            "command": mcp_command,
            "args": mcp_args,
            "env": {
                "CLAUDE_MEMORY_REPO_PATH": repo_abs,
                "CLAUDE_MEMORY_USER_ID":   args.user_id,
            }
        }

        # Write to project-level .claude.json
        project_config_path = Path(repo_abs) / ".claude.json"
        print(f"\n── MCP Server Config ──────────────────────────────")

        if project_config_path.exists():
            try:
                existing = json.loads(project_config_path.read_text())
            except (json.JSONDecodeError, OSError):
                existing = {}
        else:
            existing = {}

        existing.setdefault("mcpServers", {})
        existing["mcpServers"]["claude-memory"] = mcp_entry
        project_config_path.write_text(json.dumps(existing, indent=2) + "\n")
        print(f"✓ Configured MCP server in {project_config_path}")

        print(f"\n  Repo path : {repo_abs}")
        print(f"  User ID   : {args.user_id}")

    # ── CLAUDE.md ──────────────────────────────────────────────────────────────
    print(f"\n── CLAUDE.md ──────────────────────────────────────")
    _install_claude_md(repo_abs)

    # ── Auto-index ────────────────────────────────────────────────────────────
    if not args.no_index:
        print(f"\n── Indexing repository ─────────────────────────────")
        try:
            from claude_memory.indexer import ClaudeMemoryIndexer
            indexer = ClaudeMemoryIndexer(repo_path=repo_abs, user_id=args.user_id)
            stats = indexer.index_all()
            print(f"✓ Indexed {stats['stored']} commits "
                  f"({stats['skipped_duplicate']} duplicates, "
                  f"{stats['skipped_irrelevant']} irrelevant)")
        except Exception as exc:
            print(f"Warning: Auto-indexing failed: {exc}")
            print("  You can index manually later with: claude-memory index")

    print(f"\n  Restart Claude Code to pick up the new MCP server.\n")


# ── main dispatcher ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="claude-memory",
        description="Claude Memory System — ChromaDB + Mem0 commit index for Claude Code",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.add_parser("index",   help="Bulk-index a repository's commit history")
    sub.add_parser("serve",   help="Start the MCP server (stdio)")
    sub.add_parser("store",   help="Store a single commit (for post-commit hook)")
    sub.add_parser("status",  help="Show index statistics")
    sub.add_parser("install", help="Install the Claude Code plugin")

    # Parse only the first arg to dispatch; let sub-commands handle the rest
    args, remaining = parser.parse_known_args()

    dispatch = {
        "index":   index_cmd,
        "serve":   serve_cmd,
        "store":   store_cmd,
        "status":  status_cmd,
        "install": install_cmd,
    }

    if args.command in dispatch:
        sys.argv = [f"claude-memory {args.command}"] + remaining
        dispatch[args.command]()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
