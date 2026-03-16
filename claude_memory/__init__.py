"""
claudememory — Dual-layer ChromaDB + Mem0 commit index for Claude Code.

Layers:
  ChromaDB  — 1 document per commit, cosine similarity, metadata filters
  Mem0      — LLM-extracted context, cross-session learned interpretation

Usage:
    claude-memory index --repo-path /path/to/repo
    claude-memory serve
    claude-memory install   # installs Claude Code plugin
"""

__version__ = "0.1.7"
__author__  = "Güneş Bizim"

from claude_memory.chroma_index import ChromaCommitIndex
from claude_memory.indexer      import ClaudeMemoryIndexer
from claude_memory.filters      import is_relevant, summarize_commit, build_metadata

__all__ = [
    "ChromaCommitIndex",
    "ClaudeMemoryIndexer",
    "is_relevant",
    "summarize_commit",
    "build_metadata",
]
