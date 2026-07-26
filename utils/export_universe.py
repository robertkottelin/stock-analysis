"""Export a cross-name metrics table + static dashboard.

Writes:
  data/metrics_latest.csv     — screening / spreadsheet / LLM pack
  data/universe.csv           — registry snapshot
  dashboard/universe.json     — machine-readable for the dashboard
  dashboard/index.html        — central navigation + light screen

Usage:
    python utils/export_universe.py
    python utils/export_universe.py --skip-fetch   # use pipeline_price only (no Yahoo)

Wired into refresh_all / build_one so a full rebuild always refreshes the
dashboard after inject/bullcase.
"""
from __future__ import annotations
import os, sys, csv, json, datetime, math
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from paths import ROOT, DATA_DIR, DASHBOARD_DIR, STOCKS_DIR, ensure_data_dirs, html_path  # noqa: E402
from analytics import STOCKS, all_names                                                    # noqa: E402


def _f(x, dp=2):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    return round(float(x), dp)


def _row_from_gather(name: str, m: dict) -> dict[str, Any]:
    cfg = STOCKS[name]
    tally = cfg.get("tally") or {}
    verdict_i, _ = None, None
    try:
        from inject import verdict_from_metrics
        verdict_i, _ = verdict_from_metrics(
            m.get("kelly"), m.get("asymmetry"), m.get("price_pct"),
            m.get("rdcf_gap"), m.get("pt_gap"), m.get("mom_12m"),
        )
    except Exception:
        verdict_i = None

    bull_y10 = bull_cagr = bull_pv = None
    if "bull_case" in cfg:
        try:
            from bullcase import compute_bull_path
            s = compute_bull_path(name)["summary"]
            bull_y10 = _f(s["terminal_fv"], 2)
            bull_cagr = _f(s["price_cagr"], 4)
            bull_pv = _f(s["pv_total_ps"], 2)
        except Exception:
            pass

    report_exists = os.path.isfile(html_path(cfg))
    cur = m.get("cur") or cfg.get("currency", "€")

    return {
        "name": name,
        "ticker": cfg["ticker"],
        "currency": cur,
        "spot": _f(m.get("spot"), 2),
        "mc_median": _f(m.get("mc_median"), 2),
        "mc_p10": _f(m.get("mc_p10"), 2),
        "mc_p90": _f(m.get("mc_p90"), 2),
        "p_up": _f(m.get("p_up"), 4),
        "kelly": _f(m.get("kelly"), 4),
        "asymmetry": _f(m.get("asymmetry"), 3),
        "expected_return": _f(m.get("expected_return"), 4),
        "cvar10": _f(m.get("cvar10"), 4),
        "var10": _f(m.get("var10"), 4),
        "rdcf_gap": _f(m.get("rdcf_gap"), 4),
        "price_pct": _f(m.get("price_pct"), 4),
        "mom_12m": _f(m.get("mom_12m"), 4),
        "vol_1y": _f(m.get("vol_1y"), 4),
        "composite": _f(m.get("composite"), 4),
        "oe_spread_bp": _f(m.get("real_spread_bp"), 1),
        "oe_yield": _f(m.get("oe_yield"), 4),
        "pe_ttm": _f(m.get("pe_ttm"), 2),
        "consensus_pt": _f(m.get("consensus_pt"), 2),
        "pt_gap": _f(m.get("pt_gap"), 4),
        "mcap_m": _f(m.get("mcap_m"), 1),
        "verdict_i": verdict_i,
        "tally_bull": tally.get("bull", 0),
        "tally_mixed": tally.get("mixed", 0),
        "tally_bear": tally.get("bear", 0),
        "bull_y10_fv": bull_y10,
        "bull_price_cagr": bull_cagr,
        "bull_pv": bull_pv,
        "has_bull_case": "bull_case" in cfg,
        "html_file": cfg["html_file"],
        "report_exists": report_exists,
        "report_href": f"../stocks/{cfg['html_file']}",
        "build_date": m.get("build_date") or datetime.date.today().isoformat(),
        "asof": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def _row_fallback(name: str) -> dict[str, Any]:
    """When Yahoo/fetch fails, still list the name from config."""
    cfg = STOCKS[name]
    tally = cfg.get("tally") or {}
    return {
        "name": name,
        "ticker": cfg["ticker"],
        "currency": cfg.get("currency", "€"),
        "spot": cfg.get("pipeline_price"),
        "mc_median": None, "mc_p10": None, "mc_p90": None,
        "p_up": None, "kelly": None, "asymmetry": None,
        "expected_return": None, "cvar10": None, "var10": None,
        "rdcf_gap": None, "price_pct": None, "mom_12m": None, "vol_1y": None,
        "composite": None, "oe_spread_bp": None, "oe_yield": None,
        "pe_ttm": None,
        "consensus_pt": cfg.get("consensus_pt"),
        "pt_gap": None,
        "mcap_m": None,
        "verdict_i": None,
        "tally_bull": tally.get("bull", 0),
        "tally_mixed": tally.get("mixed", 0),
        "tally_bear": tally.get("bear", 0),
        "bull_y10_fv": None, "bull_price_cagr": None, "bull_pv": None,
        "has_bull_case": "bull_case" in cfg,
        "html_file": cfg["html_file"],
        "report_exists": os.path.isfile(html_path(cfg)),
        "report_href": f"../stocks/{cfg['html_file']}",
        "build_date": datetime.date.today().isoformat(),
        "asof": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "error": "fetch/compute failed — using config fallbacks",
    }


def collect_rows(skip_fetch: bool = False) -> list[dict]:
    rows = []
    if skip_fetch:
        for name in all_names():
            rows.append(_row_fallback(name))
        return rows

    from inject import gather  # heavy: Yahoo + MC
    for name in all_names():
        try:
            m = gather(name)
            rows.append(_row_from_gather(name, m))
            print(f"  · {name}: spot={m.get('spot')} kelly={m.get('kelly')}")
        except Exception as e:
            print(f"  · {name}: ERROR {e} — fallback row")
            rows.append(_row_fallback(name))
            rows[-1]["error"] = str(e)[:200]
    return rows


def write_csv(rows: list[dict], path: str) -> None:
    if not rows:
        return
    # stable column order
    preferred = [
        "name", "ticker", "currency", "spot", "mc_median", "mc_p10", "mc_p90",
        "p_up", "kelly", "asymmetry", "expected_return", "cvar10", "var10",
        "rdcf_gap", "price_pct", "mom_12m", "vol_1y", "composite",
        "oe_spread_bp", "oe_yield", "pe_ttm", "consensus_pt", "pt_gap", "mcap_m",
        "verdict_i", "tally_bull", "tally_mixed", "tally_bear",
        "bull_y10_fv", "bull_price_cagr", "bull_pv", "has_bull_case",
        "html_file", "report_exists", "build_date", "asof", "error",
    ]
    keys = [k for k in preferred if any(k in r for r in rows)]
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def write_universe_registry(path: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["name", "ticker", "html_file", "currency", "shares_m",
                        "has_bull_case", "quality_score", "consensus_pt"],
        )
        w.writeheader()
        for name in all_names():
            cfg = STOCKS[name]
            w.writerow({
                "name": name,
                "ticker": cfg["ticker"],
                "html_file": cfg["html_file"],
                "currency": cfg.get("currency", "€"),
                "shares_m": cfg.get("shares_m"),
                "has_bull_case": "bull_case" in cfg,
                "quality_score": cfg.get("quality_score"),
                "consensus_pt": cfg.get("consensus_pt"),
            })


def _fmt_cell(v, kind="num", cur="€"):
    if v is None or v == "":
        return "—"
    if kind == "pct":
        return f"{float(v)*100:.1f}%"
    if kind == "pct1":
        return f"{float(v)*100:.1f}%"
    if kind == "bp":
        return f"{float(v):+.0f}"
    if kind == "x":
        return f"{float(v):.2f}×"
    if kind == "money":
        return f"{cur}{float(v):,.2f}" if abs(float(v)) < 1000 else f"{cur}{float(v):,.0f}"
    if kind == "kelly":
        return f"{float(v)*100:+.1f}%"
    return str(v)


def render_dashboard_html(rows: list[dict], asof: str) -> str:
    """Self-contained dashboard styled like the pipeline reports."""
    # Sort default: kelly desc (None last)
    def sort_key(r):
        k = r.get("kelly")
        return (-k if k is not None else 999, r["name"])
    rows_sorted = sorted(rows, key=sort_key)

    body_rows = []
    for r in rows_sorted:
        cur = r.get("currency") or "€"
        href = r.get("report_href") or f"../stocks/{r.get('html_file','')}"
        exists = r.get("report_exists", True)
        link = (
            f'<a class="rlink" href="{href}">{r["name"]}</a>'
            if exists else
            f'<span class="missing" title="Report file missing">{r["name"]}</span>'
        )
        vi = (r.get("verdict_i") or "—").upper()
        vcls = "mixed"
        if vi == "BULL":
            vcls = "bull"
        elif vi == "BEAR":
            vcls = "bear"
        tally = f'{r.get("tally_bull",0)}/{r.get("tally_mixed",0)}/{r.get("tally_bear",0)}'
        err = r.get("error")
        err_note = f' <span class="err" title="{err}">⚠</span>' if err else ""
        def da(key):
            v = r.get(key)
            return "" if v is None else v

        body_rows.append(f"""
        <tr data-name="{r['name']}" data-ticker="{r['ticker']}"
            data-spot="{da('spot')}" data-mc_median="{da('mc_median')}"
            data-kelly="{da('kelly')}" data-asymmetry="{da('asymmetry')}"
            data-p_up="{da('p_up')}" data-cvar10="{da('cvar10')}"
            data-composite="{da('composite')}" data-oe_spread_bp="{da('oe_spread_bp')}"
            data-bull_y10_fv="{da('bull_y10_fv')}" data-verdict="{vi}">
          <td class="name">{link}{err_note}<div class="tkr">{r['ticker']}</div></td>
          <td class="num">{_fmt_cell(r.get('spot'), 'money', cur)}</td>
          <td class="num">{_fmt_cell(r.get('mc_median'), 'money', cur)}</td>
          <td class="num">{_fmt_cell(r.get('kelly'), 'kelly')}</td>
          <td class="num">{_fmt_cell(r.get('asymmetry'), 'x')}</td>
          <td class="num">{_fmt_cell(r.get('p_up'), 'pct')}</td>
          <td class="num">{_fmt_cell(r.get('cvar10'), 'pct')}</td>
          <td class="num">{_fmt_cell(r.get('composite'), 'pct')}</td>
          <td class="num">{_fmt_cell(r.get('oe_spread_bp'), 'bp')} bp</td>
          <td class="num">{_fmt_cell(r.get('bull_y10_fv'), 'money', cur)}</td>
          <td><span class="vchip {vcls}">{vi if vi != '—' else '—'}</span></td>
          <td class="num mono">{tally}</td>
          <td class="act"><a class="btn" href="{href}">Open</a></td>
        </tr>""")

    n = len(rows)
    n_ok = sum(1 for r in rows if r.get("report_exists"))
    n_bull = sum(1 for r in rows if (r.get("verdict_i") or "").lower() == "bull")
    n_bear = sum(1 for r in rows if (r.get("verdict_i") or "").lower() == "bear")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stock Analysis — Universe Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{{
    --paper:#EEF1ED; --surface:#FFFFFF; --surface-2:#F7F9F6;
    --line:#E1E5DE; --line-strong:#CBD2C9;
    --ink:#13201C; --muted:#5E6E66; --faint:#8B988F;
    --teal:#0F9E8B; --teal-deep:#0A5C53; --teal-wash:#E4F4F0;
    --blue:#2E6F9E; --blue-deep:#1C4A6E; --blue-wash:#E2EDF6;
    --coral:#D2603A; --coral-deep:#9A3F22; --coral-wash:#F8E7DF;
    --amber:#C99A2E; --amber-deep:#86631A; --amber-wash:#F6ECCF;
    --radius:14px;
    --mono:'IBM Plex Mono',ui-monospace,Menlo,monospace;
    --disp:'Space Grotesk','Helvetica Neue',system-ui,sans-serif;
    --body:'Inter','Helvetica Neue',system-ui,sans-serif;
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  html{{-webkit-text-size-adjust:100%}}
  body{{background:var(--paper);color:var(--ink);font-family:var(--body);line-height:1.5;font-size:15px;padding:clamp(12px,2.5vw,32px)}}
  .wrap{{max-width:1240px;margin:0 auto}}
  .eyebrow{{font-family:var(--mono);font-size:11.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--teal-deep);display:flex;align-items:center;gap:10px;margin-bottom:14px;flex-wrap:wrap}}
  .eyebrow::before{{content:"";width:26px;height:1.5px;background:var(--teal);display:inline-block}}
  h1{{font-family:var(--disp);font-weight:600;letter-spacing:-.02em;font-size:clamp(25px,5vw,36px);line-height:1.05}}
  h1 .sub{{display:block;color:var(--muted);font-weight:500;font-size:clamp(14px,2.3vw,16px);margin-top:8px;max-width:720px}}
  .kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:18px 0}}
  @media(max-width:720px){{.kpis{{grid-template-columns:repeat(2,1fr)}}}}
  .kpi{{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:12px 14px}}
  .kpi .l{{font-family:var(--mono);font-size:10px;letter-spacing:.05em;text-transform:uppercase;color:var(--faint)}}
  .kpi .v{{font-family:var(--disp);font-weight:700;font-size:24px;margin-top:2px;color:var(--ink)}}
  .panel{{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:clamp(14px,2.5vw,22px);margin-bottom:16px}}
  .toolbar{{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:14px}}
  .toolbar label{{font-family:var(--mono);font-size:11px;color:var(--muted)}}
  .toolbar input[type=search],.toolbar select{{
    font-family:var(--body);font-size:13px;padding:8px 11px;border:1px solid var(--line-strong);
    border-radius:9px;background:var(--surface-2);color:var(--ink);min-width:140px
  }}
  .toolbar input[type=search]{{min-width:200px;flex:1}}
  .hint{{font-size:12px;color:var(--muted);margin-left:auto}}
  .tbl-scroll{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
  table{{border-collapse:collapse;width:100%;font-size:13px}}
  th{{text-align:left;font-family:var(--mono);font-size:10px;letter-spacing:.05em;text-transform:uppercase;
     color:var(--faint);padding:8px 9px;border-bottom:1px solid var(--line-strong);background:var(--surface-2);cursor:pointer;user-select:none;white-space:nowrap}}
  th:hover{{color:var(--ink)}}
  th .arrow{{opacity:.35;margin-left:3px}}
  th.sorted .arrow{{opacity:1;color:var(--teal-deep)}}
  td{{padding:10px 9px;border-bottom:1px dashed var(--line);vertical-align:middle}}
  td.num{{text-align:right;font-family:var(--mono);font-weight:500;white-space:nowrap}}
  td.name .tkr{{font-family:var(--mono);font-size:10.5px;color:var(--faint);margin-top:2px}}
  a.rlink{{color:var(--blue-deep);font-weight:600;text-decoration:none}}
  a.rlink:hover{{text-decoration:underline}}
  .missing{{color:var(--coral-deep);font-weight:600}}
  .err{{color:var(--amber-deep);cursor:help}}
  .vchip{{font-family:var(--mono);font-weight:700;font-size:9.5px;letter-spacing:.06em;padding:3px 8px;border-radius:6px;color:#fff;white-space:nowrap}}
  .vchip.bull{{background:var(--teal)}} .vchip.mixed{{background:var(--amber-deep)}} .vchip.bear{{background:var(--coral)}}
  .btn{{font-family:var(--mono);font-size:11px;font-weight:600;padding:6px 11px;border-radius:8px;border:1px solid var(--line-strong);
        background:var(--surface-2);color:var(--ink);text-decoration:none;display:inline-block}}
  .btn:hover{{border-color:var(--teal);background:var(--teal-wash);color:var(--teal-deep)}}
  .mono{{font-family:var(--mono);font-size:11.5px;color:var(--muted)}}
  tr.hidden{{display:none}}
  footer{{margin-top:18px;font-size:12px;color:var(--faint);line-height:1.55}}
  footer code{{font-family:var(--mono);font-size:11px;background:var(--surface);padding:1px 5px;border-radius:4px;border:1px solid var(--line)}}
  .note{{font-size:12.5px;color:var(--muted);background:var(--surface-2);border-left:3px solid var(--teal);border-radius:0 8px 8px 0;padding:11px 14px;margin-top:14px;line-height:1.5}}
</style>
</head>
<body>
<div class="wrap">
  <div class="eyebrow">Central analysis dashboard · strict-data toolkit · as of {asof} · <a href="screener.html" style="color:inherit">Nordic universe screener →</a></div>
  <h1>Universe
    <span class="sub">Navigate every registered stock report, screen on live metrics (Kelly, CVaR, composite, OE spread), and jump into the full pipeline HTML. Rebuild with <b>python refresh_all.py</b>.</span>
  </h1>

  <div class="kpis">
    <div class="kpi"><div class="l">Names</div><div class="v">{n}</div></div>
    <div class="kpi"><div class="l">Reports on disk</div><div class="v">{n_ok}</div></div>
    <div class="kpi"><div class="l">Module-I bull</div><div class="v" style="color:var(--teal-deep)">{n_bull}</div></div>
    <div class="kpi"><div class="l">Module-I bear</div><div class="v" style="color:var(--coral-deep)">{n_bear}</div></div>
  </div>

  <div class="panel">
    <div class="toolbar">
      <input type="search" id="q" placeholder="Filter name or ticker…" autocomplete="off">
      <div>
        <label for="vf">Verdict</label>
        <select id="vf">
          <option value="">All</option>
          <option value="BULL">Bull</option>
          <option value="MIXED">Mixed</option>
          <option value="BEAR">Bear</option>
        </select>
      </div>
      <div>
        <label for="kf">Kelly</label>
        <select id="kf">
          <option value="">Any</option>
          <option value="pos">Kelly &gt; 0</option>
          <option value="neg">Kelly ≤ 0</option>
        </select>
      </div>
      <span class="hint">Click column headers to sort · metrics from last export</span>
    </div>
    <div class="tbl-scroll">
      <table id="utab">
        <thead>
          <tr>
            <th data-k="name">Name <span class="arrow">↕</span></th>
            <th data-k="spot" data-num>Spot <span class="arrow">↕</span></th>
            <th data-k="mc_median" data-num>MC med <span class="arrow">↕</span></th>
            <th data-k="kelly" data-num>Kelly <span class="arrow">↕</span></th>
            <th data-k="asymmetry" data-num>Asym <span class="arrow">↕</span></th>
            <th data-k="p_up" data-num>P(up) <span class="arrow">↕</span></th>
            <th data-k="cvar10" data-num>CVaR10 <span class="arrow">↕</span></th>
            <th data-k="composite" data-num>Comp <span class="arrow">↕</span></th>
            <th data-k="oe_spread_bp" data-num>OE spr <span class="arrow">↕</span></th>
            <th data-k="bull_y10_fv" data-num>Y10 bull <span class="arrow">↕</span></th>
            <th data-k="verdict">I-verdict <span class="arrow">↕</span></th>
            <th>Tally B/M/B</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {''.join(body_rows)}
        </tbody>
      </table>
    </div>
    <div class="note"><b>How to use.</b> This is the front door for the book. Numbers are recomputed whenever you run <code>python refresh_all.py</code> or <code>python utils/export_universe.py</code> (Yahoo + MC). Full thesis, fundamentals narrative and interactive engines live in each report. Screening CSVs: <code>data/metrics_latest.csv</code>.</div>
  </div>

  <footer>
    Generated {asof} · {n} names in registry · open a report to drill into engines, Module I/J asymmetry, and (where configured) Module U 10y upside.<br>
    Refresh CLI: <code>python refresh_all.py</code> · single name: <code>python utils/build_one.py &lt;name&gt;</code> · export only: <code>python utils/export_universe.py</code>
  </footer>
</div>
<script>
(function(){{
  const q = document.getElementById('q');
  const vf = document.getElementById('vf');
  const kf = document.getElementById('kf');
  const tbody = document.querySelector('#utab tbody');
  const rows = [].slice.call(tbody.querySelectorAll('tr'));

  function applyFilter(){{
    const term = (q.value||'').trim().toLowerCase();
    const verd = vf.value;
    const kel = kf.value;
    rows.forEach(tr => {{
      const hay = ((tr.getAttribute('data-name')||'') + ' ' + (tr.getAttribute('data-ticker')||'')).toLowerCase();
      const v = tr.getAttribute('data-verdict')||'';
      const k = parseFloat(tr.getAttribute('data-kelly'));
      let ok = true;
      if(term && hay.indexOf(term) < 0) ok = false;
      if(verd && v !== verd) ok = false;
      if(kel === 'pos' && !(k > 0)) ok = false;
      if(kel === 'neg' && !(isNaN(k) || k <= 0)) ok = false;
      tr.classList.toggle('hidden', !ok);
    }});
  }}
  q.addEventListener('input', applyFilter);
  vf.addEventListener('change', applyFilter);
  kf.addEventListener('change', applyFilter);

  let sortKey = 'kelly', sortDir = -1;
  document.querySelectorAll('#utab th[data-k]').forEach(th => {{
    th.addEventListener('click', () => {{
      const k = th.getAttribute('data-k');
      if(sortKey === k) sortDir *= -1;
      else {{ sortKey = k; sortDir = (k === 'name' || k === 'verdict') ? 1 : -1; }}
      document.querySelectorAll('#utab th').forEach(h => h.classList.remove('sorted'));
      th.classList.add('sorted');
      const num = th.hasAttribute('data-num');
      const sorted = rows.slice().sort((a,b) => {{
        let av = a.getAttribute('data-' + k);
        let bv = b.getAttribute('data-' + k);
        if(num){{
          const pa = parseFloat(av), pb = parseFloat(bv);
          const na = isNaN(pa), nb = isNaN(pb);
          if(na && nb) return 0;
          if(na) return 1;
          if(nb) return -1;
          return (pa - pb) * sortDir;
        }}
        return String(av||'').localeCompare(String(bv||'')) * sortDir;
      }});
      sorted.forEach(tr => tbody.appendChild(tr));
    }});
  }});
}})();
</script>
</body>
</html>
"""


def export(skip_fetch: bool = False) -> str:
    ensure_data_dirs()
    print("Collecting universe metrics…")
    rows = collect_rows(skip_fetch=skip_fetch)
    asof = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    metrics_path = os.path.join(DATA_DIR, "metrics_latest.csv")
    universe_path = os.path.join(DATA_DIR, "universe.csv")
    json_path = os.path.join(DASHBOARD_DIR, "universe.json")
    html_out = os.path.join(DASHBOARD_DIR, "index.html")

    write_csv(rows, metrics_path)
    write_universe_registry(universe_path)

    payload = {
        "asof": asof,
        "n": len(rows),
        "rows": rows,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    html = render_dashboard_html(rows, asof)
    with open(html_out, "w", encoding="utf-8") as f:
        f.write(html)

    return (
        f"OK — universe export: {len(rows)} names → "
        f"data/metrics_latest.csv, data/universe.csv, "
        f"dashboard/universe.json, dashboard/index.html"
    )


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    skip = "--skip-fetch" in sys.argv
    print(export(skip_fetch=skip))
    print(f"Open: file://{os.path.join(DASHBOARD_DIR, 'index.html')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
