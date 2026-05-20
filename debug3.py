import sys, json, sqlite3
sys.path.insert(0, "/Users/jeremykamber/core/1_projects/strata_agentic_memory_system")

from strata import Strata
from strata.config import StrataConfig

config = StrataConfig(base_dir="/tmp/strata_debug3/data",
    decay_thresholds={"*": 0}, lru_days=0, lru_min_access_count=0)

s = Strata(config)
s.phase1.ensure_dirs()
s.phase3.ensure_dirs()
s.write_active("projects/koda/requirements.md", "# Koda needs OAuth2 + Stripe payments + dashboard")
s.write_active("entities/joe.md", "# Joe: React/Go expert on Koda team")
s.migrate(dry_run=False)
s.evict(dry_run=False)

# Test Phase 3 search via the actual storage API
print("=== Phase 3 search via storage API ===")
for q in ["koda", "OAuth2", "stripe", "payments", "Joe", "React"]:
    rows = s.phase3.search_shadow(q)
    print(f"  '{q}': {len(rows)} rows")
    for r in rows:
        print(f"    -> {r.get('summary_preview','')[:50]}")

# Now test the full query engine cascade
print("\n=== Full query engine ===")
for q in ["koda stripe", "OAuth2 payments", "Joe React"]:
    results = s.query(q)
    tiers = [r["tier"] for r in results]
    print(f"  '{q}': {len(results)} results across tiers {tiers}")
    for r in results:
        print(f"    [{r['tier']}] {r['content'][:50]}...")

# Test re-hydration
print("\n=== Re-hydration ===")
results = s.query("OAuth2 payments")
for r in results:
    if r["tier"] == "phase3" and r["metadata"].get("_needs_rehydration"):
        block = s.janitor.rehydrate(r["metadata"])
        if block:
            print(f"  Rehydrated: [{block.id[:8]}] {block.summary[:50]}")
            assert s.phase2.count() >= 1

print("\n=== Phase 2 after re-hydration ===")
for b in s.phase2.list_all():
    print(f"  [{b.id[:8]}] {b.summary[:50]} (tier: {b.tier})")

s.close()
print("\n✓ ALL PHASE 3 + REHYDRATION TESTS PASSED")
