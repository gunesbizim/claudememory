# claudememory

[![PyPI version](https://img.shields.io/pypi/v/claudememory)](https://pypi.org/project/claudememory/)
[![Python](https://img.shields.io/pypi/pyversions/claudememory)](https://pypi.org/project/claudememory/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)

> Give Claude Code a long-term memory of your Git history.

---

## The problem

Claude Code is great at reading your current codebase — but it has no memory of *why* things were built the way they are.

Every session starts fresh. Ask it why a module was refactored, which bugs have hit the payment service before, or what architectural decision introduced the current state machine — and it has no answer. That context lives in your Git history, but it's inaccessible to the AI.

**claudememory solves this.** It indexes your entire Git commit history into a dual-layer semantic store and exposes it to Claude Code via MCP. Claude can now answer:

- *"Has the auth module had bugs before?"*
- *"Why was this abstraction introduced?"*
- *"What changed in PaymentService over the last year?"*
- *"What commits touched this file?"*

---

## How it works

Two storage layers work together on every indexed commit:

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Facts layer** | ChromaDB | 1 document per commit — cosine similarity search, metadata filters, zero LLM overhead |
| **Context layer** | Mem0 | LLM-extracted interpretation — the *why* behind each change, cross-session learned context |

ChromaDB acts as the ground truth (fast, accurate, deduplicated). Mem0 enriches results with learned context over time. Claude sees both merged together.

---

## Install

```bash
pip install claudememory
```

[![PyPI](https://img.shields.io/badge/PyPI-claudememory-blue?logo=pypi)](https://pypi.org/project/claudememory/)

No external services required. Ollama is optional — if it's not running, claudememory falls back to ChromaDB-only mode automatically.

| Mode | Setup | Cost |
|------|-------|------|
| **ChromaDB only** (no setup) | Nothing | Free, works immediately |
| **Ollama** | `ollama pull nomic-embed-text` | Free, fully local, adds semantic layer |
| **sentence-transformers** | `pip install "claudememory[sentence-transformers]"` | Free, fully local, no Ollama |
| **OpenAI** | `pip install "claudememory[openai]"` + `OPENAI_API_KEY` | ~$0.0001/commit |

---

## Quick start

```bash
cd /your/repo

# 1. Index your repository (run from inside the repo)
claude-memory index

# 2. Install Claude Code skills + MCP config
claude-memory install

# 3. Restart Claude Code — then use /claude-memory-search, /claude-memory-debug etc.
```

After setup, Claude Code automatically has access to your commit history. No prompting required — it calls the tools proactively based on what you're working on.

---

## MCP tools exposed to Claude

| Tool | What Claude can ask |
|------|---------------------|
| `search_git_history(query)` | *"Find commits related to discount logic"* |
| `latest_commits(limit)` | *"What changed while I was away?"* |
| `commits_touching_file(filename)` | *"What's the history of PaymentService?"* |
| `bug_fix_history(component)` | *"Has auth had bugs before?"* |
| `architecture_decisions(topic)` | *"Why was the state machine introduced?"* |

---

## Claude Code skills

| Skill | Trigger |
|-------|---------|
| `/claude-memory-search` | Search commit history for a topic |
| `/claude-memory-index` | Index a new repository |
| `/claude-memory-status` | Check what's indexed |
| `/claude-memory-debug` | Debug a regression with full history |

---

## CLI reference

```bash
claude-memory index                    # bulk index all commits (run from repo root)
claude-memory install                  # install Claude Code plugin (run from repo root)
claude-memory status                   # show indexed coverage
claude-memory serve                    # start MCP server (stdio)
claude-memory store HEAD               # store single commit (post-commit hook)

# Optional flags
claude-memory index --repo-path /other/repo --user-id myapp
claude-memory status --repo-path /other/repo
```

---

## Configuration

All settings via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_MEMORY_REPO_PATH` | `.` | Repository to index |
| `CLAUDE_MEMORY_USER_ID` | `claude_memory_system` | Mem0 namespace (use per-repo names) |
| `CLAUDE_MEMORY_CHROMA_DIR` | `~/.cache/claude_memory/chroma_commits` | ChromaDB storage path |
| `CLAUDE_MEMORY_EMBED_PROVIDER` | `ollama` | Embedding backend: `ollama`, `openai`, `sentence-transformers` |
| `CLAUDE_MEMORY_EMBED_MODEL` | *(provider default)* | Override embedding model name |
| `CLAUDE_MEMORY_LLM_MODEL` | *(provider default)* | Override LLM model name (Mem0 layer) |
| `OPENAI_API_KEY` | *(empty)* | Enables OpenAI embeddings + LLM automatically |
| `MEM0_API_KEY` | *(empty)* | Use Mem0 cloud instead of local inference |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama endpoint |

---

## Better with conventional commits

claudememory automatically categorizes every commit by scanning its message for keywords. If you already use [Conventional Commits](https://www.conventionalcommits.org/) (`fix:`, `feat:`, `refactor:`, etc.), the tool works out of the box with near-perfect accuracy.

Here's why it matters:

```
# Without conventional commits
"updated payment stuff"         → category: general (no signal)
"fixed the thing"               → category: fix ✓

# With conventional commits
"fix(payments): race condition" → category: fix ✓
"feat(auth): add OAuth2 flow"  → category: feat ✓
"refactor: extract BaseService" → category: refactor ✓
"perf(queries): add index"     → category: perf ✓
```

The categorizer maps directly to these prefixes:

| Commit prefix | claudememory category | Queryable via |
|---------------|----------------------|---------------|
| `fix:`, `hotfix:`, `patch:` | `fix` | `bug_fix_history()` |
| `feat:`, `feature:` | `feat` | `search_git_history(category="feat")` |
| `refactor:` | `refactor` | `architecture_decisions()` |
| `perf:` | `perf` | `search_git_history(category="perf")` |
| `security:` | `security` | `bug_fix_history(include_security=True)` |
| `revert:` | `revert` | `bug_fix_history()` |

Commits without any recognized keyword are still indexed but categorized as `general`. The relevance filter also uses these keywords to decide which commits are worth indexing at all, so well-written conventional commit messages mean higher coverage and better search results.

You don't need conventional commits to use claudememory. But if you adopt them, every tool gets smarter automatically.

---

## Works great alongside [GitNexus](https://github.com/abhigyanpatwari/GitNexus)

These two tools answer different questions and are better together:

| Question | Tool |
|----------|------|
| What does this function call? | GitNexus |
| Why was this function written this way? | claudememory |
| What will break if I change this? | GitNexus |
| Has this area had bugs before? | claudememory |
| What changed recently? | claudememory |
