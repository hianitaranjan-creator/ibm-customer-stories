"""
apply-corrections.py
--------------------
Reads corrections.json (exported from the Review Queue in the dashboard)
and permanently applies those corrections to all-case-studies.json.

Run this after exporting corrections from the dashboard, then run
7_REFRESH_DASHBOARD.bat to rebuild the dashboard with the fixed data.

Usage:
    .venv\\Scripts\\python.exe scripts\\apply-corrections.py
    .venv\\Scripts\\python.exe scripts\\apply-corrections.py --corrections path\\to\\corrections.json
"""

import json
import os
import sys
import shutil
from datetime import datetime

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CORRECTIONS = os.path.join(ROOT, "corrections.json")
STORIES_FILE        = os.path.join(ROOT, "public", "data", "all-case-studies.json")

# ── Parse args ────────────────────────────────────────────────────────────────
corrections_path = DEFAULT_CORRECTIONS
for i, arg in enumerate(sys.argv[1:], 1):
    if arg == "--corrections" and i < len(sys.argv):
        corrections_path = sys.argv[i + 1]

# ── Load corrections ──────────────────────────────────────────────────────────
if not os.path.isfile(corrections_path):
    print(f"No corrections file found at: {corrections_path}")
    print("Export corrections from the dashboard Review Queue first.")
    sys.exit(0)

with open(corrections_path, encoding="utf-8") as f:
    corr_data = json.load(f)

corrections = corr_data.get("corrections", [])
if not corrections:
    print("corrections.json is empty — nothing to apply.")
    sys.exit(0)

print(f"Loaded {len(corrections)} corrections from {corrections_path}")

# ── Load stories ──────────────────────────────────────────────────────────────
if not os.path.isfile(STORIES_FILE):
    print(f"Stories file not found: {STORIES_FILE}")
    sys.exit(1)

with open(STORIES_FILE, encoding="utf-8") as f:
    data = json.load(f)

stories = data.get("stories", [])
print(f"Loaded {len(stories)} stories from {STORIES_FILE}")

# Index by story_id for fast lookup
index = {s["story_id"]: s for s in stories if "story_id" in s}

# Also try matching by source_url as a fallback (story IDs reset each run)
url_index = {s.get("source_url", ""): s for s in stories}

# ── Apply corrections ─────────────────────────────────────────────────────────
applied = 0
skipped = 0

for c in corrections:
    story_id   = c.get("story_id", "")
    source_url = c.get("source_url", "")
    field      = c.get("field", "")
    value      = c.get("value", "")

    if not field or not value:
        skipped += 1
        continue

    # Find the story — prefer source_url match (robust across re-runs)
    story = url_index.get(source_url) or index.get(story_id)

    if not story:
        print(f"  WARN: story not found for {story_id} / {source_url} — skipping")
        skipped += 1
        continue

    old_val = story.get(field, "")
    story[field] = value
    applied += 1
    print(f"  ✓  {story.get('customer_name','?')[:40]}  [{field}]  '{old_val}' → '{value}'")

# ── Write back ────────────────────────────────────────────────────────────────
# Make a timestamped backup first
backup_path = STORIES_FILE.replace(".json", f"_backup_{datetime.now():%Y%m%d_%H%M%S}.json")
shutil.copy2(STORIES_FILE, backup_path)
print(f"\nBackup saved: {backup_path}")

data["stories"] = stories
with open(STORIES_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n✅ Applied {applied} corrections, skipped {skipped}.")
print(f"   {STORIES_FILE} updated.")
print("\nNext step: run 7_REFRESH_DASHBOARD.bat to rebuild the dashboard.")
