"""
git-memory CLI — entry points for pip-installed commands.

Commands:
    git-memory index    Bulk-index a repository's commit history
    git-memory serve    Start the MCP server
    git-memory store    Store a single commit (used by post-commit hook)
    git-memory install  Install the Claude Code plugin (skills + MCP config)
    git-memory status   Show index statistics for a repository
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).parent.parent


# ── index ─────────────────────────────────────────────────────────────────────

def index_cmd(argv=None):
    """Bulk-index a Git repository into ChromaDB + Mem0."""
    sys.path.insert(0, str(PACKAGE_ROOT / "scripts"))
    from git_memory_indexer import main
    main()


# ── serve ─────────────────────────────────────────────────────────────────────

def serve_cmd(argv=None):
    """Start the MCP server (stdio transport for Claude Code)."""
    sys.path.insert(0, str(PACKAGE_ROOT / "ai"))
    from git_memory_mcp_server import mcp
    mcp.run()


# ── store ─────────────────────────────────────────────────────────────────────

def store_cmd(argv=None):
    """Store a single commit — called by the post-commit hook."""
    sys.path.insert(0, str(PACKAGE_ROOT / "scripts"))
    from store_commit_memory import main
    main()


# ── status ────────────────────────────────────────────────────────────────────

def status_cmd(argv=None):
    """Show index statistics for a repository."""
    parser = argparse.ArgumentParser(description="Show git-memory index stats.")
    parser.add_argument("--repo-path", default=".", help="Repository path")
    parser.add_argument("--user-id", default="git_memory_system")
    args = parser.parse_args(argv)

    sys.path.insert(0, str(PACKAGE_ROOT / "ai"))
    from chroma_commit_index import ChromaCommitIndex

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

    print(f"\n── git-memory status ─────────────────────────────")
    print(f"  Repo          : {repo_name}")
    print(f"  Chroma docs   : {count}")
    print(f"  Total commits : {total_commits}")
    if isinstance(total_commits, int) and total_commits > 0:
        pct = round(count / total_commits * 100)
        print(f"  Coverage      : {pct}%")
    print()


# ── install ───────────────────────────────────────────────────────────────────

def install_cmd(argv=None):
    """
    Install the Claude Code plugin:
      1. Copy skill files to ~/.claude/skills/
      2. Print MCP server config to add to ~/.claude/claude_desktop_config.json
    """
    parser = argparse.ArgumentParser(description="Install git-memory Claude Code plugin.")
    parser.add_argument("--repo-path", default=".", help="Target repo to configure MCP for")
    parser.add_argument("--user-id", default="git_memory_system")
    parser.add_argument("--skills-only", action="store_true")
    parser.add_argument("--mcp-only",    action="store_true")
    args = parser.parse_args(argv)

    claude_dir   = Path.home() / ".claude"
    skills_dst   = claude_dir / "skills"
    skills_src   = PACKAGE_ROOT / "skills"

    # ── Skills ────────────────────────────────────────────────────────────────
    if not args.mcp_only:
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
        python_path  = sys.executable
        server_path  = str(PACKAGE_ROOT / "ai" / "git_memory_mcp_server.py")
        repo_abs     = str(Path(args.repo_path).resolve())

        config = {
            "mcpServers": {
                "git-memory": {
                    "command": python_path,
                    "args": [server_path],
                    "env": {
                        "GIT_MEMORY_REPO_PATH": repo_abs,
                        "GIT_MEMORY_USER_ID":   args.user_id,
                    }
                }
            }
        }

        config_path = claude_dir / "claude_desktop_config.json"
        print(f"\n── MCP Server Config ──────────────────────────────")

        if config_path.exists():
            existing = json.loads(config_path.read_text())
            existing.setdefault("mcpServers", {})
            existing["mcpServers"]["git-memory"] = config["mcpServers"]["git-memory"]
            config_path.write_text(json.dumps(existing, indent=2))
            print(f"✓ Merged into {config_path}")
        else:
            config_path.write_text(json.dumps(config, indent=2))
            print(f"✓ Created {config_path}")

        print(f"\n  Repo path : {repo_abs}")
        print(f"  User ID   : {args.user_id}")
        print(f"\n  Restart Claude Code to pick up the new MCP server.\n")


# ── main dispatcher ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="git-memory",
        description="Git Memory System — ChromaDB + Mem0 commit index for Claude Code",
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
        sys.argv = [f"git-memory {args.command}"] + remaining
        dispatch[args.command]()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
