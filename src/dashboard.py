"""
dashboard.py
------------
IBM Customer Proof Intelligence dashboard.
Dark Carbon-style shell. Data embedded as inline JS (works from file://).
Tabs: Overview · Stories · Products · Geography · Coverage
Sidebar: keyword search + facets (industry, geography, product).
"""

import json
import os
from src.config import DASH_DIR, DASH_DATA, DASH_HTML
from src import logger


def write_dashboard_data(stories: list[dict], proof_points: list[dict]) -> None:
    """Write data.json alongside the HTML (kept as a backup/reference copy)."""
    os.makedirs(DASH_DIR, exist_ok=True)
    slim_stories = [{k: v for k, v in s.items() if k not in ("body_text", "proof_points")} for s in stories]
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
    """Write a fully self-contained dashboard HTML file."""
    os.makedirs(DASH_DIR, exist_ok=True)
    slim_stories = [{k: v for k, v in s.items() if k not in ("body_text", "proof_points")} for s in (stories or [])]
    slim_proofs = []
    for p in (proof_points or []):
        sp = dict(p)
        if isinstance(sp.get("gtm_motions"), list):
            sp["gtm_motions"] = "; ".join(sp["gtm_motions"])
        slim_proofs.append(sp)
    data_js = json.dumps({"stories": slim_stories, "proof_points": slim_proofs}, ensure_ascii=False)
    html = _build_html(data_js, len(slim_stories))
    with open(DASH_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"Dashboard HTML written: {DASH_HTML}")


def _build_html(data_js: str, story_count: int) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>IBM Customer Proof Intelligence</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  /* IBM Carbon Light theme */
  --ink:#ffffff;          /* page background      */
  --s1:#f4f4f4;           /* surface / sidebar    */
  --s2:#e8e8e8;           /* raised surface       */
  --s3:#d1d1d1;           /* hover / track        */
  --b1:#e0e0e0;           /* border subtle        */
  --b2:#c6c6c6;           /* border strong        */
  --tx:#161616;           /* primary text         */
  --mu:#525252;           /* secondary text       */
  --fa:#8d8d8d;           /* placeholder          */
  --blue:#0f62fe;--bl2:#0043ce;--cyan:#1192e8;
  --green:#24a148;--amber:#f1c21b;--red:#da1e28;--purple:#6929c4;
  --nav-h:52px;--sb-w:256px;--r:4px;
}}
body{{font-family:'IBM Plex Sans','Helvetica Neue',Arial,sans-serif;
     background:var(--ink);color:var(--tx);font-size:14px;line-height:1.5;min-height:100vh}}
a{{color:var(--blue);text-decoration:none}}a:hover{{color:var(--bl2)}}
button{{font-family:inherit}}
::-webkit-scrollbar{{width:5px;height:5px}}
::-webkit-scrollbar-track{{background:var(--s1)}}
::-webkit-scrollbar-thumb{{background:var(--b2);border-radius:3px}}

/* NAV — stays dark (IBM Carbon convention) */
#topnav{{position:sticky;top:0;z-index:300;height:var(--nav-h);background:#161616;
  border-bottom:1px solid #393939;display:flex;align-items:center;
  justify-content:space-between;padding:0 24px;gap:12px}}
.nav-logo{{display:flex;align-items:center;gap:9px;font-weight:600;font-size:13px;
  color:#f4f4f4;white-space:nowrap;flex-shrink:0}}
.nav-badge{{background:var(--blue);padding:2px 10px;font-size:9px;font-weight:700;
  letter-spacing:.08em;text-transform:uppercase;color:#fff;flex-shrink:0}}
.nav-tabs{{display:flex;gap:0;background:#262626;border:1px solid #393939;padding:3px;flex-shrink:0}}
.tab{{padding:5px 16px;font-size:12px;font-weight:600;cursor:pointer;
  color:#8d8d8d;border:none;background:none;white-space:nowrap;transition:all .15s}}
.tab.on{{background:var(--blue);color:#fff}}
.tab:hover:not(.on){{color:#f4f4f4;background:#393939}}
.nav-r{{display:flex;align-items:center;gap:10px;flex-shrink:0}}
#live-ct{{font-size:11px;color:#8d8d8d}}.live-n{{color:#78a9ff;font-weight:700}}
#export-btn{{padding:5px 14px;background:transparent;border:1px solid #525252;
  color:#8d8d8d;font-size:11px;font-weight:600;cursor:pointer;transition:all .15s}}
#export-btn:hover{{border-color:#78a9ff;color:#78a9ff}}

/* HERO — IBM Blue band */
#hero{{background:var(--blue);border-bottom:1px solid #0043ce;padding:28px 24px 20px;position:relative;overflow:hidden}}
#hero::before{{content:'';position:absolute;top:-80px;right:-60px;width:360px;height:360px;
  background:radial-gradient(circle,rgba(255,255,255,.08) 0%,transparent 70%);pointer-events:none}}
.hero-inner{{max-width:1440px;margin:0 auto;position:relative;z-index:1}}
.hero-eye{{font-size:10px;font-weight:400;letter-spacing:.1em;text-transform:uppercase;
  color:rgba(255,255,255,.7);margin-bottom:6px}}
#hero h1{{font-size:24px;font-weight:300;line-height:1.2;margin-bottom:4px;color:#fff}}
.hero-sub{{font-size:12px;color:rgba(255,255,255,.75);max-width:560px;margin-bottom:20px;font-weight:300}}
.hero-sub span{{color:#fff;font-weight:600}}
/* KPI row */
.kpi-row{{display:flex;gap:1px;background:rgba(0,0,0,.15);flex-wrap:wrap}}
.kpi{{background:rgba(0,0,0,.18);padding:16px 20px;min-width:110px;flex:1;position:relative;overflow:hidden}}
.kpi::before{{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:rgba(255,255,255,.3)}}
.kn{{font-size:32px;font-weight:300;line-height:1;margin-bottom:3px;color:#fff}}
.kl{{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:rgba(255,255,255,.7)}}

/* ACTIVE FILTER CHIPS */
#chip-row{{display:flex;flex-wrap:wrap;gap:6px;padding:10px 24px;
  border-bottom:1px solid var(--b1);background:var(--s1);min-height:0}}
#chip-row:empty{{padding:0;border-bottom:none}}
.chip-f{{display:flex;align-items:center;gap:5px;background:rgba(15,98,254,.10);
  border:1px solid rgba(15,98,254,.35);padding:3px 8px 3px 10px;font-size:11px;color:var(--blue)}}
.chip-x{{background:none;border:none;color:var(--blue);cursor:pointer;font-size:13px;
  line-height:1;padding:0 0 0 2px}}

/* LAYOUT */
.page-body{{display:flex;max-width:1440px;margin:0 auto}}
#sidebar{{width:var(--sb-w);flex-shrink:0;background:var(--s1);
  border-right:1px solid var(--b1);position:sticky;top:var(--nav-h);
  height:calc(100vh - var(--nav-h));overflow-y:auto;padding:0 0 24px}}
#main{{flex:1;min-width:0;padding:20px 24px;background:var(--ink)}}

/* SIDEBAR */
.sb-hd{{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.12em;
  color:var(--fa);padding:14px 16px 6px;border-bottom:1px solid var(--b1)}}
.sb-sec{{padding:12px 16px;border-bottom:1px solid var(--b1)}}
.sf-lbl{{display:block;font-size:10px;font-weight:700;text-transform:uppercase;
  letter-spacing:.08em;color:var(--mu);margin-bottom:5px}}
.sf{{width:100%;background:#fff;border:1px solid var(--b2);
  padding:7px 10px;font-size:12px;color:var(--tx);outline:none;
  transition:border-color .15s;border-radius:var(--r)}}
.sf:focus{{border-color:var(--blue)}}
.btn-clear{{display:block;margin:14px 16px 0;width:calc(100% - 32px);
  padding:7px;background:transparent;border:1px solid var(--b2);
  color:var(--mu);cursor:pointer;font-size:11px;font-weight:600;
  border-radius:var(--r);transition:all .15s}}
.btn-clear:hover{{border-color:var(--blue);color:var(--blue)}}
.sb-footer{{padding:14px 16px;font-size:10px;color:var(--fa);line-height:1.4}}

/* VIEW PANELS */
.vp{{display:none}}.vp.on{{display:block}}

/* SECTION HDR */
.sec-hdr{{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}}
.sec-title{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--mu)}}
.sec-ct{{font-size:11px;color:var(--fa);background:var(--s2);border:1px solid var(--b1);
  padding:2px 10px;border-radius:10px}}

/* CHARTS */
.chart-grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-bottom:20px}}
.cc{{background:var(--s1);border:1px solid var(--b1);border-radius:var(--r);padding:18px}}
.cc-title{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;
  color:var(--mu);margin-bottom:14px}}
.bar-list{{display:flex;flex-direction:column;gap:7px}}
.br{{display:grid;grid-template-columns:140px 1fr 42px;align-items:center;gap:8px}}
.br-lbl{{font-size:11px;color:var(--tx);white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;cursor:pointer;transition:color .1s}}
.br-lbl:hover{{color:var(--bl2)}}
.br-track{{background:var(--s3);border-radius:2px;height:5px;overflow:hidden}}
.br-fill{{height:100%;border-radius:2px;transition:width .4s}}
.br-val{{font-size:11px;font-weight:700;color:var(--mu);text-align:right}}

/* RECENTLY ADDED */
.recent-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}}
.recent-card{{background:var(--s1);border:1px solid var(--b1);border-radius:var(--r);
  padding:14px;cursor:pointer;transition:background .12s;border-left:3px solid var(--blue)}}
.recent-card:hover{{background:var(--s2)}}
.rc-name{{font-size:13px;font-weight:600;color:var(--tx);margin-bottom:3px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.rc-sub{{font-size:11px;color:var(--mu)}}
.rc-date{{font-size:10px;color:var(--bl2);margin-top:6px;font-weight:600}}

/* EVIDENCE TABLE */
.tbl-wrap{{overflow-x:auto;border:1px solid var(--b1)}}
table.ev{{width:100%;border-collapse:collapse;font-size:12px}}
table.ev thead th{{background:var(--s2);padding:9px 12px;text-align:left;
  font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;
  color:var(--fa);border-bottom:1px solid var(--b1);white-space:nowrap;
  cursor:pointer;user-select:none;position:sticky;top:0}}
table.ev thead th:hover{{color:var(--bl2)}}
table.ev thead th .sort-icon{{color:var(--fa);margin-left:3px}}
table.ev tbody tr{{border-bottom:1px solid var(--b1);cursor:pointer;transition:background .1s}}
table.ev tbody tr:hover{{background:var(--s2)}}
table.ev tbody td{{padding:9px 12px;vertical-align:top;max-width:240px}}
.td-client{{font-weight:600;color:var(--tx)}}
.td-title{{color:var(--mu);font-size:11px;margin-top:2px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:220px}}
.td-tag{{display:inline-block;background:var(--s3);padding:1px 7px;
  font-size:10px;color:var(--mu);margin:1px 2px 1px 0;white-space:nowrap}}
.td-tag.blue{{background:rgba(15,98,254,.12);color:var(--blue)}}
.td-outcome{{font-size:11px;color:#24a148;line-height:1.4;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.td-date{{font-size:11px;color:var(--fa);white-space:nowrap}}
#no-results{{text-align:center;padding:48px;color:var(--mu);display:none}}

/* PAGINATION */
.pager{{display:flex;align-items:center;gap:8px;padding:12px 0;font-size:12px;color:var(--mu)}}
.pg-btn{{background:var(--s2);border:1px solid var(--b1);color:var(--mu);
  padding:4px 10px;cursor:pointer;font-size:12px;transition:all .1s}}
.pg-btn:hover:not(:disabled){{border-color:var(--blue);color:var(--blue)}}
.pg-btn:disabled{{opacity:.35;cursor:default}}
.pg-info{{flex:1;text-align:center}}

/* PRODUCTS VIEW */
.prod-wrap{{display:grid;grid-template-columns:260px 1fr;gap:14px;min-height:500px}}
.prod-list-panel{{background:var(--s1);border:1px solid var(--b1);border-radius:var(--r);
  overflow-y:auto;max-height:calc(100vh - 200px)}}
.prod-search{{padding:10px 12px;border-bottom:1px solid var(--b1);position:sticky;top:0;background:var(--s1)}}
.pi{{padding:10px 14px;border-bottom:1px solid var(--b1);cursor:pointer;
  display:flex;justify-content:space-between;align-items:center;transition:background .1s}}
.pi:hover{{background:var(--s2)}}
.pi.on{{background:rgba(15,98,254,.12);border-left:3px solid var(--blue)}}
.pi-name{{font-size:12px;font-weight:500;color:var(--tx)}}
.pi-ct{{font-size:10px;color:var(--mu);background:var(--s3);padding:1px 7px;border-radius:10px}}
.prod-detail{{background:var(--s1);border:1px solid var(--b1);border-radius:var(--r);
  display:flex;flex-direction:column}}
.prod-detail-hdr{{padding:14px 18px;border-bottom:1px solid var(--b1);
  display:flex;align-items:center;justify-content:space-between}}
.pd-title{{font-size:15px;font-weight:600;color:var(--tx)}}
.pd-sub{{font-size:11px;color:var(--mu);margin-top:2px}}
.prod-stats{{display:flex;gap:1px;background:var(--b1);border-bottom:1px solid var(--b1)}}
.ps-item{{background:var(--s2);padding:10px 16px;flex:1;text-align:center}}
.ps-n{{font-size:20px;font-weight:300;color:var(--blue)}}
.ps-l{{font-size:9px;text-transform:uppercase;letter-spacing:.06em;color:var(--mu)}}
.prod-placeholder{{display:flex;align-items:center;justify-content:center;
  height:300px;color:var(--fa);font-size:13px;flex:1}}
.prod-dropdown-row{{margin-bottom:14px;display:flex;gap:10px;align-items:center}}

/* GEO VIEW */
.geo-layout{{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:14px}}
.geo-card{{background:var(--s1);border:1px solid var(--b1);border-radius:var(--r);overflow:hidden}}
.geo-hdr{{padding:12px 16px;border-bottom:1px solid var(--b1);
  display:flex;align-items:center;justify-content:space-between;cursor:pointer}}
.geo-hdr:hover{{background:var(--s2)}}
.geo-name{{font-size:14px;font-weight:600}}
.geo-ct{{font-size:12px;font-weight:700;color:var(--blue)}}
.geo-bar-outer{{height:3px;background:var(--s3)}}
.geo-bar-fill{{height:100%;background:linear-gradient(90deg,var(--blue),var(--cyan));transition:width .4s}}
.geo-body{{overflow-y:auto;max-height:320px}}
.geo-row{{padding:8px 16px;border-bottom:1px solid var(--b1);
  display:flex;align-items:center;gap:8px;cursor:pointer;transition:background .1s}}
.geo-row:hover{{background:var(--s2)}}
.geo-row-name{{font-size:12px;font-weight:600;color:var(--tx);flex:1;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.geo-row-ind{{font-size:10px;color:var(--mu)}}
.geo-collapsed .geo-body{{display:none}}

/* COVERAGE MATRIX */
.matrix-wrap{{overflow-x:auto}}
.matrix-controls{{display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap}}
.mc-btn{{padding:5px 14px;background:var(--s2);border:1px solid var(--b1);
  color:var(--mu);font-size:11px;font-weight:600;cursor:pointer;transition:all .1s}}
.mc-btn.on{{background:var(--blue);border-color:var(--blue);color:#fff}}
table.mx{{width:100%;border-collapse:collapse;font-size:11px}}
table.mx th{{background:var(--s2);padding:8px 10px;text-align:center;
  font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;
  color:var(--fa);border:1px solid var(--b1);white-space:nowrap}}
table.mx th.row-lbl{{text-align:left;min-width:160px}}
table.mx td{{padding:7px 10px;border:1px solid var(--b1);text-align:center;
  cursor:pointer;transition:background .1s;min-width:70px}}
table.mx td:hover{{outline:2px solid var(--bl2)}}
.mx-row-lbl{{text-align:left!important;font-weight:600;color:var(--tx);
  background:var(--s2)!important;white-space:nowrap;padding:7px 12px!important}}
.mx-0{{background:var(--s3);color:var(--fa)}}
.mx-1{{background:rgba(218,30,40,.12);color:#a2191f}}
.mx-2{{background:rgba(241,194,27,.20);color:#8a6914}}
.mx-3{{background:rgba(17,146,232,.15);color:#0043ce}}
.mx-4{{background:rgba(36,161,72,.18);color:#198038}}
.mx-legend{{display:flex;gap:14px;flex-wrap:wrap;margin-top:12px;font-size:11px}}
.ml-item{{display:flex;align-items:center;gap:6px}}
.ml-swatch{{width:14px;height:14px;border-radius:2px}}

/* DRAWER */
#dr-ov{{position:fixed;inset:0;background:rgba(0,0,0,.65);z-index:400;display:none}}
#dr-ov.on{{display:block}}
#drawer{{position:fixed;top:0;right:-660px;width:min(660px,100vw);height:100vh;
  background:var(--s1);border-left:1px solid var(--b1);z-index:401;
  overflow-y:auto;transition:right .22s ease;display:flex;flex-direction:column}}
#drawer.on{{right:0}}
.dr-hdr{{padding:20px 24px 16px;border-bottom:1px solid var(--b1);
  display:flex;justify-content:space-between;align-items:flex-start;gap:12px;
  position:sticky;top:0;background:var(--s1);z-index:1}}
.dr-company{{font-size:18px;font-weight:600;color:var(--tx);line-height:1.3}}
.dr-title{{font-size:12px;color:var(--mu);margin-top:3px;font-weight:300;line-height:1.4}}
.dr-close{{background:transparent;border:1px solid var(--b2);cursor:pointer;
  font-size:16px;color:var(--mu);width:30px;height:30px;
  display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:all .12s}}
.dr-close:hover{{background:var(--s2);border-color:var(--blue);color:var(--tx)}}
.dr-body{{padding:20px 24px;flex:1}}
.dr-sec{{margin-bottom:20px}}
.dr-sec-title{{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.12em;
  color:var(--mu);margin-bottom:10px;padding-bottom:7px;border-bottom:1px solid var(--b1)}}
.meta-g{{display:grid;grid-template-columns:1fr 1fr;gap:8px 20px}}
.mk{{font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;
  color:var(--fa);margin-bottom:2px}}
.mv{{font-size:13px;color:var(--tx);font-weight:300}}
.quote-box{{background:var(--s2);border-left:3px solid var(--blue);
  padding:12px 14px;font-size:12px;color:var(--tx);line-height:1.6;
  font-style:italic;font-weight:300}}
.proof-box{{background:rgba(36,161,72,.08);border-left:3px solid var(--green);
  padding:12px 14px;font-size:12px;color:#198038;line-height:1.5}}
.dr-btn{{display:inline-block;padding:10px 22px;background:var(--blue);
  color:#fff;font-size:13px;font-weight:600;transition:background .12s}}
.dr-btn:hover{{background:#0050e6;color:#fff}}

@media(max-width:1024px){{.chart-grid{{grid-template-columns:1fr 1fr}}}}
@media(max-width:768px){{
  #sidebar{{display:none}}
  .chart-grid{{grid-template-columns:1fr}}
  .prod-wrap{{grid-template-columns:1fr}}
}}
</style>
</head>
<body>

<nav id="topnav">
  <div class="nav-logo">
    <svg width="38" height="15" viewBox="0 0 40 16" fill="none" aria-label="IBM">
      <path fill="#fff" d="M0 0h40v2H0zM0 3.6h40v2H0zM0 7.2h40v2H0zM0 10.8h40v2H0zM0 14.4h40v1.6H0z"/>
      <rect x="10" y="0" width="3.5" height="2" fill="#161616"/>
      <rect x="26.5" y="0" width="3.5" height="2" fill="#161616"/>
      <rect x="10" y="3.6" width="3.5" height="2" fill="#161616"/>
      <rect x="26.5" y="3.6" width="3.5" height="2" fill="#161616"/>
      <rect x="5" y="7.2" width="3.5" height="2" fill="#161616"/>
      <rect x="31.5" y="7.2" width="3.5" height="2" fill="#161616"/>
      <rect x="10" y="10.8" width="3.5" height="2" fill="#161616"/>
      <rect x="26.5" y="10.8" width="3.5" height="2" fill="#161616"/>
      <rect x="10" y="14.4" width="3.5" height="1.6" fill="#161616"/>
      <rect x="26.5" y="14.4" width="3.5" height="1.6" fill="#161616"/>
    </svg>
    Customer Proof Intelligence
  </div>
  <div class="nav-tabs">
    <button class="tab on"  data-view="overview">Overview</button>
    <button class="tab"     data-view="stories">Stories</button>
    <button class="tab"     data-view="products">Products</button>
    <button class="tab"     data-view="geography">Geography</button>
    <button class="tab"     data-view="coverage">Coverage</button>
  </div>
  <div class="nav-r">
    <div id="live-ct"><span class="live-n" id="lc-n">{story_count}</span> stories</div>
    <button id="export-btn">⬇ Export CSV</button>
    <div class="nav-badge">IBM Proof</div>
  </div>
</nav>

<div id="hero">
  <div class="hero-inner">
    <div class="hero-eye">IBM · Public Case Studies · Proof Intelligence</div>
    <h1>Customer Proof Intelligence</h1>
    <p class="hero-sub">
      <span id="corpus-ct">{story_count}</span> public IBM case studies — searchable by product, industry, geography or keyword.
      Indexed <span id="index-date">—</span>.
    </p>
    <div class="kpi-row">
      <div class="kpi k0"><div class="kn" id="kpi-total">{story_count}</div><div class="kl">Public Stories</div></div>
      <div class="kpi k1"><div class="kn" id="kpi-ext">—</div><div class="kl">External Clients</div></div>
      <div class="kpi k2"><div class="kn" id="kpi-prod">—</div><div class="kl">Products</div></div>
      <div class="kpi k3"><div class="kn" id="kpi-ind">—</div><div class="kl">Industries</div></div>
      <div class="kpi k4"><div class="kn" id="kpi-geo">—</div><div class="kl">Geographies</div></div>
      <div class="kpi k5"><div class="kn" id="kpi-outcomes">—</div><div class="kl">With Outcomes</div></div>
    </div>
  </div>
</div>

<div id="chip-row"></div>

<div class="page-body">

  <!-- SIDEBAR -->
  <aside id="sidebar">
    <div class="sb-hd">Filters</div>
    <div class="sb-sec">
      <label class="sf-lbl">Keyword</label>
      <input id="f-kw" class="sf" type="text" placeholder="Search all fields…">
    </div>
    <div class="sb-sec">
      <label class="sf-lbl">Industry</label>
      <select id="f-ind" class="sf"><option value="">All industries</option></select>
    </div>
    <div class="sb-sec">
      <label class="sf-lbl">Geography</label>
      <select id="f-geo" class="sf"><option value="">All geographies</option></select>
    </div>
    <div class="sb-sec">
      <label class="sf-lbl">Product / Category</label>
      <select id="f-prod" class="sf"><option value="">All products</option></select>
    </div>
    <div class="sb-sec">
      <label class="sf-lbl">Client type</label>
      <select id="f-ctype" class="sf">
        <option value="">All clients</option>
        <option value="external">External only (non-IBM)</option>
        <option value="ibm">IBM internal / Client Zero</option>
      </select>
    </div>
    <button class="btn-clear" id="btn-clear">↺ Clear all filters</button>
    <div class="sb-footer" id="sb-footer">Showing all stories</div>
  </aside>

  <main id="main">

    <!-- OVERVIEW -->
    <div class="vp on" id="vp-overview">
      <div class="chart-grid">
        <div class="cc">
          <div class="cc-title">Stories by Industry</div>
          <div class="bar-list" id="ch-ind"></div>
        </div>
        <div class="cc">
          <div class="cc-title">Stories by Geography</div>
          <div class="bar-list" id="ch-geo"></div>
        </div>
        <div class="cc">
          <div class="cc-title">Top Products by Story Count</div>
          <div class="bar-list" id="ch-prod"></div>
        </div>
        <div class="cc" style="grid-column:1/-1">
          <div class="cc-title">Stories Published Over Time</div>
          <div id="ch-time" style="height:140px;position:relative"></div>
        </div>
      </div>
      <div class="sec-hdr">
        <span class="sec-title">Recently Added</span>
        <span class="sec-ct" id="recent-ct"></span>
      </div>
      <div class="recent-grid" id="recent-grid"></div>
    </div>

    <!-- STORIES TABLE -->
    <div class="vp" id="vp-stories">
      <div class="sec-hdr">
        <span class="sec-title">Evidence Table</span>
        <span class="sec-ct" id="tbl-ct">0 stories</span>
      </div>
      <div class="tbl-wrap">
        <table class="ev" id="ev-table">
          <thead>
            <tr>
              <th data-col="customer_name">Client <span class="sort-icon">↕</span></th>
              <th data-col="industry">Industry <span class="sort-icon">↕</span></th>
              <th data-col="geography">Geography <span class="sort-icon">↕</span></th>
              <th data-col="product_categories">Products</th>
              <th data-col="quantified_proof">Outcome</th>
              <th data-col="publication_date">Published <span class="sort-icon">↕</span></th>
            </tr>
          </thead>
          <tbody id="ev-body"></tbody>
        </table>
      </div>
      <div id="no-results">No stories match your filters.</div>
      <div class="pager" id="pager">
        <button class="pg-btn" id="pg-prev">← Prev</button>
        <div class="pg-info" id="pg-info"></div>
        <button class="pg-btn" id="pg-next">Next →</button>
      </div>
    </div>

    <!-- PRODUCTS VIEW -->
    <div class="vp" id="vp-products">
      <div class="sec-hdr">
        <span class="sec-title">Stories by IBM Product</span>
        <span class="sec-ct" id="prod-ct">0 products</span>
      </div>
      <div class="prod-dropdown-row">
        <label class="sf-lbl" style="margin:0;white-space:nowrap">Quick select:</label>
        <select id="prod-dd" class="sf" style="max-width:380px">
          <option value="">— choose a product —</option>
        </select>
      </div>
      <div class="prod-wrap">
        <div class="prod-list-panel">
          <div class="prod-search">
            <input id="prod-search" class="sf" type="text" placeholder="Filter products…" style="font-size:11px;padding:5px 8px">
          </div>
          <div id="prod-list"></div>
        </div>
        <div class="prod-detail" id="prod-detail">
          <div class="prod-placeholder" id="pd-placeholder">← Select a product to see client stories</div>
          <div id="pd-inner" style="display:none">
            <div class="prod-detail-hdr">
              <div>
                <div class="pd-title" id="pd-title"></div>
                <div class="pd-sub" id="pd-sub"></div>
              </div>
            </div>
            <div class="prod-stats" id="pd-stats"></div>
            <div style="overflow-x:auto">
              <table class="ev" id="pd-table">
                <thead><tr>
                  <th>Client</th><th>Industry</th><th>Geography</th><th>Outcome</th><th>Published</th>
                </tr></thead>
                <tbody id="pd-body"></tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- GEOGRAPHY VIEW -->
    <div class="vp" id="vp-geography">
      <div class="sec-hdr">
        <span class="sec-title">Stories by Geography</span>
        <span class="sec-ct" id="geo-ct">0 geographies</span>
      </div>
      <div class="geo-layout" id="geo-layout"></div>
    </div>

    <!-- COVERAGE MATRIX -->
    <div class="vp" id="vp-coverage">
      <div class="sec-hdr">
        <span class="sec-title">Coverage Matrix — Where are the gaps?</span>
        <span class="sec-ct" id="cov-ct"></span>
      </div>
      <p style="font-size:12px;color:var(--mu);margin-bottom:14px;max-width:700px;line-height:1.5">
        Each cell shows the number of stories at the intersection of an industry row and a geography column.
        Red = 0 stories (gap) · Amber = 1–2 · Blue = 3–5 · Green = 6+.
        Click any cell to filter the Stories view.
      </p>
      <div class="matrix-controls">
        <span style="font-size:11px;color:var(--mu);align-self:center">Columns:</span>
        <button class="mc-btn on" data-mx="geo">Geography</button>
        <button class="mc-btn" data-mx="prod">Top Products</button>
      </div>
      <div class="matrix-wrap" id="matrix-wrap"></div>
      <div class="mx-legend">
        <div class="ml-item"><div class="ml-swatch mx-0" style="background:var(--s3)"></div><span style="color:var(--fa)">0 stories</span></div>
        <div class="ml-item"><div class="ml-swatch mx-1" style="background:rgba(218,30,40,.18)"></div><span style="color:var(--mu)">1–2</span></div>
        <div class="ml-item"><div class="ml-swatch mx-2" style="background:rgba(241,194,27,.18)"></div><span style="color:var(--mu)">3–5</span></div>
        <div class="ml-item"><div class="ml-swatch mx-3" style="background:rgba(17,146,232,.25)"></div><span style="color:var(--mu)">6–15</span></div>
        <div class="ml-item"><div class="ml-swatch mx-4" style="background:rgba(36,161,72,.3)"></div><span style="color:var(--mu)">16+</span></div>
      </div>
    </div>

  </main>
</div>

<!-- DRAWER -->
<div id="dr-ov"></div>
<div id="drawer">
  <div class="dr-hdr">
    <div>
      <div class="dr-company" id="dr-co"></div>
      <div class="dr-title" id="dr-title"></div>
    </div>
    <button class="dr-close" id="dr-close">✕</button>
  </div>
  <div class="dr-body" id="dr-body"></div>
</div>

<script>
// ── DATA ──────────────────────────────────────────────────────────────────────
const _RAW = {data_js};
const ALL = _RAW.stories || [];

// ── UTILS ─────────────────────────────────────────────────────────────────────
const esc = v => v == null ? '—' : String(v)
  .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const uniq = arr => [...new Set(arr.filter(Boolean))].sort();
const isIBM = s => /^\\s*ibm\\b/i.test(s.customer_name || '');

function avatarColor(n) {{
  const c=['#0f62fe','#6929c4','#005d5d','#9f1853','#1192e8','#009d9a','#198038','#b28600'];
  let h=0; for(let i=0;i<(n||'').length;i++) h=(h*31+n.charCodeAt(i))&0xffff;
  return c[h%c.length];
}}
function initials(n) {{
  if(!n) return '?';
  const w=n.trim().split(/\\s+/);
  return (w.length>=2?w[0][0]+w[w.length-1][0]:n.slice(0,2)).toUpperCase();
}}

// Full-text search across all meaningful fields
function storyText(s) {{
  return [s.customer_name, s.title, s.industry, s.geography, s.products,
          s.description, s.challenge, s.solution, s.business_outcomes,
          s.quantified_proof, s.customer_quote, s.gtm_motions,
          (s.topics||[]).join(' '), (s.product_categories||[]).join(' ')]
    .filter(Boolean).join(' ').toLowerCase();
}}

// Collect all products from both fields
function storyProds(s) {{
  const a = (s.products||'').split(',').map(p=>p.trim()).filter(p=>p&&p!=='Needs review');
  const b = (s.product_categories||[]).filter(Boolean);
  return [...new Set([...a,...b])];
}}

// ── BOOT KPIs ────────────────────────────────────────────────────────────────
const allProds = [];
ALL.forEach(s => storyProds(s).forEach(p => allProds.push(p)));
document.getElementById('kpi-ext').textContent      = ALL.filter(s=>!isIBM(s)).length;
document.getElementById('kpi-prod').textContent     = uniq(allProds).length;
document.getElementById('kpi-ind').textContent      = uniq(ALL.map(s=>s.industry).filter(i=>i&&i!=='Needs review')).length;
document.getElementById('kpi-geo').textContent      = uniq(ALL.map(s=>s.geography).filter(g=>g&&g!=='Needs review')).length;
document.getElementById('kpi-outcomes').textContent = ALL.filter(s=>s.quantified_proof).length;

// Index date from most recent collected_at
const latestDate = ALL.map(s=>s.collected_at||'').filter(Boolean).sort().pop();
if(latestDate) document.getElementById('index-date').textContent = latestDate.slice(0,10);

// ── POPULATE FILTERS ─────────────────────────────────────────────────────────
function fillSelect(id, vals) {{
  const el = document.getElementById(id);
  vals.forEach(v => {{ const o=document.createElement('option'); o.value=o.textContent=v; el.appendChild(o); }});
}}
fillSelect('f-ind',  uniq(ALL.map(s=>s.industry).filter(v=>v&&v!=='Needs review')));
fillSelect('f-geo',  uniq(ALL.map(s=>s.geography).filter(v=>v&&v!=='Needs review')));
fillSelect('f-prod', uniq(allProds));

// ── FILTER STATE ──────────────────────────────────────────────────────────────
let _filtered = ALL.slice();
let _sortCol = 'publication_date', _sortDir = -1;
let _page = 1;
const PAGE_SIZE = 50;

function readFilters() {{
  return {{
    kw:    (document.getElementById('f-kw').value||'').toLowerCase().trim(),
    ind:   document.getElementById('f-ind').value,
    geo:   document.getElementById('f-geo').value,
    prod:  document.getElementById('f-prod').value,
    ctype: document.getElementById('f-ctype').value,
  }};
}}

function applyFilters() {{
  const f = readFilters();
  _filtered = ALL.filter(s => {{
    if(f.kw && !storyText(s).includes(f.kw)) return false;
    if(f.ind && s.industry !== f.ind) return false;
    if(f.geo && s.geography !== f.geo) return false;
    if(f.prod) {{
      const prods = storyProds(s).map(p=>p.toLowerCase());
      if(!prods.some(p=>p.includes(f.prod.toLowerCase()))) return false;
    }}
    if(f.ctype === 'external' && isIBM(s)) return false;
    if(f.ctype === 'ibm' && !isIBM(s)) return false;
    return true;
  }});
  _page = 1;
  renderChips(f);
  document.getElementById('lc-n').textContent = _filtered.length;
  document.getElementById('sb-footer').textContent =
    _filtered.length === ALL.length ? 'Showing all stories'
    : `${{_filtered.length}} of ${{ALL.length}} stories`;
  render(_filtered);
}}

function renderChips(f) {{
  const row = document.getElementById('chip-row');
  row.innerHTML = '';
  const add = (lbl, clear) => {{
    const c = document.createElement('div'); c.className='chip-f';
    const x = document.createElement('button'); x.className='chip-x'; x.textContent='×';
    x.addEventListener('click', () => {{ clear(); applyFilters(); }});
    c.innerHTML = `<span>${{esc(lbl)}}</span>`; c.appendChild(x);
    row.appendChild(c);
  }};
  if(f.kw)    add(`Keyword: "${{f.kw}}"`,  () => document.getElementById('f-kw').value='');
  if(f.ind)   add(`Industry: ${{f.ind}}`,   () => document.getElementById('f-ind').value='');
  if(f.geo)   add(`Geography: ${{f.geo}}`,  () => document.getElementById('f-geo').value='');
  if(f.prod)  add(`Product: ${{f.prod}}`,   () => document.getElementById('f-prod').value='');
  if(f.ctype) add(f.ctype==='external'?'External clients only':'IBM internal only',
                  () => document.getElementById('f-ctype').value='');
}}

// ── TAB SWITCHING ────────────────────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('.tab').forEach(b=>b.classList.remove('on'));
    document.querySelectorAll('.vp').forEach(v=>v.classList.remove('on'));
    btn.classList.add('on');
    document.getElementById('vp-'+btn.dataset.view).classList.add('on');
  }});
}});

// ── SORT TABLE ───────────────────────────────────────────────────────────────
document.querySelectorAll('table.ev thead th[data-col]').forEach(th => {{
  th.addEventListener('click', () => {{
    const col = th.dataset.col;
    if(_sortCol === col) _sortDir *= -1; else {{ _sortCol=col; _sortDir=1; }}
    _page=1;
    renderTable(_filtered);
  }});
}});

// ── OVERVIEW CHARTS ───────────────────────────────────────────────────────────
function barChart(elId, data, color, onClick) {{
  const max = data[0]?.[1]||1;
  document.getElementById(elId).innerHTML = data.map(([n,c]) => `
    <div class="br">
      <div class="br-lbl" title="${{esc(n)}}" data-val="${{esc(n)}}">${{esc(n)}}</div>
      <div class="br-track"><div class="br-fill" style="width:${{(c/max*100).toFixed(1)}}%;background:${{color}}"></div></div>
      <div class="br-val">${{c}}</div>
    </div>`).join('');
  if(onClick) document.getElementById(elId).querySelectorAll('.br-lbl').forEach(el =>
    el.addEventListener('click', () => onClick(el.dataset.val)));
}}

function renderCharts(stories) {{
  // Industry
  const ic={{}};
  stories.forEach(s=>{{ if(s.industry&&s.industry!=='Needs review') ic[s.industry]=(ic[s.industry]||0)+1; }});
  barChart('ch-ind', Object.entries(ic).sort((a,b)=>b[1]-a[1]).slice(0,8),
    'linear-gradient(90deg,var(--blue),var(--cyan))',
    v=>{{ document.getElementById('f-ind').value=v; applyFilters(); switchTab('stories'); }});

  // Geo
  const gc={{}};
  stories.forEach(s=>{{ if(s.geography&&s.geography!=='Needs review') gc[s.geography]=(gc[s.geography]||0)+1; }});
  barChart('ch-geo', Object.entries(gc).sort((a,b)=>b[1]-a[1]),
    'linear-gradient(90deg,var(--cyan),#80deea)',
    v=>{{ document.getElementById('f-geo').value=v; applyFilters(); switchTab('stories'); }});

  // Products
  const pc={{}};
  stories.forEach(s=> storyProds(s).forEach(p=>{{ pc[p]=(pc[p]||0)+1; }}));
  barChart('ch-prod', Object.entries(pc).sort((a,b)=>b[1]-a[1]).slice(0,8),
    'linear-gradient(90deg,var(--amber),#ffcf47)',
    v=>{{ document.getElementById('f-prod').value=v; applyFilters(); switchTab('stories'); }});

  // Timeline
  const by={{}};
  stories.forEach(s=>{{ if(s.publication_date) {{ const y=s.publication_date.slice(0,4); by[y]=(by[y]||0)+1; }} }});
  const yrs=Object.keys(by).sort();
  const el=document.getElementById('ch-time');
  if(yrs.length<2){{ el.innerHTML='<div style="color:var(--fa);font-size:11px;padding:20px">Insufficient date data</div>'; return; }}
  const mx=Math.max(...Object.values(by),1), W=el.offsetWidth||600, H=140, pad=28;
  const bw=Math.max(6,Math.floor((W-pad*2)/yrs.length)-4);
  let svg=`<svg width="100%" height="${{H}}" viewBox="0 0 ${{W}} ${{H}}">`;
  yrs.forEach((yr,i)=>{{
    const x=pad+i*(W-pad*2)/Math.max(yrs.length-1,1)-bw/2;
    const c=by[yr], bh=(c/mx)*(H-44);
    svg+=`<rect x="${{x.toFixed(1)}}" y="${{(H-28-bh).toFixed(1)}}" width="${{bw}}" height="${{bh.toFixed(1)}}" rx="2" fill="var(--blue)" opacity=".7"/>`;
    svg+=`<text x="${{(x+bw/2).toFixed(1)}}" y="${{H-10}}" text-anchor="middle" font-size="9" fill="var(--mu)">${{yr}}</text>`;
    svg+=`<text x="${{(x+bw/2).toFixed(1)}}" y="${{(H-33-bh).toFixed(1)}}" text-anchor="middle" font-size="9" fill="var(--mu)">${{c}}</text>`;
  }});
  svg+=`</svg>`; el.innerHTML=svg;
}}

function renderRecent(stories) {{
  const recent = [...stories].sort((a,b)=>(b.publication_date||'').localeCompare(a.publication_date||'')).slice(0,6);
  document.getElementById('recent-ct').textContent = 'Latest '+recent.length;
  document.getElementById('recent-grid').innerHTML = recent.map(s => {{
    const name = s.customer_name||s.title||'Unknown';
    return `<div class="recent-card" onclick='openDrawer(ALL.find(x=>x.source_url=="${{s.source_url}}"))'>
      <div class="rc-name">${{esc(name)}}</div>
      <div class="rc-sub">${{esc(s.industry||'—')}} · ${{esc(s.geography||'—')}}</div>
      <div class="rc-date">${{esc(s.publication_date||'—')}}</div>
    </div>`;
  }}).join('');
}}

// ── EVIDENCE TABLE ────────────────────────────────────────────────────────────
function renderTable(stories) {{
  const sorted = [...stories].sort((a,b) => {{
    let av=a[_sortCol]||'', bv=b[_sortCol]||'';
    if(Array.isArray(av)) av=av.join(',');
    if(Array.isArray(bv)) bv=bv.join(',');
    return av < bv ? -_sortDir : av > bv ? _sortDir : 0;
  }});
  const total=sorted.length, pages=Math.max(1,Math.ceil(total/PAGE_SIZE));
  _page=Math.min(_page,pages);
  const slice=sorted.slice((_page-1)*PAGE_SIZE, _page*PAGE_SIZE);
  document.getElementById('tbl-ct').textContent=total+' stories';
  document.getElementById('no-results').style.display=total?'none':'block';
  document.querySelector('.tbl-wrap').style.display=total?'':'none';
  document.getElementById('pager').style.display=total?'':'none';

  document.getElementById('ev-body').innerHTML = slice.map(s => {{
    const name = s.customer_name||s.title||'Unknown';
    const prods = storyProds(s).slice(0,3);
    return `<tr onclick='openDrawer(ALL.find(x=>x.source_url=="${{s.source_url}}"))'>
      <td>
        <div class="td-client">${{esc(name)}}</div>
        <div class="td-title" title="${{esc(s.title)}}">${{esc(s.title)}}</div>
      </td>
      <td><div class="td-tag">${{esc(s.industry||'—')}}</div></td>
      <td><div class="td-tag">${{esc(s.geography||'—')}}</div></td>
      <td>${{prods.map(p=>`<div class="td-tag blue">${{esc(p)}}</div>`).join('')}}</td>
      <td><div class="td-outcome">${{esc(s.quantified_proof)}}</div></td>
      <td class="td-date">${{esc(s.publication_date||'—')}}</td>
    </tr>`;
  }}).join('');

  document.getElementById('pg-info').textContent=`Page ${{_page}} of ${{pages}} (${{total}} stories)`;
  document.getElementById('pg-prev').disabled=_page<=1;
  document.getElementById('pg-next').disabled=_page>=pages;
}}
document.getElementById('pg-prev').addEventListener('click',()=>{{ _page--; renderTable(_filtered); }});
document.getElementById('pg-next').addEventListener('click',()=>{{ _page++; renderTable(_filtered); }});

// ── PRODUCTS VIEW ─────────────────────────────────────────────────────────────
let _prodMap = {{}};

function buildProdMap(stories) {{
  _prodMap = {{}};
  stories.forEach(s => {{
    const seen=new Set();
    storyProds(s).forEach(p => {{
      if(!seen.has(p)) {{ seen.add(p); if(!_prodMap[p]) _prodMap[p]=[]; _prodMap[p].push(s); }}
    }});
  }});
}}

function renderProdsView(stories) {{
  buildProdMap(stories);
  const sorted = Object.entries(_prodMap).sort((a,b)=>b[1].length-a[1].length);
  document.getElementById('prod-ct').textContent = sorted.length+' products';

  const dd = document.getElementById('prod-dd');
  dd.innerHTML = '<option value="">— choose a product —</option>';
  sorted.forEach(([n])=>{{ const o=document.createElement('option'); o.value=o.textContent=n; dd.appendChild(o); }});

  renderProdList(sorted, '');
}}

function renderProdList(sorted, filter) {{
  const vis = filter ? sorted.filter(([n])=>n.toLowerCase().includes(filter.toLowerCase())) : sorted;
  document.getElementById('prod-list').innerHTML = vis.map(([n,strs]) =>
    `<div class="pi" data-prod="${{esc(n)}}" onclick="showProdDetail('${{esc(n)}}')">
      <span class="pi-name">${{esc(n)}}</span>
      <span class="pi-ct">${{strs.length}}</span>
    </div>`).join('');
}}

function showProdDetail(name) {{
  const strs = _prodMap[name]; if(!strs) return;
  document.querySelectorAll('.pi').forEach(el=>el.classList.toggle('on', el.dataset.prod===name));
  document.getElementById('prod-dd').value = name;
  document.getElementById('pd-placeholder').style.display='none';
  document.getElementById('pd-inner').style.display='block';
  document.getElementById('pd-title').textContent = name;

  const geos={{}}, inds={{}};
  strs.forEach(s=>{{ if(s.geography&&s.geography!=='Needs review') geos[s.geography]=(geos[s.geography]||0)+1; }});
  strs.forEach(s=>{{ if(s.industry&&s.industry!=='Needs review') inds[s.industry]=(inds[s.industry]||0)+1; }});
  const topGeo=Object.entries(geos).sort((a,b)=>b[1]-a[1]).slice(0,3).map(([g])=>g).join(', ')||'—';
  const topInd=Object.entries(inds).sort((a,b)=>b[1]-a[1]).slice(0,3).map(([i])=>i).join(', ')||'—';
  document.getElementById('pd-sub').textContent=`Top geographies: ${{topGeo}}`;
  document.getElementById('pd-stats').innerHTML=`
    <div class="ps-item"><div class="ps-n">${{strs.length}}</div><div class="ps-l">Stories</div></div>
    <div class="ps-item"><div class="ps-n">${{uniq(strs.map(s=>s.customer_name)).length}}</div><div class="ps-l">Clients</div></div>
    <div class="ps-item"><div class="ps-n">${{Object.keys(geos).length}}</div><div class="ps-l">Geographies</div></div>
    <div class="ps-item"><div class="ps-n">${{Object.keys(inds).length}}</div><div class="ps-l">Industries</div></div>`;

  const sorted=[...strs].sort((a,b)=>(a.customer_name||'').localeCompare(b.customer_name||''));
  document.getElementById('pd-body').innerHTML=sorted.map(s=>{{
    const name=s.customer_name||s.title||'Unknown';
    return `<tr onclick='openDrawer(ALL.find(x=>x.source_url=="${{s.source_url}}"))'>
      <td><div class="td-client">${{esc(name)}}</div></td>
      <td><div class="td-tag">${{esc(s.industry||'—')}}</div></td>
      <td><div class="td-tag">${{esc(s.geography||'—')}}</div></td>
      <td><div class="td-outcome">${{esc(s.quantified_proof)}}</div></td>
      <td class="td-date">${{esc(s.publication_date||'—')}}</td>
    </tr>`;
  }}).join('');
}}

document.getElementById('prod-dd').addEventListener('change', e => {{ if(e.target.value) showProdDetail(e.target.value); }});
document.getElementById('prod-search').addEventListener('input', e => {{
  const sorted=Object.entries(_prodMap).sort((a,b)=>b[1].length-a[1].length);
  renderProdList(sorted, e.target.value);
}});

// ── GEOGRAPHY VIEW ────────────────────────────────────────────────────────────
function renderGeoView(stories) {{
  const map={{}};
  stories.forEach(s=>{{ const g=s.geography||'Unknown'; if(!map[g]) map[g]=[]; map[g].push(s); }});
  const sorted=Object.entries(map).sort((a,b)=>b[1].length-a[1].length);
  const maxC=sorted[0]?.[1].length||1;
  document.getElementById('geo-ct').textContent=sorted.length+' geographies';
  document.getElementById('geo-layout').innerHTML=sorted.map(([geo,strs])=>{{
    const pct=(strs.length/maxC*100).toFixed(1);
    const rows=[...strs].sort((a,b)=>(a.customer_name||'').localeCompare(b.customer_name||'')).map(s=>{{
      const name=s.customer_name||s.title||'Unknown';
      return `<div class="geo-row" onclick='openDrawer(ALL.find(x=>x.source_url=="${{s.source_url}}"))'>
        <div class="geo-row-name">${{esc(name)}}</div>
        <div class="geo-row-ind">${{esc(s.industry||'—')}}</div>
      </div>`;
    }}).join('');
    return `<div class="geo-card">
      <div class="geo-hdr" onclick="this.closest('.geo-card').classList.toggle('geo-collapsed')">
        <span class="geo-name">${{esc(geo)}}</span>
        <span class="geo-ct">${{strs.length}}</span>
      </div>
      <div class="geo-bar-outer"><div class="geo-bar-fill" style="width:${{pct}}%"></div></div>
      <div class="geo-body">${{rows}}</div>
    </div>`;
  }}).join('');
}}

// ── COVERAGE MATRIX ───────────────────────────────────────────────────────────
let _mxMode = 'geo';
document.querySelectorAll('.mc-btn').forEach(btn=>{{
  btn.addEventListener('click', ()=>{{
    document.querySelectorAll('.mc-btn').forEach(b=>b.classList.remove('on'));
    btn.classList.add('on');
    _mxMode=btn.dataset.mx;
    renderMatrix(_filtered);
  }});
}});

function mxClass(n){{
  if(!n) return 'mx-0';
  if(n<=2) return 'mx-1';
  if(n<=5) return 'mx-2';
  if(n<=15) return 'mx-3';
  return 'mx-4';
}}

function renderMatrix(stories) {{
  const rows = uniq(stories.map(s=>s.industry).filter(v=>v&&v!=='Needs review')).slice(0,12);
  let cols;
  if(_mxMode==='geo') {{
    cols = uniq(stories.map(s=>s.geography).filter(v=>v&&v!=='Needs review'));
  }} else {{
    const pc={{}};
    stories.forEach(s=>storyProds(s).forEach(p=>{{ pc[p]=(pc[p]||0)+1; }}));
    cols = Object.entries(pc).sort((a,b)=>b[1]-a[1]).slice(0,8).map(([p])=>p);
  }}

  const gapCount = rows.reduce((acc,row)=>
    acc+cols.filter(col=>{{
      if(_mxMode==='geo') return !stories.some(s=>s.industry===row&&s.geography===col);
      else return !stories.some(s=>s.industry===row&&storyProds(s).includes(col));
    }}).length, 0);
  document.getElementById('cov-ct').textContent=`${{gapCount}} gaps identified (cells with 0 stories)`;

  let html=`<table class="mx"><thead><tr>
    <th class="row-lbl">Industry \\ ${{_mxMode==='geo'?'Geography':'Product'}}</th>
    ${{cols.map(c=>`<th title="${{esc(c)}}">${{esc(c.length>12?c.slice(0,12)+'…':c)}}</th>`).join('')}}
  </tr></thead><tbody>`;

  rows.forEach(row=>{{
    html+=`<tr><td class="mx-row-lbl">${{esc(row)}}</td>`;
    cols.forEach(col=>{{
      let n;
      if(_mxMode==='geo') n=stories.filter(s=>s.industry===row&&s.geography===col).length;
      else n=stories.filter(s=>s.industry===row&&storyProds(s).includes(col)).length;
      html+=`<td class="${{mxClass(n)}}" title="${{esc(row)}} × ${{esc(col)}}: ${{n}} stories"
        onclick='mxDrill("${{esc(row)}}","${{esc(col)}}",${{JSON.stringify(_mxMode)}})'>
        ${{n||''}}</td>`;
    }});
    html+='</tr>';
  }});
  html+='</tbody></table>';
  document.getElementById('matrix-wrap').innerHTML=html;
}}

function mxDrill(row, col, mode) {{
  document.getElementById('f-ind').value=row;
  if(mode==='geo') document.getElementById('f-geo').value=col;
  else {{ document.getElementById('f-prod').value=col; }}
  applyFilters();
  switchTab('stories');
}}

// ── DRAWER ────────────────────────────────────────────────────────────────────
function openDrawer(s) {{
  if(!s) return;
  const name=s.customer_name||s.title||'Unknown';
  document.getElementById('dr-co').textContent=name;
  document.getElementById('dr-title').textContent=s.title||'';
  const fields=[
    ['Industry',s.industry],['Geography',s.geography],
    ['Products',storyProds(s).join(', ')||'—'],
    ['Client type',isIBM(s)?'IBM internal':'External client'],
    ['Published',s.publication_date],['Collected',s.collected_at?.slice(0,10)],
  ];
  let html=`<div class="dr-sec"><div class="dr-sec-title">Details</div>
    <div class="meta-g">${{fields.map(([k,v])=>`<div><div class="mk">${{esc(k)}}</div><div class="mv">${{esc(v)}}</div></div>`).join('')}}</div>
  </div>`;
  if(s.description) html+=`<div class="dr-sec"><div class="dr-sec-title">Summary</div>
    <p style="font-size:12px;color:var(--mu);line-height:1.6">${{esc(s.description)}}</p></div>`;
  if(s.challenge) html+=`<div class="dr-sec"><div class="dr-sec-title">Challenge</div>
    <p style="font-size:12px;color:var(--mu);line-height:1.6">${{esc(s.challenge)}}</p></div>`;
  if(s.solution) html+=`<div class="dr-sec"><div class="dr-sec-title">Transformation</div>
    <p style="font-size:12px;color:var(--mu);line-height:1.6">${{esc(s.solution)}}</p></div>`;
  if(s.quantified_proof) html+=`<div class="dr-sec"><div class="dr-sec-title">Quantified Outcomes</div>
    <div class="proof-box">${{esc(s.quantified_proof)}}</div></div>`;
  if(s.customer_quote) html+=`<div class="dr-sec"><div class="dr-sec-title">Customer Quote</div>
    <div class="quote-box">${{esc(s.customer_quote)}}</div></div>`;
  if(s.topics?.length) html+=`<div class="dr-sec"><div class="dr-sec-title">Topics</div>
    <div style="display:flex;flex-wrap:wrap;gap:5px">
      ${{(s.topics||[]).slice(0,12).map(t=>`<span class="td-tag">${{esc(t)}}</span>`).join('')}}
    </div></div>`;
  html+=`<div class="dr-sec" style="display:flex;gap:10px;flex-wrap:wrap">
    <a class="dr-btn" href="${{esc(s.source_url)}}" target="_blank">Open full story ↗</a>
  </div>`;
  document.getElementById('dr-body').innerHTML=html;
  document.getElementById('drawer').classList.add('on');
  document.getElementById('dr-ov').classList.add('on');
  document.body.style.overflow='hidden';
}}
function closeDrawer(){{
  document.getElementById('drawer').classList.remove('on');
  document.getElementById('dr-ov').classList.remove('on');
  document.body.style.overflow='';
}}
document.getElementById('dr-close').addEventListener('click',closeDrawer);
document.getElementById('dr-ov').addEventListener('click',closeDrawer);
document.addEventListener('keydown',e=>{{ if(e.key==='Escape') closeDrawer(); }});

// ── CSV EXPORT ────────────────────────────────────────────────────────────────
document.getElementById('export-btn').addEventListener('click', () => {{
  const cols=[['Client','customer_name'],['Title','title'],['Industry','industry'],
    ['Geography','geography'],['Products',s=>storyProds(s).join(' | ')],
    ['Outcome','quantified_proof'],['Published','publication_date'],['URL','source_url']];
  const rows=[cols.map(([h])=>h),..._filtered.map(s=>
    cols.map(([,k])=>typeof k==='function'?k(s):(s[k]||'')))];
  const csv=rows.map(r=>r.map(v=>'"'+String(v).replace(/"/g,'""')+'"').join(',')).join('\\n');
  const a=document.createElement('a');
  a.href='data:text/csv;charset=utf-8,'+encodeURIComponent(csv);
  a.download='ibm-customer-stories.csv'; a.click();
}});

// ── HELPER: switch tab programmatically ───────────────────────────────────────
function switchTab(view) {{
  document.querySelectorAll('.tab').forEach(b=>b.classList.remove('on'));
  document.querySelectorAll('.vp').forEach(v=>v.classList.remove('on'));
  document.querySelector(`.tab[data-view="${{view}}"]`).classList.add('on');
  document.getElementById('vp-'+view).classList.add('on');
}}

// ── MASTER RENDER ─────────────────────────────────────────────────────────────
function render(stories) {{
  renderCharts(stories);
  renderRecent(stories);
  renderTable(stories);
  renderProdsView(stories);
  renderGeoView(stories);
  renderMatrix(stories);
}}

// ── WIRE FILTERS ──────────────────────────────────────────────────────────────
document.getElementById('f-kw').addEventListener('input', applyFilters);
['f-ind','f-geo','f-prod','f-ctype'].forEach(id =>
  document.getElementById(id).addEventListener('change', applyFilters));
document.getElementById('btn-clear').addEventListener('click', () => {{
  ['f-kw'].forEach(id=>document.getElementById(id).value='');
  ['f-ind','f-geo','f-prod','f-ctype'].forEach(id=>document.getElementById(id).value='');
  applyFilters();
}});

// ── BOOT ──────────────────────────────────────────────────────────────────────
applyFilters();
</script>
</body>
</html>
"""
