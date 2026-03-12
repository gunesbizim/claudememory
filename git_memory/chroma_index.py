"""
ChromaDB layer for git commits.
1 document = 1 commit — no fragmentation, no LLM extraction overhead.
"""

import logging
import os
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

log = logging.getLogger(__name__)

CHROMA_DIR  = os.getenv("GIT_MEMORY_CHROMA_DIR",
                         str(Path.home() / ".cache" / "git_memory" / "chroma_commits"))
OLLAMA_URL  = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.getenv("GIT_MEMORY_EMBED_MODEL", "nomic-embed-text")
COLLECTION  = "git_commits"


def _build_document(commit_hash, author, date, message, stats, files):
    files_str = ", ".join(files) if files else "none"
    return (
        f"{message.strip()}\n"
        f"Author: {author}\n"
        f"Date: {date}\n"
        f"Stats: {stats}\n"
        f"Files: {files_str}"
    )


class ChromaCommitIndex:
    """1 ChromaDB document per Git commit — fast, accurate, no LLM overhead."""

    def __init__(self, chroma_dir=CHROMA_DIR, ollama_url=OLLAMA_URL, embed_model=EMBED_MODEL):
        Path(chroma_dir).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=chroma_dir)
        self._ef = OllamaEmbeddingFunction(
            url=f"{ollama_url}/api/embeddings",
            model_name=embed_model,
        )
        self._col = self._client.get_or_create_collection(
            name=COLLECTION,
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_commit(self, commit_hash, author_name, author_email, committed_date,
                      message, category, files, stats_str, repo) -> bool:
        if self._col.get(ids=[commit_hash])["ids"]:
            return False
        self._col.add(
            ids=[commit_hash],
            documents=[_build_document(
                commit_hash, f"{author_name} <{author_email}>",
                committed_date[:10], message, stats_str, files,
            )],
            metadatas=[{
                "short_hash":     commit_hash[:8],
                "author_name":    author_name,
                "author_email":   author_email,
                "committed_date": committed_date,
                "category":       category,
                "repo":           repo,
                "files_str":      "|".join(files),
                "date_str":       committed_date[:10],
            }],
        )
        return True

    def search(self, query, n_results=10, category=None, repo=None) -> list[dict]:
        where = self._build_where(category=category, repo=repo)
        kwargs = dict(
            query_texts=[query],
            n_results=min(n_results, max(1, self._col.count())),
            include=["documents", "metadatas", "distances"],
        )
        if where:
            kwargs["where"] = where
        try:
            return self._format_results(self._col.query(**kwargs))
        except Exception as exc:
            log.error("Chroma search error: %s", exc)
            return []

    def get_latest(self, n=10, repo=None) -> list[dict]:
        where = self._build_where(repo=repo)
        count = self._col.count()
        if count == 0:
            return []
        kwargs = dict(limit=min(count, max(n * 3, 50)), include=["documents", "metadatas"])
        if where:
            kwargs["where"] = where
        try:
            raw = self._col.get(**kwargs)
        except Exception as exc:
            log.error("Chroma get_latest error: %s", exc)
            return []
        records = [
            {
                "commit_hash":   raw["ids"][i],
                "short_hash":    raw["metadatas"][i].get("short_hash", ""),
                "author":        raw["metadatas"][i].get("author_name", ""),
                "date":          raw["metadatas"][i].get("committed_date", ""),
                "category":      raw["metadatas"][i].get("category", "general"),
                "files_changed": [f for f in raw["metadatas"][i].get("files_str","").split("|") if f],
                "summary":       (raw.get("documents") or [""])[i],
                "source":        "chroma",
            }
            for i in range(len(raw["ids"]))
        ]
        records.sort(key=lambda r: r.get("date", ""), reverse=True)
        return records[:n]

    def search_by_file(self, filename, n_results=20) -> list[dict]:
        try:
            all_docs = self._col.get(include=["metadatas", "documents"])
            matched = [
                {
                    "commit_hash":   all_docs["ids"][i],
                    "short_hash":    m.get("short_hash", ""),
                    "author":        m.get("author_name", ""),
                    "date":          m.get("committed_date", ""),
                    "category":      m.get("category", "general"),
                    "files_changed": [f for f in m.get("files_str","").split("|") if f],
                    "summary":       (all_docs.get("documents") or [""])[i],
                    "source":        "chroma",
                }
                for i, m in enumerate(all_docs["metadatas"])
                if filename.lower() in m.get("files_str", "").lower()
            ]
            if matched:
                matched.sort(key=lambda r: r.get("date",""), reverse=True)
                return matched[:n_results]
        except Exception:
            pass
        return self.search(f"changes to {filename}", n_results=n_results)

    def count(self) -> int:
        return self._col.count()

    @staticmethod
    def _build_where(category=None, repo=None) -> Optional[dict]:
        conds = []
        if category: conds.append({"category": {"$eq": category}})
        if repo:     conds.append({"repo":     {"$eq": repo}})
        if not conds:        return None
        if len(conds) == 1:  return conds[0]
        return {"$and": conds}

    @staticmethod
    def _format_results(raw) -> list[dict]:
        ids, docs, metas, dists = (
            raw.get("ids",[[]])[0], raw.get("documents",[[]])[0],
            raw.get("metadatas",[[]])[0], raw.get("distances",[[]])[0],
        )
        return [
            {
                "commit_hash":     h,
                "short_hash":      metas[i].get("short_hash", h[:8]),
                "author":          metas[i].get("author_name", "unknown"),
                "date":            metas[i].get("committed_date", ""),
                "category":        metas[i].get("category", "general"),
                "files_changed":   [f for f in metas[i].get("files_str","").split("|") if f],
                "summary":         docs[i] if docs else "",
                "relevance_score": round(1.0 - float(dists[i] if dists else 1.0), 4),
                "source":          "chroma",
            }
            for i, h in enumerate(ids)
        ]
