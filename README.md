# git-memory

Dual-layer semantic index over Git commit history for Claude Code.

| Layer | Purpose |
|-------|---------|
| **ChromaDB** | 1 document/commit, cosine similarity, metadata filters — fast, authoritative facts |
| **Mem0** | LLM-extracted context, cross-session learned interpretation — the *why* layer |

## Install

```bash
pip install git-memory
```

Requires [Ollama](https://ollama.com) running locally with `nomic-embed-text` pulled:
```bash
ollama pull nomic-embed-text
```

## Quick start

```bash
# 1. Index your repository
git-memory index --repo-path /path/to/repo --user-id my-repo

# 2. Install Claude Code skills + MCP config
git-memory install --repo-path /path/to/repo --user-id my-repo

# 3. Restart Claude Code — then use /git-memory-search, /git-memory-debug etc.
```

## MCP tools

| Tool | Description |
|------|-------------|
| `search_git_history(query)` | Semantic search over commit history |
| `latest_commits(limit)` | N most-recent indexed commits |
| `commits_touching_file(filename)` | All commits that modified a file |
| `bug_fix_history(component)` | Bug/security fixes for a component |
| `architecture_decisions(topic)` | Refactors, migrations, design decisions |

## CLI

```bash
git-memory index    --repo-path . --user-id myapp   # bulk index
git-memory serve                                     # start MCP server (stdio)
git-memory status   --repo-path .                    # show coverage
git-memory install  --repo-path . --user-id myapp   # install plugin
git-memory store    HEAD                             # store single commit (hook)
```

## Configuration

All settings via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GIT_MEMORY_REPO_PATH` | `.` | Repository to index |
| `GIT_MEMORY_USER_ID` | `git_memory_system` | Mem0 namespace (use per-repo names) |
| `GIT_MEMORY_CHROMA_DIR` | `~/.cache/git_memory/chroma_commits` | ChromaDB storage path |
| `MEM0_API_KEY` | *(empty)* | Use Mem0 cloud instead of local Ollama |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama endpoint |

## Works great alongside [GitNexus](https://github.com/your-org/gitnexus)

- GitNexus answers **what calls what** (structural, live code)
- git-memory answers **why it was written that way** (historical, commit-level)
