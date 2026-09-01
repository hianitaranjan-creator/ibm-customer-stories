#!/usr/bin/env node
/**
 * discover-story-urls.js
 * ──────────────────────
 * Discovers IBM case-study story URLs by paginating through
 * https://www.ibm.com/case-studies using Playwright (Chromium).
 *
 * Usage (via npm scripts):
 *   npm run discover:test      – process 3 catalogue pages, write test report
 *   npm run discover:all       – process all pages, resume from checkpoint
 *   npm run discovery:report   – print a summary of the last run's report
 *
 * IBM pagination DOM (discovered via _debug-pagination.js):
 *   Next button : <a aria-label="Next" class="...pagination-next..."
 *                    aria-disabled="false" href="javascript:void(0);">
 *   Disabled    : class includes "cds--pagination-nav__page--disabled"
 *                 AND aria-disabled="true"
 *   Result count: <span data-count-total="1181">1 – 30 of 1181 items</span>
 *   Page size   : <select aria-label="Items per page"> with options 10/20/30
 *   Total pages : last page link has data-key="40" (= ceil(1181/30))
 */

"use strict";

const { chromium } = require("playwright");
const fs            = require("fs");
const path          = require("path");

// ── Constants ─────────────────────────────────────────────────────────────────

const BASE_URL      = "https://www.ibm.com/case-studies";
const IBM_BASE      = "https://www.ibm.com";
const PAGE_LIMIT    = 50;           // absolute safety cap on catalogue pages
const TEST_PAGES    = 3;            // pages processed in test mode
const POLITENESS_MS = 1800;         // min ms between page navigations
const NAV_TIMEOUT   = 60_000;       // ms to wait for page load
const CARD_TIMEOUT  = 30_000;       // ms to wait for story cards to appear
const CHANGE_TIMEOUT = 15_000;      // ms to wait for page content to change

// IBM Carbon pagination selectors (confirmed via DOM inspection)
const SEL_NEXT      = 'a[aria-label="Next"]';
const SEL_STORY_A   = 'a[href*="/case-studies/"]';
const SEL_PAGE_SIZE = 'select[aria-label="Items per page"]';
const SEL_RESULT    = '[data-count-total]';
const SEL_CARDS     = '.ibm-search__result, a[href*="/case-studies/"]';

const OUT_DIR     = path.join(__dirname, "..", "public", "data");
const URLS_FILE   = path.join(OUT_DIR, "discovered-story-urls.json");
const CHECKPOINT  = path.join(OUT_DIR, "discovery-checkpoint.json");
const REPORT_FILE = path.join(OUT_DIR, "discovery-report.json");

// ── CLI mode ──────────────────────────────────────────────────────────────────

const args   = process.argv.slice(2);
const MODE   = args.includes("--all")    ? "all"
             : args.includes("--report") ? "report"
             : "test";   // default (also covers --test)

const MAX_PAGES = MODE === "test" ? TEST_PAGES : PAGE_LIMIT;

// ── Helpers ───────────────────────────────────────────────────────────────────

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function readJson(file, fallback) {
  try {
    if (fs.existsSync(file)) return JSON.parse(fs.readFileSync(file, "utf-8"));
  } catch (_) { /* corrupt — treat as missing */ }
  return fallback;
}

function writeJson(file, data) {
  ensureDir(path.dirname(file));
  fs.writeFileSync(file, JSON.stringify(data, null, 2), "utf-8");
}

/** Return true only when the existing file is valid AND larger than newData. */
function wouldShrink(file, newUrls) {
  const existing = readJson(file, null);
  if (!existing || !Array.isArray(existing.urls)) return false;
  return existing.urls.length > newUrls.length;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function log(msg) {
  const ts = new Date().toISOString().replace("T", " ").slice(0, 19);
  console.log(`[${ts}] ${msg}`);
}

/** Normalise a raw href to a canonical /case-studies/<slug> URL, or null. */
function normalise(href) {
  if (!href) return null;
  let u = href.split("?")[0].split("#")[0].trim();
  if (u.startsWith("/")) u = IBM_BASE + u;
  if (!u.startsWith("http")) return null;
  u = u.replace(/\/+$/, "");
  if (!u.includes("/case-studies/")) return null;
  const slug = u.split("/case-studies/")[1] || "";
  if (!slug || slug === "all") return null;
  return u;
}

// ── Print-report mode ─────────────────────────────────────────────────────────

if (MODE === "report") {
  const report = readJson(REPORT_FILE, null);
  if (!report) {
    console.log("No discovery-report.json found. Run discover:test or discover:all first.");
    process.exit(0);
  }
  console.log("\n" + "═".repeat(66));
  console.log("  IBM Case Study URL Discovery — Last Run Report");
  console.log("═".repeat(66));
  console.log(`  Mode              : ${report.mode}`);
  console.log(`  Started           : ${report.startedAt}`);
  console.log(`  Finished          : ${report.finishedAt}`);
  console.log(`  Catalogue pages   : ${report.cataloguePagesProcessed}`);
  console.log(`  Total unique URLs : ${report.totalUniqueUrls}`);
  console.log(`  IBM advertised    : ${report.advertisedTotal ?? "unknown"}`);
  console.log(`  Stopped early     : ${report.stoppedEarly ? "Yes — " + report.stopReason : "No"}`);
  if (report.pagesDetail && report.pagesDetail.length) {
    console.log("\n  Page detail:");
    const h = (s, w) => String(s).slice(0, w).padEnd(w);
    console.log("  " + [h("Page",6), h("Cards",6), h("New",5), h("Total",7), "First URL slug"].join("  "));
    console.log("  " + "─".repeat(80));
    for (const p of report.pagesDetail) {
      const slug = p.firstUrl ? (p.firstUrl.split("/case-studies/")[1] || p.firstUrl).slice(0, 35) : "—";
      console.log("  " + [h(p.pageNumber,6), h(p.cardsFound,6), h(p.newUrls,5), h(p.totalSoFar,7), slug].join("  "));
    }
  }
  if (report.testChecks) {
    console.log("\n  Test checks:");
    for (const [check, passed] of Object.entries(report.testChecks)) {
      console.log(`    ${passed ? "✓" : "✗"} ${check}`);
    }
    const allPassed = Object.values(report.testChecks).every(Boolean);
    console.log(`\n  Test result: ${allPassed ? "ALL CHECKS PASSED ✓" : "SOME CHECKS FAILED ✗"}`);
  }
  console.log("\n" + "═".repeat(66) + "\n");
  process.exit(0);
}

// ── Main discovery logic ──────────────────────────────────────────────────────

(async () => {
  const startedAt = new Date().toISOString();
  log(`Starting IBM case-study URL discovery — mode: ${MODE.toUpperCase()}`);
  ensureDir(OUT_DIR);

  // ── Load checkpoint (resume support) ───────────────────────────────────────
  let checkpoint = readJson(CHECKPOINT, { pageNumber: 1, collectedUrls: [] });

  // Test mode always starts fresh
  if (MODE === "test") {
    checkpoint = { pageNumber: 1, collectedUrls: [] };
    log("Test mode: starting from page 1.");
  } else if (checkpoint.pageNumber >= MAX_PAGES) {
    // Checkpoint points at or past the last page — previous run was complete.
    // Start fresh so new stories added to earlier pages are not missed.
    checkpoint = { pageNumber: 1, collectedUrls: [] };
    log("Checkpoint was at/past last page — starting fresh to catch any new stories.");
  } else if (checkpoint.pageNumber > 1) {
    log(`Resuming from checkpoint: page ${checkpoint.pageNumber}, ${checkpoint.collectedUrls.length} URLs already collected.`);
  }

  const allUrls      = new Set(checkpoint.collectedUrls);
  let   pageNumber   = checkpoint.pageNumber;
  const pagesDetail  = [];
  let advertisedTotal = null;
  let stoppedEarly   = false;
  let stopReason     = "";

  // ── Browser launch ─────────────────────────────────────────────────────────
  log("Launching Chromium…");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent:
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    locale:   "en-US",
    viewport: { width: 1280, height: 900 },
  });
  const page = await context.newPage();
  page.on("console", () => {});
  page.on("pageerror", () => {});

  try {
    // ── Navigate to catalogue ───────────────────────────────────────────────
    log(`Navigating to ${BASE_URL} …`);
    await page.goto(BASE_URL, { waitUntil: "domcontentloaded", timeout: NAV_TIMEOUT });

    // Wait for story links to appear
    await page.waitForSelector(SEL_STORY_A, { timeout: CARD_TIMEOUT });
    await sleep(2000);   // let the JS finish rendering

    // ── Set page size to max (30 items per page) if not already ────────────
    try {
      const select = await page.$(SEL_PAGE_SIZE);
      if (select) {
        const options = await page.$$eval(
          `${SEL_PAGE_SIZE} option`,
          opts => opts.map(o => Number(o.value)).filter(v => !isNaN(v))
        );
        const maxOpt = Math.max(...options);
        if (maxOpt > 0) {
          await page.selectOption(SEL_PAGE_SIZE, String(maxOpt));
          log(`Set page size to ${maxOpt} items per page.`);
          await sleep(2500);   // wait for results to re-render
          await page.waitForSelector(SEL_STORY_A, { timeout: CARD_TIMEOUT });
        }
      }
    } catch (_) {
      log("WARN: Could not set page size — using IBM default.");
    }

    // ── Read IBM's advertised total ─────────────────────────────────────────
    try {
      const el = await page.$(SEL_RESULT);
      if (el) {
        const total = await el.getAttribute("data-count-total");
        if (total) advertisedTotal = parseInt(total, 10);
      }
      if (!advertisedTotal) {
        // Fallback: parse the result-summary text
        const summaryText = await page.textContent(
          ".ibm-search__pagination-bar__result-summary"
        ).catch(() => "");
        const m = (summaryText || "").match(/of\s+([\d,]+)/);
        if (m) advertisedTotal = parseInt(m[1].replace(/,/g, ""), 10);
      }
      if (advertisedTotal) log(`IBM advertised total: ${advertisedTotal} stories`);
    } catch (_) { /* non-fatal */ }

    // ── If resuming, fast-forward to the checkpoint page ───────────────────
    if (pageNumber > 1) {
      log(`Fast-forwarding to checkpoint page ${pageNumber}…`);
      for (let i = 1; i < pageNumber; i++) {
        const moved = await _clickNext(page);
        if (!moved) {
          log("WARN: Could not fast-forward — restarting from page 1.");
          pageNumber = 1;
          allUrls.clear();
          break;
        }
        await sleep(POLITENESS_MS);
        await page.waitForSelector(SEL_STORY_A, { timeout: CARD_TIMEOUT });
      }
    }

    // ── Page loop ───────────────────────────────────────────────────────────
    while (pageNumber <= MAX_PAGES) {
      log(`Processing catalogue page ${pageNumber}…`);

      // Wait for the active page indicator to match our expected page number
      await _waitForActivePage(page, pageNumber);

      // Collect this page's story URLs
      const pageUrls = await _collectLinks(page);
      const before   = allUrls.size;
      for (const u of pageUrls) allUrls.add(u);
      const newCount = allUrls.size - before;

      pagesDetail.push({
        pageNumber,
        firstUrl:   pageUrls[0] ?? null,
        cardsFound: pageUrls.length,
        newUrls:    newCount,
        totalSoFar: allUrls.size,
      });

      log(`  Page ${pageNumber}: ${pageUrls.length} cards, ${newCount} new, ${allUrls.size} total`);

      // Save progress
      _saveProgress(allUrls, pageNumber + 1);

      // Check whether a Next page exists and is enabled
      const nextState = await _nextButtonState(page);
      if (nextState === "absent" || nextState === "disabled") {
        log(`End of catalogue — Next is ${nextState} after page ${pageNumber}.`);
        stoppedEarly = pageNumber < MAX_PAGES;
        stopReason   = "Next button " + nextState;
        break;
      }

      // Click the numbered page link for (pageNumber + 1) when visible,
      // otherwise fall back to the Next arrow.
      const advanced = await _advanceToPage(page, pageNumber + 1);
      if (!advanced) {
        log(`Could not advance past page ${pageNumber}. Stopping.`);
        stoppedEarly = true;
        stopReason   = "Could not advance to next page";
        break;
      }

      pageNumber++;
      await sleep(POLITENESS_MS);
    }

    if (!stoppedEarly && pageNumber > MAX_PAGES) {
      stoppedEarly = true;
      stopReason   = `Safety limit of ${MAX_PAGES} pages reached`;
      log(`Safety page limit (${MAX_PAGES}) reached.`);
    }

  } finally {
    await browser.close();
  }

  // ── Final save ─────────────────────────────────────────────────────────────
  const finishedAt = new Date().toISOString();
  const urlsArray  = [...allUrls];

  if (MODE === "all" && wouldShrink(URLS_FILE, { urls: urlsArray })) {
    log(`WARN: Not overwriting ${URLS_FILE} — existing file has more URLs than this run.`);
  } else {
    writeJson(URLS_FILE, {
      generatedAt: finishedAt,
      mode:        MODE,
      totalUrls:   urlsArray.length,
      urls:        urlsArray,
    });
    log(`Saved ${urlsArray.length} unique URLs → ${URLS_FILE}`);
  }

  // Clear checkpoint on clean full-run finish
  if (MODE === "all" && !stoppedEarly) {
    writeJson(CHECKPOINT, { pageNumber: 1, collectedUrls: [] });
    log("Checkpoint cleared (full run complete).");
  } else {
    _saveProgress(allUrls, pageNumber);
  }

  // ── Build report ───────────────────────────────────────────────────────────
  const report = {
    mode: MODE,
    startedAt,
    finishedAt,
    cataloguePagesProcessed: pagesDetail.length,
    totalUniqueUrls: urlsArray.length,
    advertisedTotal,
    stoppedEarly,
    stopReason: stoppedEarly ? stopReason : null,
    pagesDetail,
  };

  // ── Test checks ────────────────────────────────────────────────────────────
  if (MODE === "test") {
    const checks = {
      "Processed exactly 3 catalogue pages":
        pagesDetail.length === TEST_PAGES,
      "Every page returned at least one story card":
        pagesDetail.every(p => p.cardsFound > 0),
      "Pages 2 and 3 each contained at least one new unique URL":
        pagesDetail.filter(p => p.pageNumber > 1).every(p => p.newUrls > 0),
      "Total unique URLs collected > 0":
        urlsArray.length > 0,
      "All URLs contain /case-studies/ path":
        urlsArray.every(u => u.includes("/case-studies/")),
    };
    report.testChecks = checks;

    const allPassed = Object.values(checks).every(Boolean);
    log("\n" + "─".repeat(64));
    log("TEST CHECKS:");
    for (const [check, passed] of Object.entries(checks)) {
      log(`  ${passed ? "✓" : "✗"} ${check}`);
    }
    log("─".repeat(64));
    log(`Test result: ${allPassed ? "ALL CHECKS PASSED ✓" : "SOME CHECKS FAILED ✗"}`);
    log("─".repeat(64) + "\n");
  }

  writeJson(REPORT_FILE, report);
  log(`Report saved → ${REPORT_FILE}`);

  // ── Summary ────────────────────────────────────────────────────────────────
  log("\n" + "═".repeat(64));
  log(`  Discovery complete (${MODE.toUpperCase()})`);
  log(`  Catalogue pages   : ${pagesDetail.length}`);
  log(`  Total unique URLs : ${urlsArray.length}`);
  if (advertisedTotal) log(`  IBM advertised    : ${advertisedTotal}`);
  if (stoppedEarly) log(`  Stopped early     : ${stopReason}`);
  log("═".repeat(64) + "\n");

  process.exitCode = 0;
})();

// ── Page interaction helpers ──────────────────────────────────────────────────

/**
 * Collect all /case-studies/<slug> hrefs from the results grid on the
 * current page. Scoped to .ibm-search__results so that persistent
 * navigation/featured links in the page chrome are excluded — this ensures
 * firstUrl reflects the actual first result card, not a nav tile.
 * Falls back to the full DOM if the results container is not found.
 */
async function _collectLinks(page) {
  // Primary: links inside the IBM results grid only
  let hrefs = await page.$$eval(
    '.ibm-search__results a[href]',
    (anchors) => anchors.map((a) => a.getAttribute("href")).filter(Boolean)
  ).catch(() => []);

  // Fallback: all case-study links in the DOM (when results container absent)
  if (hrefs.length === 0) {
    hrefs = await page.$$eval(
      'a[href*="/case-studies/"]',
      (anchors) => anchors.map((a) => a.getAttribute("href")).filter(Boolean)
    ).catch(() => []);
  }

  const seen   = new Set();
  const result = [];
  for (const href of hrefs) {
    const norm = normalise(href);
    if (norm && !seen.has(norm)) {
      seen.add(norm);
      result.push(norm);
    }
  }
  return result;
}

/**
 * Check whether the Next button is present, enabled, or disabled.
 * Returns "absent" | "disabled" | "enabled".
 */
async function _nextButtonState(page) {
  try {
    const el = await page.$(SEL_NEXT);
    if (!el) return "absent";
    const ariaDisabled = await el.getAttribute("aria-disabled");
    const classes      = await el.getAttribute("class") || "";
    if (ariaDisabled === "true" || classes.includes("cds--pagination-nav__page--disabled")) {
      return "disabled";
    }
    return "enabled";
  } catch (_) {
    return "absent";
  }
}

/**
 * Click the Next arrow button.
 * Returns true if clicked, false if not found/disabled.
 */
async function _clickNext(page) {
  const state = await _nextButtonState(page);
  if (state !== "enabled") return false;
  try {
    await page.click(SEL_NEXT, { timeout: 5000 });
    return true;
  } catch (_) {
    return false;
  }
}

/**
 * Advance to targetPage by clicking its numbered page link if visible
 * (e.g. <a data-key="2">), or by clicking the Next arrow as a fallback.
 * Returns true if a click was dispatched.
 */
async function _advanceToPage(page, targetPage) {
  // Try the numbered page link first
  try {
    const numLink = await page.$(`a[data-key="${targetPage}"]`);
    if (numLink) {
      const disabled = await numLink.getAttribute("aria-disabled");
      const cls      = await numLink.getAttribute("class") || "";
      if (disabled !== "true" && !cls.includes("--disabled")) {
        await numLink.scrollIntoViewIfNeeded();
        await numLink.click();
        return true;
      }
    }
  } catch (_) { /* fall through */ }
  // Fallback: Next arrow
  return _clickNext(page);
}

/**
 * Wait until IBM's Carbon pagination active-page indicator shows
 * expectedPage AND the results container has been re-populated with links.
 * Falls back to a fixed wait if the indicator never updates.
 */
async function _waitForActivePage(page, expectedPage) {
  const deadline = Date.now() + CHANGE_TIMEOUT;
  while (Date.now() < deadline) {
    try {
      // Check 1: active page number matches
      const active = await page.$eval(
        'a[class*="pagination-nav__page--active"]',
        el => el.getAttribute("data-key") || el.innerText.trim()
      ).catch(() => null);
      if (active === null || String(active) !== String(expectedPage)) {
        await sleep(300);
        continue;
      }
      // Check 2: results container has links (confirms DOM has re-rendered)
      const linkCount = await page.$$eval(
        '.ibm-search__results a[href]',
        anchors => anchors.filter(a => a.href.includes("/case-studies/")).length
      ).catch(() => 0);
      if (linkCount > 0) return;
    } catch (_) { /* keep polling */ }
    await sleep(300);
  }
  // Fallback: just wait for any story links
  await page.waitForSelector(SEL_STORY_A, { timeout: CARD_TIMEOUT }).catch(() => {});
}

/**
 * Persist current state to the checkpoint file.
 */
function _saveProgress(urlSet, nextPage) {
  writeJson(CHECKPOINT, {
    savedAt:       new Date().toISOString(),
    pageNumber:    nextPage,
    collectedUrls: [...urlSet],
  });
}
