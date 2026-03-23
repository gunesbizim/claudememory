<!-- claude-memory:start -->

# Claude Memory System

This project uses **claudememory** — a dual-layer semantic index over Git commit history for Claude Code.

## Always Start Here

When beginning any task in this repository:

1. Call `latest_commits(5)` to understand what changed recently
2. Call `search_git_history(<relevant topic>)` before touching any module with history
3. After fixing a bug, call `bug_fix_history(<component>)` to check for prior regressions

## Available Skills

| Task | Skill |
|------|-------|
| Search commit history for a topic | `/claude-memory-search` |
| Index a new repository | `/claude-memory-index` |
| Debug why a component behaves a certain way | `/claude-memory-debug` |
| Check what's currently indexed | `/claude-memory-status` |

## MCP Tools Reference

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

<!-- claude-memory:end -->

<!-- gitnexus:start -->
# GitNexus MCP

This project is indexed by GitNexus as **claudememory** (115 symbols, 140 relationships, 0 execution flows).

## Always Start Here

1. **Read `gitnexus://repo/{name}/context`** — codebase overview + check index freshness
2. **Match your task to a skill below** and **read that skill file**
3. **Follow the skill's workflow and checklist**

> If step 1 warns the index is stale, run `npx gitnexus analyze` in the terminal first.

## Skills

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
