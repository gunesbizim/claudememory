---
name: claude-memory-search
description: "Use when the user asks about why code was written a certain way, wants to find commits related to a bug, feature or module, or needs historical context before editing. Examples: \"why does the payment module use a state machine?\", \"what commits touched auth?\", \"find all discount-related bug fixes\""
---

# Search Git History with claude-memory

## When to Use

- User asks *why* something was built a certain way
- User is about to edit a module and needs context
- User reports a bug that may have been fixed before
- User asks about a past decision, refactor, or migration
- You need to understand the evolution of a component

## Workflow

```
1. Identify the topic/component from the user's question
2. Call search_git_history(query, limit=8)
3. If results are few, also call bug_fix_history(component)
4. If the user mentions a specific file, call commits_touching_file(filename)
5. Synthesise results into a clear narrative for the user
```

## Checklist

```
- [ ] Called search_git_history with a descriptive query
- [ ] Applied category filter if user is looking for a specific type (fix, feat, security)
- [ ] Checked commits_touching_file if a specific file is involved
- [ ] Included commit hashes in the answer so user can run git show
- [ ] Noted the date range of relevant commits
```

## Tool Details

### search_git_history
```python
search_git_history(
    query="payment state machine race condition",
    limit=8,
    category="fix"   # optional: fix | feat | security | refactor | migration | arch | perf
)
```
Returns commits ranked by cosine similarity (0–1 score). Score > 0.7 = highly relevant.

### commits_touching_file
```python
commits_touching_file(
    filename="PaymentService.php",   # partial match supported
    limit=10
)
```
Returns all commits that modified the file, newest first, enriched with ChromaDB category.

### bug_fix_history
```python
bug_fix_history(
    component="payments",
    limit=8,
    include_security=True
)
```
Returns fix/bug/hotfix/security commits for the component, ranked by relevance.

### architecture_decisions
```python
architecture_decisions(
    topic="state machine order transitions",
    limit=5
)
```
Returns refactor/migration/arch commits. Useful for "why is this designed this way?" questions.

## Example

**User:** "Why does the payment flow go through a state machine?"

```
1. search_git_history("payment state machine order transitions", limit=5)
   → [32c3389f] fix(payments): route 3DS callback through transitionStatus
     score=0.633 — "Replace direct repository updates with transitionStatus
     calls to enforce the allowed-transitions guard"

2. commits_touching_file("PaymentService.php", limit=5)
   → [32c3389f] fix(payments): route 3DS callback...
   → [599d531b] feat: add Garanti 3DS payments...
   → [114802b8] fix: Fix database column bug user_id→customer_id in PaymentService

3. Answer: "The state machine was introduced in commit 32c3389f to prevent
   race conditions on 3DS callbacks — direct status updates were bypassing
   the transition guards and triggering wrong notifications."
```
