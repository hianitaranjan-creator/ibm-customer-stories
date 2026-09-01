"""
dashboard.py
------------
Writes the local dashboard HTML file.

The data is embedded DIRECTLY inside the HTML as a JavaScript variable so
the dashboard works when you double-click index.html from Windows Explorer.
(Browsers block fetch() on local file:// URLs, so we avoid fetch entirely.)
"""

import json
import os
from src.config import DASH_DIR, DASH_DATA, DASH_HTML
from src import logger


def write_dashboard_data(stories: list[dict], proof_points: list[dict]) -> None:
    """
    Write data.json alongside the HTML (kept as a backup/reference copy).
    The HTML file embeds the same data inline and does NOT read this file.
    """
    os.makedirs(DASH_DIR, exist_ok=True)

    slim_stories = []
    for s in stories:
        slim = {k: v for k, v in s.items() if k not in ("body_text", "proof_points")}
        slim_stories.append(slim)

    slim_proofs = []
    for p in proof_points:
        sp = dict(p)
        if isinstance(sp.get("gtm_motions"), list):
            sp["gtm_motions"] = "; ".join(sp["gtm_motions"])
        slim_proofs.append(sp)

    payload = {"stories": slim_stories, "proof_points": slim_proofs}
    with open(DASH_DATA, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info(f"Dashboard data written: {DASH_DATA}")
    return slim_stories, slim_proofs


def write_dashboard_html(stories: list[dict] = None, proof_points: list[dict] = None) -> None:
    """
    Write a fully self-contained dashboard HTML file.
    The story and proof data is injected as an inline JS constant —
    no fetch(), no server, no internet connection needed.
    """
    os.makedirs(DASH_DIR, exist_ok=True)

    # Build slim copies (drop body_text which is large and not needed in UI).
    slim_stories = []
    if stories:
        for s in stories:
            slim = {k: v for k, v in s.items() if k not in ("body_text", "proof_points")}
            slim_stories.append(slim)

    slim_proofs = []
    if proof_points:
        for p in proof_points:
            sp = dict(p)
            if isinstance(sp.get("gtm_motions"), list):
                sp["gtm_motions"] = "; ".join(sp["gtm_motions"])
            slim_proofs.append(sp)

    # Serialise to a compact JSON string for embedding.
    data_js = json.dumps({"stories": slim_stories, "proof_points": slim_proofs},
                         ensure_ascii=False)

    story_count = len(slim_stories)
    proof_count  = len(slim_proofs)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IBM Customer Stories Dashboard</title>
<style>
  :root {{
    --ibm-blue:#0f62fe; --ibm-dark:#161616; --ibm-grey:#f4f4f4;
    --ibm-border:#e0e0e0;
    --strong-bg:#defbe6; --strong-fg:#198038;
    --medium-bg:#edf5ff; --medium-fg:#0043ce;
    --weak-bg:#fcf4d6;   --weak-fg:#b28600;
    --restr-bg:#f4f4f4;  --restr-fg:#6f6f6f;
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'IBM Plex Sans',Arial,sans-serif;background:#fff;
        color:var(--ibm-dark);font-size:14px}}
  header{{background:var(--ibm-blue);color:#fff;padding:16px 24px;
          display:flex;align-items:center;justify-content:space-between}}
  header h1{{font-size:20px;font-weight:600}}
  header small{{font-size:12px;opacity:.8}}
  #filters{{background:var(--ibm-grey);border-bottom:1px solid var(--ibm-border);
            padding:12px 24px;display:flex;flex-wrap:wrap;gap:12px 24px;
            align-items:flex-end}}
  .fg{{display:flex;flex-direction:column;gap:4px}}
  .fg label{{font-size:11px;font-weight:600;text-transform:uppercase;
             letter-spacing:.05em;color:#525252}}
  select,input[type=text]{{border:1px solid #c6c6c6;border-radius:2px;
    padding:6px 10px;font-size:13px;min-width:160px;background:#fff}}
  .checks{{display:flex;flex-wrap:wrap;gap:6px 12px}}
  .checks label{{display:flex;align-items:center;gap:4px;font-size:13px;cursor:pointer}}
  #age-row{{display:flex;align-items:center;gap:10px}}
  #age-val{{font-weight:600;min-width:60px}}
  input[type=range]{{width:140px}}
  button#clear-btn{{padding:7px 18px;background:#fff;border:1px solid var(--ibm-blue);
    color:var(--ibm-blue);border-radius:2px;cursor:pointer;font-size:13px}}
  button#clear-btn:hover{{background:#edf5ff}}
  #stats-bar{{padding:10px 24px;display:flex;gap:24px;flex-wrap:wrap;
              background:#fff;border-bottom:1px solid var(--ibm-border)}}
  .stat{{font-size:13px}}
  .stat strong{{font-size:18px;display:block;color:var(--ibm-blue)}}
  #main{{padding:16px 24px}}
  .story-card{{border:1px solid var(--ibm-border);border-radius:4px;
               margin-bottom:12px;overflow:hidden}}
  .sch{{padding:10px 14px;display:flex;align-items:center;gap:10px;
        background:var(--ibm-grey);cursor:pointer;justify-content:space-between}}
  .sch:hover{{background:#e8e8e8}}
  .st{{font-weight:600;flex:1}}
  .badge{{padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600}}
  .badge.Strong{{background:var(--strong-bg);color:var(--strong-fg)}}
  .badge.Medium{{background:var(--medium-bg);color:var(--medium-fg)}}
  .badge.Weak{{background:var(--weak-bg);color:var(--weak-fg)}}
  .badge.Restricted{{background:var(--restr-bg);color:var(--restr-fg)}}
  .mp{{padding:1px 7px;border-radius:10px;font-size:11px;
       background:#e0e0e0;color:#525252;white-space:nowrap}}
  .scd{{padding:12px 14px;border-top:1px solid var(--ibm-border);display:none}}
  .scd.open{{display:block}}
  .smg{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));
         gap:6px 16px;margin-bottom:10px}}
  .smg dt{{font-size:11px;text-transform:uppercase;color:#525252;font-weight:600}}
  .smg dd{{font-size:13px;margin-bottom:4px}}
  .pt{{width:100%;border-collapse:collapse;font-size:12px;margin-top:8px}}
  .pt th{{background:#e0e0e0;padding:5px 8px;text-align:left;
           font-size:11px;text-transform:uppercase}}
  .pt td{{padding:5px 8px;border-bottom:1px solid var(--ibm-border);vertical-align:top}}
  .pt tr:last-child td{{border-bottom:none}}
  a.sl{{color:var(--ibm-blue);font-size:12px}}
  #no-results{{text-align:center;padding:40px;color:#525252;font-size:15px}}
</style>
</head>
<body>
<header>
  <h1>IBM Customer Stories Dashboard</h1>
  <small id="dstamp">{story_count} stories &nbsp;|&nbsp; {proof_count} proof points</small>
</header>

<div id="filters">
  <div class="fg">
    <label>Customer</label>
    <input type="text" id="f-customer" placeholder="Type to search&hellip;">
  </div>
  <div class="fg">
    <label>Industry</label>
    <select id="f-industry"><option value="">All industries</option></select>
  </div>
  <div class="fg">
    <label>Geography</label>
    <select id="f-geo"><option value="">All geographies</option></select>
  </div>
  <div class="fg">
    <label>IBM Product</label>
    <select id="f-product"><option value="">All products</option></select>
  </div>
  <div class="fg">
    <label>GTM Motion</label>
    <div class="checks" id="f-gtm"></div>
  </div>
  <div class="fg">
    <label>Open / Governed / Hybrid</label>
    <div class="checks" id="f-ogh"></div>
  </div>
  <div class="fg">
    <label>Data Type</label>
    <div class="checks" id="f-struct"></div>
  </div>
  <div class="fg">
    <label>Proof Strength</label>
    <div class="checks" id="f-strength"></div>
  </div>
  <div class="fg">
    <label>Max Publication Age</label>
    <div id="age-row">
      <input type="range" id="f-age" min="0" max="4" step="1" value="4">
      <span id="age-val">All</span>
    </div>
  </div>
  <div class="fg" style="justify-content:flex-end">
    <button id="clear-btn">Clear filters</button>
  </div>
</div>

<div id="stats-bar">
  <div class="stat"><strong id="s-stories">0</strong>Stories</div>
  <div class="stat"><strong id="s-proofs">0</strong>Proof points</div>
  <div class="stat"><strong id="s-strong">0</strong>Strong</div>
  <div class="stat"><strong id="s-medium">0</strong>Medium</div>
  <div class="stat"><strong id="s-weak">0</strong>Weak</div>
  <div class="stat"><strong id="s-restricted">0</strong>Restricted</div>
</div>

<div id="main">
  <div id="story-list"></div>
  <div id="no-results" style="display:none">No stories match your filters.</div>
</div>

<script>
// ── Inline data (no fetch needed — works from file://) ──────────────────
const _RAW = {data_js};
const ALL_STORIES = _RAW.stories || [];
const ALL_PROOFS  = _RAW.proof_points || [];

const proofsByStory = {{}};
ALL_PROOFS.forEach(p => {{
  if (!proofsByStory[p.story_id]) proofsByStory[p.story_id] = [];
  proofsByStory[p.story_id].push(p);
}});

// ── Build filter dropdowns / checkboxes ────────────────────────────────
function unique(arr) {{ return [...new Set(arr.filter(Boolean))].sort(); }}

function populate(id, values) {{
  const sel = document.getElementById(id);
  values.forEach(v => {{
    const o = document.createElement("option");
    o.value = o.textContent = v;
    sel.appendChild(o);
  }});
}}

function buildChecks(id, values) {{
  const c = document.getElementById(id);
  values.forEach(v => {{
    const lbl = document.createElement("label");
    const cb  = document.createElement("input");
    cb.type = "checkbox"; cb.value = v; cb.checked = true;
    cb.addEventListener("change", applyFilters);
    lbl.append(cb, " " + v);
    c.appendChild(lbl);
  }});
}}

populate("f-industry", unique(ALL_STORIES.map(s => s.industry)));
populate("f-geo",      unique(ALL_STORIES.map(s => s.geography)));
const prods = [];
ALL_STORIES.forEach(s => {{
  if (s.products) s.products.split(",").forEach(p => prods.push(p.trim()));
}});
populate("f-product", unique(prods));
buildChecks("f-gtm", [
  "Real-time data and context","Governed data for AI",
  "Data integration and modernization","Cost and workload optimization"
]);
buildChecks("f-ogh",      unique(ALL_STORIES.map(s => s.open_governed_hybrid)));
buildChecks("f-struct",   unique(ALL_STORIES.map(s => s.structured_unstructured)));
buildChecks("f-strength", ["Strong","Medium","Weak","Restricted"]);

// ── Age slider ──────────────────────────────────────────────────────────
const AGE_LABELS = ["6 months","1 year","2 years","3 years","All"];
const AGE_MONTHS = [6,12,24,36,Infinity];
document.getElementById("f-age").addEventListener("input", function() {{
  document.getElementById("age-val").textContent = AGE_LABELS[+this.value];
  applyFilters();
}});

// ── Filter logic ────────────────────────────────────────────────────────
function getChecked(id) {{
  return [...document.querySelectorAll(`#${{id}} input[type=checkbox]:checked`)]
    .map(cb => cb.value);
}}

function applyFilters() {{
  const fc = document.getElementById("f-customer").value.toLowerCase().trim();
  const fi = document.getElementById("f-industry").value;
  const fg = document.getElementById("f-geo").value;
  const fp = document.getElementById("f-product").value;
  const fgtm  = getChecked("f-gtm");
  const fogh  = getChecked("f-ogh");
  const fst   = getChecked("f-struct");
  const fps   = getChecked("f-strength");
  const maxAge = AGE_MONTHS[+document.getElementById("f-age").value];

  const filtered = ALL_STORIES.filter(s => {{
    if (fc && !(s.customer_name||"").toLowerCase().includes(fc)) return false;
    if (fi && s.industry !== fi) return false;
    if (fg && s.geography !== fg) return false;
    if (fp && !(s.products||"").includes(fp)) return false;
    const gtm = s.gtm_motions || "";
    if (!fgtm.some(m => gtm.includes(m))) return false;
    if (!fogh.includes(s.open_governed_hybrid)) return false;
    if (!fst.includes(s.structured_unstructured)) return false;
    if (!fps.includes(s.proof_strength)) return false;
    if (maxAge !== Infinity) {{
      const age = +s.publication_age_months;
      if (!isNaN(age) && age > maxAge) return false;
    }}
    return true;
  }});
  render(filtered);
}}

// ── Render ──────────────────────────────────────────────────────────────
function render(stories) {{
  const list = document.getElementById("story-list");
  const none = document.getElementById("no-results");
  list.innerHTML = "";

  const vp = stories.flatMap(s => proofsByStory[s.story_id] || []);
  const sc = k => vp.filter(p => p.proof_strength === k).length;
  document.getElementById("s-stories").textContent    = stories.length;
  document.getElementById("s-proofs").textContent     = vp.length;
  document.getElementById("s-strong").textContent     = sc("Strong");
  document.getElementById("s-medium").textContent     = sc("Medium");
  document.getElementById("s-weak").textContent       = sc("Weak");
  document.getElementById("s-restricted").textContent = sc("Restricted");

  if (!stories.length) {{ none.style.display="block"; return; }}
  none.style.display = "none";

  stories.forEach(s => {{
    const proofs = proofsByStory[s.story_id] || [];
    const card = document.createElement("div");
    card.className = "story-card";

    const hdr = document.createElement("div");
    hdr.className = "sch";
    hdr.innerHTML = `
      <span class="st">${{esc(s.customer_name||"Unnamed")}} &mdash; ${{esc(s.title||"")}}</span>
      <span class="badge ${{s.proof_strength}}">${{s.proof_strength||"—"}}</span>
      <span class="mp">${{esc(s.industry||"")}}</span>
      <span class="mp">${{esc(s.geography||"")}}</span>
      <span style="font-size:18px;color:#8d8d8d">&#9660;</span>`;

    const det = document.createElement("div");
    det.className = "scd";
    det.innerHTML = `
      <dl class="smg">
        <dt>Story ID</dt><dd>${{esc(s.story_id)}}</dd>
        <dt>Named / Unnamed</dt><dd>${{esc(s.named_unnamed)}}</dd>
        <dt>Client Zero</dt><dd>${{esc(s.client_zero)}}</dd>
        <dt>Business Partner</dt><dd>${{esc(s.business_partner)}}</dd>
        <dt>GTM Motions</dt><dd>${{esc(s.gtm_motions)}}</dd>
        <dt>Open/Governed/Hybrid</dt><dd>${{esc(s.open_governed_hybrid)}}</dd>
        <dt>Structured/Unstructured</dt><dd>${{esc(s.structured_unstructured)}}</dd>
        <dt>Products</dt><dd>${{esc(s.products)}}</dd>
        <dt>Publication Date</dt><dd>${{esc(s.publication_date)}}</dd>
        <dt>QA Flag</dt><dd>${{esc(s.qa_flag||"—")}}</dd>
      </dl>
      <a class="sl" href="${{esc(s.source_url)}}" target="_blank">Open original story ↗</a>
      ${{proofs.length ? proofTable(proofs) : "<p style='margin-top:8px;color:#525252'>No proof points extracted.</p>"}}`;

    hdr.addEventListener("click", () => det.classList.toggle("open"));
    card.append(hdr, det);
    list.appendChild(card);
  }});
}}

function proofTable(proofs) {{
  const rows = proofs.map(p => `<tr>
    <td><span class="badge ${{p.proof_strength}}">${{esc(p.proof_strength)}}</span></td>
    <td>${{esc(p.proof_type)}}</td>
    <td>${{esc((p.proof_text||"").substring(0,200))}}${{(p.proof_text||"").length>200?"…":""}}</td>
    <td>${{esc(p.result_type)}}</td>
    <td>${{esc(p.quantified_result||"—")}}</td>
    <td>${{esc(p.gtm_motions)}}</td>
  </tr>`).join("");
  return `<table class="pt" style="margin-top:10px">
    <thead><tr><th>Strength</th><th>Type</th><th>Proof Text</th>
    <th>Result Type</th><th>Quantity</th><th>GTM</th></tr></thead>
    <tbody>${{rows}}</tbody></table>`;
}}

function esc(v) {{
  if (v === null || v === undefined) return "—";
  return String(v).replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}}

// ── Clear ───────────────────────────────────────────────────────────────
document.getElementById("clear-btn").addEventListener("click", () => {{
  document.getElementById("f-customer").value = "";
  document.getElementById("f-industry").value = "";
  document.getElementById("f-geo").value = "";
  document.getElementById("f-product").value = "";
  document.getElementById("f-age").value = 4;
  document.getElementById("age-val").textContent = "All";
  document.querySelectorAll("#filters input[type=checkbox]").forEach(cb=>cb.checked=true);
  applyFilters();
}});

document.getElementById("f-customer").addEventListener("input", applyFilters);
["f-industry","f-geo","f-product"].forEach(id=>
  document.getElementById(id).addEventListener("change", applyFilters));

// ── Initial render ──────────────────────────────────────────────────────
applyFilters();
</script>
</body>
</html>
"""
    with open(DASH_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"Dashboard HTML written: {DASH_HTML}")
