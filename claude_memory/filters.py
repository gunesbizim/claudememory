"""
Commit filtering and metadata extraction.
Shared by the indexer, store script, and MCP server.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import git as _git

RELEVANT_KEYWORDS = {
    "fix", "bug", "refactor", "security", "arch", "architecture",
    "perf", "performance", "breaking", "migrate", "migration",
    "deprecat", "revert", "feat", "feature", "design", "restructure",
    "upgrade", "downgrade", "critical", "hotfix", "patch", "chore",
}

MAX_FILES_PER_COMMIT = 20


def is_relevant(message: str) -> bool:
    """True if commit message contains at least one signal keyword."""
    lowered = message.lower()
    return any(kw in lowered for kw in RELEVANT_KEYWORDS)


def summarize_commit(commit: "_git.Commit") -> str:
    """Build a concise, LLM-readable summary of a commit for Mem0 storage."""
    dt = datetime.fromtimestamp(commit.committed_date, tz=timezone.utc)
    date_str = dt.strftime("%Y-%m-%d %H:%M UTC")

    try:
        changed_files = list(commit.stats.files.keys())[:MAX_FILES_PER_COMMIT]
        file_summary = ", ".join(changed_files) if changed_files else "none"
        ins = commit.stats.total.get("insertions", 0)
        dels = commit.stats.total.get("deletions", 0)
        stats_str = f"+{ins}/-{dels} lines across {len(commit.stats.files)} file(s)"
    except Exception:
        file_summary = "unavailable"
        stats_str = "unavailable"

    return "\n".join([
        f"Commit: {commit.hexsha}",
        f"Author: {commit.author.name} <{commit.author.email}>",
        f"Date: {date_str}",
        f"Message: {commit.message.strip()}",
        f"Stats: {stats_str}",
        f"Files changed: {file_summary}",
    ])


def build_metadata(commit: "_git.Commit", repo_name: str) -> dict:
    """Structured metadata dict stored alongside the memory."""
    dt = datetime.fromtimestamp(commit.committed_date, tz=timezone.utc)

    msg = commit.message.lower()
    category = "general"
    for kw in ("fix", "bug", "security", "refactor", "perf", "performance",
               "arch", "feature", "feat", "migration", "revert"):
        if kw in msg:
            category = kw
            break

    try:
        files = list(commit.stats.files.keys())[:MAX_FILES_PER_COMMIT]
    except Exception:
        files = []

    return {
        "type":           "git_commit",
        "repo":           repo_name,
        "commit_hash":    commit.hexsha,
        "short_hash":     commit.hexsha[:8],
        "author_name":    commit.author.name,
        "author_email":   commit.author.email,
        "committed_date": dt.isoformat(),
        "category":       category,
        "files_changed":  files,
    }
