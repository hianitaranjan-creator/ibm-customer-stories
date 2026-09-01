"""
run.py
------
Main entry point for the IBM Customer Stories application.

Usage (called by the .bat files — you do not need to run this directly):
  python run.py --mode test    # Process 10 stories only
  python run.py --mode full    # Process all stories

What happens:
  1. Discovers story URLs from the IBM case-studies website.
  2. Downloads each story page (uses cache if already downloaded).
  3. Parses each page to extract structured data and proof points.
  4. Classifies each proof point (GTM motion, proof strength, etc.).
  5. Builds the coverage matrix and evidence pipeline.
  6. Writes the Excel workbook.
  7. Writes the dashboard data file and HTML.
"""

import argparse
import sys
import time

# ── Argument parsing ───────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="IBM Customer Stories collector")
parser.add_argument(
    "--mode",
    choices=["test", "full"],
    default="test",
    help="'test' = 10 stories only, 'full' = all stories",
)
args = parser.parse_args()

test_mode = (args.mode == "test")

# ── Initialise logging ─────────────────────────────────────────────────────
from src import logger
from src.config import EXCEL_TEST, EXCEL_FULL

mode_label = "Test (10 stories)" if test_mode else "Full"
logger.init_run(mode_label)

start_time = time.time()

print()
print("=" * 60)
print(f"  IBM Customer Stories — {mode_label} mode")
print("=" * 60)
print()

# ── Step 1: Discover story URLs ────────────────────────────────────────────
from src.scraper import discover_story_urls, fetch_story
from src.config import TEST_STORY_LIMIT

print(f"Step 1: Discovering story URLs on www.ibm.com/case-studies …")
story_urls = discover_story_urls(test_mode=test_mode)

if not story_urls:
    print()
    print("ERROR: No story URLs were found.")
    print("Please check your internet connection and try again.")
    sys.exit(1)

print(f"        Found {len(story_urls)} story URL(s).")
print()

# ── Step 2: Download + parse each story ───────────────────────────────────
from src.parser import parse_story, qa_exceptions

stories: list[dict] = []
failed_urls: list[str] = []

total = len(story_urls)
for i, url in enumerate(story_urls, start=1):
    print(f"Step 2: Fetching story {i}/{total}: {url}")
    html = fetch_story(url)
    if not html:
        failed_urls.append(url)
        print(f"        FAILED — will record in QA sheet.")
        continue
    story = parse_story(url, html)
    stories.append(story)
    logger.increment("stories_processed")

print()
print(f"        Parsed {len(stories)} story/stories. {len(failed_urls)} failed.")
print()

# ── Step 3: Classify ───────────────────────────────────────────────────────
from src.classifier import classify_story

print("Step 3: Classifying proof points …")
all_proof_points: list[dict] = []
for story in stories:
    classify_story(story)
    all_proof_points.extend(story.get("proof_points", []))

print(f"        {len(all_proof_points)} proof point(s) classified.")
print()

# ── Step 4: Coverage matrix + evidence pipeline ────────────────────────────
from src.gap_analyzer import (
    build_coverage_matrix, build_evidence_pipeline, build_executive_summary
)

print("Step 4: Building coverage matrix and evidence pipeline …")
matrix   = build_coverage_matrix(stories)
pipeline = build_evidence_pipeline(matrix, stories)
summary  = build_executive_summary(stories, all_proof_points, matrix, pipeline)
print(f"        {len(pipeline)} evidence gap(s) identified.")
print()

# ── Step 5: Write Excel ────────────────────────────────────────────────────
from src.excel_writer import write_workbook

output_path = EXCEL_TEST if test_mode else EXCEL_FULL
print(f"Step 5: Writing Excel workbook to:")
print(f"        {output_path}")

# Record any failed URLs as QA exceptions.
from src.parser import _add_qa
for url in failed_urls:
    _add_qa("N/A", "page_download", url, "Page could not be downloaded — needs manual review")

elapsed = time.time() - start_time
run_stats = logger.finalise_run(elapsed)
run_stats["stories_processed"] = len(stories)
run_stats["proof_points_extracted"] = len(all_proof_points)

write_workbook(
    output_path   = output_path,
    stories       = stories,
    proof_points  = all_proof_points,
    matrix        = matrix,
    pipeline      = pipeline,
    qa_exceptions = qa_exceptions,
    run_stats     = run_stats,
    summary       = summary,
)
print("        Done.")
print()

# ── Step 6: Write dashboard ────────────────────────────────────────────────
from src.dashboard import write_dashboard_data, write_dashboard_html
from src.config import DASH_HTML

print("Step 6: Writing dashboard …")
write_dashboard_data(stories, all_proof_points)
write_dashboard_html(stories=stories, proof_points=all_proof_points)
print(f"        Dashboard written to: {DASH_HTML}")
print()

# ── Summary ────────────────────────────────────────────────────────────────
print("=" * 60)
print("  COMPLETE")
print("=" * 60)
print(f"  Stories processed : {len(stories)}")
print(f"  Proof points      : {len(all_proof_points)}")
print(f"  Failed pages      : {len(failed_urls)}")
print(f"  QA exceptions     : {len(qa_exceptions)}")
print(f"  Evidence gaps     : {len(pipeline)}")
print(f"  Duration          : {elapsed:.1f}s")
print(f"  Excel output      : {output_path}")
print()

if failed_urls:
    print("  FAILED URLs:")
    for u in failed_urls:
        print(f"    - {u}")
    print()

if qa_exceptions:
    print(f"  {len(qa_exceptions)} field(s) need human review — see QA Exceptions sheet in Excel.")
    print()

print("  Double-click 4_OPEN_DASHBOARD.bat to explore the results in your browser.")
print()
