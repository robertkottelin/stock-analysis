"""Generator for stocks/micron-pipeline.html.

Micron (MU) is data-heavy (a hyper-cyclical memory name with a violent FY2023
trough and an FY2026 AI/HBM super-cycle), so the fundamental-dashboard charts
are computed from real arrays here rather than hand-plotted — guaranteeing the
pixel geometry matches the numbers. Authored narrative is embedded as strings;
the interactive Module A engine mirrors stocks/config_micron.py's engine exactly.

Run once to (re)emit the report skeleton:

    python stocks/_micron_build.py

Then build the live layers (Modules I/J/U, audit, tallies, finalize, verify):

    python utils/build_one.py micron

The CSS (base + shared UX fixes) is lifted verbatim from the Konecranes report
so every report shares one design system; Module-I/J, audit and bull-case CSS
are added by the framework at build time.
"""
from __future__ import annotations
import os, re, sys, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "utils"))
from analytics import fetch_chart, series  # noqa: E402

CUR = "$"

# ------------------------------------------------------------------ real data
# Fiscal years end late August. Reported annual line items (Yahoo
# fundamentals-timeseries / Micron FY releases), $bn unless noted.
FY      = [2022, 2023, 2024, 2025]
REV     = [30.76, 15.54, 25.11, 37.38]      # revenue $bn
EPS     = [7.75, -5.34, 0.70, 7.59]         # diluted EPS $
GM      = [45.2, -9.1, 22.3, 39.8]          # gross margin %
OM      = [31.6, -34.8, 5.2, 26.2]          # operating margin %
NM      = [28.2, -37.5, 3.1, 22.8]          # net margin %
EBITDA  = [16.88, 2.49, 9.58, 18.48]        # $bn
EBITDAM = [54.9, 16.0, 38.2, 49.4]          # EBITDA margin %
ROE     = [17.4, -13.2, 1.7, 15.8]          # %
OCF     = [15.18, 1.56, 8.51, 17.52]        # $bn
FCF     = [3.11, -6.12, 0.12, 1.67]         # $bn
DE      = [0.15, 0.32, 0.31, 0.28]          # debt / equity
COV     = [51.0, None, 2.3, 20.4]           # interest coverage (EBIT / interest); FY23 n.m. (loss)
CURR    = [2.89, 4.46, 2.63, 2.52]          # current ratio
QUICK   = [2.00, 2.70, 1.67, 1.79]          # quick ratio
PB      = [1.25, 1.71, 2.37, 2.47]          # year-end price / book
EVEBIT  = [3.6, 32.1, 11.8, 7.5]            # year-end EV / EBITDA (FY23 on trough EBITDA — n.m.)
YREND_PX = [55.44, 69.17, 95.64, 118.82]    # ~fiscal-year-end share price

# Trailing-twelve-month (FY2026 in progress) — the AI/HBM super-cycle
TTM = dict(rev=90.27, eps=44.23, gm=72.6, om=None, nm=55.9, ebitda=68.22, ebitdam=75.6,
           roe=66.6, ocf=51.43, fcf=7.64, curr=3.43, quick=2.93, de=0.09,
           pe=19.2, pb=13.2, evebitda=13.8, price=848.95, mcap=958.8, ev=939.2,
           netcash=19.6, fwd_eps=150.77, fwd_pe=5.6, beta=2.14, cons_pt=1491.95,
           target_low=361.0, target_high=2200.0, n_analysts=42)

# Calibrated MC / scenario anchors (utils/analytics on the wired config)
MC = dict(p10=561, median=827, p90=1169, p_up=46, kelly=0, asym=1.00,
          cvar10=-43, var10=-34, rdcf_implied=62.5, rdcf_mode=62.0,
          scen_bear=282, scen_base=829, scen_bull=1501, cons_gap=76)


# ------------------------------------------------------------------ SVG helpers
# Small quality-card geometry (matches Konecranes qcards): 360×208 viewBox,
# plot area x∈[44,344], y∈[22,166]. Four categories centred at 81.5 … 306.5.
PX0, PX1, PY0, PY1 = 44, 344, 22, 166
CX = [81.5, 156.5, 231.5, 306.5]
BW = 34
TEAL, BLUE, AMB, AMBD, CORAL, CORALD, FAINT, MUT, INK = (
    "var(--teal)", "var(--blue)", "var(--amber)", "var(--amber-deep)",
    "var(--coral)", "var(--coral-deep)", "var(--faint)", "var(--muted)", "var(--ink)")


def _yfun(ymin, ymax):
    def y(v):
        return PY1 - (v - ymin) / (ymax - ymin) * (PY1 - PY0)
    return y


def _grid(ymin, ymax, ticks, tickfmt):
    y = _yfun(ymin, ymax)
    s = '<g stroke="var(--line)" stroke-width="1">'
    for t in ticks:
        s += f'<line x1="{PX0}" y1="{y(t):.1f}" x2="{PX1}" y2="{y(t):.1f}"/>'
    s += '</g>'
    s += '<g font-family="IBM Plex Mono,monospace" font-size="9" fill="var(--faint)" text-anchor="end">'
    for t in ticks:
        s += f'<text x="39" y="{y(t)+3:.1f}">{tickfmt(t)}</text>'
    s += '</g>'
    s += f'<line x1="{PX0}" y1="{PY1}" x2="{PX1}" y2="{PY1}" stroke="var(--line-strong)" stroke-width="1.1"/>'
    s += f'<line x1="{PX0}" y1="{PY0}" x2="{PX0}" y2="{PY1}" stroke="var(--line-strong)" stroke-width="1.1"/>'
    return s


def _cats():
    s = '<g font-family="IBM Plex Mono,monospace" font-size="9.5" text-anchor="middle">'
    for cx, fy in zip(CX, FY):
        s += f'<text x="{cx}" y="184" fill="var(--muted)" font-weight="500">{fy}</text>'
    s += '</g>'
    return s


def card(title, sub, body_svg, read):
    return (f'<div class="qcard"><div class="qtt">{title}</div><div class="qsub">{sub}</div>'
            f'<svg viewBox="0 0 360 208" style="width:100%;height:auto" role="img">{body_svg}</svg>'
            f'<div class="qread">{read}</div></div>')


def bars(vals, ymin, ymax, ticks, tickfmt, valfmt, colorfn, ttm=None, danger=None):
    """Vertical bars with a zero baseline; supports negatives."""
    y = _yfun(ymin, ymax)
    y0 = y(0)
    s = _grid(ymin, ymax, ticks, tickfmt)
    if danger is not None:
        dv, dl, dc = danger
        s += (f'<line x1="{PX0}" y1="{y(dv):.1f}" x2="{PX1}" y2="{y(dv):.1f}" stroke="{dc}" '
              f'stroke-width="1" stroke-dasharray="4 4" opacity="0.8"/>'
              f'<text x="47" y="{y(dv)-3:.1f}" font-family="IBM Plex Mono,monospace" font-size="8" fill="{dc}" text-anchor="start">{dl}</text>')
    for cx, v in zip(CX, vals):
        if v is None:
            s += (f'<text x="{cx}" y="{y0-4:.1f}" text-anchor="middle" font-family="IBM Plex Mono,monospace" '
                  f'font-size="8.5" fill="var(--faint)">n.m.</text>')
            continue
        col = colorfn(v)
        yv = y(v)
        top = min(yv, y0)
        h = abs(yv - y0)
        s += f'<rect x="{cx-BW/2:.1f}" y="{top:.1f}" width="{BW}" height="{h:.1f}" rx="2.5" fill="{col}"/>'
        ly = (yv - 5) if v >= 0 else (yv + 11)
        s += (f'<text x="{cx}" y="{ly:.1f}" text-anchor="middle" font-family="IBM Plex Mono,monospace" '
              f'font-size="9" font-weight="600" fill="{col}">{valfmt(v)}</text>')
    s += _cats()
    if ttm is not None:
        tv, tl, tc = ttm
        yv = max(PY0 + 6, min(PY1 - 2, y(tv)))
        s += (f'<line x1="{PX0}" y1="{yv:.1f}" x2="{PX1}" y2="{yv:.1f}" stroke="{tc}" stroke-width="1.1" stroke-dasharray="1 2" opacity="0.9"/>'
              f'<text x="{PX1-2}" y="{yv-3:.1f}" text-anchor="end" font-family="IBM Plex Mono,monospace" font-size="8" fill="{tc}">{tl}</text>')
    return s


def lines(series_list, ymin, ymax, ticks, tickfmt):
    """One or more line series over the 4 fiscal years. series_list: (vals,color,label-dots)."""
    y = _yfun(ymin, ymax)
    s = _grid(ymin, ymax, ticks, tickfmt)
    y0 = y(0)
    if ymin < 0 < ymax:
        s += f'<line x1="{PX0}" y1="{y0:.1f}" x2="{PX1}" y2="{y0:.1f}" stroke="var(--line-strong)" stroke-width="0.8" stroke-dasharray="2 3" opacity="0.7"/>'
    for vals, col, _lab in series_list:
        pts = " ".join(f"{cx:.1f},{y(v):.1f}" for cx, v in zip(CX, vals))
        s += f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2.2" stroke-linejoin="round"/>'
        s += f'<g fill="{col}" stroke="var(--surface)" stroke-width="1.5">'
        for cx, v in zip(CX, vals):
            s += f'<circle cx="{cx:.1f}" cy="{y(v):.1f}" r="3.2"/>'
        s += '</g>'
    s += _cats()
    return s


def bars_line(bar_vals, b_ymin, b_ymax, b_ticks, b_tickfmt, b_valfmt, b_color,
              line_vals, l_ymin, l_ymax, l_tickfmt, l_color, l_valfmt):
    """Bars (left axis) + a line (right axis)."""
    yb = _yfun(b_ymin, b_ymax)
    yl = _yfun(l_ymin, l_ymax)
    s = _grid(b_ymin, b_ymax, b_ticks, b_tickfmt)
    # right axis labels
    s += '<g font-family="IBM Plex Mono,monospace" font-size="9" fill="var(--amber-deep)" text-anchor="start">'
    for t in b_ticks:
        lv = l_ymin + (t - b_ymin) / (b_ymax - b_ymin) * (l_ymax - l_ymin)
        s += f'<text x="349" y="{yb(t)+3:.1f}">{l_tickfmt(lv)}</text>'
    s += '</g>'
    yb0 = yb(0)
    for cx, v in zip(CX, bar_vals):
        if v is None:
            s += (f'<text x="{cx}" y="{yb0-4:.1f}" text-anchor="middle" font-family="IBM Plex Mono,monospace" '
                  f'font-size="8.5" fill="var(--faint)">n.m.</text>')
            continue
        col = b_color(v)
        yv = yb(v); top = min(yv, yb0); h = abs(yv - yb0)
        s += f'<rect x="{cx-BW/2:.1f}" y="{top:.1f}" width="{BW}" height="{h:.1f}" rx="2.5" fill="{col}"/>'
        ly = (yv - 5) if v >= 0 else (yv + 11)
        s += (f'<text x="{cx}" y="{ly:.1f}" text-anchor="middle" font-family="IBM Plex Mono,monospace" '
              f'font-size="9" font-weight="600" fill="{col}">{b_valfmt(v)}</text>')
    pts = " ".join(f"{cx:.1f},{yl(v):.1f}" for cx, v in zip(CX, line_vals))
    s += f'<polyline points="{pts}" fill="none" stroke="{l_color}" stroke-width="2.2" stroke-linejoin="round"/>'
    s += f'<g fill="{l_color}" stroke="var(--surface)" stroke-width="1.5">'
    for cx, v in zip(CX, line_vals):
        s += f'<circle cx="{cx:.1f}" cy="{yl(v):.1f}" r="3.2"/>'
    s += '</g>'
    s += '<g font-family="IBM Plex Mono,monospace" font-size="8.5" font-weight="600" fill="var(--amber-deep)" paint-order="stroke" stroke="var(--surface-2)" stroke-width="2.6">'
    for cx, v in zip(CX, line_vals):
        s += f'<text x="{cx+6:.1f}" y="{yl(v)-4:.1f}" text-anchor="start">{l_valfmt(v)}</text>'
    s += '</g>'
    s += _cats()
    return s


def price_eps_overlay():
    """Big co-movement overlay: daily price (left) vs TTM diluted EPS (right),
    each normalised to its own axis. The AI super-cycle dwarfs the pre-2026
    tape, so this reads shape/timing, not levels."""
    chart = fetch_chart("MU", "5y")
    ts, px = series(chart)
    X0, X1, Y0, Y1 = 58, 648, 30, 252
    pmin, pmax = 0, 1300
    emin, emax = -8, 48
    def xf(i):
        return X0 + i / (len(px) - 1) * (X1 - X0)
    def yp(v):
        return Y1 - (v - pmin) / (pmax - pmin) * (Y1 - Y0)
    def ye(v):
        return Y1 - (v - emin) / (emax - emin) * (Y1 - Y0)
    # downsample price to ~300 pts
    step = max(1, len(px) // 300)
    idx = list(range(0, len(px), step))
    if idx[-1] != len(px) - 1:
        idx.append(len(px) - 1)
    ppts = " ".join(f"{xf(i):.1f},{yp(px[i]):.1f}" for i in idx)
    # EPS points at fiscal year-ends + TTM, placed by date fraction across window
    import datetime as _dt
    t0 = ts[0]; t1 = ts[-1]
    def frac_x(d):
        tt = _dt.datetime(d.year, d.month, d.day).timestamp()
        f = (tt - t0) / (t1 - t0)
        return X0 + max(0, min(1, f)) * (X1 - X0)
    eps_pts = [(_dt.date(2022, 8, 31), 7.75), (_dt.date(2023, 8, 31), -5.34),
               (_dt.date(2024, 8, 30), 0.70), (_dt.date(2025, 8, 29), 7.59),
               (_dt.date(2026, 7, 17), 44.23)]
    epoly = " ".join(f"{frac_x(d):.1f},{ye(v):.1f}" for d, v in eps_pts)
    # y grid (price, left) 0..1300
    s = '<defs><clipPath id="peclip"><rect x="58" y="30" width="590" height="222"/></clipPath></defs>'
    s += '<g stroke="var(--line)" stroke-width="1">'
    for t in (0, 325, 650, 975, 1300):
        s += f'<line x1="58" y1="{yp(t):.1f}" x2="648" y2="{yp(t):.1f}"/>'
    s += '</g>'
    s += '<line x1="58" y1="30" x2="58" y2="252" stroke="var(--line-strong)" stroke-width="1.2"/>'
    s += '<line x1="648" y1="30" x2="648" y2="252" stroke="var(--line-strong)" stroke-width="1.2"/>'
    s += '<line x1="58" y1="252" x2="648" y2="252" stroke="var(--line-strong)" stroke-width="1.2"/>'
    s += '<g font-family="IBM Plex Mono,monospace" font-size="10" fill="var(--blue-deep)" text-anchor="end">'
    for t in (0, 325, 650, 975, 1300):
        s += f'<text x="50" y="{yp(t)+3.5:.1f}">${t}</text>'
    s += '</g>'
    s += '<g font-family="IBM Plex Mono,monospace" font-size="10" fill="var(--amber-deep)" text-anchor="start">'
    for t in (-8, 6, 20, 34, 48):
        s += f'<text x="658" y="{ye(t)+3.5:.1f}">{"+" if t>=0 else ""}{t}</text>'
    s += '</g>'
    s += f'<g clip-path="url(#peclip)"><polyline points="{ppts}" fill="none" stroke="var(--blue)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/></g>'
    s += f'<polyline points="{epoly}" fill="none" stroke="var(--amber-deep)" stroke-width="2.2" stroke-linejoin="round"/>'
    s += '<g fill="var(--amber-deep)" stroke="var(--surface)" stroke-width="1.6">'
    for d, v in eps_pts:
        s += f'<circle cx="{frac_x(d):.1f}" cy="{ye(v):.1f}" r="3.6"/>'
    s += '</g>'
    s += ('<g font-family="IBM Plex Mono,monospace" font-size="9.5" font-weight="600" fill="var(--amber-deep)">'
          f'<text x="{frac_x(_dt.date(2023,8,31)):.1f}" y="{ye(-5.34)+13:.1f}" text-anchor="middle" paint-order="stroke" stroke="var(--surface-2)" stroke-width="2.6">-5.34</text>'
          f'<text x="{frac_x(_dt.date(2026,7,17)):.1f}" y="{ye(44.23)-8:.1f}" text-anchor="end" paint-order="stroke" stroke="var(--surface-2)" stroke-width="2.6">+44.23</text>'
          '</g>')
    s += '<g font-family="IBM Plex Mono,monospace" font-size="10" fill="var(--muted)" text-anchor="middle">'
    for yr in (2022, 2023, 2024, 2025, 2026):
        s += f'<text x="{frac_x(_dt.date(yr,1,1)):.1f}" y="272">{yr}</text>'
    s += '</g>'
    s += '<text x="8" y="20" text-anchor="start" font-family="IBM Plex Mono,monospace" font-size="10" font-weight="600" fill="var(--blue-deep)">Share price $</text>'
    s += '<text x="658" y="20" text-anchor="start" font-family="IBM Plex Mono,monospace" font-size="10" font-weight="600" fill="var(--amber-deep)">TTM EPS $</text>'
    return f'<svg viewBox="0 0 720 300" style="width:100%;height:auto" role="img" aria-label="Micron share price versus trailing-twelve-month diluted EPS.">{s}</svg>'


# colour helpers
def pos_neg(v):
    return TEAL if v >= 0 else CORAL
def amber(v):
    return AMB
def blue(v):
    return BLUE


# ------------------------------------------------------------------ Module Q
def module_Q():
    overlay = price_eps_overlay()
    c_rev = card("① Revenue ($bn) &amp; EPS", "Bars = revenue &middot; <span style='color:var(--amber-deep)'>line = diluted EPS (right)</span>",
        bars_line(REV, 0, 40, [0, 10, 20, 30, 40], lambda t: f"{t:.0f}", lambda v: f"{v:.1f}", pos_neg,
                  EPS, -8, 10, lambda v: f"{'+' if v>=0 else ''}{v:.0f}", AMBD, lambda v: f"{'+' if v>=0 else ''}{v:.2f}"),
        "<b>The memory cycle, in one chart.</b> Revenue $30.8&rarr;$15.5 (FY23 glut)&rarr;$37.4bn; EPS $7.75&rarr;<b>&minus;$5.34</b>&rarr;+$7.59. TTM (FY26) has since exploded to <b>~$90bn</b> revenue / <b>$44.23</b> EPS on the AI/HBM super-cycle &mdash; off this axis.")
    c_mgn = card("② Profit margins", "<span style='color:var(--teal)'>gross</span> &middot; <span style='color:var(--blue)'>operating</span> &middot; <span style='color:var(--amber-deep)'>net</span> &divide; revenue",
        lines([(GM, TEAL, "gross"), (OM, BLUE, "op"), (NM, AMBD, "net")], -40, 80, [-40, 0, 40, 80], lambda t: f"{t:.0f}%"),
        "<b>Violently cyclical.</b> Gross margin went <b>negative (&minus;9%)</b> in the FY23 glut, then back to ~40%. TTM gross margin is now ~<b>72.6%</b> and net ~55.9% &mdash; the HBM-led peak.")
    c_roe = card("③ Return on equity", "Net income &divide; equity &middot; <span style='color:var(--coral-deep)'>dashed = TTM</span>",
        bars(ROE, -20, 80, [-20, 0, 20, 40, 60, 80], lambda t: f"{t:.0f}%", lambda v: f"{v:.1f}", pos_neg,
             ttm=(66.6, "TTM ~66.6%", CORALD)),
        "<b>From &minus;13% to ~66%.</b> ROE swung negative in FY23, recovered to ~16% (FY25), and TTM sits near <b>66.6%</b> at the super-cycle peak &mdash; the definition of a cyclical, not a steady compounder.")
    c_cf = card("④ Cash flow ($bn)", "Bars = FCF &middot; <span style='color:var(--blue)'>line = operating CF (right)</span>",
        bars_line(FCF, -8, 4, [-8, -4, 0, 4], lambda t: f"{t:.0f}", lambda v: f"{'+' if v>=0 else ''}{v:.1f}", pos_neg,
                  OCF, 0, 18, lambda v: f"{v:.0f}", BLUE, lambda v: f"{v:.0f}"),
        "<b>The capex reality.</b> Operating cash flow is huge and positive every year ($1.6&ndash;$17.5bn), but <b>free</b> cash flow is thin or negative &mdash; fab capex ($8&ndash;$16bn/yr) eats it. TTM OCF ~$51bn, FCF ~$7.6bn. Owner earnings live and die on the capex line.")
    c_eb = card("⑤ EBITDA ($bn) &amp; margin", "Bars = EBITDA &middot; <span style='color:var(--amber-deep)'>line = EBITDA margin (right)</span>",
        bars_line(EBITDA, 0, 20, [0, 5, 10, 15, 20], lambda t: f"{t:.0f}", lambda v: f"{v:.1f}", pos_neg,
                  EBITDAM, 0, 80, lambda v: f"{v:.0f}%", AMBD, lambda v: f"{v:.0f}%"),
        "<b>Engine input.</b> EBITDA $16.9&rarr;$2.5 (trough)&rarr;$18.5bn; margin 55%&rarr;16%&rarr;49%. The Module-A engine values a <b>through-cycle</b> EBITDA, not the ~$68bn / ~76% TTM peak.")
    c_bs = card("⑥ Leverage &amp; liquidity", "Bars = debt/equity &middot; <span style='color:var(--teal-deep)'>line = current ratio (right)</span>",
        bars_line(DE, 0, 0.4, [0, 0.1, 0.2, 0.3, 0.4], lambda t: f"{t:.1f}", lambda v: f"{v:.2f}", amber,
                  CURR, 0, 5, lambda v: f"{v:.0f}", "var(--teal-deep)", lambda v: f"{v:.1f}×"),
        "<b>Fortress balance sheet.</b> Debt/equity peaked ~0.32 in the trough (when they drew liquidity) and is back to ~0.28; current ratio 2.5&ndash;4.5×. TTM: net <b>cash</b> ~$19.6bn, current ratio 3.4×.")
    c_val = card("⑦ Valuation (year-end)", "Bars = EV/EBITDA &middot; <span style='color:var(--amber-deep)'>line = P/B (right)</span>",
        bars_line([EVEBIT[0], None, EVEBIT[2], EVEBIT[3]], 0, 14, [0, 3.5, 7, 10.5, 14], lambda t: f"{t:.0f}", lambda v: f"{v:.1f}×", blue,
                  PB, 0, 3, lambda v: f"{v:.0f}", AMBD, lambda v: f"{v:.1f}"),
        "<b>Cheap on trough optics.</b> Year-end EV/EBITDA 3.6&ndash;11.8× (FY23 n.m. on trough EBITDA), P/B 1.2&rarr;2.5×. <b>Now</b>: EV/EBITDA ~13.8×, P/B ~13.2× &mdash; the re-rating is in the price, not the multiple.")
    c_cov = card("⑧ Interest coverage", "EBIT &divide; interest expense",
        bars(COV, 0, 55, [0, 15, 30, 45], lambda t: f"{t:.0f}×", lambda v: f"{v:.0f}×", pos_neg,
             danger=(1.0, "1× = danger", CORAL)),
        "<b>Comfortable outside the trough.</b> Coverage 51×&rarr;<b>n.m.</b> (FY23 loss)&rarr;2.3×&rarr;20×. The one year it broke is the whole risk: a deep memory glut turns EBIT negative.")
    cards = "".join([c_rev, c_mgn, c_roe, c_cf, c_eb, c_bs, c_val, c_cov])
    return f'''<section class="mod" id="mQ"><div class="mod-head"><div class="mod-no">Q</div><div class="ht"><h2>Fundamental quality &amp; valuation dashboard</h2><div class="hq">Profitability, cash, leverage, valuation and the memory cycle &mdash; from fetched annual financials (FY2022&ndash;FY2025) plus the FY2026 TTM super-cycle.</div></div><span class="tagchip c">Fetched financials</span></div>
    <div class="verdict mixed"><span class="vchip">MIXED</span><span class="vtext">A textbook <b>cyclical</b>: a negative-gross-margin trough (FY23) two years before an AI-driven super-cycle (TTM revenue ~$90bn, ~76% EBITDA margin, ~66% ROE). Current fundamentals are exceptional; the question the rest of the report asks is <b>how much of it is through-cycle</b>.</span></div>
    <p class="body">Every figure is <b>fetched</b> from Yahoo&rsquo;s fundamentals feed (annual income statement, balance sheet, cash-flow) and, where a ratio, computed from those line items. The trailing-twelve-month (TTM) column reflects the FY2026-in-progress AI/HBM super-cycle and is called out separately so the annual bars stay on a readable scale.</p>
    <div class="mc-wrap" style="margin:6px 0 4px"><div class="mc-title">Share price vs earnings &mdash; does the tape track the fundamentals?</div><div class="mc-sub">Daily close (left) against TTM diluted EPS (right), each normalised to fill the plot. This reads <b>co-movement and lead/lag</b>, not levels &mdash; the FY26 AI super-cycle is off-scale on both.</div><div class="hist-leg"><span><span class="sw" style="background:var(--blue)"></span>Share price $&nbsp;&middot;&nbsp;left</span><span><span class="sw" style="background:var(--amber-deep)"></span>TTM diluted EPS $&nbsp;&middot;&nbsp;right</span></div>{overlay}<div class="reading" style="margin-top:12px"><b>How to read it.</b> Price and EPS trough together (FY23) and inflect together (FY26). The <span class='asm'>scales are normalised independently</span> &mdash; only shape and timing are meaningful. The lesson: in memory, the tape follows the earnings cycle, and both just went vertical.</div></div>
    <div class="qgrid">{cards}</div>
    <div class="src">Source: Yahoo Finance fundamentals-timeseries (MU, annual FY2022&ndash;FY2025) + the MU 5-year daily chart cache for prices and the TTM column. Ratios computed at build time. Cards use reported fiscal years; the FY2026 super-cycle is shown as the trailing-twelve-month read.</div></section>'''


# ------------------------------------------------------------------ authored modules
def module_T():
    return '''<section class="mod" id="mThesis">
    <div class="mod-head"><div class="mod-no">T</div>
      <div class="ht"><h2>Business thesis &amp; macro place</h2><div class="hq">What Micron is, where the cash comes from, and how it sits at the centre of the AI · robotics · data · energy build-out.</div></div>
      <span class="tagchip a">Sourced + judgment</span>
    </div>
    <div class="verdict bull"><span class="vchip">BULL · THESIS</span><span class="vtext">Of the names in this book, Micron is the <b>most direct beneficiary of the AI build-out that still trades as a hardware cyclical</b>. Memory is the co-processor to compute: every AI accelerator needs high-bandwidth memory (HBM), and Micron is one of only three vendors on earth who can make it. The thesis is strong; the <i>valuation debate</i> (Modules A&ndash;C) is entirely about how much of the super-cycle is through-cycle.</span></div>

    <p class="body"><b>What the company is.</b> Micron Technology (NASDAQ: MU) is one of the world&rsquo;s largest makers of <b>memory and storage</b> semiconductors &mdash; <b>DRAM</b> (~70%+ of revenue: the working memory in servers, PCs, phones and cars) and <b>NAND</b> flash (the balance: SSDs and storage). It is the only US-headquartered scaled memory maker, against Korea&rsquo;s Samsung and SK hynix. TTM revenue has reached ~<b>$90bn</b> with a ~<b>76% EBITDA margin</b> and net <b>cash</b> &mdash; figures unrecognisable against the FY2023 memory glut, when gross margin went negative.</p>

    <p class="body"><b>Why memory is different now.</b> For decades memory was a brutal, undifferentiated commodity: three players, boom-bust capex, margins to zero at the bottom. Two things changed. First, <b>consolidation and capital discipline</b> &mdash; DRAM is a rational three-firm oligopoly. Second, and decisively, <b>HBM</b>: the stacked, high-bandwidth DRAM bolted next to every AI GPU. HBM is capacity-constrained, sold out quarters ahead, priced at a large premium, and gross-margin-accretive. It has dragged the entire memory complex into an up-cycle with a genuinely new secular demand driver on top of the old cycle.</p>

    <div style="font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--blue-deep);font-weight:600;margin:18px 0 10px">◆ Place in the macro stack — five trend lenses</div>
    <p class="body" style="margin-bottom:12px">Micron does not train models or design GPUs. It sells the <b>memory layer</b> without which none of them run. The question is which macro waves touch that layer &mdash; and here, unlike most industrials, the answer is &ldquo;the biggest one, directly.&rdquo;</p>
    <div class="lenses" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr))">
      <div class="lens comp"><div class="lt">1 · AI (direct, not narrative)</div><div class="lh">HBM for accelerators</div><div class="lb">Every AI training/inference system pairs compute with HBM. Micron is one of three HBM suppliers; capacity is pre-sold and margin-accretive. This is the <b>core thesis</b> &mdash; a direct, contracted AI revenue line, not a second-order tailwind.</div></div>
      <div class="lens empir"><div class="lt">2 · Computing &amp; data centres</div><div class="lh">Content-per-server growth</div><div class="lb">Beyond HBM, AI servers carry far more standard DRAM and SSD content than traditional servers. Data-center is Micron&rsquo;s fastest-growing end market &mdash; a <b>volume + mix</b> tailwind that compounds with every rack built.</div></div>
      <div class="lens owner"><div class="lt">3 · Robotics &amp; edge AI</div><div class="lh">Memory at the edge</div><div class="lb">Autonomy, humanoids and industrial robots are memory-hungry at the edge (LPDDR, automotive-grade DRAM/NAND). Micron&rsquo;s embedded/auto franchise is a <b>long-dated call option</b> on inference moving out of the datacenter.</div></div>
      <div class="lens empir"><div class="lt">4 · Data &amp; storage</div><div class="lh">The data-gravity flywheel</div><div class="lb">AI both consumes and generates data at scale, lifting NAND/SSD demand across cloud and enterprise. A <b>cyclical-but-secular</b> support to the NAND half of the business, historically the weaker franchise.</div></div>
      <div class="lens comp"><div class="lt">5 · Energy &amp; supply security</div><div class="lh">Fabs, power &amp; CHIPS policy</div><div class="lb">Leading-edge memory fabs are enormous, power-hungry, and strategically prized; US/CHIPS-era incentives support Micron&rsquo;s domestic capacity. Energy cost and grid access are real inputs &mdash; and a <b>geopolitical moat</b> for the only US memory major.</div></div>
    </div>

    <div class="synth" style="margin-top:16px"><b>Investment thesis (one paragraph).</b> Own Micron if you want <b>the memory arm of the AI trade</b> &mdash; a scaled, US-based, net-cash HBM/DRAM maker in a disciplined oligopoly, at a forward multiple (~5.6× forward EPS) that screams &ldquo;the market thinks this is a peak.&rdquo; Fade it if you believe memory always reverts &mdash; that HBM commoditises as three vendors scale, the DRAM cycle glut returns, and today&rsquo;s ~76% EBITDA margin is a top, not a new plateau. The whole report is built around that single fault line: <b>the durability of the through-cycle memory margin.</b></div>

    <div class="note b"><b>How to read the rest of this report.</b> The next modules are the <b>fundamentals block</b> &mdash; the fetched quality dashboard (Q), forensic scores (D), capital allocation (E), peers (G) and positioning (F). Then the report drops into the through-cycle valuation engine (A), the driver analysis (B), scenarios (C), the perfect-execution ceiling (U), kill-criteria (H) and the institutional asymmetry / base-rate layers (I · J). Start with the business and the cycle; then stress-test the price.
      <div class="src">Business description and figures: Micron FY2025 results, the Yahoo TTM fundamentals feed, and HBM/data-center investor commentary. Macro mapping is analytic judgment layered on those sourced business lines.</div>
    </div>
  </section>'''


def module_D():
    return '''<section class="mod" id="mD">
    <div class="mod-head"><div class="mod-no">D</div>
      <div class="ht"><h2>Forensic &amp; earnings-quality scores</h2><div class="hq">Balance-sheet strength and accrual quality — computed from the fetched financials.</div></div>
      <span class="tagchip c">Computed</span>
    </div>
    <div class="verdict bull"><span class="vchip">BULL</span><span class="vtext">The balance sheet is a <b>fortress at the peak</b>: net <b>cash</b> (~$19.6bn), current ratio 3.4×, interest coverage restored to ~20×+, and earnings backed by huge operating cash flow. The one forensic caveat is structural, not accounting: memory earnings quality is <b>cyclical</b> &mdash; the same scorecard would have flashed red in FY2023.</span></div>
    <p class="body">These are the classic solvency and earnings-quality checks, computed from the reported line items. On a cyclical, read them as a <b>through-cycle</b> resilience test &mdash; can the company survive the trough that always comes? &mdash; not as a steady-state quality grade.</p>
    <div class="scores">
      <div class="sc"><div class="scl">Balance sheet <span class="tg s">computed</span></div><div class="scv">Net cash</div><div class="scband good">FORTRESS</div><div class="scd">Cash &amp; ST investments ~$26bn vs total debt ~$6.4bn &rarr; net cash ~<b>$19.6bn</b>. Debt/equity ~0.09. The super-cycle paid down debt and built a cash war-chest &mdash; the trough-survival buffer.</div></div>
      <div class="sc"><div class="scl">Liquidity <span class="tg s">computed</span></div><div class="scv">3.4<span class="un">×</span></div><div class="scband good">STRONG</div><div class="scd">Current ratio 3.4×, quick ratio 2.9×. Even in the FY23 trough, current ratio never fell below ~2.5× &mdash; ample working-capital cushion through the cycle.</div></div>
      <div class="sc"><div class="scl">Coverage <span class="tg s">computed</span></div><div class="scv">~20<span class="un">×+</span></div><div class="scband good">AMPLE</div><div class="scd">EBIT / interest ~20× (FY25) and vastly higher on TTM EBIT. The exception is the tell: FY2023&rsquo;s operating loss broke coverage entirely &mdash; the risk is a deep glot, not leverage.</div></div>
      <div class="sc"><div class="scl">Accrual quality <span class="tg c">computed</span></div><div class="scv">Cash-backed</div><div class="scband good">CLEAN</div><div class="scd">Operating cash flow (~$17.5bn FY25, ~$51bn TTM) runs well above net income &mdash; earnings are cash-backed, not accrual-inflated. Sloan-style accrual risk is low; the capex line, not accruals, is where cash leaks.</div></div>
      <div class="sc"><div class="scl">Inventory <span class="tg c">computed</span></div><div class="scv">Cyclical</div><div class="scband mid">WATCH</div><div class="scd">Inventory ~$8&ndash;9bn; in a glut it swells and gets written down (FY23). At a super-cycle peak, lean, pre-sold HBM inventory is a strength &mdash; but inventory is the first cyclical warning light.</div></div>
      <div class="sc"><div class="scl">Earnings durability <span class="tg c">computed</span></div><div class="scv">Peak</div><div class="scband mid">CYCLICAL</div><div class="scd">TTM ROE ~66% and ~56% net margin are <b>peak-cycle</b> readings. Forensically clean, but not steady-state &mdash; the base-rate module (J) shows today sits at the top of the margin cycle.</div></div>
    </div>
    <div class="note t"><b>Read.</b> On accounting quality Micron is clean and cash-backed, with a genuinely fortress balance sheet built during the up-cycle &mdash; a real <b>bull</b> on solvency and trough-survival. The asterisk is that every one of these gauges is riding the top of the cycle; the honest forensic risk here is not fraud or leverage but <b>mean reversion</b>, which the valuation modules price directly.
      <div class="src">Computed from the fetched FY2022&ndash;FY2025 income statement, balance sheet and cash-flow plus the TTM feed. Cyclical framing is analytic judgment.</div>
    </div>
  </section>'''


def module_E():
    return '''<section class="mod" id="mE">
    <div class="mod-head"><div class="mod-no">E</div>
      <div class="ht"><h2>Capital-allocation record</h2><div class="hq">The facts, not a graded opinion.</div></div>
      <span class="tagchip s">Sourced</span>
    </div>
    <div class="verdict mixed"><span class="vchip">MIXED</span><span class="vtext">Capital allocation in memory is dominated by one line: <b>fab capex</b>. Micron reinvests $8&ndash;$16bn/yr to hold leading-edge DRAM/HBM &mdash; the price of staying in the oligopoly. Returns to shareholders (a small dividend + buybacks) are real but second to the capex treadmill; the discipline that matters most is <b>not over-building into the next glut</b>.</span></div>
    <p class="body">The reference-class question for a memory maker is not &ldquo;how much did they return?&rdquo; but &ldquo;did they invest counter-cyclically and avoid flooding their own market?&rdquo; The record here is the industry&rsquo;s new-found discipline &mdash; capex cut hard into the FY23 trough, ramped for HBM into the up-cycle.</p>
    <div class="bars">
      <div class="br"><div class="brl">Fab &amp; HBM capex<small>the dominant use of cash · $8&ndash;$16bn/yr</small></div><div class="brt"><div class="brf" style="left:0;width:88%;background:var(--blue)"></div></div><div class="brv" style="color:var(--blue-deep)">~$16bn</div></div>
      <div class="br"><div class="brl">R&amp;D<small>leading-edge DRAM / HBM roadmap</small></div><div class="brt"><div class="brf" style="left:0;width:21%;background:var(--teal)"></div></div><div class="brv" style="color:var(--teal-deep)">~$3.8bn</div></div>
      <div class="br"><div class="brl">Buybacks<small>main shareholder return · opportunistic</small></div><div class="brt"><div class="brf" style="left:0;width:14%;background:var(--amber)"></div></div><div class="brv" style="color:var(--amber-deep)">variable</div></div>
      <div class="br"><div class="brl">Dividend<small>small, growing · ~0.1% yield at this price</small></div><div class="brt"><div class="brf" style="left:0;width:4%;background:var(--faint)"></div></div><div class="brv" style="color:var(--muted)">token</div></div>
    </div>
    <p class="body" style="margin-top:16px"><b>The debt round-trip.</b> Micron drew liquidity and let debt/equity rise to ~0.32 through the FY23 trough (prudent &mdash; funding through the bottom), then used super-cycle cash to pay debt down and flip to a <b>net-cash</b> position. That is exactly the counter-cyclical balance-sheet management you want to see; the open question is whether HBM capex now gets over-extended at the top.</p>
    <div class="note a"><b>Read.</b> Disciplined through the last cycle, net-cash today, but this is a <b>capital-intensity</b> story: owner returns are gated by a $10&ndash;$16bn annual capex bill that never stops. The bull needs that capex to build a durable HBM lead; the bear&rsquo;s capital-allocation nightmare is a supply race that turns today&rsquo;s HBM capex into tomorrow&rsquo;s glut. <b>Mixed</b> &mdash; excellent balance-sheet stewardship, structurally capex-hungry.
      <div class="src">Sources: Micron FY2025 cash-flow statement (capex, R&amp;D), the fetched debt/equity history, and HBM capex commentary. Buyback/dividend cadence per company capital-return disclosures.</div>
    </div>
  </section>'''


def module_G():
    return '''<section class="mod" id="mG">
    <div class="mod-head"><div class="mod-no">G</div>
      <div class="ht"><h2>Peer multiples</h2><div class="hq">Micron computed; comparables sourced/approx. The live peer read is in Module I.</div></div>
      <span class="tagchip a">Computed + sourced</span>
    </div>
    <div class="verdict mixed"><span class="vchip">MIXED</span><span class="vtext">On <b>forward</b> earnings Micron looks absurdly cheap (~5.6× forward EPS); on <b>trailing EV/EBITDA</b> (~13.8× on peak EBITDA) it is full. Both are true &mdash; the entire memory group trades at a low multiple of peak earnings because the market prices the revert. The clean, unambiguous comparison is the <b>live 12-month relative return vs SK hynix &amp; Western Digital</b> in Module I.</span></div>
    <p class="body"><b>The memory-multiple paradox.</b> A forward P/E of ~5.6× would be remarkable for almost any other business. For memory it is normal at a cycle peak: the market refuses to capitalise peak earnings, so the multiple compresses precisely when earnings are highest. Read the peer bars as &ldquo;the whole complex is optically cheap on peak numbers,&rdquo; not as a discount to be arbitraged.</p>
    <div class="bars" id="peerbars"></div>
    <p class="body" style="margin-top:16px"><b>Micron&rsquo;s own multiples (computed, live).</b> Trailing P/E ~19×, forward P/E ~5.6×, EV/EBITDA ~13.8×, P/B ~13.2×. The gap between trailing and forward P/E is the market&rsquo;s implied earnings <i>decline</i> &mdash; i.e. it is pricing a roll-over, not extrapolating the super-cycle.</p>
    <div class="note b"><b>Read.</b> Peer multiples don&rsquo;t settle the debate here &mdash; every memory name is cheap on peak earnings and dear on trough earnings. That is why this report leans on the <b>through-cycle engine</b> (Module A) and the <b>base-rate</b> position (Module J) rather than a single peer multiple. The one crisp peer signal &mdash; has Micron out- or under-performed its arch-rival SK hynix over the last year &mdash; is computed live in Module I.
      <div class="src">Micron multiples computed from live price + fetched fundamentals. Peer forward-P/E bars are approximate, sourced context (memory names trade at low-single-digit-to-low-double-digit forward multiples on peak earnings); exact live peer multiples vary by provider, so the peer <i>return</i> comparison is deferred to Module I where the data is unambiguous.</div>
    </div>
  </section>'''


def module_F():
    return '''<section class="mod" id="mF">
    <div class="mod-head"><div class="mod-no">F</div>
      <div class="ht"><h2>Positioning &amp; ownership</h2><div class="hq">Only what's actually fetchable.</div></div>
      <span class="tagchip s">Sourced</span>
    </div>
    <div class="verdict mixed"><span class="vchip">MIXED</span><span class="vtext">The sell-side is <b>emphatically bullish</b> &mdash; a strong-buy consensus, a mean target ~<b>$1,492</b> (~+76% above spot) across 42 analysts. But the same crowding, a beta of ~<b>2.1</b>, and a stock already up ~7× off its low make this a high-momentum, high-reflexivity name where positioning cuts both ways.</span></div>
    <p class="body"><b>What is fetchable.</b> Micron is one of the most heavily-covered, most-owned semis in the market &mdash; broad institutional ownership, deep options liquidity, and index membership (S&amp;P 500, Nasdaq 100, semis ETFs). The clean, sourced positioning signals are the analyst consensus and the price&rsquo;s own factor profile.</p>
    <div class="kg">
      <div class="kgi"><div class="k">Consensus rating</div><div class="v">Strong buy <small>42 analysts</small></div></div>
      <div class="kgi pos"><div class="k">Mean price target</div><div class="v">$1,492 <small>+76% vs spot</small></div></div>
      <div class="kgi"><div class="k">Target range</div><div class="v">$361 – $2,200</div></div>
      <div class="kgi neg"><div class="k">Beta (5y)</div><div class="v">~2.1 <small>high sensitivity</small></div></div>
    </div>
    <p class="body" style="margin-top:16px"><b>The reflexivity caveat.</b> A ~$360-to-$2,200 target range is not consensus &mdash; it is a coin-flip on the cycle dressed up as a mean. When the sell-side is this crowded on a 2.1-beta name that has already 7×&rsquo;d, the marginal buyer is thin and the down-moves are violent (the stock is already ~30% off its 52-week high). Strong sponsorship is a support in an up-tape and an accelerant in a down-tape.</p>
    <div class="note c"><b>Read.</b> Bullish, aligned sell-side and blue-chip index sponsorship &mdash; genuinely supportive &mdash; against extreme dispersion, high beta and a stock that has already made its big move. <b>Mixed</b>: the positioning is a tailwind you cannot lean on, because the same factors that lift it in an AI up-cycle amplify the drawdown when memory sentiment turns.
      <div class="src">Sources: Yahoo Finance consensus (rating, mean/high/low target, 42 analysts) and the fetched 5-year beta; index membership per the universe screener. Insider/short-flow detail excluded (see footer).</div>
    </div>
  </section>'''


def module_A():
    return '''<section class="mod" id="mA">
    <div class="mod-head"><div class="mod-no">A</div>
      <div class="ht"><h2>Valuation engine — correlated &amp; fat-tailed</h2><div class="hq">Through-cycle EBITDA margin × EV/EBITDA multiple, plus net cash.</div></div>
      <span class="tagchip c">Computed</span>
    </div>
    <div class="verdict mixed"><span class="vchip">MIXED</span><span class="vtext">Base-case median ≈ <b>$830</b> vs the ~$849 price &mdash; essentially fair (~46% of paths above price), with an enormous cyclical band (P10 ~$560, P90 ~$1,170). No edge at spot; the entire value lives in the <b>through-cycle margin</b> and the <b>multiple</b> knobs.</span></div>
    <p class="body">20,000 paths. Fair value per share = <b>EV/EBITDA multiple × (revenue × EBITDA margin) + net cash</b>, ÷ 1,129.4m shares. Because memory is too cyclical to capitalise on spot earnings, every marginal is a <b>through-cycle</b> range spanning trough to peak: the EBITDA margin runs 44&ndash;80% (FY23 trough ~16%, TTM peak ~76%), the multiple 8.5&ndash;20× (the market caps memory), revenue $72&ndash;$138bn, net cash $8&ndash;$34bn.</p>
    <p class="body" style="font-size:12.5px;color:var(--muted)"><span class="asm">Your assumptions ↓</span> &nbsp;The through-cycle EBITDA margin (does the HBM-era ~62% hold, or does memory revert toward ~45%?) and the central multiple (does the market ever pay up for shallower cycles?) are <b>your</b> calls. Correlation and tail control how hard the drivers fall together in a glut.</p>
    <div class="mc-wrap">
      <div class="mc-title">◆ Correlated Monte-Carlo — 20,000 paths, live</div>
      <div class="mc-sub">Fixed inputs (sourced): 1,129.4m shares, price $848.95 (live, 2026-07-19); revenue and net-cash marginals centred on the TTM/through-cycle base ($100bn / $20bn net cash).</div>
      <div class="controls">
        <div class="ctrl">
          <label><span class="lab">Through-cycle EBITDA margin <span>% · assumption</span></span><span class="cval"><span id="v-mgn">62</span>%</span></label>
          <input type="range" id="i-mgn" min="44" max="80" step="0.5" value="62">
          <div class="tri">FY23 trough ~16% · FY25 ~49% · TTM peak ~76% · mode 62%</div>
        </div>
        <div class="ctrl">
          <label><span class="lab">Central EV/EBITDA multiple <span>× · assumption</span></span><span class="cval"><span id="v-mlt">15.0</span>×</span></label>
          <input type="range" id="i-mlt" min="8.5" max="20" step="0.1" value="15.0">
          <div class="tri">now ~13.8× on peak EBITDA · memory stays multiple-capped · re-rate = bull</div>
        </div>
        <div class="ctrl">
          <label><span class="lab">Driver correlation <span>assumption</span></span><span class="cval"><span id="v-corr">60</span>%</span></label>
          <input type="range" id="i-corr" min="0" max="100" step="5" value="60">
          <div class="tri">0% = independent · 100% = full co-movement (a real glut)</div>
        </div>
        <div class="ctrl">
          <label><span class="lab">Tail / glut-shock risk <span>assumption</span></span><span class="cval"><span id="v-tail">6</span>%</span></label>
          <input type="range" id="i-tail" min="0" max="15" step="1" value="6">
          <div class="tri">chance a path hits a correlated memory downturn</div>
        </div>
      </div>
      <div class="cmp">
        <div class="cmpcard">
          <div class="ct"><span class="dd" style="background:var(--faint)"></span>Independent drivers</div>
          <div class="cmprow"><span class="ck">Median fair value</span><span class="cv" id="oi-med">$830</span></div>
          <div class="cmprow"><span class="ck">P10 (downside)</span><span class="cv" id="oi-p10">$590</span></div>
          <div class="cmprow"><span class="ck">P90 (upside)</span><span class="cv" id="oi-p90">$1110</span></div>
          <div class="cmprow"><span class="ck">P(deep loss, &lt; $450)</span><span class="cv" id="oi-tail">1%</span></div>
        </div>
        <div class="cmpcard hot">
          <div class="ct"><span class="dd" style="background:var(--coral)"></span>Correlated + fat tails</div>
          <div class="cmprow"><span class="ck">Median fair value</span><span class="cv warn" id="co-med">$830</span></div>
          <div class="cmprow"><span class="ck">P10 (downside)</span><span class="cv neg" id="co-p10">$560</span></div>
          <div class="cmprow"><span class="ck">P90 (upside)</span><span class="cv pos" id="co-p90">$1170</span></div>
          <div class="cmprow"><span class="ck">P(deep loss, &lt; $450)</span><span class="cv neg" id="co-tail">2%</span></div>
        </div>
      </div>
      <div class="hist-wrap">
        <div class="hist-leg">
          <span><span class="sw" style="background:var(--coral);opacity:.55"></span>worth &lt; $848.95</span>
          <span><span class="sw" style="background:var(--teal);opacity:.6"></span>worth &gt; $848.95</span>
          <span><span class="sw" style="background:var(--ink)"></span>price</span>
          <span><span class="sw" style="background:var(--amber)"></span>median</span>
          <span><span class="sw" style="background:var(--faint)"></span>indep P10</span>
        </div>
        <svg id="hist" viewBox="0 0 700 235" preserveAspectRatio="xMidYMid meet" style="width:100%;height:auto"></svg>
      </div>
      <div class="reading" id="reading"></div>
    </div>
    <div class="note c"><b>Why this matters.</b> Correlation barely moves the median but fattens the downside dramatically &mdash; exactly right for memory, where margin, volume and multiple all collapse together in a glut. The independent model radically understates how bad a real cycle turn is. The base case is <i>fair</i>; the trade is a bet on which knob &mdash; margin durability up, or mean-reversion down &mdash; wins.</div>
  </section>'''


def module_B():
    return '''<section class="mod" id="mB">
    <div class="mod-head"><div class="mod-no">B</div>
      <div class="ht"><h2>Driver analysis — what moves the stock</h2><div class="hq">The question this dashboard was built around.</div></div>
      <span class="tagchip a">Computed + sourced</span>
    </div>
    <div class="verdict mixed"><span class="vchip">MIXED</span><span class="vtext">One swing factor dominates: the <b>through-cycle EBITDA margin</b> &mdash; a proxy for &ldquo;is the HBM/DRAM pricing step-change durable?&rdquo; It governs the tornado, the scenarios and the reverse-DCF alike. A diagnostic, not a direction: near-total dependence on a single, genuinely uncertain variable.</span></div>
    <p class="body"><b>Lens 1 — fair-value sensitivity (computed tornado).</b> Each bar swings one driver P10→P90, others held at mode. The <b>EV/EBITDA multiple</b> is the widest lever, with <b>revenue</b> and the <b>EBITDA margin</b> close behind — all three first-order (memory is a price × volume business, and margin and multiple both key off the cycle); net cash is second-order on a $959bn market cap.</p>
    <svg id="tornado" viewBox="0 0 700 200" preserveAspectRatio="xMidYMid meet" style="width:100%;height:auto"></svg>
    <p class="body" style="margin-top:18px"><b>Lens 2 — what actually moves the price (sourced).</b> Micron trades tick-for-tick with the <b>AI-memory narrative</b>: HBM pricing/allocation headlines, hyperscaler capex guides, and read-throughs from Nvidia and SK hynix. The revealed driver is the market&rsquo;s assessment of <i>how long</i> the HBM shortage and DRAM discipline last.</p>
    <div class="reactab">
      <div class="rr"><div class="re">HBM sold out</div><div class="rd">Each confirmation that HBM3E/HBM4 capacity is pre-booked and margin-accretive re-rates the whole complex &mdash; the single most powerful up-driver.</div><div class="rp" style="color:var(--teal-deep)">▲ bull</div></div>
      <div class="rr"><div class="re">Hyperscaler capex</div><div class="rd">AI-datacenter capex guides from the cloud majors set memory-content expectations; an up-guide is a direct volume + mix tailwind.</div><div class="rp" style="color:var(--teal-deep)">▲ bull</div></div>
      <div class="rr"><div class="re">Supply adds</div><div class="rd">Samsung/SK hynix HBM &amp; DRAM capacity announcements are the classic memory bear signal &mdash; the market instantly prices the next glut.</div><div class="rp">▼ bear</div></div>
    </div>
    <p class="body" style="margin-top:18px"><b>Lens 3 — the structural driver (sourced).</b> Underneath the headlines, the value is set by <b>industry supply discipline</b>. A rational three-firm DRAM oligopoly that adds capacity in line with demand keeps margins structurally higher; a share war collapses them. HBM&rsquo;s technical difficulty (yield, packaging) is currently the discipline&rsquo;s enforcer.</p>
    <div class="note b"><b>Synthesis — the master gauge is the through-cycle memory margin.</b> The tornado says margin + multiple are the biggest fair-value levers (Lens 1); the tape moves on HBM/AI-demand signals (Lens 2); and the structural driver is oligopoly supply discipline (Lens 3). They converge because <b>all three are the same question</b>: does memory pricing power persist above its historical through-cycle level? Unlike Konecranes&rsquo; order book or Neste&rsquo;s crack spread, Micron&rsquo;s master variable is the <b>durability of the HBM-era margin</b> &mdash; and the reverse-DCF (Module I) shows the market is implying it holds near ~62.5%.
      <div class="src">Sources: Micron HBM/data-center commentary; AI-capex read-throughs (Nvidia is the fetched demand-factor in Module I); memory-oligopoly structure. Tornado computed from the engine.</div>
    </div>
  </section>'''


def module_C():
    return '''<section class="mod" id="mC">
    <div class="mod-head"><div class="mod-no">C</div>
      <div class="ht"><h2>Scenario probabilities + Bayesian updating</h2><div class="hq">Computed anchors; your odds.</div></div>
      <span class="tagchip a">Computed + your assumptions</span>
    </div>
    <div class="verdict mixed"><span class="vchip">MIXED</span><span class="vtext">The scenario spread is <b>enormous</b> &mdash; a memory glut (~$280) to an AI-memory secular win (~$1,500, near the $1,492 consensus). At neutral priors the weighted value sits near the price. This is a <b>wide two-sided bet on the cycle</b>, not a tight fair-value call.</span></div>
    <p class="body">The three fair values are <b>computed</b> &mdash; each is the engine&rsquo;s median run at a paired revenue / margin / multiple setting for that regime. The prior weights and evidence likelihood-ratios are <b>your</b> subjective inputs.</p>
    <div class="scen">
      <div class="scard bear"><div class="sn">Bear — memory reverts</div><div class="sd">A classic glut: Samsung/SK hynix add HBM &amp; DRAM supply, pricing rolls, the through-cycle margin falls toward ~44% and the multiple de-rates to ~9× on cyclical fear.</div><div class="sfv" id="sfv-bear">$280</div><div class="sfvl">engine median · computed</div></div>
      <div class="scard base"><div class="sn">Base — super-cycle plateaus</div><div class="sd">HBM keeps the through-cycle margin elevated (~62%) on ~$100bn revenue; the market pays ~15× on peak-ish EBITDA. Roughly today&rsquo;s reality, sustained a while.</div><div class="sfv" id="sfv-base">$830</div><div class="sfvl">engine median · computed</div></div>
      <div class="scard bull"><div class="sn">Bull — AI-memory secular win</div><div class="sd">HBM scarcity persists, content-per-server compounds, revenue ~$130bn at ~72% margin, and the market re-rates memory to ~18× as cycles visibly shallow. Near consensus.</div><div class="sfv" id="sfv-bull">$1500</div><div class="sfvl">engine median · computed</div></div>
    </div>
    <div class="controls" style="grid-template-columns:1fr 1fr 1fr">
      <div class="ctrl"><label><span class="lab">Prior — Bear <span>assumption</span></span><span class="cval"><span id="v-pb">30</span>%</span></label><input type="range" id="i-pb" min="0" max="100" step="5" value="30"></div>
      <div class="ctrl"><label><span class="lab">Prior — Base <span>assumption</span></span><span class="cval"><span id="v-pn">45</span>%</span></label><input type="range" id="i-pn" min="0" max="100" step="5" value="45"></div>
      <div class="ctrl"><label><span class="lab">Prior — Bull <span>assumption</span></span><span class="cval"><span id="v-pu">25</span>%</span></label><input type="range" id="i-pu" min="0" max="100" step="5" value="25"></div>
    </div>
    <div style="font-family:var(--mono);font-size:10.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--faint);margin:16px 0 8px">Toggle evidence as it arrives → <span class="asm">(likelihood ratios are illustrative assumptions)</span></div>
    <div class="evid" id="evid">
      <div class="ev" data-lr="0.4,1.0,2.0">HBM4 pre-booked &amp; margin-accretive <span class="ar">▲bull</span></div>
      <div class="ev" data-lr="0.5,1.1,1.7">Hyperscaler AI capex guides up <span class="ar">▲bull</span></div>
      <div class="ev" data-lr="0.6,1.1,1.5">DRAM supply stays disciplined <span class="ar">▲bull</span></div>
      <div class="ev bearish" data-lr="2.2,1.0,0.4">Competitors flood HBM/DRAM supply <span class="ar">▼bear</span></div>
      <div class="ev bearish" data-lr="2.0,1.0,0.5">DRAM spot pricing rolls over <span class="ar">▼bear</span></div>
      <div class="ev bearish" data-lr="1.8,1.0,0.6">AI-capex digestion / air-pocket <span class="ar">▼bear</span></div>
    </div>
    <div style="margin-top:16px">
      <div style="font-family:var(--mono);font-size:10px;color:var(--faint);text-transform:uppercase;letter-spacing:.05em;margin-bottom:5px">Posterior weights</div>
      <div class="wbar" id="wbar"><div class="wp bear" id="wp-b"></div><div class="wp base" id="wp-n"></div><div class="wp bull" id="wp-u"></div></div>
      <div class="wlab"><span id="wl-b">Bear 30%</span><span id="wl-n">Base 45%</span><span id="wl-u">Bull 25%</span></div>
    </div>
    <div class="blend">
      <span class="bn" id="blend-fv">$830</span>
      <span class="bl">probability-weighted fair value vs <b>$848.95</b> price · <span id="blend-gap">≈ fair</span>. Anchors computed; weighting is your judgment.</span>
    </div>
  </section>'''


def module_H():
    return '''<section class="mod" id="mH">
    <div class="mod-head"><div class="mod-no">H</div>
      <div class="ht"><h2>Kill-criteria &amp; decision journal</h2><div class="hq">Pre-committed exits — the discipline layer.</div></div>
      <span class="tagchip a">Your pre-commitments</span>
    </div>
    <div class="verdict mixed"><span class="vchip">MIXED</span><span class="vtext">A process overlay, not a direction. Every trigger centres on the master variable &mdash; memory pricing / margin durability &mdash; so the thesis fails fast the moment the cycle signals a turn.</span></div>
    <p class="body">Decision <i>rules</i>, not data &mdash; thresholds set now, while disinterested. Memory rewards those who sell into euphoria and buy into the glut; these triggers are designed to enforce that against your own future emotions.</p>
    <div class="kc">
      <div class="kci"><div class="kx"></div><div><b>DRAM pricing rolls over.</b> Contract/spot DRAM prices fall for <span class="kv">two consecutive quarters</span> &mdash; the leading domino of every memory down-cycle.</div></div>
      <div class="kci"><div class="kx"></div><div><b>HBM premium compresses.</b> HBM moves from <span class="kv">sold-out to available</span>, or a competitor takes material share at the lead customer &mdash; the secular premium is eroding.</div></div>
      <div class="kci"><div class="kx"></div><div><b>Gross margin gives back the step-change.</b> Company gross margin falls <span class="kv">below ~45% and is still declining</span> &mdash; the through-cycle margin thesis is failing.</div></div>
      <div class="kci"><div class="kx"></div><div><b>Supply discipline breaks.</b> Samsung or SK hynix announce a <span class="kv">large capacity/HBM expansion</span> into softening demand &mdash; the oligopoly is turning into a share war.</div></div>
      <div class="kci"><div class="kx"></div><div><b>Inventory swells.</b> Days-of-inventory <span class="kv">rise sharply for two quarters</span> as bookings slow &mdash; the classic pre-glut warning light.</div></div>
      <div class="kci"><div class="kx"></div><div><b>Valuation overshoots.</b> Price implies <span class="kv">a through-cycle EBITDA margin &gt; ~75%</span> on the reverse-DCF (Module I) &mdash; the market is capitalising the peak as permanent; trim, don&rsquo;t chase.</div></div>
    </div>
    <div class="note c"><b>Decision-journal prompt (falsifiable, dated):</b> log today&rsquo;s call &mdash; e.g. &ldquo;through-cycle EBITDA margin ~62% holds on HBM discipline, fair value ~$830, secular-win optionality to ~$1,500&rdquo; &mdash; and the specific DRAM-pricing, HBM-allocation and competitor-capex prints over the next two quarters that would confirm or refute it. If a kill-criterion fires in a cyclical, act first and re-litigate later.</div>
  </section>'''


def scorecard():
    return '''<section class="mod" id="mSum">
    <div class="mod-head"><div class="mod-no" style="color:var(--amber-deep)">∑</div>
      <div class="ht"><h2>Scorecard — the thirteen reads</h2><div class="hq">Each verdict follows from that module's own data, struck at the base case.</div></div>
    </div>
    <div class="tbl-scroll"><table class="scoretab">
      <thead><tr><th>Module</th><th>Verdict</th><th>What drives it</th></tr></thead>
      <tbody>
        <tr><td>T · Thesis &amp; macro</td><td><span class="vchip bull">BULL</span></td><td>The most direct AI beneficiary in the book — HBM/DRAM oligopolist — still trading as a hardware cyclical</td></tr>
        <tr><td>Q · Quality dashboard</td><td><span class="vchip mixed">MIXED</span></td><td>Exceptional TTM returns (~66% ROE, ~76% EBITDA margin) but a negative-margin FY23 trough in the same window</td></tr>
        <tr><td>D · Forensics</td><td><span class="vchip bull">BULL</span></td><td>Net cash ~$19.6bn, 3.4× current ratio, cash-backed earnings — a fortress at the peak</td></tr>
        <tr><td>E · Capital record</td><td><span class="vchip mixed">MIXED</span></td><td>Counter-cyclical balance-sheet stewardship, but structurally capex-hungry ($8–$16bn/yr)</td></tr>
        <tr><td>G · Peers</td><td><span class="vchip mixed">MIXED</span></td><td>Cheap on forward EPS, full on peak EV/EBITDA — the whole memory group prices the revert</td></tr>
        <tr><td>F · Positioning</td><td><span class="vchip mixed">MIXED</span></td><td>Strong-buy consensus (+76% mean PT) vs 2.1 beta and a stock already up ~7×</td></tr>
        <tr><td>A · Engine</td><td><span class="vchip mixed">MIXED</span></td><td>Median ~$830 vs ~$849; roughly fair, enormous cyclical band (P10 ~$560 / P90 ~$1,170)</td></tr>
        <tr><td>B · Driver analysis</td><td><span class="vchip mixed">MIXED</span></td><td>Whole thesis rides one swing factor — durability of the HBM-era through-cycle margin</td></tr>
        <tr><td>C · Scenarios + Bayes</td><td><span class="vchip mixed">MIXED</span></td><td>Huge two-sided spread ~$280 (glut) to ~$1,500 (secular win); weighted ≈ fair</td></tr>
        <tr><td>H · Kill-criteria</td><td><span class="vchip mixed">MIXED</span></td><td>Process overlay; every trigger centres on memory pricing / margin durability</td></tr>
      </tbody>
    </table></div>
    <div class="tally">
      <div class="tbar"><div class="tp bull" style="width:23.1%"></div><div class="tp mixed" style="width:76.9%"></div><div class="tp bear" style="width:0.0%"></div></div>
      <div class="tlab"><span class="tb">3 Bull</span><span class="tm">10 Mixed</span><span class="tr">0 Bear</span></div>
    </div>
    <div class="overall">
      <span class="ov-chip">NET: MIXED — the AI-memory bet, fairly priced</span>
      <div class="ov-text">A genuinely strong <b>thesis</b> (T · direct AI beneficiary, D · fortress balance sheet) wrapped around a <b>fairly-priced, hyper-cyclical</b> valuation. Read the <b>thesis &amp; cycle first</b> (T · Q · D · E · G · F), then stress-test with the through-cycle engine (A–C): the base case (~$830) sits right around the ~$849 price, but the scenario band is vast (~$280 glut to ~$1,500 secular win). The whole call reduces to <b>one variable</b> — the durability of the HBM-era through-cycle margin, which the reverse-DCF (Module I) says the market is pricing near ~62.5%. Size it as the <b>wide, two-sided cycle bet it is</b>, with the Module-H triggers pre-committed; the perfect-execution ceiling (Module U) frames the upside if the oligopoly and HBM discipline hold.</div>
    </div>
  </section>'''


def footer():
    return '''<footer>
    <div class="notes">
      <h4>How the engine computes (Module A)</h4>
      <p>20,000 paths. Each driver is drawn from a triangular distribution: through-cycle EBITDA margin (bounds 44–80%, your mode), EV/EBITDA multiple (bounds 8.5–20×, your mode), revenue Tri($72, $100, $138 bn), net cash Tri($8, $20, $34 bn). Fair value = multiple × (revenue × EBITDA margin) + net cash, ÷ 1,129.4m shares. Dependence: a one-factor copula (loadings — margin 0.80, revenue 0.75, multiple 0.55, net cash 0.25, scaled by your correlation knob) plus a regime-shock mixture (your tail knob sets the glut probability). Correlation 0 and tail 0 reproduce the independent model. Tornado, scenario anchors and the Bayesian posterior are all computed live and mirror the Python engine in <code>stocks/config_micron.py</code>.</p>
      <h4>The three labels, precisely</h4>
      <p><span style="color:var(--teal-deep)"><b>Sourced</b></span>: fetched from a citable source (Micron FY releases, the Yahoo fundamentals feed, sell-side consensus). <span style="color:var(--blue-deep)"><b>Computed</b></span>: calculated here from sourced inputs (the simulation, forensic ratios, Micron&rsquo;s own multiples). <span style="color:var(--amber-deep)"><b>Your assumption</b></span>: an input you set (through-cycle margin, central multiple, correlation, tail, scenario priors, evidence weights, kill thresholds).</p>
      <h4>What was cut, not faked</h4>
      <div class="cut"></div>
      <p class="disc">For analysis and education only — not investment advice, not a recommendation, not a price target. The model quantifies the uncertainty in a set of assumptions; it does not make those assumptions correct. Live spot &amp; factor exposures are fetched at build time; annual figures are Micron&rsquo;s reported FY2022–FY2025, and the FY2026 super-cycle figures are the trailing-twelve-month values from the Yahoo fundamentals feed as of build — verify against Micron&rsquo;s SEC filings before acting.</p>
    </div>
  </footer>'''


# ------------------------------------------------------------------ Module A JS
# Mirrors stocks/config_micron.py's engine exactly: fv = (mult×(rev×mgn/100)+nc)/shares.
ENGINE_JS = '''<script>
  const PRICE=848.95, SHARES=1129.4, N=20000;
  const MARG={lo:44,hi:80}, MULT={lo:8.5,hi:20.0}, SALES={lo:72000,md:100000,hi:138000}, NC={lo:8000,md:20000,hi:34000};
  const RHO={mgn:0.80,sales:0.75,mlt:0.55,nc:0.25};

  function randn(){let u=0,v=0;while(u===0)u=Math.random();while(v===0)v=Math.random();return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v);}
  function Phi(x){const t=1/(1+0.2316419*Math.abs(x));const d=0.3989423*Math.exp(-x*x/2);let p=d*t*(0.3193815+t*(-0.3565638+t*(1.781478+t*(-1.821256+t*1.330274))));return x>0?1-p:p;}
  function triInv(u,a,m,b){const c=(m-a)/(b-a);return u<c?a+Math.sqrt(u*(b-a)*(m-a)):b-Math.sqrt((1-u)*(b-a)*(b-m));}

  function simulate(midMgn,midMlt,corr,pStress,paths){
    const n=paths||N;const fv=new Float64Array(n);
    for(let i=0;i<n;i++){
      let Z=randn();
      if(pStress>0 && Math.random()<pStress) Z=Z*2.0-0.4;
      const draw=(rho,a,m,b)=>{const L=corr*rho;const e=randn();const nn=L*Z+Math.sqrt(Math.max(0,1-L*L))*e;return triInv(Phi(nn),a,m,b);};
      const mgn=draw(RHO.mgn,MARG.lo,midMgn,MARG.hi);
      const sal=draw(RHO.sales,SALES.lo,SALES.md,SALES.hi);
      const mlt=draw(RHO.mlt,MULT.lo,midMlt,MULT.hi);
      const nc=draw(RHO.nc,NC.lo,NC.md,NC.hi);
      fv[i]=(mlt*(sal*mgn/100)+nc)/SHARES;
    }
    fv.sort();
    const q=x=>fv[Math.min(n-1,Math.floor(x*n))];
    let under=0,deep=0;const thr=450;
    for(let i=0;i<n;i++){if(fv[i]>PRICE)under++;if(fv[i]<thr)deep++;}
    return {fv,p10:q(.10),p50:q(.50),p90:q(.90),under:under/n,deep:deep/n};
  }

  const HX0=12,HX1=688,HY0=8,HY1=188,VMAX=2000,BINS=40;
  function xOf(v){return HX0+(Math.min(Math.max(v,0),VMAX)/VMAX)*(HX1-HX0);}
  function drawHist(fv,median,indP10){
    const bw=VMAX/BINS,counts=new Array(BINS).fill(0);
    for(let i=0;i<fv.length;i++){let b=Math.floor(fv[i]/bw);if(b<0)b=0;if(b>=BINS)b=BINS-1;counts[b]++;}
    const maxC=Math.max(...counts);let s='';
    for(let b=0;b<BINS;b++){const vc=(b+0.5)*bw,x=xOf(b*bw),x2=xOf((b+1)*bw),w=Math.max(1,x2-x-1.4);
      const h=maxC?(counts[b]/maxC)*(HY1-HY0):0,y=HY1-h;const fill=vc<PRICE?'var(--coral)':'var(--teal)',op=vc<PRICE?0.55:0.6;
      s+='<rect x="'+x.toFixed(1)+'" y="'+y.toFixed(1)+'" width="'+w.toFixed(1)+'" height="'+h.toFixed(1)+'" fill="'+fill+'" opacity="'+op+'" rx="1.5"/>';}
    s+='<line x1="'+HX0+'" y1="'+HY1+'" x2="'+HX1+'" y2="'+HY1+'" stroke="var(--line-strong)" stroke-width="1"/>';
    for(let v=0;v<=2000;v+=400){const x=xOf(v);s+='<line x1="'+x+'" y1="'+HY1+'" x2="'+x+'" y2="'+(HY1+4)+'" stroke="var(--line-strong)" stroke-width="1"/>';
      s+='<text x="'+x+'" y="'+(HY1+17)+'" text-anchor="middle" font-family="var(--mono)" font-size="10" fill="var(--muted)">$'+v+'</text>';}
    const xi=xOf(indP10);
    s+='<line x1="'+xi+'" y1="'+(HY0+20)+'" x2="'+xi+'" y2="'+HY1+'" stroke="var(--faint)" stroke-width="1.5" stroke-dasharray="2 3"/>';
    s+='<text x="'+xi+'" y="'+(HY0+15)+'" text-anchor="middle" font-family="var(--mono)" font-size="9" fill="var(--faint)">indep P10</text>';
    const xm=xOf(median);
    s+='<line x1="'+xm+'" y1="'+(HY0-2)+'" x2="'+xm+'" y2="'+HY1+'" stroke="var(--amber)" stroke-width="2" stroke-dasharray="3 3"/>';
    s+='<text x="'+xm+'" y="'+(HY0+8)+'" text-anchor="middle" font-family="var(--mono)" font-size="10" font-weight="600" fill="var(--amber-deep)">median $'+median.toFixed(0)+'</text>';
    const xp=xOf(PRICE);
    s+='<line x1="'+xp+'" y1="'+(HY0-2)+'" x2="'+xp+'" y2="'+HY1+'" stroke="var(--ink)" stroke-width="2"/>';
    s+='<text x="'+xp+'" y="'+(HY1+30)+'" text-anchor="middle" font-family="var(--mono)" font-size="10.5" font-weight="600" fill="var(--ink)">price $848.95</text>';
    document.getElementById('hist').innerHTML=s;
  }

  function fvAt(o){
    const midMgn=+document.getElementById('i-mgn').value, midMlt=+document.getElementById('i-mlt').value;
    const mgn=o.mgn!==undefined?o.mgn:midMgn;
    const mlt=o.mlt!==undefined?o.mlt:midMlt;
    const sal=o.sal!==undefined?o.sal:SALES.md;
    const nc=o.nc!==undefined?o.nc:NC.md;
    return (mlt*(sal*mgn/100)+nc)/SHARES;
  }
  function drawTornado(){
    const rows=[
      {n:'EBITDA margin',lo:fvAt({mgn:44}),hi:fvAt({mgn:80})},
      {n:'EV/EBITDA multiple',lo:fvAt({mlt:8.5}),hi:fvAt({mlt:20})},
      {n:'Revenue',lo:fvAt({sal:72000}),hi:fvAt({sal:138000})},
      {n:'Net cash',lo:fvAt({nc:8000}),hi:fvAt({nc:34000})},
    ];
    rows.forEach(r=>{r.w=Math.abs(r.hi-r.lo);r.min=Math.min(r.lo,r.hi);r.max=Math.max(r.lo,r.hi);});
    rows.sort((a,b)=>b.w-a.w);
    const allMin=Math.min(...rows.map(r=>r.min)),allMax=Math.max(...rows.map(r=>r.max));
    const X0=150,X1=688,W=X1-X0,base=allMin-40,span=(allMax+40)-base;
    const sx=v=>X0+((v-base)/span)*W;
    const rowH=38,top=10;let s='';
    rows.forEach((r,i)=>{const y=top+i*rowH;
      s+='<text x="'+(X0-10)+'" y="'+(y+rowH/2+4)+'" text-anchor="end" font-family="var(--body)" font-size="12" fill="var(--ink)">'+r.n+'</text>';
      s+='<rect x="'+sx(r.min).toFixed(1)+'" y="'+(y+6)+'" width="'+(sx(r.max)-sx(r.min)).toFixed(1)+'" height="'+(rowH-16)+'" rx="4" fill="'+(i===0?'var(--coral)':'var(--teal)')+'" opacity="'+(i===0?0.7:0.45)+'"/>';
      s+='<text x="'+(sx(r.min)-5).toFixed(1)+'" y="'+(y+rowH/2+4)+'" text-anchor="end" font-family="var(--mono)" font-size="10" fill="var(--muted)">$'+Math.min(r.lo,r.hi).toFixed(0)+'</text>';
      s+='<text x="'+(sx(r.max)+5).toFixed(1)+'" y="'+(y+rowH/2+4)+'" font-family="var(--mono)" font-size="10" fill="var(--muted)">$'+Math.max(r.lo,r.hi).toFixed(0)+'</text>';});
    const yb=top+rows.length*rowH;
    s+='<line x1="'+sx(PRICE).toFixed(1)+'" y1="'+top+'" x2="'+sx(PRICE).toFixed(1)+'" y2="'+yb+'" stroke="var(--ink)" stroke-width="1.5"/>';
    s+='<text x="'+sx(PRICE).toFixed(1)+'" y="'+(yb+15)+'" text-anchor="middle" font-family="var(--mono)" font-size="10" font-weight="600" fill="var(--ink)">price $848.95</text>';
    document.getElementById('tornado').setAttribute('viewBox','0 0 700 '+(yb+26));
    document.getElementById('tornado').innerHTML=s;
  }

  function update(){
    const midMgn=+document.getElementById('i-mgn').value, midMlt=+document.getElementById('i-mlt').value;
    const corr=(+document.getElementById('i-corr').value)/100, tail=(+document.getElementById('i-tail').value)/100;
    document.getElementById('v-mgn').textContent=midMgn.toFixed(0);
    document.getElementById('v-mlt').textContent=midMlt.toFixed(1);
    document.getElementById('v-corr').textContent=Math.round(corr*100);
    document.getElementById('v-tail').textContent=Math.round(tail*100);
    const ind=simulate(midMgn,midMlt,0,0);
    const cor=simulate(midMgn,midMlt,corr,tail);
    document.getElementById('oi-med').textContent='$'+ind.p50.toFixed(0);
    document.getElementById('oi-p10').textContent='$'+ind.p10.toFixed(0);
    document.getElementById('oi-p90').textContent='$'+ind.p90.toFixed(0);
    document.getElementById('oi-tail').textContent=Math.round(ind.deep*100)+'%';
    document.getElementById('co-med').textContent='$'+cor.p50.toFixed(0);
    document.getElementById('co-p10').textContent='$'+cor.p10.toFixed(0);
    document.getElementById('co-p90').textContent='$'+cor.p90.toFixed(0);
    document.getElementById('co-tail').textContent=Math.round(cor.deep*100)+'%';
    drawHist(cor.fv,cor.p50,ind.p10);
    const widen=(cor.p90-cor.p10)-(ind.p90-ind.p10);
    document.getElementById('reading').innerHTML='With correlation at <b>'+Math.round(corr*100)+'%</b> and a <b>'+Math.round(tail*100)+'%</b> glut chance, the median holds near <b>$'+cor.p50.toFixed(0)+'</b> (≈ the independent $'+ind.p50.toFixed(0)+'), but the 80% band widens by ~<span class="down">$'+widen.toFixed(0)+'</span> and the chance of a deep-downside outcome (worth under $450) rises from <b>'+Math.round(ind.deep*100)+'%</b> to <span class="down">'+Math.round(cor.deep*100)+'%</span>. P(undervalued at $848.95) is '+Math.round(cor.under*100)+'%.';
    drawTornado();
  }

  function simScen(rLo,rMd,rHi,mLo,mMd,mHi,kLo,kMd,kHi,paths){
    const n=paths||10000;const fv=new Float64Array(n);
    for(let i=0;i<n;i++){
      let Z=randn(); if(Math.random()<0.06) Z=Z*2.0-0.4;
      const draw=(rho,a,m,b)=>{const L=0.6*rho;const e=randn();const nn=L*Z+Math.sqrt(Math.max(0,1-L*L))*e;return triInv(Phi(nn),a,m,b);};
      const rev=draw(RHO.sales,rLo,rMd,rHi);
      const mgn=draw(RHO.mgn,mLo,mMd,mHi);
      const mlt=draw(RHO.mlt,kLo,kMd,kHi);
      const nc=draw(RHO.nc,NC.lo,NC.md,NC.hi);
      fv[i]=(mlt*(rev*mgn/100)+nc)/SHARES;
    }
    fv.sort();return fv[Math.floor(0.5*n)];
  }
  let SFV={bear:280,base:830,bull:1500};
  function computeScenarioAnchors(){
    SFV.bear=simScen(60000,78000,95000, 34,44,54, 7.0,9.0,11.0);
    SFV.base=simScen(85000,100000,118000, 52,62,70, 12.5,15.0,17.0);
    SFV.bull=simScen(110000,130000,150000, 64,72,80, 15.5,18.0,20.0);
    document.getElementById('sfv-bear').textContent='$'+SFV.bear.toFixed(0);
    document.getElementById('sfv-base').textContent='$'+SFV.base.toFixed(0);
    document.getElementById('sfv-bull').textContent='$'+SFV.bull.toFixed(0);
    updateBayes();
  }
  function updateBayes(){
    let pb=+document.getElementById('i-pb').value, pn=+document.getElementById('i-pn').value, pu=+document.getElementById('i-pu').value;
    document.getElementById('v-pb').textContent=pb; document.getElementById('v-pn').textContent=pn; document.getElementById('v-pu').textContent=pu;
    let sum=pb+pn+pu; if(sum===0){pb=pn=pu=1;sum=3;}
    let wb=pb/sum, wn=pn/sum, wu=pu/sum;
    document.querySelectorAll('#evid .ev.on').forEach(el=>{const lr=el.getAttribute('data-lr').split(',').map(Number);wb*=lr[0];wn*=lr[1];wu*=lr[2];});
    const z=wb+wn+wu; wb/=z; wn/=z; wu/=z;
    document.getElementById('wp-b').style.width=(wb*100)+'%';
    document.getElementById('wp-n').style.width=(wn*100)+'%';
    document.getElementById('wp-u').style.width=(wu*100)+'%';
    document.getElementById('wl-b').textContent='Bear '+Math.round(wb*100)+'%';
    document.getElementById('wl-n').textContent='Base '+Math.round(wn*100)+'%';
    document.getElementById('wl-u').textContent='Bull '+Math.round(wu*100)+'%';
    const fv=wb*SFV.bear+wn*SFV.base+wu*SFV.bull;
    document.getElementById('blend-fv').textContent='$'+fv.toFixed(0);
    const gap=(fv/PRICE-1)*100;
    document.getElementById('blend-gap').textContent=(Math.abs(gap)<1.5?'≈ fair vs price':(gap<0?'≈ '+Math.abs(gap).toFixed(0)+'% below':'≈ '+gap.toFixed(0)+'% above'));
  }
  document.querySelectorAll('#evid .ev').forEach(el=>el.addEventListener('click',()=>{el.classList.toggle('on');updateBayes();}));
  ['i-pb','i-pn','i-pu'].forEach(id=>document.getElementById(id).addEventListener('input',updateBayes));

  function peerBar(label,sub,val,disp,color){
    const pct=Math.min(val/28,1)*100;
    return '<div class="br"><div class="brl">'+label+'<small>'+sub+'</small></div><div class="brt"><div class="brf" style="width:'+pct+'%;background:'+color+'"></div></div><div class="brv" style="color:'+color+'">'+disp+'</div></div>';
  }
  document.getElementById('peerbars').innerHTML=[
    peerBar('Semis median (broad)','fwd P/E · approx',25,'~25×','var(--faint)'),
    peerBar('Western Digital','fwd P/E · approx',11,'~11×','var(--teal)'),
    peerBar('SK hynix','fwd P/E · approx',7,'~7×','var(--teal-deep)'),
    peerBar('Micron','fwd P/E 5.6× · computed',5.6,'~5.6×','var(--coral)'),
  ].join('');

  ['i-mgn','i-mlt','i-corr','i-tail'].forEach(id=>document.getElementById(id).addEventListener('input',update));
  update(); computeScenarioAnchors();

  const links=[].slice.call(document.querySelectorAll('.stepper a'));
  const map={};links.forEach(a=>{const h=a.getAttribute('href');if(h&&h.charAt(0)==='#')map[h.slice(1)]=a;});
  const stepperEl=document.querySelector('.stepper');
  function centerStep(a){
    if(!stepperEl||!a)return;
    const left=a.offsetLeft-(stepperEl.clientWidth-a.clientWidth)/2;
    const max=Math.max(0,stepperEl.scrollWidth-stepperEl.clientWidth);
    const target=Math.max(0,Math.min(max,left));
    if(typeof stepperEl.scrollTo==='function'){
      try{stepperEl.scrollTo({left:target,behavior:'smooth'});}
      catch(err){stepperEl.scrollLeft=target;}
    }else{stepperEl.scrollLeft=target;}
  }
  let activeStepId=null;
  const visibleMods=new Set();
  function syncActiveStep(){
    let best=null,bestDist=Infinity;
    const band=window.innerHeight*0.38;
    visibleMods.forEach(function(el){
      const r=el.getBoundingClientRect();
      const dist=Math.abs(r.top-band);
      if(dist<bestDist){bestDist=dist;best=el;}
    });
    if(!best)return;
    const id=best.id;
    if(id===activeStepId)return;
    activeStepId=id;
    links.forEach(l=>l.classList.remove('active'));
    const a=map[id];
    if(a){a.classList.add('active');centerStep(a);}
  }
  const obs=new IntersectionObserver(function(es){
    es.forEach(function(e){
      if(e.isIntersecting)visibleMods.add(e.target);
      else visibleMods.delete(e.target);
    });
    syncActiveStep();
  },{rootMargin:'-35% 0px -50% 0px',threshold:[0,0.1,0.25]});
  document.querySelectorAll('.mod, .audit').forEach(s=>obs.observe(s));
  links.forEach(a=>a.addEventListener('click',function(){
    const id=(a.getAttribute('href')||'').slice(1);
    activeStepId=id;
    links.forEach(l=>l.classList.remove('active'));
    a.classList.add('active');
    centerStep(a);
  }));
</script>'''


def header():
    return '''  <div class="eyebrow">Research pipeline · strict-data · Micron Technology, Inc. · NASDAQ: MU · built 2026-07-19</div>
  <h1>Micron — the memory arm of the AI trade
    <span class="sub">Fundamentals and the cycle first — then the valuation engine. The only scaled US memory maker (NASDAQ: MU), one of three HBM suppliers to the AI build-out, valued <b>through-cycle</b> on EBITDA margin × EV/EBITDA multiple plus net cash. Every figure is <b>sourced</b>, <b>computed</b> from sourced inputs, or an explicit <b>assumption</b> you set. The headline sequence: <b>what is the business, how good is it at the peak, and what is it worth once you underwrite the whole cycle?</b></span>
  </h1>

  <div class="keystat">
    <div class="ks"><div class="kl">Price</div><div class="kv">$848.95</div></div>
    <div class="ks"><div class="kl">Market cap</div><div class="kv">$959<small>bn</small></div></div>
    <div class="ks"><div class="kl">Net cash</div><div class="kv">$19.6<small>bn</small></div></div>
    <div class="ks"><div class="kl">P/E</div><div class="kv">~19<small>× (fwd ~5.6×)</small></div></div>
    <div class="ks"><div class="kl">EV/EBITDA</div><div class="kv">~13.8<small>×</small></div></div>
    <div class="ks"><div class="kl">Beta</div><div class="kv">~2.1</div></div>
    <div class="ks"><div class="kl">Cons. PT</div><div class="kv">$1,492<small> (+76%)</small></div></div>
  </div>

  <div class="legend">
    <span class="lg sourced"><span class="d"></span>Sourced — fetched &amp; cited</span>
    <span class="lg computed"><span class="d"></span>Computed — by this tool from sourced inputs</span>
    <span class="lg assumed"><span class="d"></span>Your assumption — a judgment you set, not data</span>
  </div>

  <div class="hero">
    <div class="htag">◆ How to read this build — fundamentals &amp; cycle first</div>
    <h3>Start with <b>what the business is</b> and <b>why memory is different now</b> (HBM + oligopoly discipline). Then read the books. Only after that should you touch the through-cycle Monte-Carlo engine and the institutional layers.</h3>
    <div class="lenses">
      <div class="lens empir">
        <div class="lt">Part 1 — Thesis &amp; cycle</div>
        <div class="lh">Module T</div>
        <div class="lb">The memory business, the HBM/AI demand driver, the DRAM oligopoly, and Micron&rsquo;s place in the AI · robotics · data · energy stack — as the most direct AI beneficiary that still trades like a hardware cyclical.</div>
      </div>
      <div class="lens owner">
        <div class="lt">Part 2 — Fundamentals</div>
        <div class="lh">Modules Q · D · E · G · F</div>
        <div class="lb">Fetched quality dashboard (incl. the FY23 trough), forensic balance-sheet scores, the capex-dominated capital record, peer multiples and positioning. The &ldquo;how good is it, and how cyclical?&rdquo; block.</div>
      </div>
      <div class="lens comp">
        <div class="lt">Part 3 — Deeper analysis</div>
        <div class="lh">Modules A–C · U · H · I · J</div>
        <div class="lb">Through-cycle correlated MC engine, driver tornado, Bayesian scenarios, the 10-year ceiling, kill-criteria, price-asymmetry and base-rate composites — the stress tests once you understand the cycle.</div>
      </div>
    </div>
    <div class="synth"><b>Master read (spoiler for later modules).</b> The most <i>predictive</i> near-term mover is the <b>AI-memory narrative</b> (HBM allocation, hyperscaler capex, competitor supply); the single <i>fundamental</i> variable that sets fair value through-cycle is the <b>durability of the HBM-era EBITDA margin</b>. The base case (~$830) sits right around the ~$849 price — the reverse-DCF (Module I) says the market is implying a ~62.5% through-cycle margin holds. The trade is a wide, two-sided bet on the cycle, not a mispricing at spot.</div>
  </div>

  <nav class="stepper" id="stepper">
    <a href="#mThesis"><span class="n">T</span>Thesis &amp; cycle</a>
    <a href="#mQ"><span class="n">Q</span>Quality</a>
    <a href="#mD"><span class="n">D</span>Forensics</a>
    <a href="#mE"><span class="n">E</span>Capital record</a>
    <a href="#mG"><span class="n">G</span>Peers</a>
    <a href="#mF"><span class="n">F</span>Positioning</a>
    <a href="#mA"><span class="n">A</span>Engine</a>
    <a href="#mB"><span class="n">B</span>Driver analysis</a>
    <a href="#mC"><span class="n">C</span>Scenarios + Bayes</a>
    <a href="#mH"><span class="n">H</span>Kill-criteria</a>
    <a href="#mSum"><span class="n">∑</span>Scorecard</a>
  </nav>'''


HEAD_TOP = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Micron Technology (MU) — Research Pipeline (strict-data)</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
'''


def _css_blocks():
    """Reuse the Konecranes base + shared-UX CSS verbatim so all reports share
    one design system; Module-I/J, audit and bull-case CSS are added by the
    framework at build time."""
    kon = open(os.path.join(HERE, "konecranes-pipeline.html"), encoding="utf-8").read()
    base = re.search(r'<style>\s*\n?\s*:root\{.*?</style>', kon, re.S)
    uxfix = re.search(r'<style id="ux-fixes">.*?</style>', kon, re.S)
    if not base or not uxfix:
        raise RuntimeError("could not extract CSS blocks from konecranes-pipeline.html")
    return base.group(0) + "\n\n" + uxfix.group(0)


def build_html():
    parts = [
        HEAD_TOP,
        _css_blocks(),
        "\n</head>\n<body>\n<div class=\"wrap\">\n",
        header(),
        "\n",
        module_T(), "\n",
        module_Q(), "\n",
        module_D(), "\n",
        module_E(), "\n",
        module_G(), "\n",
        module_F(), "\n",
        module_A(), "\n",
        module_B(), "\n",
        module_C(), "\n",
        module_H(), "\n",
        scorecard(), "\n",
        footer(), "\n",
        "</div>\n",
        ENGINE_JS,
        "\n</body>\n</html>\n",
    ]
    return "".join(parts)


def main():
    html = build_html()
    out = os.path.join(HERE, "micron-pipeline.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"OK — wrote {out} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
