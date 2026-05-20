import sys, json, sqlite3
sys.path.insert(0, "/Users/jeremykamber/core/1_projects/strata_agentic_memory_system")

from strata import Strata
from strata.config import StrataConfig

config = StrataConfig(base_dir="/tmp/strata_debug2/data",
    decay_thresholds={"*": 0}, lru_days=0, lru_min_access_count=0)

s = Strata(config)
s.phase1.ensure_dirs()
s.phase3.ensure_dirs()
s.write_active("projects/koda/requirements.md", "# Koda needs OAuth2 + Stripe payments + dashboard")
s.write_active("entities/joe.md", "# Joe: React/Go expert on Koda team")
s.migrate(dry_run=False)
s.evict(dry_run=False)

# Direct SQL to test FTS
db = sqlite3.connect(str(config.phase3_shadow_path()))

# Test various FTS queries
queries = ["koda", "stripe", "oauth", "oauth stripe", "OAuth2", "payments", "*"]
for q in queries:
    try:
        rows = db.execute(
            """SELECT si.* FROM shadow_index si
               JOIN shadow_fts fts ON si.rowid = fts.rowid
               WHERE shadow_fts MATCH ?
               ORDER BY rank""", (q,)
        ).fetchall()
        print(f"  '{q}': {len(rows)} rows")
        if rows:
            for r in rows:
                print(f"    id={r['id'][:8]} preview={r['summary_preview'][:50]}")
    except Exception as e:
        print(f"  '{q}': ERROR - {e}")

# Show raw shadow_fts content
print("\nShadow FTS rows:")
for row in db.execute("SELECT rowid, * FROM shadow_fts").fetchall():
    print(f"  FTS rowid={row['rowid']}, keywords={str(row['keywords'])[:40]}, summary={str(row['summary_preview'])[:50]}")
s.close()
