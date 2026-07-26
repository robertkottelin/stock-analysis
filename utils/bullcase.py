"""Perfect-execution / 10-year bull-case path engine.

A reusable tool that answers: *if everything goes right for N years, what
is a realistic best-case stock price — and what CAGR / present value does
that imply from today's tape?*

Config-driven via ``STOCKS[name]["bull_case"]``. Stocks without a block are
skipped. Designed for EBITA×multiple (+ net cash) compounders first; the
year engine can be overridden per stock.

CLI:
    python utils/bullcase.py konecranes          # compute + inject Module U
    python utils/bullcase.py konecranes --print  # numbers only, no HTML write
    python utils/bullcase.py all
"""
from __future__ import annotations
import os, sys, re, math, json
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from paths import html_path                                          # noqa: E402
from analytics import STOCKS, all_names, fetch_chart, series         # noqa: E402


def _live_spot(cfg: dict) -> float:
    """Live spot so 'vs spot' upside/CAGR/PV lines track the tape; the
    authored pipeline_price is only the offline fallback."""
    try:
        chart = fetch_chart(cfg["ticker"], "5y")
        _, px = series(chart)
        return float(chart["chart"]["result"][0]["meta"].get("regularMarketPrice") or px[-1])
    except Exception:
        return float(cfg["pipeline_price"])


# ---------------------------------------------------------------------------
# Core path math
# ---------------------------------------------------------------------------

def _lerp(a: float, b: float, t: float) -> float:
    """Linear blend; t in [0, 1]."""
    return a + (b - a) * t


def _smoothstep(t: float) -> float:
    """Ease-in-out so early years move slower than a pure linear ramp."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def compute_bull_path(name: str, overrides: dict | None = None) -> dict:
    """Year-by-year perfect-execution path for a stock.

    Returns a dict with ``years`` (list of per-year snapshots) and ``summary``
    (terminal price, CAGR, PV, cumulative dividends, shares retired, etc.).
    """
    cfg = STOCKS[name]
    bc = cfg.get("bull_case")
    if not bc:
        raise KeyError(f"{name} has no bull_case config block")

    p = dict(bc["path"])
    if overrides:
        p.update(overrides)

    horizon = int(bc.get("horizon_years", p.get("horizon_years", 10)))
    cur = cfg.get("currency", "€")
    spot = _live_spot(cfg)

    sales = float(p["sales_0"])
    mgn = float(p["mgn_0"])          # %
    mlt = float(p["mlt_0"])
    nc = float(p["nc_0"])            # €m net cash
    shares = float(p["shares_0"])    # millions

    sales_cagr = float(p["sales_cagr"])
    mgn_term = float(p["mgn_term"])
    mlt_term = float(p["mlt_term"])
    tax = float(p.get("tax_rate", 0.22))
    # FCF as a fraction of EBITA after a simple tax haircut
    fcf_on_ebita = float(p.get("fcf_on_ebita", 0.78))
    payout = float(p.get("payout_ratio", 0.45))       # of FCF → dividends
    buyback = float(p.get("buyback_ratio", 0.20))     # of FCF → buybacks
    # residual FCF accrues to net cash
    discount = float(p.get("discount_rate", 0.09))
    # buybacks executed at that year's fair value (no free lunch)
    buyback_at_fv = bool(p.get("buyback_at_fv", True))

    # Optional custom year fair-value engine; default = Konecranes-style
    year_engine = bc.get("year_engine")  # Callable[[dict], float] per-share

    def fv_ps(sales_m, mgn_pct, mlt_x, nc_m, sh_m) -> float:
        if year_engine is not None:
            return float(year_engine({
                "sales": sales_m, "mgn": mgn_pct, "mlt": mlt_x,
                "nc": nc_m, "shares": sh_m,
            }))
        if sh_m <= 0:
            return 0.0
        return (mlt_x * (sales_m * mgn_pct / 100.0) + nc_m) / sh_m

    years: list[dict] = []
    # year 0 = today (base)
    price0 = fv_ps(sales, mgn, mlt, nc, shares)
    years.append({
        "year": 0,
        "label": "Y0 · now",
        "sales": sales, "mgn": mgn, "mlt": mlt, "nc": nc, "shares": shares,
        "ebita": sales * mgn / 100.0,
        "fcf": 0.0, "div_total": 0.0, "div_ps": 0.0,
        "buyback_m": 0.0, "shares_retired": 0.0,
        "fv": price0,
        "pv_of_fv": price0,
    })

    cum_div_pv = 0.0
    cum_div_nom = 0.0
    cum_fcf = 0.0
    cum_buyback = 0.0

    for y in range(1, horizon + 1):
        t = y / horizon
        te = _smoothstep(t)

        sales = float(p["sales_0"]) * ((1.0 + sales_cagr) ** y)
        mgn = _lerp(float(p["mgn_0"]), mgn_term, te)
        mlt = _lerp(float(p["mlt_0"]), mlt_term, te)

        ebita = sales * mgn / 100.0
        fcf = ebita * (1.0 - tax) * fcf_on_ebita  # €m
        cum_fcf += fcf

        div_total = fcf * payout
        buyback_m = fcf * buyback
        retained = fcf - div_total - buyback_m  # → net cash

        # provisional FV before buyback (using pre-buyback shares)
        fv_pre = fv_ps(sales, mgn, mlt, nc + retained, shares)
        px_bb = fv_pre if buyback_at_fv else spot * ((1 + sales_cagr) ** y)
        shares_retired = (buyback_m / px_bb) if px_bb > 0 else 0.0
        # floor: never retire more than 50% of the STARTING count (the
        # in-page JS mirrors this; flooring on the current-year count would
        # let the floor itself compound below 50% of the original)
        shares = max(shares - shares_retired, float(p["shares_0"]) * 0.5)
        nc = nc + retained  # buyback cash leaves the firm; retained stays

        fv = fv_ps(sales, mgn, mlt, nc, shares)
        div_ps = div_total / shares if shares > 0 else 0.0
        cum_div_nom += div_total
        cum_div_pv += div_total / ((1.0 + discount) ** y)
        cum_buyback += buyback_m

        years.append({
            "year": y,
            "label": f"Y{y}",
            "sales": sales, "mgn": mgn, "mlt": mlt, "nc": nc, "shares": shares,
            "ebita": ebita,
            "fcf": fcf, "div_total": div_total, "div_ps": div_ps,
            "buyback_m": buyback_m, "shares_retired": shares_retired,
            "fv": fv,
            "pv_of_fv": fv / ((1.0 + discount) ** y),
        })

    term = years[-1]
    # Equity total return path: price CAGR ignoring dividends
    price_cagr = (term["fv"] / spot) ** (1.0 / horizon) - 1.0 if spot > 0 else 0.0
    # Approx total shareholder return incl. reinvested divs (nominal cum div / shares_0 + term fv)
    tsr_end = term["fv"] + (cum_div_nom / float(p["shares_0"]))
    tsr_cagr = (tsr_end / spot) ** (1.0 / horizon) - 1.0 if spot > 0 else 0.0

    # Present value of terminal equity + dividend stream (per share, on starting shares for divs)
    pv_term = term["fv"] / ((1.0 + discount) ** horizon)
    # Dividends accrued to a share that wasn't bought back: use cum_div_pv / starting shares
    # (conservative: attributes all div cash to the original share count)
    pv_divs_ps = cum_div_pv / float(p["shares_0"])
    pv_total_ps = pv_term + pv_divs_ps

    mid = years[horizon // 2] if horizon >= 2 else term

    summary = {
        "name": name,
        "ticker": cfg["ticker"],
        "currency": cur,
        "spot": spot,
        "horizon": horizon,
        "consensus_pt": cfg.get("consensus_pt"),
        "terminal_fv": term["fv"],
        "terminal_sales": term["sales"],
        "terminal_mgn": term["mgn"],
        "terminal_mlt": term["mlt"],
        "terminal_nc": term["nc"],
        "terminal_shares": term["shares"],
        "terminal_ebita": term["ebita"],
        "mid_fv": mid["fv"],
        "mid_year": mid["year"],
        "price_cagr": price_cagr,
        "tsr_cagr": tsr_cagr,
        "pv_term_ps": pv_term,
        "pv_divs_ps": pv_divs_ps,
        "pv_total_ps": pv_total_ps,
        "discount_rate": discount,
        "cum_fcf": cum_fcf,
        "cum_div_nom": cum_div_nom,
        "cum_buyback": cum_buyback,
        "shares_retired_total": float(p["shares_0"]) - term["shares"],
        "upside_vs_spot": term["fv"] / spot - 1.0 if spot else 0.0,
        "pv_premium_vs_spot": pv_total_ps / spot - 1.0 if spot else 0.0,
        "path": p,
        "label": bc.get("label", "Perfect-execution bull"),
    }
    return {"years": years, "summary": summary, "config": bc}


# ---------------------------------------------------------------------------
# HTML render
# ---------------------------------------------------------------------------

CSS_BULL = """
<style id="bullcase-css">
  /* Module U — perfect-execution bull path */
  .bullpath{border:1.5px solid var(--teal);border-radius:12px;padding:clamp(14px,2.5vw,20px);background:linear-gradient(180deg,#fff,var(--teal-wash));margin-top:8px}
  .bullpath .bp-title{font-family:var(--mono);font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--teal-deep);font-weight:600;margin-bottom:4px}
  .bullpath .bp-sub{font-size:12.5px;color:var(--muted);margin-bottom:14px;line-height:1.45}
  .bp-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:12px 0 16px}
  @media(max-width:780px){.bp-kpis{grid-template-columns:repeat(2,1fr)}}
  @media(max-width:420px){.bp-kpis{grid-template-columns:1fr}}
  .bp-kpis .k{background:var(--surface);border:1px solid var(--line);border-radius:11px;padding:12px 14px;min-width:0}
  .bp-kpis .k .lab{font-family:var(--mono);font-size:9.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--faint)}
  .bp-kpis .k .val{font-family:var(--disp);font-weight:700;font-size:22px;letter-spacing:-.02em;color:var(--teal-deep);margin-top:3px;line-height:1.1}
  .bp-kpis .k .val small{font-size:12px;font-weight:500;color:var(--muted);margin-left:4px}
  .bp-kpis .k .hint{font-size:11px;color:var(--muted);margin-top:4px;line-height:1.35}
  .bp-controls{display:grid;grid-template-columns:repeat(2,1fr);gap:14px 22px;margin:8px 0 6px}
  @media(max-width:560px){.bp-controls{grid-template-columns:1fr}}
  .guard{display:flex;gap:10px;padding:10px 12px;border:1px solid var(--line);border-radius:10px;font-size:12.5px;line-height:1.45;background:var(--surface)}
  .guard .gdot{flex:0 0 auto;width:8px;height:8px;border-radius:50%;background:var(--teal);margin-top:6px}
  .mile{display:grid;grid-template-columns:52px 1fr;gap:10px;padding:9px 0;border-bottom:1px dashed var(--line);font-size:13px;line-height:1.45}
  .mile .my{font-family:var(--mono);font-weight:600;color:var(--teal-deep);font-size:12px}
  .mile .mt{color:var(--ink)}
  #bull-chart{width:100%;height:auto;display:block;margin-top:8px}
</style>
"""


def _fmt_money(cur: str, x: float, dp: int = 0) -> str:
    if dp == 0:
        return f"{cur}{x:,.0f}"
    return f"{cur}{x:,.{dp}f}"


def _fmt_pct(x: float, dp: int = 1, sign: bool = False) -> str:
    s = f"{x*100:+.{dp}f}%" if sign else f"{x*100:.{dp}f}%"
    return s


def render_module_U(name: str, result: dict | None = None) -> str:
    """HTML for Module U (perfect-execution 10y bull path)."""
    result = result or compute_bull_path(name)
    s = result["summary"]
    bc = result["config"]
    years = result["years"]
    cur = s["currency"]
    spot = s["spot"]
    H = s["horizon"]
    p = s["path"]

    # Path table rows (show Y0, every year, or subsample if long)
    rows = ""
    for y in years:
        cls = " class='cur'" if y["year"] == H else ("" if y["year"] else " class='now'")
        rows += (
            f"<tr{cls}><td>{y['label']}</td>"
            f"<td class='num'>{y['sales']:,.0f}</td>"
            f"<td class='num'>{y['mgn']:.1f}%</td>"
            f"<td class='num'>{y['mlt']:.1f}×</td>"
            f"<td class='num'>{y['nc']:,.0f}</td>"
            f"<td class='num'>{y['shares']:.1f}</td>"
            f"<td class='num'><b>{cur}{y['fv']:.0f}</b></td></tr>"
        )

    milestones = bc.get("milestones") or []
    mile_html = ""
    for m in milestones:
        mile_html += (
            f"<div class='mile'><div class='my'>Y{m['year']}</div>"
            f"<div class='mt'>{m['text']}</div></div>"
        )

    guards = bc.get("guards") or []
    guard_html = "".join(
        f"<div class='guard'><span class='gdot'></span><div>{g}</div></div>"
        for g in guards
    )

    narrative = bc.get("narrative", "")
    method = bc.get("method_note", "")
    label = s["label"]

    cons = s.get("consensus_pt")
    cons_line = ""
    if cons and cons < s["terminal_fv"]:
        cons_line = f"Consensus PT {cur}{cons:.0f} sits below this terminal — the street prices a cycle, not a decade of perfect execution."
    elif cons:
        cons_line = f"Consensus PT {cur}{cons:.0f} already sits at or above this terminal — even the perfect-execution path adds nothing to the street's number."

    # Defaults for JS controls (mirror path)
    js_defaults = {
        "sales0": p["sales_0"],
        "mgn0": p["mgn_0"],
        "mlt0": p["mlt_0"],
        "nc0": p["nc_0"],
        "shares0": p["shares_0"],
        "salesCagr": p["sales_cagr"] * 100,
        "mgnTerm": p["mgn_term"],
        "mltTerm": p["mlt_term"],
        "tax": p.get("tax_rate", 0.22) * 100,
        "fcfOn": p.get("fcf_on_ebita", 0.78) * 100,
        "payout": p.get("payout_ratio", 0.45) * 100,
        "buyback": p.get("buyback_ratio", 0.20) * 100,
        "discount": p.get("discount_rate", 0.09) * 100,
        "horizon": H,
        "spot": spot,
        "cur": cur,
    }

    # Chart polyline from years
    def chart_svg(yrs: list[dict]) -> str:
        W, Hgt, pad_l, pad_r, pad_t, pad_b = 700, 200, 48, 16, 16, 36
        xs = [y["year"] for y in yrs]
        fvs = [y["fv"] for y in yrs]
        lo, hi = min(fvs + [spot]) * 0.92, max(fvs) * 1.06
        if hi <= lo:
            hi = lo + 1
        def X(i):
            return pad_l + (W - pad_l - pad_r) * (xs[i] / max(xs[-1], 1))
        def Y(v):
            return pad_t + (Hgt - pad_t - pad_b) * (1 - (v - lo) / (hi - lo))
        pts = " ".join(f"{X(i):.1f},{Y(fvs[i]):.1f}" for i in range(len(yrs)))
        # spot line
        y_spot = Y(spot)
        labels = ""
        for i, y in enumerate(yrs):
            if y["year"] in (0, H // 2, H) or y["year"] == H:
                labels += (
                    f'<text x="{X(i):.1f}" y="{Y(y["fv"])-8:.1f}" text-anchor="middle" '
                    f'font-family="var(--mono)" font-size="10" font-weight="600" fill="var(--teal-deep)">'
                    f'{cur}{y["fv"]:.0f}</text>'
                )
        x_ticks = ""
        for i, y in enumerate(yrs):
            if y["year"] % max(1, H // 5) == 0 or y["year"] == H:
                x_ticks += (
                    f'<text x="{X(i):.1f}" y="{Hgt-10}" text-anchor="middle" '
                    f'font-family="var(--mono)" font-size="10" fill="var(--muted)">Y{y["year"]}</text>'
                )
        return f'''<svg id="bull-chart" viewBox="0 0 {W} {Hgt}" preserveAspectRatio="xMidYMid meet" style="width:100%;height:auto" role="img" aria-label="Bull-case fair-value path">
  <line x1="{pad_l}" y1="{y_spot:.1f}" x2="{W-pad_r}" y2="{y_spot:.1f}" stroke="var(--faint)" stroke-width="1.2" stroke-dasharray="4 3"/>
  <text x="{W-pad_r}" y="{y_spot-4:.1f}" text-anchor="end" font-family="var(--mono)" font-size="9" fill="var(--faint)">spot {cur}{spot:.0f}</text>
  <polyline fill="none" stroke="var(--teal)" stroke-width="2.4" points="{pts}"/>
  {"".join(f'<circle cx="{X(i):.1f}" cy="{Y(fvs[i]):.1f}" r="3.2" fill="var(--teal-deep)"/>' for i in range(len(yrs)))}
  {labels}
  {x_ticks}
</svg>'''

    svg = chart_svg(years)

    # Adaptive slider bounds — bracket each config value with headroom so no
    # stock's assumptions clamp against a hardcoded range (a 14%-EBITA industrial
    # and a 60%-EBITDA memory maker both have to fit). Ranges only ever widen the
    # old Konecranes defaults, never narrow below a value in use.
    _mgn0, _mgnT = float(p["mgn_0"]), float(p["mgn_term"])
    _mlt0, _mltT = float(p["mlt_0"]), float(p["mlt_term"])
    _scagr = p["sales_cagr"] * 100
    _fcf = p.get("fcf_on_ebita", 0.78) * 100
    _disc = p.get("discount_rate", 0.09) * 100
    sl_scagr = (0, max(12, round(_scagr) + 4))
    sl_mgn = (max(0, round(min(_mgn0, _mgnT) * 0.55)), round(max(_mgn0, _mgnT) * 1.3))
    sl_mlt = (max(1, round(min(_mlt0, _mltT) * 0.6)), round(max(_mlt0, _mltT) * 1.4))
    sl_disc = (max(2, round(_disc) - 6), round(_disc) + 6)
    sl_fcf = (min(50, max(10, round(_fcf) - 20)), 95)

    html = f'''
  <section class="mod" id="mU" style="border:1.5px solid var(--teal)">
    <div class="mod-head"><div class="mod-no" style="color:var(--teal-deep)">U</div>
      <div class="ht"><h2>Perfect-execution bull — the 10-year ceiling</h2><div class="hq">{label}. If everything goes right for {H} years, what is a realistic best-case stock price?</div></div>
      <span class="tagchip a">Scenario tool · your assumptions</span>
    </div>

    <div class="verdict bull"><span class="vchip">BULL · CEILING</span><span class="vtext">Under the default perfect-execution path, year-{H} fair value lands near <b>{cur}{s["terminal_fv"]:.0f}</b> — about <b>{_fmt_pct(s["upside_vs_spot"], 0, sign=True)}</b> above today’s <b>{cur}{spot:.2f}</b>, a price CAGR of <b>{_fmt_pct(s["price_cagr"], 1)}</b> (total-shareholder-return ≈ <b>{_fmt_pct(s["tsr_cagr"], 1)}</b> incl. dividends). Discounted back at {_fmt_pct(s["discount_rate"], 0)}, the PV of that terminal equity plus dividends is ≈ <b>{cur}{s["pv_total_ps"]:.0f}</b> per share ({_fmt_pct(s["pv_premium_vs_spot"], 0, sign=True)} vs spot). {cons_line}</span></div>

    <p class="body"><b>What this module is — and is not.</b> Modules A–C underwrite a <i>through-cycle base</i>. This one is the opposite exercise: an explicit, end-to-end <b>everything-goes-right</b> path over {H} years — sales compound, margin reaches a defended peak, the market awards a quality multiple, free cash builds or buys back stock. Every driver below is an <b>assumption</b> you can move; the defaults are ambitious but deliberately short of fantasy (no Atlas-Copco multiple, no 20% sales CAGR). {narrative}</p>

    <div class="bullpath">
      <div class="bp-title">◆ Live bull-path calculator — {H}-year perfect execution</div>
      <div class="bp-sub">Fair value each year = EV/EBITA multiple × (sales × EBITA margin) + net cash, ÷ diluted shares. Net cash and share count evolve from free-cash-flow: a slice pays the dividend, a slice buys back stock at that year’s fair value, the rest accrues to the balance sheet.</div>

      <div class="bp-kpis" id="bp-kpis">
        <div class="k"><div class="lab">Year-{H} fair value</div><div class="val" id="bp-term">{cur}{s["terminal_fv"]:.0f}</div><div class="hint" id="bp-term-h">{_fmt_pct(s["upside_vs_spot"], 0, sign=True)} vs spot {cur}{spot:.2f}</div></div>
        <div class="k"><div class="lab">Price CAGR ({H}y)</div><div class="val" id="bp-cagr">{_fmt_pct(s["price_cagr"], 1)}</div><div class="hint" id="bp-cagr-h">TSR ≈ {_fmt_pct(s["tsr_cagr"], 1)} incl. dividends</div></div>
        <div class="k"><div class="lab">PV @ {_fmt_pct(s["discount_rate"], 0)} disc.</div><div class="val" id="bp-pv">{cur}{s["pv_total_ps"]:.0f}</div><div class="hint" id="bp-pv-h">Terminal PV {cur}{s["pv_term_ps"]:.0f} + div PV {cur}{s["pv_divs_ps"]:.0f}</div></div>
        <div class="k"><div class="lab">Y{s["mid_year"]} checkpoint</div><div class="val" id="bp-mid">{cur}{s["mid_fv"]:.0f}</div><div class="hint" id="bp-mid-h">Sales {s["terminal_sales"]/((1+p["sales_cagr"])**(H-s["mid_year"])):,.0f}→{s["terminal_sales"]:,.0f} €m by Y{H}</div></div>
      </div>

      <div class="bp-controls">
        <div class="ctrl">
          <label><span class="lab">Sales CAGR <span>% · assumption</span></span><span class="cval"><span id="bv-scagr">{p["sales_cagr"]*100:.1f}</span>%</span></label>
          <input type="range" id="bi-scagr" min="{sl_scagr[0]}" max="{sl_scagr[1]}" step="0.1" value="{p["sales_cagr"]*100:.1f}">
          <div class="tri">Perfect-execution revenue compounding over the horizon</div>
        </div>
        <div class="ctrl">
          <label><span class="lab">Terminal EBITA/EBITDA margin <span>% · assumption</span></span><span class="cval"><span id="bv-mgn">{p["mgn_term"]:.1f}</span>%</span></label>
          <input type="range" id="bi-mgn" min="{sl_mgn[0]}" max="{sl_mgn[1]}" step="0.1" value="{p["mgn_term"]:.1f}">
          <div class="tri">Today ~{p["mgn_0"]:.1f}%; the terminal through-cycle margin you underwrite</div>
        </div>
        <div class="ctrl">
          <label><span class="lab">Terminal multiple <span>× · assumption</span></span><span class="cval"><span id="bv-mlt">{p["mlt_term"]:.1f}</span>×</span></label>
          <input type="range" id="bi-mlt" min="{sl_mlt[0]}" max="{sl_mlt[1]}" step="0.1" value="{p["mlt_term"]:.1f}">
          <div class="tri">Now ~{p["mlt_0"]:.1f}× · the terminal EV/EBITA(DA) the market grants</div>
        </div>
        <div class="ctrl">
          <label><span class="lab">Discount rate <span>% · assumption</span></span><span class="cval"><span id="bv-disc">{p.get("discount_rate",0.09)*100:.0f}</span>%</span></label>
          <input type="range" id="bi-disc" min="{sl_disc[0]}" max="{sl_disc[1]}" step="0.5" value="{p.get("discount_rate",0.09)*100:.0f}">
          <div class="tri">For PV of terminal equity + dividends only — not a WACC claim</div>
        </div>
        <div class="ctrl">
          <label><span class="lab">FCF / EBITA after tax <span>% · assumption</span></span><span class="cval"><span id="bv-fcf">{p.get("fcf_on_ebita",0.78)*100:.0f}</span>%</span></label>
          <input type="range" id="bi-fcf" min="{sl_fcf[0]}" max="{sl_fcf[1]}" step="1" value="{p.get("fcf_on_ebita",0.78)*100:.0f}">
          <div class="tri">Cash conversion after tax haircut — capex-heavy names sit lower</div>
        </div>
        <div class="ctrl">
          <label><span class="lab">Buyback share of FCF <span>% · assumption</span></span><span class="cval"><span id="bv-bb">{p.get("buyback_ratio",0.20)*100:.0f}</span>%</span></label>
          <input type="range" id="bi-bb" min="0" max="50" step="1" value="{p.get("buyback_ratio",0.20)*100:.0f}">
          <div class="tri">Executed at that year’s FV; rest of non-dividend FCF → net cash</div>
        </div>
      </div>

      <div class="hist-wrap" id="bp-chart-wrap">{svg}</div>

      <div class="tbl-scroll" style="margin-top:14px">
        <table class="brtab" id="bp-table">
          <thead><tr>
            <th>Year</th>
            <th style="text-align:right">Sales €m</th>
            <th style="text-align:right">EBITA %</th>
            <th style="text-align:right">EV/EBITA</th>
            <th style="text-align:right">Net cash €m</th>
            <th style="text-align:right">Shares m</th>
            <th style="text-align:right">Fair value</th>
          </tr></thead>
          <tbody id="bp-tbody">{rows}</tbody>
        </table>
      </div>

      <div class="kg" style="margin-top:14px" id="bp-endstate">
        <div class="kgi pos"><div class="k">Y{H} EBITA</div><div class="v">{cur}{s["terminal_ebita"]:,.0f}m</div></div>
        <div class="kgi"><div class="k">Y{H} sales</div><div class="v">{cur}{s["terminal_sales"]:,.0f}m</div></div>
        <div class="kgi"><div class="k">Shares retired</div><div class="v">{s["shares_retired_total"]:.1f}m</div></div>
        <div class="kgi pos"><div class="k">Cum. FCF ({H}y)</div><div class="v">{cur}{s["cum_fcf"]:,.0f}m</div></div>
      </div>
    </div>

    <div style="font-family:var(--mono);font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--teal-deep);font-weight:600;margin:20px 0 8px">◆ What “everything goes right” means (milestones)</div>
    <div>{mile_html if mile_html else '<p class="body">No milestones configured.</p>'}</div>

    <div style="font-family:var(--mono);font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--coral-deep);font-weight:600;margin:20px 0 8px">◆ Kill-switches — the path breaks if…</div>
    <div style="display:flex;flex-direction:column;gap:8px">{guard_html if guard_html else '<p class="body">No guards configured.</p>'}</div>

    <div class="note t" style="margin-top:16px"><b>How to use this number.</b> The year-{H} fair value is a <i>ceiling under a named path</i>, not a target price and not a probability-weighted expectation. Compare it to Module C’s near-term bull (~scenario card) and to Module A’s P90: if even perfect execution only compounds at high-single-digit CAGR, the asymmetry lives elsewhere; if the ceiling is a multi-bagger with credible milestones, the right tail is economically real. Move the sliders until the path stops feeling honest — that boundary is the point of the tool.
      <div class="src">Method: {method if method else "sales compound at assumed CAGR; margin and multiple ease from today to terminal via smoothstep; FCF = EBITA × (1 − tax) × conversion; split into dividend / buyback / cash."} Defaults from stocks/config.py → bull_case. Interactive path recomputed in-browser; Python reference engine in utils/bullcase.py.</div>
    </div>
  </section>
'''

    # Client-side recalculation (mirrors Python math closely enough for UX)
    js = f'''
<script id="bullcase-js">
(function(){{
  const D = {json.dumps(js_defaults)};
  const $ = (id) => document.getElementById(id);
  function smoothstep(t){{ t=Math.max(0,Math.min(1,t)); return t*t*(3-2*t); }}
  function lerp(a,b,t){{ return a+(b-a)*t; }}
  function fvps(sales,mgn,mlt,nc,sh){{ return sh>0 ? (mlt*(sales*mgn/100)+nc)/sh : 0; }}
  function fmt(cur,x,dp){{ return cur + (dp===0?Math.round(x).toLocaleString('en-US'):x.toFixed(dp)); }}
  function pct(x,dp){{ return (x*100).toFixed(dp)+'%'; }}

  function run(){{
    if(!$('bi-scagr')) return;
    const sales0=+D.sales0, mgn0=+D.mgn0, mlt0=+D.mlt0, nc0=+D.nc0, sh0=+D.shares0;
    const scagr=($('bi-scagr').value)/100;
    const mgnT=+$('bi-mgn').value;
    const mltT=+$('bi-mlt').value;
    const disc=($('bi-disc').value)/100;
    const fcfOn=($('bi-fcf').value)/100;
    const bb=($('bi-bb').value)/100;
    const tax=D.tax/100;
    const H=+D.horizon|0;
    const spot=+D.spot, cur=D.cur;
    // Dividend payout fixed from server default (buyback is the free slider)
    const pay = D.payout/100;

    $('bv-scagr').textContent=(scagr*100).toFixed(1);
    $('bv-mgn').textContent=mgnT.toFixed(1);
    $('bv-mlt').textContent=mltT.toFixed(1);
    $('bv-disc').textContent=(disc*100).toFixed(0);
    $('bv-fcf').textContent=(fcfOn*100).toFixed(0);
    $('bv-bb').textContent=(bb*100).toFixed(0);

    let sales=sales0, mgn=mgn0, mlt=mlt0, nc=nc0, sh=sh0;
    let cumDiv=0, cumDivPv=0, cumFcf=0, cumBb=0;
    const rows=[];
    rows.push({{y:0,sales,mgn,mlt,nc,sh,fv:fvps(sales,mgn,mlt,nc,sh)}});
    for(let y=1;y<=H;y++){{
      const te=smoothstep(y/H);
      sales=sales0*Math.pow(1+scagr,y);
      mgn=lerp(mgn0,mgnT,te);
      mlt=lerp(mlt0,mltT,te);
      const ebita=sales*mgn/100;
      const fcf=ebita*(1-tax)*fcfOn;
      cumFcf+=fcf;
      const divT=fcf*pay;
      const bbM=fcf*bb;
      const retained=fcf-divT-bbM;
      const fvPre=fvps(sales,mgn,mlt,nc+retained,sh);
      const retired=fvPre>0?bbM/fvPre:0;
      sh=Math.max(sh-retired, sh0*0.5);
      nc=nc+retained;
      const fv=fvps(sales,mgn,mlt,nc,sh);
      cumDiv+=divT;
      cumDivPv+=divT/Math.pow(1+disc,y);
      cumBb+=bbM;
      rows.push({{y,sales,mgn,mlt,nc,sh,fv,ebita}});
    }}
    const term=rows[rows.length-1];
    const mid=rows[Math.floor(H/2)];
    const priceCagr=Math.pow(term.fv/spot,1/H)-1;
    const tsrEnd=term.fv+(cumDiv/sh0);
    const tsrCagr=Math.pow(tsrEnd/spot,1/H)-1;
    const pvTerm=term.fv/Math.pow(1+disc,H);
    const pvDiv=cumDivPv/sh0;
    const pvTot=pvTerm+pvDiv;
    const up=term.fv/spot-1;

    $('bp-term').textContent=fmt(cur,term.fv,0);
    $('bp-term-h').textContent=(up>=0?'+':'')+pct(up,0)+' vs spot '+fmt(cur,spot,2);
    $('bp-cagr').textContent=pct(priceCagr,1);
    $('bp-cagr-h').textContent='TSR ≈ '+pct(tsrCagr,1)+' incl. dividends';
    $('bp-pv').textContent=fmt(cur,pvTot,0);
    $('bp-pv-h').textContent='Terminal PV '+fmt(cur,pvTerm,0)+' + div PV '+fmt(cur,pvDiv,0);
    $('bp-mid').textContent=fmt(cur,mid.fv,0);
    $('bp-mid-h').textContent='Y'+mid.y+' on the same path';

    // end-state strip
    const es=$('bp-endstate');
    if(es){{
      es.innerHTML=
        '<div class="kgi pos"><div class="k">Y'+H+' EBITA</div><div class="v">'+fmt(cur,term.ebita|| (term.sales*term.mgn/100),0)+'m</div></div>'+
        '<div class="kgi"><div class="k">Y'+H+' sales</div><div class="v">'+fmt(cur,term.sales,0)+'m</div></div>'+
        '<div class="kgi"><div class="k">Shares retired</div><div class="v">'+(sh0-term.sh).toFixed(1)+'m</div></div>'+
        '<div class="kgi pos"><div class="k">Cum. FCF ('+H+'y)</div><div class="v">'+fmt(cur,cumFcf,0)+'m</div></div>';
    }}

    // table
    const tb=$('bp-tbody');
    if(tb){{
      tb.innerHTML=rows.map(r=>{{
        const lab=r.y===0?'Y0 · now':'Y'+r.y;
        const curCls=r.y===H?' class="cur"':(r.y===0?' class="now"':'');
        return '<tr'+curCls+'><td>'+lab+'</td>'+
          '<td class="num">'+Math.round(r.sales).toLocaleString('en-US')+'</td>'+
          '<td class="num">'+r.mgn.toFixed(1)+'%</td>'+
          '<td class="num">'+r.mlt.toFixed(1)+'×</td>'+
          '<td class="num">'+Math.round(r.nc).toLocaleString('en-US')+'</td>'+
          '<td class="num">'+r.sh.toFixed(1)+'</td>'+
          '<td class="num"><b>'+fmt(cur,r.fv,0)+'</b></td></tr>';
      }}).join('');
    }}

    // chart
    const wrap=$('bp-chart-wrap');
    if(wrap){{
      const W=700,Hgt=200,pl=48,pr=16,pt=16,pb=36;
      const fvs=rows.map(r=>r.fv);
      let lo=Math.min(spot,...fvs)*0.92, hi=Math.max(...fvs)*1.06;
      if(hi<=lo) hi=lo+1;
      const X=i=>pl+(W-pl-pr)*(rows[i].y/H);
      const Y=v=>pt+(Hgt-pt-pb)*(1-(v-lo)/(hi-lo));
      let pts=rows.map((r,i)=>X(i).toFixed(1)+','+Y(r.fv).toFixed(1)).join(' ');
      let dots=rows.map((r,i)=>'<circle cx="'+X(i).toFixed(1)+'" cy="'+Y(r.fv).toFixed(1)+'" r="3.2" fill="var(--teal-deep)"/>').join('');
      let labs='';
      rows.forEach((r,i)=>{{
        if(r.y===0||r.y===Math.floor(H/2)||r.y===H){{
          labs+='<text x="'+X(i).toFixed(1)+'" y="'+(Y(r.fv)-8).toFixed(1)+'" text-anchor="middle" font-family="var(--mono)" font-size="10" font-weight="600" fill="var(--teal-deep)">'+fmt(cur,r.fv,0)+'</text>';
        }}
      }});
      let xt='';
      rows.forEach((r,i)=>{{
        if(r.y%Math.max(1,Math.floor(H/5))===0||r.y===H){{
          xt+='<text x="'+X(i).toFixed(1)+'" y="'+(Hgt-10)+'" text-anchor="middle" font-family="var(--mono)" font-size="10" fill="var(--muted)">Y'+r.y+'</text>';
        }}
      }});
      const ys=Y(spot);
      wrap.innerHTML='<svg id="bull-chart" viewBox="0 0 '+W+' '+Hgt+'" preserveAspectRatio="xMidYMid meet" style="width:100%;height:auto" role="img">'
        +'<line x1="'+pl+'" y1="'+ys.toFixed(1)+'" x2="'+(W-pr)+'" y2="'+ys.toFixed(1)+'" stroke="var(--faint)" stroke-width="1.2" stroke-dasharray="4 3"/>'
        +'<text x="'+(W-pr)+'" y="'+(ys-4).toFixed(1)+'" text-anchor="end" font-family="var(--mono)" font-size="9" fill="var(--faint)">spot '+fmt(cur,spot,0)+'</text>'
        +'<polyline fill="none" stroke="var(--teal)" stroke-width="2.4" points="'+pts+'"/>'
        +dots+labs+xt+'</svg>';
    }}
  }}
  ['bi-scagr','bi-mgn','bi-mlt','bi-disc','bi-fcf','bi-bb'].forEach(id=>{{
    const el=$(id); if(el) el.addEventListener('input', run);
  }});
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', run);
  else run();
}})();
</script>
'''
    return html + js


# ---------------------------------------------------------------------------
# Inject into report HTML
# ---------------------------------------------------------------------------

def inject(name: str) -> str:
    """Compute bull path and (re)inject Module U into the stock HTML report."""
    cfg = STOCKS[name]
    if "bull_case" not in cfg:
        return f"SKIP — {name}: no bull_case config"

    result = compute_bull_path(name)
    frag = render_module_U(name, result)
    s = result["summary"]
    path = html_path(cfg)

    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    # CSS once
    if 'id="bullcase-css"' not in html:
        html = html.replace("</head>", CSS_BULL + "\n</head>", 1)

    # Replace or insert module (use callable repl to avoid re.escape issues with \u etc.)
    if 'id="mU"' in html:
        html = re.sub(
            r'\s*<section class="mod" id="mU"[^>]*>.*?</section>\s*(?:<script id="bullcase-js">.*?</script>\s*)?',
            lambda _m: "\n\n" + frag + "\n\n",
            html,
            count=1,
            flags=re.S,
        )
    else:
        # Prefer after Module C; else before scorecard; else before audit
        inserted = False
        for marker in (
            r'(</section>\s*)(?=<section class="mod" id="mH">)',
            r'(</section>\s*)(?=<section class="mod" id="mI">)',
            r'(</section>\s*)(?=<section class="mod" id="mSum">)',
            r'(</section>\s*)(?=<section class="audit")',
        ):
            if re.search(marker, html):
                html = re.sub(
                    marker,
                    lambda m: m.group(1) + "\n" + frag + "\n",
                    html,
                    count=1,
                )
                inserted = True
                break
        if not inserted:
            raise RuntimeError(f"Could not find insert point for Module U in {path}")

    # Stepper link
    if '<a href="#mU">' not in html:
        html = re.sub(
            r'(<a href="#mC"[^>]*>.*?</a>)',
            r'\1\n    <a href="#mU"><span class="n">U</span>10y upside</a>',
            html,
            count=1,
            flags=re.S,
        )
        if '<a href="#mU">' not in html:
            html = re.sub(
                r'(<a href="#mH"[^>]*>.*?</a>)',
                r'<a href="#mU"><span class="n">U</span>10y upside</a>\n    \1',
                html,
                count=1,
                flags=re.S,
            )

    # Scorecard row
    row_u = (
        f'<tr><td>U · 10y upside</td><td><span class="vchip bull">BULL</span></td>'
        f'<td>Perfect-execution Y{s["horizon"]} FV ≈ {s["currency"]}{s["terminal_fv"]:.0f} '
        f'({_fmt_pct(s["price_cagr"], 1)} price CAGR; PV ≈ {s["currency"]}{s["pv_total_ps"]:.0f})</td></tr>'
    )
    if "<td>U · 10y upside</td>" in html:
        html = re.sub(
            r"<tr><td>U · 10y upside</td>.*?</tr>",
            row_u,
            html,
            count=1,
            flags=re.S,
        )
    else:
        # Prefer after C (near-term scenarios → long-horizon ceiling), else after H
        inserted_row = False
        for pat in (
            r"(<tr><td>C · Scenarios \+ Bayes</td>.*?</tr>)",
            r"(<tr><td>H · Kill-criteria</td>.*?</tr>)",
        ):
            if re.search(pat, html, re.S):
                html = re.sub(
                    pat,
                    lambda m, row=row_u: m.group(1) + "\n        " + row,
                    html,
                    count=1,
                    flags=re.S,
                )
                inserted_row = True
                break
        if not inserted_row:
            html = re.sub(
                r"(<table class=\"scoretab\">.*?)(</tbody>)",
                lambda m, row=row_u: m.group(1) + "        " + row + "\n      " + m.group(2),
                html,
                count=1,
                flags=re.S,
            )

    # Scorecard title count is synced by finalize.py (which runs after this
    # step in both orchestrators) from the actual row count — nothing to do here.

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    return (
        f"OK — {name}: Module U injected. "
        f"Y{s['horizon']} FV {s['currency']}{s['terminal_fv']:.0f} "
        f"({_fmt_pct(s['price_cagr'], 1)} CAGR, "
        f"PV {s['currency']}{s['pv_total_ps']:.0f} @ {_fmt_pct(s['discount_rate'], 0)})"
    )


def _print_path(name: str) -> None:
    r = compute_bull_path(name)
    s = r["summary"]
    cur = s["currency"]
    print(f"=== {name.upper()} ({s['ticker']}) perfect-execution {s['horizon']}y ===")
    print(f"  Spot            {cur}{s['spot']:.2f}")
    print(f"  Y{s['horizon']} fair value  {cur}{s['terminal_fv']:.0f}   ({_fmt_pct(s['upside_vs_spot'], 0, sign=True)} vs spot)")
    print(f"  Price CAGR      {_fmt_pct(s['price_cagr'], 2)}")
    print(f"  TSR CAGR        {_fmt_pct(s['tsr_cagr'], 2)}  (incl. dividends)")
    print(f"  PV @ {_fmt_pct(s['discount_rate'], 0):>5}     {cur}{s['pv_total_ps']:.0f}   (term {cur}{s['pv_term_ps']:.0f} + divs {cur}{s['pv_divs_ps']:.0f})")
    print(f"  Y{s['mid_year']} checkpoint  {cur}{s['mid_fv']:.0f}")
    print(f"  Terminal state  sales {cur}{s['terminal_sales']:,.0f}m · mgn {s['terminal_mgn']:.1f}% · "
          f"mlt {s['terminal_mlt']:.1f}× · nc {cur}{s['terminal_nc']:,.0f}m · sh {s['terminal_shares']:.1f}m")
    print(f"  Cum FCF / div / bb  {cur}{s['cum_fcf']:,.0f}m / {cur}{s['cum_div_nom']:,.0f}m / {cur}{s['cum_buyback']:,.0f}m")
    print()
    print(f"  {'Yr':>4} {'Sales':>8} {'Mgn':>6} {'Mlt':>6} {'NC':>8} {'Sh':>7} {'FV':>8}")
    for y in r["years"]:
        print(
            f"  Y{y['year']:<3} {y['sales']:>8,.0f} {y['mgn']:>5.1f}% {y['mlt']:>5.1f}× "
            f"{y['nc']:>8,.0f} {y['shares']:>7.1f} {cur}{y['fv']:>7.0f}"
        )


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    print_only = "--print" in sys.argv
    which = args[0] if args else "all"

    targets = all_names() if which == "all" else [which]
    for n in targets:
        if n not in STOCKS:
            print(f"Unknown: {n}. Known: {list(STOCKS)}")
            return 1
        if "bull_case" not in STOCKS[n]:
            if which != "all":
                print(f"{n}: no bull_case config — add STOCKS['{n}']['bull_case']")
                return 1
            continue
        if print_only:
            _print_path(n)
        else:
            _print_path(n)
            print(inject(n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
