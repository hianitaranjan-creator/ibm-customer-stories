/**
 * crawl-ibm-case-studies.ts
 * ─────────────────────────
 * Crawlee-powered crawler for IBM.com case studies.
 *
 * Implements Sub-Tasks 3, 4, 5, 6 from complete-case-study-crawler-plan.md
 *
 * Modes (set via CLI args or environment):
 *   --test   Process first 2 catalogue pages, max 10 story pages
 *   --all    Process all catalogue pages (1000+ stories)
 *   --validate  Print report only (no crawl)
 *
 * Output files:
 *   public/data/all-case-studies.json
 *   public/data/data-platform-case-studies.json
 *   public/data/crawl-report.json
 *   public/data/failed-urls.json
 */

import { CheerioCrawler, RequestQueue, Configuration, log } from "crawlee";
import * as fs from "fs";
import * as path from "path";
import type { CheerioAPI } from "cheerio";

// ── Configuration ─────────────────────────────────────────────────────────────

const IBM_BASE          = "https://www.ibm.com";
const CATALOGUE_URL     = "https://www.ibm.com/case-studies";
const OUTPUT_DIR        = path.join(__dirname, "..", "public", "data");
const TAXONOMY_PATH     = path.join(__dirname, "..", "src", "config", "product-taxonomy.json");
const CHECKPOINT_FILE   = path.join(OUTPUT_DIR, ".crawl-checkpoint.json");

// Request behaviour — matches Python pipeline's politeness settings
const MAX_CONCURRENCY   = 2;
const REQUEST_DELAY_MS  = 1500;   // minimum ms between requests (politeness)
const MAX_RETRIES       = 3;
const TIMEOUT_SECS      = 30;

// Parse CLI mode flags
const args = process.argv.slice(2);
const MODE: "test" | "all" | "validate" =
  args.includes("--all")      ? "all"
  : args.includes("--validate") ? "validate"
  : "test"; // default

const TEST_CATALOGUE_PAGES = 2;
const TEST_MAX_STORIES     = 10;

console.log(`\n${"=".repeat(60)}`);
console.log(`  IBM Case Study Crawler — mode: ${MODE.toUpperCase()}`);
console.log(`${"=".repeat(60)}\n`);

// ── Types ─────────────────────────────────────────────────────────────────────

interface CaseStudy {
  id:                   string;
  canonicalUrl:         string;
  clientName:           string | null;
  title:                string | null;
  description:          string | null;
  industry:             string | null;
  geography:            string | null;
  productCategories:    string[];
  productsMentioned:    string[];
  topics:               string[];
  challenge:            string | null;
  solution:             string | null;
  businessOutcomes:     string | null;
  quantifiedProof:      string | null;
  customerQuote:        string | null;
  publicationDate:      string | null;
  lastUpdatedDate:      string | null;
  collectedAt:          string;
}

interface FailedUrl {
  url:      string;
  reason:   string;
  attempts: number;
}

interface CrawlReport {
  crawlStartedAt:               string;
  crawlFinishedAt:              string;
  mode:                         string;
  advertisedTotal:              number | null;
  cataloguePagesProcessed:      number;
  uniqueStoryUrlsDiscovered:    number;
  storiesSuccessfullyProcessed: number;
  storiesFailed:                number;
  duplicateUrlsRemoved:         number;
  dataPlatformRelevant:         number;
  storiesNeedingManualReview:   number;
  percentageCollected:          string;
  validationPassed:             boolean;
  note:                         string;
}

// ── Load product taxonomy (v2 schema) ────────────────────────────────────────

interface TaxonomyProduct {
  approvedName:    string;
  historicalNames: string[];
  previousBranding: string[];
  abbreviations:   string[];
  motions:         string[];
  aliases:         string[];
}

const taxonomy = JSON.parse(fs.readFileSync(TAXONOMY_PATH, "utf-8"));

// v2 uses 'products' key; support v1 'categories' as fallback during migration
const TAXONOMY_PRODUCTS: Record<string, TaxonomyProduct> = taxonomy.products ?? {};
const DATA_PLATFORM_MOTIONS = new Set<string>(taxonomy.motions ?? []);

// ── Geography inference (ported from src/parser.py) ──────────────────────────

const GEO_MAP: Record<string, string[]> = {
  "North America": [
    "united states", "u.s.", "us ", "usa", "canada", "canadian",
    "american", "north america",
  ],
  "EMEA": [
    "uk", "united kingdom", "britain", "germany", "german", "france",
    "french", "spain", "spanish", "italy", "italian", "netherlands",
    "dutch", "belgium", "sweden", "norway", "denmark", "finland",
    "switzerland", "austria", "poland", "czech", "hungary", "europe",
    "european", "middle east", "africa", "african", "south africa",
    "nigeria", "kenya", "saudi", "emirates", "uae", "israel",
    "turkey", "türkiye", "ireland", "scotland", "wales", "portugal",
    "greece", "russia",
  ],
  "APAC": [
    "india", "indian", "china", "chinese", "australia", "australian",
    "new zealand", "singapore", "hong kong", "south korea", "korea",
    "taiwan", "indonesia", "malaysia", "thailand", "vietnam",
    "philippines", "bangladesh", "pakistan", "asia", "asia pacific", "apac",
  ],
  "Japan":         ["japan", "japanese"],
  "Latin America": [
    "brazil", "brazilian", "mexico", "mexican", "argentina", "argentine",
    "colombia", "colombian", "chile", "chilean", "peru", "venezuela",
    "latin america", "latam",
  ],
};

function inferGeography(text: string): string | null {
  const lower = text.toLowerCase();
  for (const [region, keywords] of Object.entries(GEO_MAP)) {
    if (keywords.some((kw) => lower.includes(kw))) return region;
  }
  return "Other / Global";
}

// ── Industry inference (ported from src/parser.py) ────────────────────────────

const INDUSTRY_MAP: Record<string, string[]> = {
  "Financial Services":       ["bank", "banking", "financial", "insurance", "capital markets", "investment", "fintech", "credit", "loan", "mortgage", "payment", "wealth management"],
  "Healthcare & Life Sciences": ["health", "hospital", "clinic", "pharmaceutical", "pharma", "biotech", "life science", "medical", "patient", "drug", "genomic", "laboratory", "lab "],
  "Telecommunications":       ["telecom", "telco", "mobile network", "5g", "broadband", "carrier", "operator", "communications provider"],
  "Retail & Consumer Goods":  ["retail", "retailer", "consumer goods", "e-commerce", "ecommerce", "supermarket", "grocery", "fashion", "apparel", "cpg"],
  "Manufacturing":            ["manufactur", "automotive", "automobile", "car maker", "industrial", "supply chain", "factory", "plant", "aerospace", "chemical", "steel", "semiconductor"],
  "Energy & Utilities":       ["energy", "utility", "utilities", "oil", "gas", "electric", "power grid", "renewable", "solar", "wind", "nuclear"],
  "Government & Public Sector": ["government", "federal", "municipal", "public sector", "ministry", "agency", "department of", "city of", "state of"],
  "Transportation & Logistics": ["transport", "logistics", "shipping", "freight", "airline", "airport", "railway", "rail ", "port ", "fleet"],
  "Education":                ["university", "college", "school", "education", "academic", "research institution"],
  "Media & Entertainment":    ["media", "entertainment", "broadcast", "publishing", "gaming", "streaming platform"],
};

function inferIndustry(text: string): string | null {
  const lower = text.toLowerCase();
  let best = "Other";
  let bestHits = 0;
  for (const [industry, keywords] of Object.entries(INDUSTRY_MAP)) {
    const hits = keywords.filter((kw) => lower.includes(kw)).length;
    if (hits > bestHits) { bestHits = hits; best = industry; }
  }
  return bestHits > 0 ? best : null;
}

// ── Product detection (v2 taxonomy) ──────────────────────────────────────────
//
// Rules enforced here (mirroring taxonomy _matching_rules):
//   • A product matches ONLY when a specific alias phrase is found verbatim.
//   • Output productCategories uses approvedName — never the raw alias.
//   • productsMentioned records the alias phrase that actually appeared in the
//     text, for full traceability back to the source story.
//   • If nothing matches, both arrays are empty → story flagged "Needs review".

function detectProducts(text: string): { mentioned: string[]; categories: string[] } {
  const lower = text.toLowerCase();
  const mentioned: string[]  = [];
  const categories: string[] = [];

  for (const [, product] of Object.entries(TAXONOMY_PRODUCTS)) {
    const matchedAlias = product.aliases.find((alias) =>
      lower.includes(alias.toLowerCase())
    );
    if (matchedAlias) {
      // Record the approved name (not the raw alias) as the category
      if (!categories.includes(product.approvedName)) {
        categories.push(product.approvedName);
      }
      // Record the exact phrase found in the story text for traceability
      if (!mentioned.includes(matchedAlias)) {
        mentioned.push(matchedAlias);
      }
    }
  }
  return { mentioned, categories };
}

// ── Data Platform relevance (v2 taxonomy) ────────────────────────────────────
//
// A story is Data Platform relevant if at least one matched product belongs to
// one of the three approved Data Platform GTM motions. No keyword fallback —
// that would admit generic AI/analytics stories that mention no product.

function isDataPlatformRelevant(story: CaseStudy): boolean {
  return story.productCategories.some((approvedName) => {
    const product = TAXONOMY_PRODUCTS[approvedName];
    return product?.motions.some((m) => DATA_PLATFORM_MOTIONS.has(m)) ?? false;
  });
}

// ── Quantified proof extraction (ported from src/parser.py) ─────────────────

const QUANTITY_RE = /(\d[\d,.]*\s*(?:[%x×]|times|percent|\$|USD|EUR|GBP|£|€|million|billion|thousand|hours?|days?|weeks?|months?|years?|minutes?|seconds?|TB|GB|MB|KB))|([£$€]\s*\d[\d,.]*)/gi;
const OUTCOME_VERBS_RE = /\b(reduc|increas|improv|cut|sav|achiev|deliver|boost|accelerat|eliminat|lower|faster|gain|generat|grow|shrink|optimiz|consolidat|deploy|migrat|process|handl|complet|resolv|enabl|transform)\b/i;

function extractQuantifiedProof(text: string): string | null {
  const sentences = text.split(/(?<=[.!?])\s+/);
  for (const s of sentences) {
    if (OUTCOME_VERBS_RE.test(s) && QUANTITY_RE.test(s)) {
      // Reset lastIndex after test()
      QUANTITY_RE.lastIndex = 0;
      return s.trim().slice(0, 300);
    }
  }
  return null;
}

// ── Story extraction from a page ($) ────────────────────────────────────────

function cleanQuote(raw: string): string {
  // Collapse whitespace runs; strip leading/trailing whitespace
  return raw.replace(/\s+/g, " ").trim();
}

// ── Heuristic: does this string look like a tagline rather than a company name?
// Taglines tend to be sentence-case phrases with verbs. We avoid flagging
// prepositions that commonly appear in proper names (e.g. "State of Oregon",
// "Bank of America") — only flag when combined with a clear action verb.
const TAGLINE_RE = /\b(building|enabling|powering|transforming|modernizing|leveraging|accelerating|driving|unlocking|delivering|improving|reducing|saving|boosting|realising|realizing|discovering|how|why|when|where|new pace|the new|a new)\b/i;

function slugToCompanyName(slug: string): string | null {
  if (!slug || slug.includes("/")) return null;
  // Convert kebab-case to Title Case words, drop common IBM suffixes
  const words = slug
    .replace(/-(bob|ibm|case|study)$/i, "")
    .split("-")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1));
  const name = words.join(" ").trim();
  // Reject if it looks like a path segment or very short
  return name.length >= 2 ? name : null;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function extractStory(url: string, $: any): CaseStudy {
  const slug = url.replace(/\/$/, "").split("/case-studies/")[1] ?? url;

  // canonical URL
  const canonical = $('link[rel="canonical"]').attr("href") ?? url;

  // Title — strip " | IBM" suffix
  const rawTitle = $("title").text().trim();
  const title = rawTitle ? rawTitle.replace(/\s*\|\s*IBM\s*$/i, "").trim() || null : null;

  // Description
  const description =
    $('meta[name="description"]').attr("content")?.trim() ||
    $('meta[property="og:description"]').attr("content")?.trim() ||
    null;

  // Client name strategy (in priority order):
  //   1. <title> "CompanyName | IBM" — BUT only if it looks like a proper name,
  //      not a tagline sentence. IBM sometimes uses a tagline as the <title>.
  //   2. JSON-LD structured data (name / author / brand / provider)
  //   3. CSS class hints (customer / client / company / brand)
  //   4. Slug converted to Title Case (always a safe last resort — never invented)
  let clientName: string | null = null;

  // Step 1: use title only if it does NOT look like a tagline
  if (title && !TAGLINE_RE.test(title)) {
    clientName = title;
  }

  // Step 2: JSON-LD
  if (!clientName) {
    $('script[type="application/ld+json"]').each((_, el) => {
      if (clientName) return;
      try {
        const data = JSON.parse($(el).html() ?? "{}");
        const items = Array.isArray(data) ? data : [data];
        for (const item of items) {
          for (const key of ["name", "author", "brand", "provider"]) {
            const val = item[key];
            const name = typeof val === "string" ? val : val?.name;
            if (name && name.length > 2 && name.length < 100) {
              clientName = name;
              return;
            }
          }
        }
      } catch { /* ignore */ }
    });
  }

  // Step 3: DOM class hints
  if (!clientName) {
    $('[class*="customer"],[class*="client"],[class*="company"],[class*="brand"]').each((_, el) => {
      if (clientName) return;
      const t = $(el).text().trim();
      if (t.length > 2 && t.length < 80 && !TAGLINE_RE.test(t)) clientName = t;
    });
  }

  // Step 4: slug → Title Case  (factual, never invented — derived from the URL)
  if (!clientName) {
    clientName = slugToCompanyName(slug);
  }

  // Full body text for inference (strip nav/header/footer/scripts)
  $("nav,header,footer,script,style,noscript").remove();
  const bodyText = $.root().text().replace(/\s+/g, " ").trim();

  // Dates
  const pubDate =
    $('meta[property="article:published_time"]').attr("content")?.slice(0, 10) ||
    $('meta[name="date"]').attr("content")?.slice(0, 10) ||
    $('meta[name="DC.date"]').attr("content")?.slice(0, 10) ||
    $("time[datetime]").first().attr("datetime")?.slice(0, 10) ||
    null;

  const modDate =
    $('meta[property="article:modified_time"]').attr("content")?.slice(0, 10) ||
    $('meta[name="last-modified"]').attr("content")?.slice(0, 10) ||
    null;

  // Topics / keywords
  const keywordsMeta = $('meta[name="keywords"]').attr("content") ?? "";
  const topics = keywordsMeta
    ? keywordsMeta.split(",").map((k) => k.trim()).filter(Boolean)
    : [];

  // Geography — prefer country hint from topics before scanning body text
  // Topics often contain the real country name (e.g. "Italy", "Germany", "United Kingdom...")
  let geographyFromTopics: string | null = null;
  for (const topic of topics) {
    const geo = inferGeography(topic);
    if (geo && geo !== "Other / Global") { geographyFromTopics = geo; break; }
  }

  // Challenge / Solution / Business Outcomes
  // IBM pages often use heading-then-paragraph structure
  let challenge: string | null = null;
  let solution: string | null  = null;
  let businessOutcomes: string | null = null;

  $("h2,h3").each((_, el) => {
    const heading = $(el).text().trim().toLowerCase();
    const next = $(el).next("p,div").text().trim().slice(0, 500) || null;
    if (!challenge && /challenge|problem|issue|situation/.test(heading))       challenge = next;
    if (!solution  && /solution|approach|how|answer/.test(heading))            solution  = next;
    if (!businessOutcomes && /outcome|result|benefit|impact/.test(heading))    businessOutcomes = next;
  });

  // Quote — extract the quote sentence only; strip the attribution block.
  // IBM collapses attribution (Name / Role / Company) into the same text node.
  // After cleanQuote() the full text looks like one of:
  //   "…quote sentence. FirstName LastName Role Company"
  //   "…quote sentence. — FirstName LastName"
  // Strategy: find the end of the last sentence-ending punctuation (. ! ?)
  // that is not immediately followed by a capital letter starting another
  // sentence.  Everything after the last such boundary is attribution.
  let customerQuote: string | null = null;
  $("blockquote,q,[class*='quote']").each((_, el) => {
    if (customerQuote) return;
    const t = cleanQuote($(el).text());
    if (t.length < 20) return;

    // Find the last sentence-ending boundary: '. ' or '! ' or '? '
    // followed by a capital letter (start of a new sentence — likely attribution)
    // OR a dash attribution marker
    const SENT_END_RE = /[.!?]\s+(?=[A-Z])/g;
    let lastSentEnd = -1;
    let m: RegExpExecArray | null;
    while ((m = SENT_END_RE.exec(t)) !== null) {
      lastSentEnd = m.index + 1; // position of the char after the punctuation
    }

    // Also check for em-dash attribution pattern
    const dashIdx = t.search(/\s(?:—|–)\s*[A-Z]/);

    // Take the quote up to the last sentence end, or dash, whichever comes first
    let cutAt = t.length;
    if (lastSentEnd > 20) cutAt = lastSentEnd;
    if (dashIdx > 20 && dashIdx < cutAt) cutAt = dashIdx;

    const quoteOnly = t.slice(0, cutAt).trim();
    const trimmed = (quoteOnly || t).slice(0, 300).trim();
    if (trimmed.length > 20) customerQuote = trimmed;
  });

  // Products
  const { mentioned, categories } = detectProducts(bodyText);

  // Industry
  const industry  = inferIndustry(bodyText);

  // Geography — topics-based hit takes priority over body scan
  const geography = geographyFromTopics ?? inferGeography(bodyText);

  // Quantified proof
  const quantifiedProof = extractQuantifiedProof(bodyText);

  return {
    id:               slug,
    canonicalUrl:     canonical,
    clientName,
    title,
    description,
    industry,
    geography,
    productCategories: categories,
    productsMentioned: mentioned,
    topics,
    challenge,
    solution,
    businessOutcomes,
    quantifiedProof,
    customerQuote,
    publicationDate:  pubDate,
    lastUpdatedDate:  modDate,
    collectedAt:      new Date().toISOString(),
  };
}

// ── Main crawler ──────────────────────────────────────────────────────────────

async function main(): Promise<void> {

  // Validate-only mode — just print the last report
  if (MODE === "validate") {
    const reportPath = path.join(OUTPUT_DIR, "crawl-report.json");
    if (!fs.existsSync(reportPath)) {
      console.error("No crawl-report.json found. Run a crawl first.");
      process.exit(1);
    }
    const report: CrawlReport = JSON.parse(fs.readFileSync(reportPath, "utf-8"));
    console.log(JSON.stringify(report, null, 2));
    process.exit(report.validationPassed ? 0 : 1);
  }

  fs.mkdirSync(OUTPUT_DIR, { recursive: true });

  // ── Resume: load checkpoint from previous interrupted run ─────────────────
  // The checkpoint records every URL that was successfully processed so that
  // an interrupted --all run can skip those URLs instead of re-fetching them.
  interface Checkpoint {
    crawlStartedAt:  string;
    completedUrls:   string[];   // canonicalUrl of every story already extracted
    stories:         CaseStudy[];
    failedUrls:      FailedUrl[];
    advertisedTotal: number | null;
  }

  let checkpoint: Checkpoint | null = null;
  if (MODE === "all" && fs.existsSync(CHECKPOINT_FILE)) {
    try {
      checkpoint = JSON.parse(fs.readFileSync(CHECKPOINT_FILE, "utf-8")) as Checkpoint;
      console.log(`\n▶ Resuming from checkpoint: ${checkpoint.completedUrls.length} URLs already done, ${checkpoint.stories.length} stories loaded.\n`);
    } catch {
      console.warn("  Could not parse checkpoint file — starting fresh.");
      checkpoint = null;
    }
  }

  const completedUrls = new Set<string>(checkpoint?.completedUrls ?? []);

  // ── State ──────────────────────────────────────────────────────────────────
  const crawlStartedAt       = checkpoint?.crawlStartedAt ?? new Date().toISOString();
  const discoveredUrls        = new Set<string>();
  const stories: CaseStudy[]  = checkpoint?.stories ?? [];
  const failedUrls: FailedUrl[] = checkpoint?.failedUrls ?? [];
  let advertisedTotal: number | null = checkpoint?.advertisedTotal ?? null;
  let cataloguePagesProcessed = 0;
  let duplicateUrlsRemoved    = 0;

  const maxCataloguePages = MODE === "test" ? TEST_CATALOGUE_PAGES : Infinity;
  const maxStoryPages     = MODE === "test" ? TEST_MAX_STORIES : Infinity;

  // ── Checkpoint writer ─────────────────────────────────────────────────────
  // Called after every successfully extracted story in --all mode.
  function saveCheckpoint(): void {
    if (MODE !== "all") return;
    const cp: Checkpoint = {
      crawlStartedAt,
      completedUrls: [...completedUrls],
      stories,
      failedUrls,
      advertisedTotal,
    };
    fs.writeFileSync(CHECKPOINT_FILE, JSON.stringify(cp), "utf-8");
  }

  // ── Request queue ──────────────────────────────────────────────────────────
  // Disable Crawlee's default storage (we manage our own JSON output)
  Configuration.getGlobalConfig().set("persistStorage", false);

  const queue = await RequestQueue.open();
  await queue.addRequest({ url: CATALOGUE_URL, label: "CATALOGUE", userData: { page: 1 } });

  // ── Crawler ────────────────────────────────────────────────────────────────
  const crawler = new CheerioCrawler({
    requestQueue: queue,
    maxConcurrency:              MAX_CONCURRENCY,
    requestHandlerTimeoutSecs:   TIMEOUT_SECS,
    maxRequestRetries:           MAX_RETRIES,
    minConcurrency:              1,

    // ── Catalogue page handler ─────────────────────────────────────────────
    requestHandler: async ({ request, $, enqueueLinks }) => {

      const label    = request.label ?? "STORY";
      const pageNum  = (request.userData?.page as number) ?? 1;

      // ── CATALOGUE PAGE ────────────────────────────────────────────────────
      if (label === "CATALOGUE") {
        cataloguePagesProcessed++;
        console.log(`\n[Catalogue] Page ${pageNum} — ${request.url}`);

        // Try to read advertised total from page text
        if (!advertisedTotal) {
          const bodyText = $("body").text();
          const match = bodyText.match(/(\d[\d,]*)\s*(?:result|case stud|stor)/i);
          if (match) {
            advertisedTotal = parseInt(match[1].replace(/,/g, ""), 10);
            console.log(`  Advertised total: ${advertisedTotal}`);
          }
        }

        // Collect story URLs from this catalogue page.
        // Reject:  /case-studies/  (index)
        //          /case-studies/all  (filter view)
        //          /case-studies/topic/xxx  (category/tag pages — contain a sub-slash)
        //          anything that is not a simple <slug> identifier
        let newOnThisPage = 0;
        $('a[href*="/case-studies/"]').each((_, el) => {
          let href = $(el).attr("href") ?? "";
          if (href.startsWith("/")) href = IBM_BASE + href;
          href = href.split("?")[0].split("#")[0].replace(/\/$/, "");
          if (!href.includes("/case-studies/")) return;
          const afterPrefix = href.split("/case-studies/")[1] ?? "";
          // Must be a simple slug: no sub-slashes, non-empty, not a reserved word
          if (!afterPrefix || afterPrefix.includes("/") || afterPrefix === "all") return;
          // Must look like a slug: only letters, digits, hyphens
          if (!/^[a-z0-9-]+$/i.test(afterPrefix)) return;

          if (!discoveredUrls.has(href)) {
            discoveredUrls.add(href);
            newOnThisPage++;
          } else {
            duplicateUrlsRemoved++;
          }
        });

        console.log(`  New story URLs: ${newOnThisPage}  |  Total discovered: ${discoveredUrls.size}`);

        // Enqueue story pages (up to maxStoryPages)
        // Skip URLs already in the checkpoint (resume) or already in stories[]
        let queued = 0;
        for (const storyUrl of discoveredUrls) {
          if (stories.length + queued >= maxStoryPages) break;
          if (completedUrls.has(storyUrl)) {
            // Already successfully processed in a previous run — skip silently
            continue;
          }
          const alreadyDone = stories.some((s) => s.canonicalUrl === storyUrl || `${IBM_BASE}/case-studies/${s.id}` === storyUrl);
          if (!alreadyDone) {
            await queue.addRequest({ url: storyUrl, label: "STORY" }, { forefront: false });
            queued++;
          }
        }
        if (queued > 0) console.log(`  Enqueued ${queued} story pages`);

        // Enqueue next catalogue page if under limit.
        // Stop only when IBM's "Next" button is absent/disabled — NOT when
        // newOnThisPage === 0, because on a resume run all URLs on early pages
        // are already in discoveredUrls but new ones may exist on later pages.
        const nextDisabled =
          $('button[aria-label*="Next" i][disabled]').length > 0 ||
          $('a[aria-label*="Next" i][aria-disabled="true"]').length > 0 ||
          $('[class*="pagination"] [class*="next"][disabled]').length > 0;

        if (cataloguePagesProcessed < maxCataloguePages && !nextDisabled) {
          const nextPage = pageNum + 1;
          const nextUrl  = `${CATALOGUE_URL}?page=${nextPage}`;
          console.log(`  Enqueueing next catalogue page: ${nextUrl}`);
          await queue.addRequest({
            url: nextUrl,
            label: "CATALOGUE",
            userData: { page: nextPage },
          });
        } else if (nextDisabled) {
          console.log("  Next button disabled — catalogue exhausted.");
        }
      }

      // ── STORY PAGE ────────────────────────────────────────────────────────
      else {
        if (stories.length >= maxStoryPages) return;
        console.log(`[Story ${stories.length + 1}/${maxStoryPages === Infinity ? "∞" : maxStoryPages}] ${request.url}`);

        // Politeness delay between story page requests
        if (REQUEST_DELAY_MS > 0) {
          await new Promise((r) => setTimeout(r, REQUEST_DELAY_MS));
        }

        try {
          const story = extractStory(request.url, $);
          stories.push(story);
          // Mark this URL complete in the resume set and flush checkpoint to disk
          completedUrls.add(story.canonicalUrl);
          saveCheckpoint();
          console.log(`  ✓ ${story.clientName ?? story.title ?? story.id}  |  ${story.industry ?? "?"}  |  ${story.geography ?? "?"}`);
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          console.warn(`  ✗ Extraction error: ${msg}`);
          failedUrls.push({ url: request.url, reason: msg, attempts: request.retryCount + 1 });
          saveCheckpoint();
        }
      }
    },

    // ── Failed request handler ─────────────────────────────────────────────
    failedRequestHandler: async ({ request }) => {
      console.warn(`[FAILED] ${request.url}`);
      failedUrls.push({
        url:      request.url,
        reason:   `Max retries (${MAX_RETRIES}) exceeded`,
        attempts: MAX_RETRIES,
      });
    },
  });

  // ── Run ────────────────────────────────────────────────────────────────────
  console.log(`Starting crawl (mode: ${MODE}, maxCataloguePages: ${maxCataloguePages === Infinity ? "all" : maxCataloguePages}, maxStories: ${maxStoryPages === Infinity ? "all" : maxStoryPages})…\n`);
  await crawler.run();

  // Small delay to ensure all writes settle
  await new Promise((r) => setTimeout(r, 500));

  const crawlFinishedAt = new Date().toISOString();

  // ── Sub-Task 5: Data Platform filter ─────────────────────────────────────
  const dpStories = stories.filter(isDataPlatformRelevant);

  // ── Sub-Task 6: Crawl report + validation ─────────────────────────────────
  const needsReview = stories.filter(
    (s) => !s.clientName && !s.industry && !s.geography
  ).length;

  const pctCollected = advertisedTotal && advertisedTotal > 0
    ? ((stories.length / advertisedTotal) * 100).toFixed(2) + "%"
    : MODE === "test"
      ? `${stories.length} stories (test mode — no total known)`
      : "unknown";

  const validationPassed = MODE === "test"
    ? true  // test mode: just confirm we got something
    : advertisedTotal
      ? stories.length / advertisedTotal >= 0.95
      : false;

  const report: CrawlReport = {
    crawlStartedAt,
    crawlFinishedAt,
    mode:                         MODE,
    advertisedTotal,
    cataloguePagesProcessed,
    uniqueStoryUrlsDiscovered:    discoveredUrls.size,
    storiesSuccessfullyProcessed: stories.length,
    storiesFailed:                failedUrls.length,
    duplicateUrlsRemoved,
    dataPlatformRelevant:         dpStories.length,
    storiesNeedingManualReview:   needsReview,
    percentageCollected:          pctCollected,
    validationPassed,
    note: MODE === "test"
      ? `Test mode: processed first ${cataloguePagesProcessed} catalogue page(s), max ${TEST_MAX_STORIES} story pages.`
      : validationPassed
        ? "Full crawl passed validation (≥95% of advertised stories collected)."
        : "VALIDATION FAILED — fewer than 95% of advertised stories were collected.",
  };

  // ── Write output files ────────────────────────────────────────────────────
  const writeJson = (filename: string, data: unknown) => {
    const filepath = path.join(OUTPUT_DIR, filename);
    fs.writeFileSync(filepath, JSON.stringify(data, null, 2), "utf-8");
    console.log(`  Wrote: ${filepath}  (${JSON.stringify(data).length.toLocaleString()} bytes)`);
  };

  console.log("\n── Writing output files ──────────────────────────────────────");
  writeJson("all-case-studies.json",            stories);
  writeJson("data-platform-case-studies.json",  dpStories);
  writeJson("crawl-report.json",                report);
  writeJson("failed-urls.json",                 failedUrls);

  // Remove checkpoint on successful completion — clean state for next run
  if (MODE === "all" && fs.existsSync(CHECKPOINT_FILE)) {
    fs.unlinkSync(CHECKPOINT_FILE);
    console.log("  Removed checkpoint (crawl complete).");
  }

  // ── Print summary ─────────────────────────────────────────────────────────
  console.log("\n" + "=".repeat(60));
  console.log("  CRAWL COMPLETE");
  console.log("=".repeat(60));
  console.log(`  Mode:                   ${MODE}`);
  console.log(`  Advertised total:       ${advertisedTotal ?? "not found on page"}`);
  console.log(`  Catalogue pages:        ${cataloguePagesProcessed}`);
  console.log(`  Unique URLs discovered: ${discoveredUrls.size}`);
  console.log(`  Stories extracted:      ${stories.length}`);
  console.log(`  Failed:                 ${failedUrls.length}`);
  console.log(`  Duplicate URLs removed: ${duplicateUrlsRemoved}`);
  console.log(`  Data Platform stories:  ${dpStories.length}`);
  console.log(`  Needs manual review:    ${needsReview}`);
  console.log(`  % collected:            ${pctCollected}`);
  console.log(`  Validation:             ${validationPassed ? "PASSED ✓" : "FAILED ✗"}`);
  console.log("=".repeat(60) + "\n");

  // Print one example story
  if (stories.length > 0) {
    console.log("── Example extracted story ───────────────────────────────────");
    console.log(JSON.stringify(stories[0], null, 2));
  }

  if (!validationPassed && MODE !== "test") {
    process.exit(1);
  }
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
