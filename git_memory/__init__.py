"""
git-memory — Dual-layer ChromaDB + Mem0 commit index for Claude Code.

Layers:
  ChromaDB  — 1 document per commit, cosine similarity, metadata filters
  Mem0      — LLM-extracted context, cross-session learned interpretation

Usage:
    git-memory index --repo-path /path/to/repo
    git-memory serve
    git-memory install   # installs Claude Code plugin
"""

__version__ = "0.1.0"
__author__  = "Güneş Bizim"

from git_memory.chroma_index import ChromaCommitIndex
from git_memory.indexer      import GitMemoryIndexer
from git_memory.filters      import is_relevant, summarize_commit, build_metadata

__all__ = [
    "ChromaCommitIndex",
    "GitMemoryIndexer",
    "is_relevant",
    "summarize_commit",
    "build_metadata",
]
