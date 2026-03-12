#!/usr/bin/env python3
"""
Realistic Claude-style queries against the lokumcu memory index.
Tests both layers (ChromaDB + Mem0) with questions a developer would actually ask.
"""
import os, sys
os.environ["GIT_MEMORY_REPO_PATH"] = "../lokumcu"
os.environ["GIT_MEMORY_USER_ID"]   = "lokumcu"
sys.path.insert(0, "ai")

from git_memory_mcp_server import (
    search_git_history,
    latest_commits,
    commits_touching_file,
    bug_fix_history,
    architecture_decisions,
)

W = 64
def header(title): print(f"\n{'═'*W}\n  {title}\n{'═'*W}")
def rule():        print(f"{'─'*W}")

def show(results, max_items=5):
    for r in results[:max_items]:
        if "error" in r or "message" in r:
            print(f"  ⚠  {r}")
            continue
        score = r.get("relevance_score")
        score_str = f"  score={score:.3f}" if score else ""
        src = "✦" if r.get("source","") == "chroma" else "◆"
        print(f"  {src} [{r.get('short_hash','?')}] {r.get('date','')[:10]}  "
              f"{r.get('category','').upper():<12}{score_str}")
        # First line of summary
        summary = r.get("summary","").splitlines()[0][:75]
        if summary: print(f"      {summary}")
        files = r.get("files_changed",[])
        if files:
            shown = ", ".join(f.split("/")[-1] for f in files[:3])
            more  = f" +{len(files)-3} more" if len(files)>3 else ""
            print(f"      Files: {shown}{more}")
        ctx = r.get("learned_context",[])
        if ctx:
            print(f"      🧠 Mem0: {ctx[0][:80]}")
        print()

# ── 1. Payment bugs ───────────────────────────────────────────────────────────
header("Q1  bug_fix_history('payments')")
print("  → What bugs were fixed in the payment flow?\n")
show(bug_fix_history("payments", limit=5))

# ── 2. 3DS flow ───────────────────────────────────────────────────────────────
header("Q2  search_git_history('3DS callback state machine')")
print("  → How was the Garanti 3DS payment callback handled?\n")
show(search_git_history("3DS callback state machine", limit=4))

# ── 3. Recent changes ─────────────────────────────────────────────────────────
header("Q3  latest_commits(8)")
print("  → What changed recently in the project?\n")
show(latest_commits(8), max_items=8)

# ── 4. Discount system evolution ─────────────────────────────────────────────
header("Q4  search_git_history('discount code cart', category='fix')")
print("  → What discount-related bugs were fixed?\n")
show(search_git_history("discount code cart", category="fix", limit=5))

# ── 5. Auth architecture ──────────────────────────────────────────────────────
header("Q5  architecture_decisions('auth password')")
print("  → How was authentication designed/changed?\n")
show(architecture_decisions("auth password", limit=5))

# ── 6. Who touched PaymentService ────────────────────────────────────────────
header("Q6  commits_touching_file('PaymentService.php')")
print("  → All commits that modified PaymentService.php\n")
show(commits_touching_file("PaymentService.php", limit=6), max_items=6)

# ── 7. Role & permissions ─────────────────────────────────────────────────────
header("Q7  search_git_history('role permission dealer customer representative')")
print("  → How was the role/permission system built?\n")
show(search_git_history("role permission dealer customer representative", limit=5))

# ── 8. Image upload pipeline ──────────────────────────────────────────────────
header("Q8  commits_touching_file('ImageHelper')")
print("  → What changed in the image handling code?\n")
show(commits_touching_file("ImageHelper", limit=4), max_items=4)

# ── 9. Security fixes ────────────────────────────────────────────────────────
header("Q9  bug_fix_history('orders', include_security=True)")
print("  → Security and correctness fixes in orders\n")
show(bug_fix_history("orders", include_security=True, limit=5))

# ── 10. Migration history ─────────────────────────────────────────────────────
header("Q10 search_git_history('database migration schema')")
print("  → What schema migrations were added?\n")
show(search_git_history("database migration schema", limit=5))

print(f"\n{'═'*W}")
print("  ✦ = ChromaDB (structured, 1 doc/commit, cosine score)")
print("  ◆ = Mem0 fallback   🧠 = Mem0 learned context")
print(f"{'═'*W}\n")
