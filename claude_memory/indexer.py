"""
Dual-layer Git commit indexer.
Writes each commit to ChromaDB (facts) + Mem0 (learned context).
"""

import argparse
import logging
import os
from pathlib import Path
from typing import Optional

import git
from mem0 import Memory

from claude_memory.filters      import is_relevant, summarize_commit, build_metadata
from claude_memory.chroma_index import ChromaCommitIndex

log = logging.getLogger(__name__)


class ClaudeMemoryIndexer:
    """Indexes relevant commits into ChromaDB (Layer 1) and Mem0 (Layer 2)."""

    def __init__(self, repo_path=".", mem0_config=None, user_id="claude_memory_system"):
        self.repo      = git.Repo(repo_path, search_parent_directories=True)
        self.repo_name = Path(self.repo.working_dir).name
        self.user_id   = user_id
        self.chroma    = ChromaCommitIndex()
        try:
            self.memory = Memory.from_config(mem0_config or self._default_mem0_config())
        except Exception as exc:
            print(f"⚠ Mem0/Ollama unavailable — Layer 2 (semantic context) disabled: {exc}")
            print("  To enable it, install and start Ollama: https://ollama.com")
            print("  Or set OPENAI_API_KEY to use OpenAI embeddings instead.")
            self.memory = None
        log.info("Repo   : %s  User: %s  Chroma: %d docs",
                 self.repo_name, user_id, self.chroma.count())

    @staticmethod
    def _default_mem0_config() -> dict:
        if key := os.getenv("MEM0_API_KEY"):
            return {"api_key": key}
        chroma_path = str(Path.home() / ".cache" / "claude_memory" / "chroma")
        vector_store = {
            "provider": "chroma",
            "config": {"collection_name": "claude_memory", "path": chroma_path},
        }
        embed_provider = os.getenv("CLAUDE_MEMORY_EMBED_PROVIDER", "ollama")
        if embed_provider == "openai" or os.getenv("OPENAI_API_KEY"):
            embedder = {"provider": "openai", "config": {
                "model": os.getenv("CLAUDE_MEMORY_EMBED_MODEL", "text-embedding-3-small"),
                "api_key": os.getenv("OPENAI_API_KEY"),
            }}
            llm = {"provider": "openai", "config": {
                "model": os.getenv("CLAUDE_MEMORY_LLM_MODEL", "gpt-4o-mini"),
                "api_key": os.getenv("OPENAI_API_KEY"),
            }}
        else:
            embedder = {"provider": "ollama", "config": {
                "model": os.getenv("CLAUDE_MEMORY_EMBED_MODEL", "nomic-embed-text"),
            }}
            llm = {"provider": "ollama", "config": {
                "model": os.getenv("CLAUDE_MEMORY_LLM_MODEL", "qwen2.5"),
            }}
        return {"vector_store": vector_store, "embedder": embedder, "llm": llm}

    def index_commit(self, commit: git.Commit, force=False) -> bool:
        if not is_relevant(commit.message) and not force:
            return False

        meta    = build_metadata(commit, self.repo_name)
        summary = summarize_commit(commit)
        stats   = summary.split("Stats: ")[-1].split("\n")[0] if "Stats:" in summary else ""

        # Layer 1 — ChromaDB (dedup gate)
        try:
            inserted = self.chroma.upsert_commit(
                commit_hash=commit.hexsha,
                author_name=meta["author_name"],
                author_email=meta["author_email"],
                committed_date=meta["committed_date"],
                message=commit.message.strip(),
                category=meta["category"],
                files=meta["files_changed"],
                stats_str=stats,
                repo=self.repo_name,
            )
        except Exception as exc:
            log.error("Chroma insert failed %s: %s", commit.hexsha[:8], exc)
            inserted = False

        if not inserted and not force:
            return False

        # Layer 2 — Mem0 (interpretations)
        if self.memory is not None:
            try:
                self.memory.add(
                    messages=[{"role": "user", "content": summary}],
                    user_id=self.user_id,
                    metadata=meta,
                )
            except Exception as exc:
                log.warning("Mem0 failed for %s (Chroma OK): %s", commit.hexsha[:8], exc)

        log.info("Stored [%s] %s (%s)",
                 meta["short_hash"], commit.message.splitlines()[0][:72], meta["category"])
        return True

    def index_all(self, branch="HEAD", limit=None, dry_run=False) -> dict:
        commits = list(self.repo.iter_commits(branch, max_count=limit))
        log.info("Found %d commits to evaluate", len(commits))
        stored = irrelevant = dupes = errors = 0

        for i, commit in enumerate(commits, 1):
            if i % 100 == 0:
                log.info("Progress: %d / %d", i, len(commits))
            if not is_relevant(commit.message):
                irrelevant += 1
                continue
            if dry_run:
                log.info("[DRY-RUN] %s  %s", commit.hexsha[:8], commit.message.splitlines()[0][:72])
                stored += 1
                continue
            try:
                if self.index_commit(commit):
                    stored += 1
                else:
                    dupes += 1
            except Exception as exc:
                log.error("Error %s: %s", commit.hexsha[:8], exc)
                errors += 1

        stats = dict(total_evaluated=len(commits), stored=stored,
                     skipped_irrelevant=irrelevant, skipped_duplicate=dupes, errors=errors)
        log.info("Done. %s", stats)
        return stats


def main():
    p = argparse.ArgumentParser(description="Bulk-index Git history into ChromaDB + Mem0.")
    p.add_argument("--repo-path", default=".")
    p.add_argument("--branch",    default="HEAD")
    p.add_argument("--limit",     type=int, default=None)
    p.add_argument("--user-id",   default="claude_memory_system")
    p.add_argument("--dry-run",   action="store_true")
    args = p.parse_args()

    indexer = ClaudeMemoryIndexer(repo_path=args.repo_path, user_id=args.user_id)
    stats   = indexer.index_all(branch=args.branch, limit=args.limit, dry_run=args.dry_run)

    print("\n── Indexing Summary ──────────────────────────")
    for k, v in stats.items():
        print(f"  {k:<25} {v}")


if __name__ == "__main__":
    main()
