#!/usr/bin/env python3
"""Shim — real implementation lives in git_memory.store."""
import sys
import argparse
from pathlib import Path
from git_memory.indexer import GitMemoryIndexer
from git_memory.filters import is_relevant


def main():
    p = argparse.ArgumentParser(description="Store a single commit into ChromaDB + Mem0.")
    p.add_argument("commit_ref", nargs="?", default="HEAD")
    p.add_argument("--repo-path", default=".")
    p.add_argument("--user-id",   default="git_memory_system")
    p.add_argument("--force",     action="store_true")
    args = p.parse_args()

    import git
    repo   = git.Repo(args.repo_path, search_parent_directories=True)
    commit = repo.commit(args.commit_ref)

    if not is_relevant(commit.message) and not args.force:
        sys.exit(1)

    indexer = GitMemoryIndexer(repo_path=args.repo_path, user_id=args.user_id)
    stored  = indexer.index_commit(commit, force=args.force)
    sys.exit(0 if stored else 1)


if __name__ == "__main__":
    main()
