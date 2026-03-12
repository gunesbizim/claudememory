<!-- git-memory:start -->

# Git Memory System

This project provides **git-memory** — a dual-layer semantic index over Git commit history for Claude Code.

Two storage layers work together:
- **ChromaDB** — 1 document per commit, cosine similarity, metadata filters (fast, authoritative facts)
- **Mem0** — LLM-extracted context, cross-session learned interpretation (why things were built a certain way)

## Always Start Here

When beginning any task in a repository that has git-memory configured:

1. Call `latest_commits(5)` to understand what changed recently
2. Call `search_git_history(<relevant topic>)` before touching any module with history
3. After fixing a bug, call `bug_fix_history(<component>)` to check for prior regressions

## Available Skills

| Task | Skill |
|------|-------|
| Search commit history for a topic | `/git-memory-search` |
| Index a new repository | `/git-memory-index` |
| Debug why a component behaves a certain way | `/git-memory-debug` |
| Check what's currently indexed | `/git-memory-status` |

## MCP Tools Reference

These tools are available when the `git-memory` MCP server is running.

| Tool | What it gives you | When to use |
|------|-------------------|-------------|
| `search_git_history(query, limit, category)` | Commits semantically related to a topic | Before editing any significant module |
| `latest_commits(limit)` | N most-recent indexed commits | Session start, before investigating regressions |
| `commits_touching_file(filename, limit)` | All commits that modified a file | Before editing a file — understand its history |
| `bug_fix_history(component, include_security)` | Bug/security fixes for a component | Before adding new code near known bug areas |
| `architecture_decisions(topic, limit)` | Refactors, migrations, design decisions | Understanding why code is structured a certain way |

## Proactive Usage Rules

**Always call before editing:**
```
commits_touching_file("PaymentService.php")  # know what's broken here before
bug_fix_history("auth")                       # avoid re-introducing fixed bugs
```

**Always call at session start:**
```
latest_commits(10)   # what changed while you were away?
```

**Always call when confused about design:**
```
architecture_decisions("state machine")  # why was this abstraction introduced?
search_git_history("why was X removed")
```

## Category Filter Values

Use `category=` in `search_git_history()` to narrow results:

| Category | Matches |
|----------|---------|
| `fix`    | Bug fixes, hotfixes, patches |
| `feat`   | New features |
| `security` | Security-related changes |
| `refactor` | Code refactors |
| `migration` | Database/schema migrations |
| `arch`   | Architecture decisions |
| `perf`   | Performance improvements |

## Integration with GitNexus

If GitNexus is also configured, use both systems together:

| Question | Use |
|----------|-----|
| What does this function call? | GitNexus `context(symbol)` |
| Why was this function written this way? | git-memory `search_git_history(symbol)` |
| What will break if I change this? | GitNexus `impact(symbol)` |
| Has this area had bugs before? | git-memory `bug_fix_history(component)` |
| What changed recently? | git-memory `latest_commits(10)` |

## Setup for a New Repository

```bash
# 1. Index the repo
git-memory index --repo-path /path/to/repo --user-id my-repo

# 2. Install Claude Code plugin (skills + MCP config)
git-memory install --repo-path /path/to/repo --user-id my-repo

# 3. Restart Claude Code
```

<!-- git-memory:end -->
