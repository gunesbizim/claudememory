#!/usr/bin/env python3
"""
claude_memory_mcp_server.py

MCP server that exposes Claude memory tools to Claude Code.
Run with:
    python ai/claude_memory_mcp_server.py

Or register it in ~/.claude/claude_desktop_config.json (see config/mcp_config_example.json).

Tools exposed:
  - search_git_history(query)          Search semantic memory of commits
  - latest_commits(limit)              Retrieve the N most-recent indexed commits
  - commits_touching_file(filename)    Commits that modified a specific file
  - bug_fix_history(component)         Bug/fix commits scoped to a component/path
"""

import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# FastMCP — install via: pip install fastmcp
from fastmcp import FastMCP

# Mem0 — install via: pip install mem0ai
from mem0 import Memory

# GitPython — install via: pip install gitpython
import git

# ChromaDB direct layer
from claude_memory.chroma_index import ChromaCommitIndex

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.WARNING,           # keep MCP stdout clean for the protocol
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger(__name__)

# ── Configuration (override via environment variables) ─────────────────────────
REPO_PATH  = os.getenv("CLAUDE_MEMORY_REPO_PATH", ".")
USER_ID    = os.getenv("CLAUDE_MEMORY_USER_ID", "claude_memory_system")
MEM0_KEY   = os.getenv("MEM0_API_KEY", "")
CHROMA_DIR = os.getenv(
    "CLAUDE_MEMORY_CHROMA_DIR",
    str(Path.home() / ".cache" / "claude_memory" / "chroma_commits"),
)

def _derive_repo_name() -> str:
    """Derive repo directory name from REPO_PATH, matching the indexer's convention."""
    try:
        r = git.Repo(REPO_PATH, search_parent_directories=True)
        return Path(r.working_dir).name
    except Exception:
        return Path(REPO_PATH).resolve().name

REPO_NAME = _derive_repo_name()

# ── Mem0 initialisation ────────────────────────────────────────────────────────

def _build_mem0_config() -> dict:
    if MEM0_KEY:
        return {"api_key": MEM0_KEY}
    return {
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": "claude_memory",
                "path": CHROMA_DIR,
            },
        },
        "embedder": {
            "provider": "ollama",
            "config": {"model": "nomic-embed-text"},
        },
        "llm": {
            "provider": "ollama",
            "config": {"model": "qwen2.5"},
        },
    }


_memory: Optional[Memory] = None
_chroma: Optional[ChromaCommitIndex] = None


def get_memory() -> Memory:
    global _memory
    if _memory is None:
        _memory = Memory.from_config(_build_mem0_config())
    return _memory


def get_chroma() -> ChromaCommitIndex:
    global _chroma
    if _chroma is None:
        _chroma = ChromaCommitIndex(chroma_dir=CHROMA_DIR)
    return _chroma


# ── Git repo helper ────────────────────────────────────────────────────────────

def get_repo() -> Optional[git.Repo]:
    try:
        return git.Repo(REPO_PATH, search_parent_directories=True)
    except git.InvalidGitRepositoryError:
        log.warning("No git repository found at %s", REPO_PATH)
        return None


def _unwrap(raw) -> list:
    """Mem0 returns either a list or {'results': [...]} — normalise to list."""
    if isinstance(raw, dict):
        return raw.get("results", [])
    return raw or []


def _dedupe(records: list[dict]) -> list[dict]:
    """Deduplicate by commit_hash, keeping the highest-relevance entry per commit."""
    seen: dict[str, dict] = {}
    for r in records:
        h = r.get("commit_hash", "unknown")
        if h not in seen or r.get("relevance_score", 0) > seen[h].get("relevance_score", 0):
            seen[h] = r
    return list(seen.values())


def _merge_results(
    chroma_results: list[dict],
    mem0_results: list[dict],
) -> list[dict]:
    """
    Merge ChromaDB commit facts with Mem0 learned context.

    Strategy:
      - Chroma  → authoritative for commit facts (hash, date, files, category)
      - Mem0    → enriches with learned_context (what the LLM extracted/interpreted)
      - Commits only in Mem0 are included as fallback (Chroma may not have them yet)
      - Final dedup by commit_hash, sorted by relevance score descending
    """
    merged: dict[str, dict] = {}

    # Start with Chroma results (ground truth)
    for r in chroma_results:
        h = r.get("commit_hash", "unknown")
        merged[h] = {**r, "learned_context": []}

    # Enrich or add from Mem0
    for r in mem0_results:
        h = r.get("commit_hash", "unknown")
        context_text = r.get("summary", "")
        if h in merged:
            merged[h]["learned_context"].append(context_text)
        else:
            # Commit in Mem0 but not yet in Chroma (e.g. during migration)
            merged[h] = {**r, "learned_context": [context_text], "source": "mem0_only"}

    results = list(merged.values())
    results.sort(key=lambda r: r.get("relevance_score", 0), reverse=True)
    return results


def _format_result(result: dict) -> dict:
    """Normalise a single Mem0 search result into a clean dict."""
    memory_text = result.get("memory", result.get("text", ""))
    metadata    = result.get("metadata", {})
    score       = result.get("score", result.get("relevance_score", 0.0))

    return {
        "commit_hash":    metadata.get("commit_hash", "unknown"),
        "short_hash":     metadata.get("short_hash", "unknown"),
        "author":         metadata.get("author_name", "unknown"),
        "date":           metadata.get("committed_date", "unknown"),
        "category":       metadata.get("category", "general"),
        "files_changed":  metadata.get("files_changed", []),
        "summary":        memory_text,
        "relevance_score": round(float(score), 4),
    }


# ── MCP server ─────────────────────────────────────────────────────────────────
mcp = FastMCP("claudememory")


# ── Tool 1: search_git_history ─────────────────────────────────────────────────
@mcp.tool()
def search_git_history(
    query: str,
    limit: int = 10,
    category: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Semantically search the indexed Git history for commits related to a topic.

    Args:
        query:    Natural-language description of what you're looking for.
                  Examples: "authentication refactor", "database migration", "XSS fix"
        limit:    Maximum number of results to return (default 10, max 50).
        category: Optional filter — one of: fix, bug, security, refactor, perf,
                  arch, feature, migration, revert, general.

    Returns:
        List of commit records ordered by semantic relevance.

    Example usage by Claude:
        search_git_history("how was the payment module redesigned")
        search_git_history("SQL injection", category="security")
    """
    limit = min(max(1, limit), 50)

    # Layer 1 — ChromaDB: fast, accurate, 1 result per commit
    chroma_results = get_chroma().search(
        query=query,
        n_results=limit,
        category=category,
        repo=REPO_NAME,
    )

    # Layer 2 — Mem0: learned context enrichment
    mem0_results = []
    try:
        raw = get_memory().search(query=query, user_id=USER_ID, limit=limit)
        mem0_results = _dedupe([_format_result(r) for r in _unwrap(raw)])
    except Exception as exc:
        log.warning("Mem0 search failed (Chroma still available): %s", exc)

    results = _merge_results(chroma_results, mem0_results)
    if category:
        results = [r for r in results if r.get("category") == category]

    if not results:
        return [{"message": f"No commits found matching '{query}'"}]

    return results[:limit]


# ── Tool 2: latest_commits ─────────────────────────────────────────────────────
@mcp.tool()
def latest_commits(limit: int = 10) -> list[dict[str, Any]]:
    """
    Retrieve the most-recently indexed commits from memory.

    Args:
        limit: Number of recent commits to return (default 10, max 100).

    Returns:
        List of commit records sorted newest-first.

    Example usage by Claude:
        latest_commits(5)   # "what changed recently?"
    """
    limit = min(max(1, limit), 100)

    # ChromaDB has reliable date metadata — use it as primary source
    records = get_chroma().get_latest(n=limit, repo=REPO_NAME)

    # Enrich with Mem0 learned context
    mem0_map: dict[str, list[str]] = {}
    try:
        raw = get_memory().get_all(user_id=USER_ID)
        for r in _dedupe([_format_result(r) for r in _unwrap(raw)]):
            h = r.get("commit_hash", "")
            if h:
                mem0_map.setdefault(h, []).append(r.get("summary", ""))
    except Exception:
        pass

    for r in records:
        r["learned_context"] = mem0_map.get(r.get("commit_hash", ""), [])

    return records


# ── Tool 3: commits_touching_file ──────────────────────────────────────────────
@mcp.tool()
def commits_touching_file(filename: str, limit: int = 20) -> list[dict[str, Any]]:
    """
    Find indexed commits that modified a specific file.

    Searches both the live Git log and the Mem0 index.
    The Git log is authoritative for the file list; Mem0 provides
    semantic enrichment (category, author, stored summary).

    Args:
        filename: File path relative to repo root (partial match supported).
                  Examples: "src/auth/login.py", "migrations/", "README.md"
        limit:    Max results (default 20).

    Returns:
        Commits that touched the file, newest first.
    """
    limit = min(max(1, limit), 100)
    repo  = get_repo()

    if repo is None:
        return [{"error": "Git repository not accessible"}]

    # Walk git log — try exact path first, then scan all commits for partial match.
    # This handles both "app/Services/PaymentService.php" and "PaymentService.php".
    git_commits: list[dict] = []

    def _commit_row(commit) -> dict:
        dt = datetime.fromtimestamp(commit.committed_date, tz=timezone.utc)
        return {
            "commit_hash":   commit.hexsha,
            "short_hash":    commit.hexsha[:8],
            "author":        commit.author.name,
            "date":          dt.isoformat(),
            "summary":       commit.message.strip(),
            "files_changed": list(commit.stats.files.keys())[:20],
        }

    try:
        # Exact path match (fast)
        exact = list(repo.iter_commits(paths=filename, max_count=limit * 3))
        git_commits = [_commit_row(c) for c in exact]
    except Exception:
        pass

    if not git_commits:
        # Partial / basename match — scan all commits and filter by file list
        needle = filename.lower()
        try:
            for commit in repo.iter_commits(max_count=500):
                files = list(commit.stats.files.keys())
                if any(needle in f.lower() for f in files):
                    git_commits.append(_commit_row(commit))
                    if len(git_commits) >= limit * 3:
                        break
        except Exception as exc:
            log.error("Git log scan failed: %s", exc)
            return [{"error": str(exc)}]

    if not git_commits:
        return [{"message": f"No commits found touching '{filename}'"}]

    # ChromaDB: metadata-exact file search (faster, no LLM needed)
    chroma_map: dict[str, dict] = {
        r["commit_hash"]: r
        for r in get_chroma().search_by_file(filename, n_results=limit * 2, repo=REPO_NAME)
    }

    # Mem0: learned context enrichment
    mem0_map: dict[str, list[str]] = {}
    try:
        raw = get_memory().search(
            query=f"changes to {filename}", user_id=USER_ID, limit=50
        )
        for r in _dedupe([_format_result(r) for r in _unwrap(raw)]):
            h = r.get("commit_hash", "")
            if h:
                mem0_map.setdefault(h, []).append(r.get("summary", ""))
    except Exception:
        pass

    enriched = []
    for gc in git_commits[:limit]:
        h = gc["commit_hash"]
        chroma_data = chroma_map.get(h, {})
        enriched.append({
            **gc,
            "category":         chroma_data.get("category", "general"),
            "in_chroma_index":  bool(chroma_data),
            "learned_context":  mem0_map.get(h, []),
        })

    return enriched


# ── Tool 4: bug_fix_history ────────────────────────────────────────────────────
@mcp.tool()
def bug_fix_history(
    component: str,
    limit: int = 15,
    include_security: bool = True,
) -> list[dict[str, Any]]:
    """
    Retrieve all bug-fix and security commits related to a component or topic.

    Uses semantic search filtered to fix/bug/security/hotfix categories,
    then re-ranks by relevance to the component name.

    Args:
        component:        Component name, module path, or topic keyword.
                          Examples: "auth", "payment", "database", "api/v2/users.py"
        limit:            Max commits to return (default 15).
        include_security: Also include security-category commits (default True).

    Returns:
        Relevant fix commits, most-relevant first.

    Example usage by Claude:
        bug_fix_history("authentication")
        bug_fix_history("payments", include_security=False)
    """
    limit = min(max(1, limit), 100)
    target_categories = {"fix", "bug", "hotfix", "patch", "revert"}
    if include_security:
        target_categories.add("security")

    # ChromaDB: category-filtered semantic search (clean, 1 result/commit)
    chroma_results = []
    for cat in target_categories:
        chroma_results += get_chroma().search(
            query=f"{component} {cat}",
            n_results=limit,
            category=cat,
            repo=REPO_NAME,
        )

    # Mem0: learned context for each fix
    mem0_results = []
    try:
        for q in [f"bug fix {component}", f"security {component}"]:
            raw = get_memory().search(query=q, user_id=USER_ID, limit=20)
            mem0_results += [_format_result(r) for r in _unwrap(raw)]
    except Exception as exc:
        log.warning("Mem0 bug_fix search failed: %s", exc)

    merged = _merge_results(chroma_results, _dedupe(mem0_results))

    # Strict category filter, fall back to all if too few
    filtered = [r for r in merged if r.get("category") in target_categories]
    if len(filtered) < 3:
        filtered = merged

    if not filtered:
        return [{"message": f"No bug-fix history found for component '{component}'"}]

    return filtered[:limit]


# ── Tool 5: architecture_decisions ────────────────────────────────────────────
@mcp.tool()
def architecture_decisions(topic: str = "", limit: int = 10) -> list[dict[str, Any]]:
    """
    Surface architectural decision commits — refactors, migrations, design changes.

    Args:
        topic:  Optional topic to narrow the search (e.g., "database", "API design").
        limit:  Max commits to return (default 10).

    Returns:
        Architectural commits most relevant to the topic.
    """
    limit = min(max(1, limit), 50)
    arch_categories = {"arch", "architecture", "refactor", "migration", "redesign"}
    query = f"architecture design decision {topic}".strip()

    # ChromaDB: category-filtered search for arch categories + unfiltered semantic
    chroma_arch = []
    for cat in arch_categories:
        chroma_arch += get_chroma().search(query=query, n_results=limit, category=cat, repo=REPO_NAME)

    # Also do an unfiltered semantic search — catches 'feat' commits that are
    # architecturally significant but weren't categorised as refactor/migration
    chroma_broad = get_chroma().search(query=query, n_results=limit, repo=REPO_NAME)
    chroma_results = chroma_arch + [r for r in chroma_broad
                                    if r["commit_hash"] not in
                                    {x["commit_hash"] for x in chroma_arch}]

    # Mem0: fallback + learned context
    mem0_results = []
    try:
        raw = get_memory().search(query=query, user_id=USER_ID, limit=limit * 2)
        mem0_results = _dedupe([_format_result(r) for r in _unwrap(raw)])
    except Exception as exc:
        log.warning("Mem0 arch search failed: %s", exc)

    merged = _merge_results(chroma_results, mem0_results)

    # Prefer arch-category commits, but include others as fallback
    arch_first = [r for r in merged if r.get("category") in arch_categories]
    others     = [r for r in merged if r.get("category") not in arch_categories]
    combined   = (arch_first + others)[:limit]

    return combined if combined else [{"message": "No architectural commits found"}]


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run()
