/**
 * scrape-story-details.js
 * -----------------------
 * Scrapes individual IBM case-study pages for structured story data.
 * Reads URLs from public/data/discovered-story-urls.json (produced by
 * discover-story-urls.js) and writes to public/data/all-case-studies.json.
 *
 * Usage:
 *   node scripts/scrape-story-details.js --test     # scrape first 5 URLs
 *   node scripts/scrape-story-details.js --all      # scrape all URLs
 *   node scripts/scrape-story-details.js --report   # print last run report
 */

"use strict";

const { chromium } = require("playwright");
const fs           = require("fs");
const path         = require("path");
const crypto       = require("crypto");

// ── Constants ─────────────────────────────────────────────────────────────────

const TEST_LIMIT       = 5;        // stories scraped in test mode
const POLITENESS_MS    = 400;      // ms between page requests (per worker)
const NAV_TIMEOUT      = 45_000;   // ms to wait for page navigation
const CONTENT_WAIT     = 15_000;   // ms to wait for main content selector
const RECONNECT_WAIT   = 30_000;   // ms to wait before retrying after disconnect
const RECONNECT_TRIES  = 5;        // max consecutive disconnect retries before abort
const CONCURRENCY      = 3;        // parallel browser contexts (polite default)

// Resource types to block — analytics/ads/tracking add latency with no scraping value
const BLOCKED_TYPES = new Set(["image", "media", "font", "stylesheet"]);
const BLOCKED_HOSTS = [
  "adobedtm.com", "omtrdc.net", "demdex.net", "doubleclick.net",
  "google-analytics.com", "googletagmanager.com", "googlesyndication.com",
  "cdn.optimizely.com", "bizible.com", "marketo.net", "munchkin.marketo",
  "nr-data.net", "newrelic.com", "hotjar.com", "clarity.ms",
];

const OUT_DIR      = path.join(__dirname, "..", "public", "data");
const URLS_FILE    = path.join(OUT_DIR, "discovered-story-urls.json");
const OUTPUT_FILE  = path.join(OUT_DIR, "all-case-studies.json");
const REPORT_FILE  = path.join(OUT_DIR, "scraping-report.json");
const FAILED_FILE  = path.join(OUT_DIR, "failed-urls.json");

// ── CLI mode ──────────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
const MODE = args.includes("--all")    ? "all"
           : args.includes("--test")   ? "test"
           : args.includes("--report") ? "report"
           : "test";  // default to test for safety

// ── Utilities ─────────────────────────────────────────────────────────────────

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
  // Write to a temp file then rename atomically — prevents EBUSY errors when
  // OneDrive or antivirus holds a lock on the target file during sync.
  const tmp = file + ".tmp";
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2), "utf-8");
  try {
    fs.renameSync(tmp, file);
  } catch (_) {
    // rename can fail across drives; fall back to copy+delete
    fs.copyFileSync(tmp, file);
    fs.unlinkSync(tmp);
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function log(msg) {
  const ts = new Date().toISOString().replace("T", " ").slice(0, 19);
  console.log(`[${ts}] ${msg}`);
}

/** Derive a stable id from a canonical URL (slug portion). */
function urlToId(url) {
  const slug = (url.split("/case-studies/")[1] || "").replace(/\/$/, "") || url;
  return slug || crypto.createHash("md5").update(url).digest("hex").slice(0, 8);
}

// ── Print-report mode ─────────────────────────────────────────────────────────

if (MODE === "report") {
  const report = readJson(REPORT_FILE, null);
  if (!report) {
    console.log("No scraping-report.json found. Run scrape:test or scrape:all first.");
    process.exit(0);
  }
  console.log("\n" + "═".repeat(64));
  console.log("  IBM Case Study Scraping — Last Run Report");
  console.log("═".repeat(64));
  console.log(`  Mode              : ${report.mode}`);
  console.log(`  Started           : ${report.startedAt}`);
  console.log(`  Finished          : ${report.finishedAt}`);
  console.log(`  URLs attempted    : ${report.attempted}`);
  console.log(`  Succeeded         : ${report.succeeded}`);
  console.log(`  Failed            : ${report.failed}`);
  console.log(`  Skipped (cached)  : ${report.skipped}`);
  if (report.testChecks) {
    console.log("\n  Test checks:");
    for (const [check, passed] of Object.entries(report.testChecks)) {
      console.log(`    ${passed ? "✓" : "✗"} ${check}`);
    }
    const allPassed = Object.values(report.testChecks).every(Boolean);
    console.log(`\n  Test result: ${allPassed ? "ALL CHECKS PASSED ✓" : "SOME CHECKS FAILED ✗"}`);
  }
  console.log("\n" + "═".repeat(64) + "\n");
  process.exit(0);
}

// ── Page scraping logic ───────────────────────────────────────────────────────

/**
 * Extract all structured fields from a loaded IBM case-study page.
 * Returns a flat object matching the all-case-studies.json schema.
 *
 * Selectors confirmed against live IBM pages (Carbon Design System / cmp- prefix):
 *   title       → h1.cmp-leadspace__heading
 *   clientName  → meta[name="searchTitle"]
 *   quote       → .callout-quote (text only, stop before attribution)
 *   stats       → .cds--cta-block-item__statistic-styling (needs networkidle)
 *   industry    → meta[name="keywords"] parsed for industry terms
 *   geography   → meta[name="keywords"] parsed for country/region terms
 *   topics      → meta[name="primaryTaxonomyEn"] + meta[name="primaryTopic"]
 *   products    → meta[name="keywords"] + body-text keyword scan
 */
async function extractStory(page, url) {
  const id = urlToId(url);

  // ── Title ──────────────────────────────────────────────────────────────────
  // IBM case-study pages render the story headline in h1.cmp-leadspace__heading.
  // Fallback to any h1 whose text is longer than a single generic word.
  const title = await page.evaluate(() => {
    const GENERIC = new Set(["software","services","consulting","solutions","technology","hardware"]);
    const candidates = Array.from(document.querySelectorAll("h1"));
    for (const h of candidates) {
      const t = h.textContent.trim();
      if (t && !GENERIC.has(t.toLowerCase())) return t;
    }
    // Last-resort: og:title minus the " | IBM" suffix
    const og = document.querySelector('meta[property="og:title"]');
    if (og) return (og.getAttribute("content") || "").replace(/\s*\|\s*IBM\s*$/i, "").trim() || null;
    return null;
  }).catch(() => null);

  // ── Client / company name ──────────────────────────────────────────────────
  // meta[name="searchTitle"] reliably contains the client name on IBM pages.
  // Fallback to og:title (strip " | IBM") when searchTitle is absent.
  const clientName = await page.evaluate(() => {
    const st = document.querySelector('meta[name="searchTitle"]');
    if (st) {
      const v = (st.getAttribute("content") || "").trim();
      if (v) return v;
    }
    const og = document.querySelector('meta[property="og:title"]');
    if (og) {
      const v = (og.getAttribute("content") || "").replace(/\s*\|\s*IBM\s*$/i, "").trim();
      if (v) return v;
    }
    return null;
  }).catch(() => null);

  // ── Description / summary ─────────────────────────────────────────────────
  const description = await page.$eval(
    'meta[name="description"], meta[property="og:description"]',
    el => el.getAttribute("content")
  ).catch(async () =>
    page.$eval("p", el => el.textContent.trim()).catch(() => null)
  );

  // ── Challenge / Solution / Outcomes (section-heading walk) ────────────────
  const { challenge, solution, businessOutcomes } = await page.evaluate(() => {
    function sectionByHeading(keyword) {
      const headers = Array.from(document.querySelectorAll("h2, h3, h4"));
      for (const h of headers) {
        if ((h.textContent || "").toLowerCase().includes(keyword)) {
          // Prefer the closest wrapping section/article's body text,
          // skipping the heading itself.
          const section = h.closest("section, article, .cds--content-section, [class*='content-section']");
          if (section) {
            // Exclude the heading node and collect remaining text
            const clone = section.cloneNode(true);
            const hClone = clone.querySelector("h2, h3, h4");
            if (hClone) hClone.remove();
            const text = clone.innerText.replace(/\s+/g, " ").trim();
            if (text.length > 20) return text.slice(0, 1200);
          }
          // Fallback: next sibling element
          const next = h.parentElement ? h.parentElement.nextElementSibling : h.nextElementSibling;
          if (next) return next.innerText.replace(/\s+/g, " ").trim().slice(0, 1200);
        }
      }
      return null;
    }
    return {
      challenge:        sectionByHeading("challenge") || sectionByHeading("problem"),
      solution:         sectionByHeading("solution")  || sectionByHeading("approach"),
      businessOutcomes: sectionByHeading("result")    || sectionByHeading("outcome") || sectionByHeading("benefit"),
    };
  }).catch(() => ({ challenge: null, solution: null, businessOutcomes: null }));

  // ── Quantified proof (stat call-outs) ──────────────────────────────────────
  // IBM uses .cds--cta-block-item__statistic-styling for stat tiles.
  // These are CSS-animated counters: only correct after networkidle load.
  // Fallback: body-text numeric line scan.
  const quantifiedProof = await page.evaluate(() => {
    const statEls = Array.from(document.querySelectorAll(".cds--cta-block-item__statistic-styling"));
    if (statEls.length) {
      return statEls.map(el => el.innerText.replace(/\s+/g, " ").trim()).filter(Boolean).join(" | ");
    }
    // Fallback: scan body text for lines with quantities
    const lines = (document.body.innerText || "").split("\n")
      .map(l => l.trim())
      .filter(l => /\d[\d,.]*\s*(%|x|×|times|percent|\$|USD|£|€|million|billion|hours?|days?|weeks?)/.test(l) && l.length < 200);
    return lines.slice(0, 10).join(" | ") || null;
  }).catch(() => null);

  // ── Customer quote ─────────────────────────────────────────────────────────
  // IBM uses .callout-quote for the pull-quote block and .quote-source-details
  // for the attribution. We capture them separately and strip layout whitespace.
  const { customerQuote, quoteAttribution } = await page.evaluate(() => {
    const quoteEl  = document.querySelector(".callout-quote");
    const sourceEl = document.querySelector(".quote-source-details");
    const quote    = quoteEl  ? quoteEl.textContent.replace(/\s+/g, " ").trim().slice(0, 500) : null;
    const source   = sourceEl ? sourceEl.textContent.replace(/\s+/g, " ").trim().slice(0, 150) : null;
    return { customerQuote: quote, quoteAttribution: source };
  }).catch(() => ({ customerQuote: null, quoteAttribution: null }));

  // ── Industry, Geography, Topics — parsed from meta[name="keywords"] ────────
  // IBM embeds a rich comma-separated keywords meta on every case-study page,
  // e.g. "United States of America,IBM Instana,Government,Observability".
  const { industry, geography, topics } = await page.evaluate(() => {
    const INDUSTRY_MAP = {
      "government": "Government", "public sector": "Government",
      "banking": "Banking & Financial Markets", "financial": "Banking & Financial Markets",
      "insurance": "Insurance",
      "healthcare": "Healthcare", "health": "Healthcare", "hospital": "Healthcare",
      "retail": "Retail", "consumer": "Consumer Products",
      "manufacturing": "Industrial", "automotive": "Automotive",
      "telecom": "Telecommunications", "telecommunication": "Telecommunications",
      "energy": "Energy & Utilities", "utilities": "Energy & Utilities",
      "education": "Education",
      "media": "Media & Entertainment", "entertainment": "Media & Entertainment",
      "pharma": "Life Sciences", "life sciences": "Life Sciences",
      "aerospace": "Aerospace & Defense", "defense": "Aerospace & Defense",
      "transport": "Travel & Transportation", "travel": "Travel & Transportation",
      "technology": "Technology", "software": "Technology",
    };
    const COUNTRY_TO_GEO = {
      "united states": "Americas", "usa": "Americas", "canada": "Americas",
      "brazil": "Americas", "latin america": "Americas",
      "united kingdom": "EMEA", "germany": "EMEA", "france": "EMEA",
      "spain": "EMEA", "italy": "EMEA", "netherlands": "EMEA",
      "sweden": "EMEA", "norway": "EMEA", "denmark": "EMEA",
      "poland": "EMEA", "switzerland": "EMEA", "austria": "EMEA",
      "south africa": "EMEA", "middle east": "EMEA", "europe": "EMEA",
      "india": "Asia Pacific", "japan": "Asia Pacific", "china": "Asia Pacific",
      "australia": "Asia Pacific", "singapore": "Asia Pacific",
      "korea": "Asia Pacific", "taiwan": "Asia Pacific", "apac": "Asia Pacific",
      "asia": "Asia Pacific",
    };

    const kwMeta = document.querySelector('meta[name="keywords"]');
    const kwStr  = kwMeta ? (kwMeta.getAttribute("content") || "") : "";
    const tokens = kwStr.split(",").map(t => t.trim()).filter(Boolean);

    // Industry: first token matching an industry keyword
    let industry = null;
    for (const tok of tokens) {
      const lower = tok.toLowerCase();
      for (const [kw, label] of Object.entries(INDUSTRY_MAP)) {
        if (lower.includes(kw)) { industry = label; break; }
      }
      if (industry) break;
    }

    // Geography: first token matching a country/region
    let geography = null;
    for (const tok of tokens) {
      const lower = tok.toLowerCase();
      for (const [kw, region] of Object.entries(COUNTRY_TO_GEO)) {
        if (lower.includes(kw)) { geography = region; break; }
      }
      if (geography) break;
    }

    // Topics: primaryTaxonomyEn + primaryTopic metas
    const taxMeta   = document.querySelector('meta[name="primaryTaxonomyEn"]');
    const topicMeta = document.querySelector('meta[name="primaryTopic"]');
    const topicSet  = new Set();
    if (taxMeta)   (taxMeta.getAttribute("content")   || "").split(",").map(t => t.trim()).filter(Boolean).forEach(t => topicSet.add(t));
    if (topicMeta) (topicMeta.getAttribute("content") || "").split(",").map(t => t.trim()).filter(Boolean).forEach(t => topicSet.add(t));
    // Also include non-IBM-product keyword tokens as topics
    tokens.filter(t => !t.startsWith("IBM ") && t.length < 60).forEach(t => topicSet.add(t));

    return { industry, geography, topics: [...topicSet].slice(0, 20) };
  }).catch(() => ({ industry: null, geography: null, topics: [] }));

  // ── Product categories & products mentioned ────────────────────────────────
  // Primary source: meta[name="keywords"] tokens starting with "IBM ".
  // Secondary: body-text keyword scan for product name matches.
  const { productCategories, productsMentioned } = await page.evaluate(() => {
    const IBM_PRODUCTS = [
      "watsonx","watson","cloud pak","db2","cognos","planning analytics",
      "maximo","turbonomic","envizi","aspera","appscan","guardium","qradar",
      "sterling","instana","openshift","ansible","red hat",
      "infosphere","datastage","databand","manta","knowledge catalog",
      "openpages","openscale","decision optimization",
      "spss","ilog","business automation","filenet",
      "content manager","case manager","datacap","granite",
    ];

    // From keywords meta
    const kwMeta = document.querySelector('meta[name="keywords"]');
    const kwStr  = kwMeta ? (kwMeta.getAttribute("content") || "") : "";
    const kwProducts = kwStr.split(",").map(t => t.trim())
      .filter(t => t.startsWith("IBM "))
      .map(t => t.replace(/^IBM /, "").trim());

    // From body text
    const body = (document.body.innerText || "").toLowerCase();
    const bodyProducts = IBM_PRODUCTS.filter(p => body.includes(p));

    const allProducts = [...new Set([
      ...kwProducts,
      ...bodyProducts.map(p => p.charAt(0).toUpperCase() + p.slice(1)),
    ])];

    // Categories from the facet hierarchy meta
    const facetMeta = document.querySelector('meta[name="ibm.search.facet.field_hierarchy_01"]');
    const facetStr  = facetMeta ? (facetMeta.getAttribute("content") || "") : "";
    const categories = [...new Set(
      facetStr.split(",").map(t => {
        // "Product Categories:Data and analytics / Data fab..." → "Data and analytics"
        const m = t.match(/Product Categories:([^/,]+)/);
        return m ? m[1].trim() : null;
      }).filter(Boolean)
    )].slice(0, 8);

    return { productCategories: categories, productsMentioned: allProducts.slice(0, 15) };
  }).catch(() => ({ productCategories: [], productsMentioned: [] }));

  // ── Publication date ───────────────────────────────────────────────────────
  const publicationDate = await page.evaluate(() => {
    const el = document.querySelector(
      'meta[name="article:published_time"], meta[property="article:published_time"], ' +
      'meta[name="dcterms.date"], meta[name="DC.date"], time[datetime]'
    );
    if (el) return (el.getAttribute("content") || el.getAttribute("datetime") || "").slice(0, 10) || null;
    const timeEl = document.querySelector("time");
    return timeEl ? (timeEl.getAttribute("datetime") || timeEl.textContent || "").slice(0, 10) || null : null;
  }).catch(() => null);

  const lastUpdatedDate = await page.evaluate(() => {
    const el = document.querySelector('meta[name="last-modified"], meta[property="article:modified_time"]');
    return el ? (el.getAttribute("content") || "").slice(0, 10) || null : null;
  }).catch(() => null);

  return {
    id,
    canonicalUrl:         url,
    clientName:           clientName   || null,
    title:                title        || null,
    description:          description  || null,
    industry:             industry     || null,
    geography:            geography    || null,
    productCategories:    productCategories,
    productsMentioned:    productsMentioned,
    topics:               topics,
    challenge:            challenge         || null,
    solution:             solution          || null,
    businessOutcomes:     businessOutcomes  || null,
    quantifiedProof:      quantifiedProof   || null,
    customerQuote:        customerQuote     || null,
    quoteAttribution:     quoteAttribution  || null,
    publicationDate:      publicationDate   || null,
    lastUpdatedDate:      lastUpdatedDate   || null,
    collectedAt:          new Date().toISOString(),
  };
}

// ── Main scraping logic ───────────────────────────────────────────────────────

(async () => {
  const startedAt = new Date().toISOString();
  log(`Starting IBM case-study detail scraping — mode: ${MODE.toUpperCase()}`);
  ensureDir(OUT_DIR);

  // ── Load URL list ──────────────────────────────────────────────────────────
  const urlData = readJson(URLS_FILE, null);
  if (!urlData || !Array.isArray(urlData.urls) || urlData.urls.length === 0) {
    log("ERROR: No URLs found in discovered-story-urls.json.");
    log("Run 'node scripts/discover-story-urls.js --test' first.");
    process.exit(1);
  }

  const allUrls  = urlData.urls;
  const urlsToScrape = MODE === "test" ? allUrls.slice(0, TEST_LIMIT) : allUrls;
  log(`URLs available: ${allUrls.length} — scraping: ${urlsToScrape.length}`);

  // ── Load existing results (for incremental --all runs) ────────────────────
  const existing    = readJson(OUTPUT_FILE, []);
  const existingMap = new Map(existing.map(s => [s.canonicalUrl, s]));

  // In --all mode results are written incrementally; work from the live file.
  // In --test mode always start fresh.
  const results  = MODE === "test" ? [] : [...existing];
  const failed   = [];
  let succeeded  = 0;
  let skipped    = 0;
  let disconnectStreak = 0;  // consecutive network-disconnect failures

  // ── Browser launch ─────────────────────────────────────────────────────────
  log("Launching Chromium…");
  const browser = await chromium.launch({ headless: true });

  /** Create a new context with route-blocking enabled. */
  async function makeContext() {
    const ctx = await browser.newContext({
      userAgent:
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
      locale:   "en-US",
      viewport: { width: 1280, height: 900 },
    });
    // Block images, fonts, stylesheets and known analytics/ad hosts to cut load time
    await ctx.route("**/*", (route) => {
      const req = route.request();
      if (BLOCKED_TYPES.has(req.resourceType())) return route.abort();
      const url = req.url();
      if (BLOCKED_HOSTS.some(h => url.includes(h))) return route.abort();
      route.continue();
    });
    return ctx;
  }

  /**
   * Scrape a single URL, returning { story, error, isDisconnect }.
   * Owns its own page; opens and closes it internally.
   */
  async function scrapeOne(ctx, url) {
    const page = await ctx.newPage();
    page.on("console", () => {});
    page.on("pageerror", () => {});

    let story = null;
    let lastError = null;
    let isDisconnect = false;

    for (let attempt = 1; attempt <= 2; attempt++) {
      try {
        await page.goto(url, { waitUntil: "domcontentloaded", timeout: NAV_TIMEOUT });

        // Wait for the IBM leadspace heading to confirm content is rendered
        await page.waitForSelector(
          "h1.cmp-leadspace__heading, h1, main",
          { timeout: CONTENT_WAIT }
        ).catch(() => { /* non-fatal */ });

        await sleep(200);  // brief settle for deferred meta injection

        story = await extractStory(page, url);
        isDisconnect = false;
        break;
      } catch (err) {
        lastError = err.message || String(err);
        isDisconnect = lastError.includes("ERR_INTERNET_DISCONNECTED") ||
                       lastError.includes("ERR_NETWORK_CHANGED") ||
                       lastError.includes("ERR_NAME_NOT_RESOLVED");
        if (attempt < 2) await sleep(isDisconnect ? 5000 : 1500);
      }
    }

    await page.close();
    return { story, lastError, isDisconnect };
  }

  // ── Concurrent worker pool ─────────────────────────────────────────────────
  // Build a queue of URLs to scrape, then run CONCURRENCY workers in parallel.
  // Each worker pulls the next URL, scrapes it, records the result, and loops.
  // Shared mutable state (results, failed, counts) is updated synchronously
  // between awaits, so no locking is needed in single-threaded JS.

  const queue = urlsToScrape.filter(url => {
    if (MODE === "all" && existingMap.has(url)) {
      skipped++;
      return false;
    }
    return true;
  });

  if (skipped > 0) log(`Skipping ${skipped} already-scraped URLs.`);
  log(`Launching ${Math.min(CONCURRENCY, queue.length)} workers for ${queue.length} URLs…`);

  let queueIdx = 0;  // next URL index to hand out

  try {
    await Promise.all(
      Array.from({ length: Math.min(CONCURRENCY, queue.length) }, async (_, workerIdx) => {
        const ctx = await makeContext();
        try {
          while (true) {
            // Atomically claim the next URL
            const idx = queueIdx++;
            if (idx >= queue.length) break;

            const url = queue[idx];
            const globalIdx = idx + 1;
            const pct = `[${globalIdx}/${queue.length}]`;
            log(`W${workerIdx + 1} ${pct} Scraping: ${url}`);

            const { story, lastError, isDisconnect } = await scrapeOne(ctx, url);

            if (story) {
              disconnectStreak = 0;
              if (MODE === "all") {
                const existing_idx = results.findIndex(s => s.canonicalUrl === url);
                if (existing_idx >= 0) results[existing_idx] = story;
                else results.push(story);
                writeJson(OUTPUT_FILE, results);  // incremental flush
              } else {
                results.push(story);
              }
              succeeded++;
              log(`W${workerIdx + 1} ${pct} ✓ ${story.title || story.id}`);
            } else {
              failed.push({ url, error: lastError });
              if (MODE === "all") writeJson(FAILED_FILE, failed);
              log(`W${workerIdx + 1} ${pct} ✗ ${(lastError || "").slice(0, 100)}`);

              if (isDisconnect) {
                disconnectStreak++;
                if (disconnectStreak >= RECONNECT_TRIES) {
                  log(`W${workerIdx + 1} ABORT: ${RECONNECT_TRIES} consecutive disconnects. Re-run when restored.`);
                  log(`Progress saved: ${results.length} stories, ${failed.length} failed.`);
                  queueIdx = queue.length;  // signal all workers to stop
                  break;
                }
                log(`W${workerIdx + 1} Disconnect — waiting ${RECONNECT_WAIT / 1000}s… (${disconnectStreak}/${RECONNECT_TRIES})`);
                await sleep(RECONNECT_WAIT);
                queueIdx--;  // retry same URL
              }
            }

            await sleep(POLITENESS_MS);
          }
        } finally {
          await ctx.close();
        }
      })
    );
  } finally {
    await browser.close();
  }

  // ── Save outputs ───────────────────────────────────────────────────────────
  const finishedAt = new Date().toISOString();

  // In --all mode the file was flushed incrementally; this is the final sync.
  // In --test mode this is the only write.
  writeJson(OUTPUT_FILE, results);
  log(`Saved ${results.length} stories → ${OUTPUT_FILE}`);

  writeJson(FAILED_FILE, failed);
  if (failed.length) {
    log(`${failed.length} URLs failed → ${FAILED_FILE}`);
  }

  // ── Build report ───────────────────────────────────────────────────────────
  const report = {
    mode:       MODE,
    startedAt,
    finishedAt,
    attempted:  urlsToScrape.length - skipped,
    succeeded,
    failed:     failed.length,
    skipped,
    totalInOutput: results.length,
  };

  // ── Test checks ────────────────────────────────────────────────────────────
  if (MODE === "test") {
    const checks = {
      [`Attempted exactly ${TEST_LIMIT} URLs`]:
        (urlsToScrape.length - skipped) === TEST_LIMIT,
      "At least one story was scraped successfully":
        succeeded > 0,
      "Every successful story has a canonicalUrl":
        results.every(s => s.canonicalUrl && s.canonicalUrl.includes("/case-studies/")),
      "Every successful story has an id":
        results.every(s => Boolean(s.id)),
      "Failure rate under 80%":
        succeeded > 0 && (failed.length / urlsToScrape.length) < 0.8,
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
  log(`  Scraping complete (${MODE.toUpperCase()})`);
  log(`  Attempted  : ${report.attempted}`);
  log(`  Succeeded  : ${succeeded}`);
  log(`  Failed     : ${failed.length}`);
  log(`  Skipped    : ${skipped}`);
  log(`  Output     : ${results.length} stories total`);
  log("═".repeat(64) + "\n");

  process.exitCode = 0;
})();
