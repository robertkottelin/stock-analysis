"""One-shot script to inject Modules K, L, M and the ✓ Conclusions section
into spacex-analytics-pipeline.html.

Module map (after the 2026 four-leg rebuild):
  K — Priced-in decomposition (four-leg sum-of-the-parts)
  L — Connectivity / Starlink unit-economics
  M — Frontier optionality (deep-space future potential)
  ✓ — Conclusions & watch-list

These sections are hand-authored, stock-specific narrative — the framework's
generic Modules I/J from utils/inject.py are already in place and are not
touched here. This script is idempotent: it looks for the mK/mL/mM/mN/mConc
anchors and replaces them if they already exist (mN is a legacy id that is
removed on sight, so re-running after the political-overlay module was dropped
leaves no stale section).

It also patches the JS `PRICE` constant in Module A to the live Yahoo spot, so
the interactive engine, histogram and tornado show the current price rather
than the authored snapshot.

Numbers are traceable to:
- stocks/config_spacex.py — engine drivers, base rates, primary sources
- SpaceX S-1/424B4 filing — FY2025 & Q1'26 P&L, segment split, subs
- Sell-side 2030E models (Goldman/JPMorgan/Morgan Stanley) — leg calibration
- SpaceX/xAI lunar-manufacturing & orbital-data-centre programme — Module M
- Starship payload/launch-cost targets — Module M
- Live Yahoo Finance v8 fetch (utils/inject.py cached) — spot, market cap
"""
from __future__ import annotations
import os, re, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from stocks.config import STOCKS  # noqa: E402
from analytics import fetch_chart, series, reverse_dcf  # noqa: E402

_DISC_2030 = 1.10 ** 4
_DISC_2035 = 1.10 ** 9
_NET_CASH_BN = 25.0
_XAI_ANCHOR_BN = 250.0


def _live_context() -> dict:
    """Fetch the same live inputs Modules I/A use and re-run the four-leg
    sum-of-the-parts at every driver's mode, so Modules K & M reference numbers
    that cannot drift out of sync with the pipeline's own engine."""
    cfg = STOCKS["spacex"]
    chart = fetch_chart(cfg["ticker"], "5y")
    _, px = series(chart)
    spot = chart["chart"]["result"][0]["meta"].get("regularMarketPrice") or px[-1]
    rd = reverse_dcf("spacex", spot)
    shares_m = cfg["shares_m"]
    d = cfg["drivers"]

    # Per-leg present value at every driver's mode (same math the engine runs).
    conn_pv_bn     = d["conn_rev"]["md"] * d["conn_margin"]["md"] * d["conn_mult"]["md"] / _DISC_2030
    launch_pv_bn   = d["space_rev"]["md"] * d["space_mult"]["md"] / _DISC_2030
    orbital_pv_bn  = d["orbital_rev"]["md"]  * d["frontier_mult"]["md"] / _DISC_2035
    frontier_pv_bn = d["frontier_rev"]["md"] * d["frontier_mult"]["md"] / _DISC_2035
    ai_md_bn       = d["ai_value"]["md"]
    equity_mode_bn = (conn_pv_bn + launch_pv_bn + orbital_pv_bn + frontier_pv_bn
                      + ai_md_bn + _NET_CASH_BN)
    per_share_at_mode = equity_mode_bn * 1000.0 / shares_m

    def ps(x_bn: float) -> float:
        return x_bn * 1000.0 / shares_m

    # (EV $bn, $/share, % of mode equity) per leg
    legs = {
        "starlink": (conn_pv_bn,     ps(conn_pv_bn),     100.0 * conn_pv_bn     / equity_mode_bn),
        "launch":   (launch_pv_bn,   ps(launch_pv_bn),   100.0 * launch_pv_bn   / equity_mode_bn),
        "orbital":  (orbital_pv_bn,  ps(orbital_pv_bn),  100.0 * orbital_pv_bn  / equity_mode_bn),
        "frontier": (frontier_pv_bn, ps(frontier_pv_bn), 100.0 * frontier_pv_bn / equity_mode_bn),
        "ai":       (ai_md_bn,       ps(ai_md_bn),       100.0 * ai_md_bn       / equity_mode_bn),
        "netcash":  (_NET_CASH_BN,   ps(_NET_CASH_BN),   100.0 * _NET_CASH_BN   / equity_mode_bn),
    }

    mcap_bn = spot * shares_m / 1000.0
    ev_bn = mcap_bn - _NET_CASH_BN
    implied_ai_bn = rd["implied"]

    return {
        "spot": spot,
        "shares_m": shares_m,
        "mcap_bn": mcap_bn,
        "ev_bn": ev_bn,
        "legs": legs,
        "equity_mode_bn": equity_mode_bn,
        "per_share_at_mode": per_share_at_mode,
        "price_over_mode_ps": spot - per_share_at_mode,
        "implied_ai_bn": implied_ai_bn,
        "mode_ai_bn": ai_md_bn,
        "xai_anchor_bn": _XAI_ANCHOR_BN,
        "ai_over_anchor": implied_ai_bn / _XAI_ANCHOR_BN,
        "mcap_share_of_ai_pct": 100.0 * implied_ai_bn / mcap_bn,
        # orbital-datacenter leg detail (Module N)
        "orbital_rev_md":  d["orbital_rev"]["md"],
        "orbital_rev_lo":  d["orbital_rev"]["lo"],
        "orbital_rev_hi":  d["orbital_rev"]["hi"],
        "orbital_ev_2035_bn": d["orbital_rev"]["md"] * d["frontier_mult"]["md"],
        "orbital_ps": ps(orbital_pv_bn),
        "orbital_pct": 100.0 * orbital_pv_bn / equity_mode_bn,
        "orbital_hi_ps": ps(d["orbital_rev"]["hi"] * d["frontier_mult"]["hi"] / _DISC_2035),
        # other-frontier leg detail (Module M)
        "frontier_rev_md":  d["frontier_rev"]["md"],
        "frontier_rev_lo":  d["frontier_rev"]["lo"],
        "frontier_rev_hi":  d["frontier_rev"]["hi"],
        "frontier_mult_md": d["frontier_mult"]["md"],
        "frontier_mult_lo": d["frontier_mult"]["lo"],
        "frontier_mult_hi": d["frontier_mult"]["hi"],
        "frontier_ev_2035_bn": d["frontier_rev"]["md"] * d["frontier_mult"]["md"],
        "frontier_ps": ps(frontier_pv_bn),
        "frontier_pct": 100.0 * frontier_pv_bn / equity_mode_bn,
        "frontier_hi_ps": ps(d["frontier_rev"]["hi"] * d["frontier_mult"]["hi"] / _DISC_2035),
        # Connectivity / Starlink calibration (Module L)
        "rev_2025": 18.674,
        "conn_rev_2025": 11.4,
        "conn_ebitda_2025": 7.0,
        "conn_margin_2025": 0.63,
        "space_rev_2025": 4.086,
        "ai_rev_2025": 3.2,
        "q1_26_rev": 4.694,
        "subs_ye_2025_m": 8.9,
        "subs_mar_2026_m": 10.3,
        "arpu_2025_usd": 11400.0 / ((5.3 + 8.9) / 2 * 12),          # ~$134/mo blended
        "arpu_q1_26_usd": (11.4 / 18.674 * 4.694) / (((8.9 + 10.3) / 2) * 3),  # ~$100/mo blended
    }


def render_K(ctx: dict) -> str:
    legs = ctx["legs"]
    sl, lu, ob, fr, ai, nc = (legs["starlink"], legs["launch"], legs["orbital"],
                              legs["frontier"], legs["ai"], legs["netcash"])
    return f"""
  <!-- K — PRICED-IN DECOMPOSITION · five-leg SOTP (SpaceX build) -->
  <section class="mod" id="mK">
    <div class="mod-head"><div class="mod-no">K</div>
      <div class="ht"><h2>What the price already contains &mdash; the five-leg decomposition</h2><div class="hq">Starlink, launch, orbital datacenters, other frontier and the AI mark &mdash; separated, each as a share of value.</div></div>
      <span class="tagchip s">Sourced &middot; live</span>
    </div>
    <div class="verdict bear"><span class="vchip">BEAR</span><span class="vtext"><b>Two pillars, not one &mdash; but the AI mark is still the swing.</b> At the pipeline&rsquo;s own mode assumptions Starlink (<b>{sl[2]:.0f}%</b>) and the AI segment (<b>{ai[2]:.0f}%</b>) are co-equal pillars; launch (<b>{lu[2]:.0f}%</b>), orbital datacenters (<b>{ob[2]:.0f}%</b>) and other frontier (<b>{fr[2]:.0f}%</b>) are the smaller wings. Yet the reverse-DCF still says today&rsquo;s price implies an AI-segment value of <b>${ctx['implied_ai_bn']:.0f}bn</b> &mdash; <b>{ctx['ai_over_anchor']:.1f}&times; the xAI acquisition anchor</b> ($250bn) and <b>{ctx['mcap_share_of_ai_pct']:.0f}%</b> of the entire market cap.</span></div>

    <p class="body"><b>The arithmetic.</b> Live spot <span class="hl">${ctx['spot']:.2f}</span> &times; {ctx['shares_m']:,.0f}m shares = <span class="hl">${ctx['mcap_bn']:.0f}bn</span> market cap; net cash ~$25bn keeps EV within ~1% of it. The engine at every driver&rsquo;s <i>mode</i> produces <span class="hl">${ctx['per_share_at_mode']:.0f}/share</span>, decomposed in the table below. The gap between that mode value and today&rsquo;s price &mdash; <b>${ctx['price_over_mode_ps']:+.0f}/share</b> &mdash; is the market&rsquo;s incremental mark on the AI segment above the pipeline&rsquo;s $700bn mode: it grids out to an implied <b>${ctx['implied_ai_bn']:.0f}bn</b>. The 2025 build let that one residual absorb <i>everything</i> the operating segments couldn&rsquo;t explain; this build gives the deep-space future two explicit legs (orbital datacenters &rarr; Module N, other frontier &rarr; Module M) so the residual is smaller and honestly labelled.</p>

    <table class="brtab">
      <thead><tr><th>Value leg</th><th style="text-align:right">EV at mode</th><th style="text-align:right">$/share</th><th style="text-align:right">% of value</th><th>Priced on</th></tr></thead>
      <tbody>
        <tr><td>Connectivity / Starlink</td><td class="num">${sl[0]:.0f}bn</td><td class="num">${sl[1]:.0f}</td><td class="num">{sl[2]:.0f}%</td><td>2030E rev $70bn &times; 64% EBITDA &times; 24&times;, disc. 4y</td></tr>
        <tr><td>Space / launch + Starship</td><td class="num">${lu[0]:.0f}bn</td><td class="num">${lu[1]:.0f}</td><td class="num">{lu[2]:.0f}%</td><td>2030E rev $16bn &times; 8&times; EV/Sales, disc. 4y</td></tr>
        <tr><td>Orbital datacenters &rarr; Module N</td><td class="num">${ob[0]:.0f}bn</td><td class="num">${ob[1]:.0f}</td><td class="num">{ob[2]:.0f}%</td><td>2035E space-compute rev $25bn &times; 6&times; EV/Sales, disc. 9y</td></tr>
        <tr><td>Other frontier &rarr; Module M</td><td class="num">${fr[0]:.0f}bn</td><td class="num">${fr[1]:.0f}</td><td class="num">{fr[2]:.0f}%</td><td>2035E rev $25bn &times; 6&times; EV/Sales, disc. 9y</td></tr>
        <tr class="cur"><td>AI segment (xAI + X + ground Colossus)</td><td class="num now">${ai[0]:.0f}bn</td><td class="num now">${ai[1]:.0f}</td><td class="num now">{ai[2]:.0f}%</td><td>EV drawn directly; $700bn mode (xAI anchor $250bn)</td></tr>
        <tr><td>Net cash</td><td class="num">${nc[0]:.0f}bn</td><td class="num">${nc[1]:.0f}</td><td class="num">{nc[2]:.0f}%</td><td>$75bn raise &minus; $29.1bn LT debt &minus; est. burn</td></tr>
        <tr><td><b>Total &mdash; mode fair value</b></td><td class="num"><b>${ctx['equity_mode_bn']:.0f}bn</b></td><td class="num"><b>${ctx['per_share_at_mode']:.0f}</b></td><td class="num"><b>100%</b></td><td>vs live spot ${ctx['spot']:.2f}</td></tr>
      </tbody>
    </table>

    <div class="cmp" style="margin-top:16px">
      <div class="cmpcard"><div style="font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--teal-deep);font-weight:600;margin-bottom:8px">Priced in</div>
        <div class="cmprow"><span class="ck">Starlink at ~$70bn 2030 revenue</span><span class="cv">${sl[1]:.0f}/sh via a 24&times; segment multiple</span></div>
        <div class="cmprow"><span class="ck">xAI merger at ~$250bn (Feb&rsquo;26)</span><span class="cv">and then some &mdash; the mark is now ~{ctx['ai_over_anchor']:.1f}&times; that</span></div>
        <div class="cmprow"><span class="ck">Orbital datacenters (space-based AI compute)</span><span class="cv">${ob[1]:.0f}/sh at mode &mdash; a real, sized leg now (Module N)</span></div>
        <div class="cmprow"><span class="ck">Other frontier (moon factories, P2P)</span><span class="cv">${fr[1]:.0f}/sh &mdash; the base case, not the tail (Module M)</span></div>
        <div class="cmprow"><span class="ck">Ground Colossus rented to Anthropic</span><span class="cv">a real, monetised revenue leg &mdash; embedded in AI rev</span></div>
      </div>
      <div class="cmpcard"><div style="font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--coral-deep);font-weight:600;margin-bottom:8px">Not priced / unproven</div>
        <div class="cmprow"><span class="ck">The orbital-datacenter right tail</span><span class="cv">space compute at scale would add ~${ctx['orbital_hi_ps']:.0f}/sh &mdash; pure optionality (Module N)</span></div>
        <div class="cmprow"><span class="ck">The other-frontier right tail</span><span class="cv">moon factories at scale ~${ctx['frontier_hi_ps']:.0f}/sh more</span></div>
        <div class="cmprow"><span class="ck">Cursor $60bn acquisition close</span><span class="cv">walk-away costs $1.5bn + $8.5bn deferred fee</span></div>
        <div class="cmprow"><span class="ck">Sep&ndash;Dec 2026 lock-up wall</span><span class="cv">90&ndash;180-day founder/PE/employee unlocks</span></div>
        <div class="cmprow"><span class="ck">Common-control governance discount</span><span class="cv">market has not yet demanded one</span></div>
      </div>
    </div>

    <div class="note b"><b>How the reverse-DCF frames it.</b> Module I solves for the AI-segment value that reconciles the median MC fair value to spot: <span class="hl blue">${ctx['implied_ai_bn']:.0f}bn</span>. That sits <b>{100*(ctx['implied_ai_bn']-ctx['mode_ai_bn'])/ctx['mode_ai_bn']:+.0f}%</b> above the pipeline&rsquo;s $700bn mode, near the top of the frontier-lab peer range (OpenAI ~$500bn secondary mid-2025; Anthropic ~$183bn primary Sep-2025), and roughly {ctx['ai_over_anchor']:.1f}&times; the xAI transaction anchor. The decomposition above is the point: Starlink is a real, cash-generative pillar you can underwrite; the two frontier-class legs (orbital datacenters, other frontier) are genuine optionality with long right tails; but the marginal dollar of today&rsquo;s price is still an AI-mark call. Note the orbital-datacenter leg is <i>space-based</i> compute &mdash; the ground Colossus is already inside the AI segment, so there is no double-count. Upside from here needs either that AI mark to be defensible <i>or</i> the frontier tails to start printing revenue.</div>
  </section>
"""


def render_L(ctx: dict) -> str:
    """Connectivity / Starlink unit-economics nowcast + 2030 target grid."""
    subs_grid = [20, 30, 40, 50, 60, 80]   # million
    arpu_grid = [70, 90, 110, 130, 150]    # $/mo blended
    rows = []
    for s in subs_grid:
        row = [f"<td class='num'>{s}M</td>"]
        for a in arpu_grid:
            rev = s * a * 12 / 1000.0  # $bn
            in_range = 45.0 <= rev <= 100.0
            at_mode  = abs(rev - 70.0) < 4.0
            cls = " class='num cur'" if at_mode else (" class='num'" if in_range else " class='num' style='color:var(--faint)'")
            row.append(f"<td{cls}>${rev:.0f}bn</td>")
        rows.append("<tr>" + "".join(row) + "</tr>")
    grid_body = "\n        ".join(rows)

    arpu_2025 = ctx["arpu_2025_usd"]
    arpu_q1 = ctx["arpu_q1_26_usd"]

    return f"""
  <!-- L — CONNECTIVITY UNIT-ECONOMICS MODEL (SpaceX build) -->
  <section class="mod" id="mL">
    <div class="mod-head"><div class="mod-no">L</div>
      <div class="ht"><h2>Connectivity unit-economics &mdash; what has to be true</h2><div class="hq">Decomposing the Starlink leg (2030 revenue) into subscribers &times; ARPU.</div></div>
      <span class="tagchip c">Computed &middot; new model</span>
    </div>
    <div class="verdict mixed"><span class="vchip">MIXED</span><span class="vtext"><b>Base case reachable, but not by more of the same.</b> The pipeline&rsquo;s $70bn mode requires <b>~40M subs at $150/mo</b> or <b>~60M subs at $100/mo</b> &mdash; either is a 4&ndash;6&times; leap from today, on a base whose blended ARPU is already <i>falling</i> as direct-to-cell mix rises.</span></div>

    <p class="body"><b>The equation.</b> Connectivity segment revenue = average subscribers &times; blended ARPU &times; 12. Everything above this in the engine (EBITDA margin &times; multiple &times; discount factor) simply prices what this line delivers. So the entire Starlink leg of the sum-of-the-parts comes down to <i>which cell in the grid below</i> the world settles at.</p>
    <div style="font-family:var(--mono);font-size:12.5px;background:var(--surface-2);border:1px dashed var(--line-strong);border-radius:10px;padding:13px 15px;line-height:1.7;overflow-x:auto">
      2030 Connectivity revenue [$bn] = subscribers_2030 [M] &times; ARPU_2030 [$/mo] &times; 12 &divide; 1000<br>
      2030 Connectivity EBITDA [$bn] = revenue [$bn] &times; margin (base 64%)<br>
      2030 Connectivity segment value [$bn] = EBITDA [$bn] &times; multiple (base 24&times;) &divide; 1.10<sup>4</sup>&nbsp; <span style="color:var(--faint)">// discount 4y at 10%</span>
    </div>

    <p class="body" style="margin-top:12px"><b>Calibration.</b> FY2025: revenue <span class="hl">$11.4bn</span>, avg subs (5.3 &rarr; 8.9)M = 7.1M &rArr; blended ARPU <span class="hl">${arpu_2025:.0f}/mo</span> at 63% EBITDA margin. Q1&rsquo;26 imputed (Connectivity ~61% of the $4.694bn total, avg subs 9.6M) &rArr; blended ARPU <span class="hl neg">${arpu_q1:.0f}/mo</span>. That is a <b>~{100*(arpu_2025-arpu_q1)/arpu_2025:.0f}% ARPU decline in one quarter</b> &mdash; the D2C mix shift, low-ARPU consumer international, and volume-tier pricing all pulling the same direction. Whether ARPU stabilises or continues down decides the grid.</p>

    <p class="body" style="margin-top:14px"><b>The grid.</b> Green cells = inside the pipeline&rsquo;s 2030 revenue range ($45&ndash;100bn); teal-shaded = at the $70bn mode; faint = outside the range.</p>
    <table class="brtab">
      <thead>
        <tr><th>Subs 2030 &darr;&nbsp;&nbsp;/&nbsp;&nbsp;ARPU &rarr;</th><th style="text-align:right">$70/mo</th><th style="text-align:right">$90/mo</th><th style="text-align:right">$110/mo</th><th style="text-align:right">$130/mo</th><th style="text-align:right">$150/mo</th></tr>
      </thead>
      <tbody>
        {grid_body}
      </tbody>
    </table>

    <div class="note t" style="margin-top:14px"><b>Why the grid matters.</b> Two consumer businesses are competing inside Starlink&rsquo;s ARPU line: (1) high-ARPU aviation / maritime / enterprise / DoD ($500&ndash;5,000/mo per active seat) and (2) low-ARPU consumer + direct-to-cell (D2C is essentially a wholesale wireless-carrier line, monetised at cents per underlying phone user). If (2) scales faster, blended ARPU keeps falling and Starlink needs an <i>enormous</i> subscriber count to hit the pipeline&rsquo;s $70bn mode. If (1) scales faster, fewer subs get there but the achievable ceiling (subs &times; ARPU) is tighter.</div>

    <p class="body" style="margin-top:14px"><b>What must be verified before the Q2 print.</b></p>
    <table class="brtab">
      <thead><tr><th>Metric</th><th style="text-align:right">FY2025</th><th style="text-align:right">Q1&rsquo;26</th><th>Direction that keeps the mode intact</th></tr></thead>
      <tbody>
        <tr><td>Subscribers (period end)</td><td class="num">8.9M</td><td class="num">10.3M</td><td>&gt;12M by YE 2026 (implies ~+35% CAGR to 40M by 2030)</td></tr>
        <tr><td>Connectivity revenue growth y/y</td><td class="num">+48%</td><td class="num">flat q/q</td><td>&gt;+30% y/y at Q2 print &mdash; the deceleration cannot start yet</td></tr>
        <tr><td>Blended ARPU trajectory</td><td class="num">~${arpu_2025:.0f}</td><td class="num">~${arpu_q1:.0f}</td><td>Stabilise &ge;$95 &mdash; break below implies a D2C-dominant path</td></tr>
        <tr><td>Segment EBITDA margin</td><td class="num">63%</td><td class="num">n/d</td><td>Hold &gt;55% &mdash; break below signals capacity ahead of demand</td></tr>
      </tbody>
    </table>

    <div class="reading"><b>How to read it.</b> (1) <b>The Starlink leg&rsquo;s mode is defensible, but not from the current trajectory.</b> To hit $70bn conn_rev in 2030, subscribers have to compound at 30&ndash;40% for four years <i>while</i> ARPU stops falling. (2) <b>The Q1&rsquo;26 ARPU drop is the single loudest signal in the S-1.</b> If it repeats in Q2 without volume acceleration, the grid slides toward the low-ARPU column and the $45bn low is more likely than the $70bn mode. (3) <b>Starlink is one of two co-equal pillars now</b> (Module K) &mdash; a real, cash-generative business, unlike the AI mark it sits beside. (4) <b>First live test:</b> Q2&rsquo;26 subs and Connectivity revenue growth, printing Aug&ndash;Sep 2026.</div>

    <div class="note c"><b>Where this model breaks.</b> ARPU trajectory is imputed from segment share &times; total revenue &mdash; segment quarterly disclosure would collapse the assumption. If SpaceX begins reporting Starlink revenue separately, replace the ARPU calibration here with the printed number. Direct-to-cell economics are still forming; today&rsquo;s ~$5/mo wholesale rate per underlying carrier customer could be a floor or a ceiling. All of these become fetchable as the tape and the filings mature; the grid does not need to be re-derived, only re-calibrated.</div>
  </section>
"""


def render_M(ctx: dict) -> str:
    """Frontier optionality — the deep-space future potential, decomposed."""
    # TAM (rows) × effective SpaceX capture (cols) -> risk-adjusted 2035E revenue
    tam_grid = [100, 250, 500, 900]        # $bn — 2035 addressable frontier pools
    cap_grid = [0.05, 0.10, 0.20, 0.35]    # effective capture = share × probability
    lo, md, hi = ctx["frontier_rev_lo"], ctx["frontier_rev_md"], ctx["frontier_rev_hi"]
    rows = []
    for t in tam_grid:
        cells = [f"<td class='num'>${t}bn</td>"]
        for c in cap_grid:
            rev = t * c
            in_band = lo <= rev <= hi
            at_mode = abs(rev - md) <= 8
            cls = " class='num cur'" if at_mode else (" class='num'" if in_band else " class='num' style='color:var(--faint)'")
            cells.append(f"<td{cls}>${rev:.0f}bn</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    grid_body = "\n        ".join(rows)

    return f"""
  <!-- M — OTHER FRONTIER OPTIONALITY (SpaceX build) -->
  <section class="mod" id="mM">
    <div class="mod-head"><div class="mod-no">M</div>
      <div class="ht"><h2>Other frontier optionality &mdash; moon factories, payload, point-to-point</h2><div class="hq">The deep-space markets beyond orbital datacenters (those are Module N) &mdash; priced as a risk-adjusted, deeply-discounted call option.</div></div>
      <span class="tagchip c">Computed &middot; frontier leg</span>
    </div>
    <div class="verdict mixed"><span class="vchip">MIXED</span><span class="vtext"><b>Huge, uniquely-held, and genuinely unpriced by cash flows.</b> The deep-space markets beyond orbital compute &mdash; lunar/in-space manufacturing, payload-to-orbit new markets, point-to-point &mdash; barely exist today, so the leg is a <i>risk-adjusted</i> 2035E revenue (TAM &times; capture &times; probability) on a shared frontier EV/Sales multiple, discounted nine years. At mode it adds <b>${ctx['frontier_ps']:.0f}/share</b> ({ctx['frontier_pct']:.0f}% of value); the right tail &mdash; the moon-factory vision at scale &mdash; is worth <b>~${ctx['frontier_hi_ps']:.0f}/share</b>. (Orbital datacenters, the flagship frontier use-case, are broken out separately in <b>Module N</b>.)</span></div>

    <p class="body"><b>Why this leg exists.</b> Starship is the hinge. A fully-reusable vehicle lifting <b>150 t reusable / 250 t expendable</b> to LEO at a target of <b>$100&ndash;200/kg</b> (aspirationally $10) against ~$1,500/kg today is not an incremental improvement &mdash; it is the ~10&times; cost collapse that makes an entire class of markets economically possible for the first time. SpaceX is the only entity that owns the launch and the satellite bus (Starlink) needed to build them. Musk has publicly re-prioritised a self-sustaining <b>city on the Moon</b> this decade; the &ldquo;moon factory&rdquo; thesis (lunar &amp; in-space manufacturing) sits here, while the solar-powered orbital-datacenter piece of it is valued in Module N.</p>

    <table class="brtab">
      <thead><tr><th>Frontier market</th><th>Basis / status (2026)</th><th>Independent size signal</th><th>What to watch</th></tr></thead>
      <tbody>
        <tr><td><b>Payload-to-orbit cost collapse</b></td><td>Starship 150&ndash;250 t to LEO; $100&ndash;200/kg target vs ~$1,500 today</td><td class="num">~10&times;</td><td>Full-reuse demo; realised $/kg; flight cadence</td></tr>
        <tr><td><b>Moon factories</b> (lunar &amp; in-space mfg)</td><td>Shotwell &ldquo;AI on the Moon&rdquo;; Musk &ldquo;city on the Moon&rdquo; this decade; NASA Artemis HLS landing ~2028</td><td>emerging</td><td>First lunar-manufacturing / ISRU demo; HLS cadence</td></tr>
        <tr><td><b>Point-to-point Earth transport</b></td><td>USSF &ldquo;Rocket Cargo&rdquo; demo (~$102m, scalable to $1bn+); sub-hour global delivery</td><td class="num">DoD-led</td><td>Operational cargo contract; safety/regulatory path</td></tr>
        <tr><td><b>Launch-TAM expansion</b> (defence, deep space)</td><td>NASA HLS ~$2.89bn + $1.15bn awards; NSSL; deep-space science</td><td class="num">$615bn sat mkt &rsquo;32</td><td>Contract book vs Boeing/ULA/RKLB; cadence</td></tr>
        <tr><td style="color:var(--faint)">Orbital datacenters &rarr; <b>Module N</b></td><td style="color:var(--faint)">Split into its own leg (space-based AI compute)</td><td class="num" style="color:var(--faint)">see N</td><td style="color:var(--faint)">valued separately to avoid burying it</td></tr>
      </tbody>
    </table>

    <p class="body" style="margin-top:16px"><b>The decomposition.</b> The engine draws a risk-adjusted 2035E revenue for these other-frontier markets ($4&ndash;90bn, mode $25bn) &mdash; itself <b>TAM &times; effective-capture</b> (capture share &times; probability the category is real at scale). The grid shows which pair each revenue anchor needs. Green cells = inside the driver&rsquo;s $4&ndash;90bn band; teal-shaded = at the ~$25bn mode; faint = outside.</p>
    <table class="brtab">
      <thead>
        <tr><th>2035 TAM &darr;&nbsp;&nbsp;/&nbsp;&nbsp;effective capture &rarr;</th><th style="text-align:right">5%</th><th style="text-align:right">10%</th><th style="text-align:right">20%</th><th style="text-align:right">35%</th></tr>
      </thead>
      <tbody>
        {grid_body}
      </tbody>
    </table>

    <div style="font-family:var(--mono);font-size:12.5px;background:var(--surface-2);border:1px dashed var(--line-strong);border-radius:10px;padding:13px 15px;line-height:1.7;margin-top:14px;overflow-x:auto">
      other-frontier revenue 2035 [$bn] = TAM [$bn] &times; capture-share &times; probability&nbsp; <span style="color:var(--faint)">// mode ${md:.0f}bn</span><br>
      other-frontier EV 2035 [$bn]       = revenue &times; EV/Sales (mode 6&times;)&nbsp; <span style="color:var(--faint)">// ${ctx['frontier_ev_2035_bn']:.0f}bn</span><br>
      other-frontier value today [$bn]   = EV 2035 &divide; 1.10<sup>9</sup>&nbsp; <span style="color:var(--faint)">// ~${ctx['legs']['frontier'][0]:.0f}bn &rarr; ${ctx['frontier_ps']:.0f}/share</span>
    </div>

    <div class="note t" style="margin-top:14px"><b>Why nine years and why risk-adjusted.</b> These revenues are 2030s events, not 2030 events, so the leg is discounted to 2035 (9y at 10%) &mdash; roughly half the undiscounted value. And the driver is <i>already</i> probability-weighted: a $25bn mode is, e.g., a $250bn 2035 in-space-manufacturing + P2P pool at a 10% effective capture, <i>not</i> a promise that SpaceX books $25bn. That is why the modal contribution is a modest ${ctx['frontier_ps']:.0f}/share while the tail is large: this is a call option, priced like one.</div>

    <div class="reading"><b>How to read it.</b> (1) <b>Deep-space goals now have an explicit home.</b> Moon factories, cheap heavy lift and point-to-point are priced here; the orbital-datacenter flagship is priced in Module N. (2) <b>It is optionality, not a base case.</b> At mode it is ~{ctx['frontier_pct']:.0f}% of value; its honest role is to fatten the upside tail (Module A&rsquo;s P90, Module B&rsquo;s tornado). (3) <b>The unlock is verifiable.</b> Unlike the AI mark, this leg has physical milestones &mdash; realised $/kg, first lunar-manufacturing demo, an operational Rocket-Cargo contract. (4) <b>Kill/confirm:</b> if Starship full reuse and $/kg stall, the whole leg is a mirage; if $/kg falls as targeted, the mode is conservative.</div>

    <div class="note c"><b>Where this leg breaks.</b> Every number here is a <i>forward</i> estimate on markets that are pre-revenue for SpaceX today, so the ranges are wide by design and the sourcing is directional (analyst TAMs, executive statements, comparable raises), not audited filings. The point is not precision &mdash; it is to stop the deep-space future from being priced at zero <i>or</i> hidden inside the AI mark. As real contracts, cadence and $/kg print, re-calibrate the driver in stocks/config.py; the leg does not need to be re-derived.</div>
  </section>
"""


def render_N(ctx: dict) -> str:
    """Orbital datacenters — space-based AI compute, broken out as its own leg."""
    ob = ctx["legs"]["orbital"]
    lo, md, hi = ctx["orbital_rev_lo"], ctx["orbital_rev_md"], ctx["orbital_rev_hi"]
    rev_per_gw = 8.0   # $bn/GW-year — illustrative annual revenue of a ~1 GW AI datacentre
    gw_grid = [5, 10, 25, 50]              # GW of orbital compute deployed by 2035
    cap_grid = [0.05, 0.10, 0.20, 0.35]    # SpaceX effective capture = share × probability
    rows = []
    for g in gw_grid:
        cells = [f"<td class='num'>{g} GW</td>"]
        for c in cap_grid:
            rev = g * rev_per_gw * c
            in_band = lo <= rev <= hi
            at_mode = abs(rev - md) <= 8
            cls = " class='num cur'" if at_mode else (" class='num'" if in_band else " class='num' style='color:var(--faint)'")
            cells.append(f"<td{cls}>${rev:.0f}bn</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    grid_body = "\n        ".join(rows)

    return f"""
  <!-- N — ORBITAL DATACENTERS (SpaceX build) -->
  <section class="mod" id="mN">
    <div class="mod-head"><div class="mod-no">N</div>
      <div class="ht"><h2>Orbital datacenters &mdash; space-based AI compute, its own leg</h2><div class="hq">Datacenters in space, broken out of the frontier lump: sized, decomposed, and gated on the one thing SpaceX uniquely controls.</div></div>
      <span class="tagchip c">Computed &middot; new leg</span>
    </div>
    <div class="verdict mixed"><span class="vchip">MIXED</span><span class="vtext"><b>Yes, it&rsquo;s priced &mdash; now visibly.</b> Space-based, solar-powered AI compute is the flagship &ldquo;moon factory&rdquo; use-case, so it gets its own leg rather than hiding inside the frontier lump. At mode it adds <b>${ob[1]:.0f}/share</b> ({ob[2]:.0f}% of value); the right tail &mdash; a gigawatt-scale orbital-compute constellation &mdash; is worth <b>~${ctx['orbital_hi_ps']:.0f}/share</b>. Distinct from the <i>ground</i> Colossus already inside the AI segment, so no double-count.</span></div>

    <p class="body"><b>Why SpaceX, and why this is a real leg.</b> Orbital datacenters solve terrestrial AI&rsquo;s power/land/cooling wall with 24/7 solar and radiative cooling &mdash; but they only pay off if launch is cheap enough. The break-even to beat ground datacenters is roughly <b>$500/kg</b> for GPU payloads, and Google puts full viability at <b>&lt;$200/kg by 2035</b>, plausible only if Starship reaches ~180 launches/year. That gate is exactly the payload-cost collapse <b>SpaceX uniquely owns</b> (Module M) &mdash; and SpaceX also owns the satellite bus (Starlink) and, via xAI, the compute and the demand. No competitor holds all three. This is why the datacenter-in-space opportunity is a SpaceX leg, not a generic space-economy line.</p>

    <table class="brtab">
      <thead><tr><th>Evidence</th><th>2026 status</th><th>Read</th></tr></thead>
      <tbody>
        <tr><td><b>The gate: launch $/kg</b></td><td>Break-even ~$500/kg for GPUs; &lt;$200/kg by 2035 for full viability (Google)</td><td>Ties this leg directly to Starship &mdash; the Module-M hinge</td></tr>
        <tr><td><b>Starcloud</b></td><td>NVIDIA H100 flown in orbit; 5 GW single-site concept (4 km solar array); unicorn raise</td><td>First mover; proves the physics at small scale</td></tr>
        <tr><td><b>Google &ldquo;Project Suncatcher&rdquo;</b></td><td>Solar-powered TPU satellite constellation; demo mission ~2027</td><td>A hyperscaler validating the thesis &mdash; and a customer/competitor</td></tr>
        <tr><td><b>SpaceX / xAI</b></td><td>xAI merger framed around solar-powered AI satellites; Shotwell &ldquo;AI on the Moon&rdquo;</td><td>The stated strategy this leg prices</td></tr>
        <tr><td><b>Market size</b></td><td>~$1.8bn (2029) &rarr; ~$39bn (2035); $10&ndash;50bn/yr by 2030 on demand projections</td><td>Near-term TAM is modest; the vision (GW-scale) is the tail</td></tr>
      </tbody>
    </table>

    <p class="body" style="margin-top:16px"><b>The decomposition.</b> The orbital driver is SpaceX&rsquo;s risk-adjusted 2035E space-compute revenue (${lo:.0f}&ndash;${hi:.0f}bn, mode ${md:.0f}bn). Read it as <b>GW deployed &times; revenue/GW-year &times; SpaceX effective capture</b> (capture share &times; probability the category is real). The grid uses ~${rev_per_gw:.0f}bn/GW-year (a ~1 GW AI datacentre&rsquo;s rough annual revenue). Green = inside the driver&rsquo;s ${lo:.0f}&ndash;${hi:.0f}bn band; teal-shaded = at the ~${md:.0f}bn mode; faint = outside.</p>
    <table class="brtab">
      <thead>
        <tr><th>Orbital GW 2035 &darr;&nbsp;&nbsp;/&nbsp;&nbsp;SpaceX effective capture &rarr;</th><th style="text-align:right">5%</th><th style="text-align:right">10%</th><th style="text-align:right">20%</th><th style="text-align:right">35%</th></tr>
      </thead>
      <tbody>
        {grid_body}
      </tbody>
    </table>

    <div style="font-family:var(--mono);font-size:12.5px;background:var(--surface-2);border:1px dashed var(--line-strong);border-radius:10px;padding:13px 15px;line-height:1.7;margin-top:14px;overflow-x:auto">
      orbital revenue 2035 [$bn]  = GW &times; ~${rev_per_gw:.0f}bn/GW-yr &times; SpaceX capture&nbsp; <span style="color:var(--faint)">// mode ${md:.0f}bn</span><br>
      orbital EV 2035 [$bn]       = orbital revenue &times; EV/Sales (shared 6&times;)&nbsp; <span style="color:var(--faint)">// ${ctx['orbital_ev_2035_bn']:.0f}bn</span><br>
      orbital value today [$bn]   = orbital EV 2035 &divide; 1.10<sup>9</sup>&nbsp; <span style="color:var(--faint)">// ~${ob[0]:.0f}bn &rarr; ${ob[1]:.0f}/share</span>
    </div>

    <div class="note b" style="margin-top:14px"><b>The double-count guard.</b> Today&rsquo;s AI compute &mdash; the <i>ground</i> Colossus clusters, incl. capacity rented to Anthropic &mdash; is already inside the <b>AI segment</b> ($700bn mode, Module K). This leg is only the <i>space-based</i> datacenter business (2035E), so the two do not overlap. If you believe orbital compute simply migrates the AI segment&rsquo;s existing revenue off-planet rather than adding new revenue, dial this slider down and the AI slider up; if you believe it is a genuinely new market, this leg is where it lives.</div>

    <div class="reading"><b>How to read it.</b> (1) <b>This is the &ldquo;datacenters in space&rdquo; question, answered.</b> It is priced &mdash; ${ob[1]:.0f}/share at mode ({ob[2]:.0f}% of value), ~${ctx['orbital_hi_ps']:.0f}/share in the tail &mdash; and now has its own slider in Module A and its own bar in the Module B tornado. (2) <b>It is optionality gated on hardware.</b> The whole leg lives or dies on Starship $/kg; watch the realised cost curve before the TAM. (3) <b>The near-term TAM is small, the vision is not.</b> $39bn by 2035 is the base; a gigawatt-scale constellation is the ${ctx['orbital_hi_ps']:.0f}/share tail. (4) <b>First real signals:</b> Starcloud/Suncatcher milestones and the first MW-scale orbital-compute contract.</div>

    <div class="note c"><b>Where this leg breaks.</b> Radiation, thermal rejection at scale, on-orbit servicing and latency are unsolved at GW scale; the ~${rev_per_gw:.0f}bn/GW-year revenue assumption is illustrative, not sourced; and if $/kg stalls above ~$500 the economics never close. As real cost, capacity and contracts print, re-calibrate <code>orbital_rev</code> in stocks/config.py &mdash; the leg does not need to be re-derived.</div>
  </section>
"""


def render_Conc(ctx: dict) -> str:
    return f"""
  <!-- CONCLUSIONS (SpaceX build) -->
  <section class="mod" id="mConc">
    <div class="mod-head"><div class="mod-no" style="color:var(--teal-deep)">&#10003;</div>
      <div class="ht"><h2>Conclusions &amp; watch-list &mdash; the single-source summary</h2><div class="hq">Everything the SpaceX build concluded, in one place, with dates.</div></div>
      <span class="tagchip a">Synthesis &middot; live</span>
    </div>
    <p class="body"><b>The thesis in one paragraph.</b> SpaceX is the best-executing industrial company of the modern era, valued as the sum of five legs: a real Starlink cash pillar (~{ctx['legs']['starlink'][2]:.0f}% of value at mode), a launch business (~{ctx['legs']['launch'][2]:.0f}%), two deep-space options &mdash; orbital datacenters (~{ctx['legs']['orbital'][2]:.0f}%, Module N) and other frontier (~{ctx['legs']['frontier'][2]:.0f}%, Module M), each with a much larger right tail &mdash; and a common-controlled AI mark (~{ctx['legs']['ai'][2]:.0f}% at mode but ~{ctx['mcap_share_of_ai_pct']:.0f}% of the market cap once the price&rsquo;s premium over mode is attributed to it). The engine at every driver&rsquo;s mode returns <span class="hl">${ctx['per_share_at_mode']:.0f}/share</span>; live spot is <span class="hl">${ctx['spot']:.2f}</span>; the <b>${ctx['price_over_mode_ps']:+.0f}/share</b> in between is the market&rsquo;s AI re-rating &mdash; an implied <b>${ctx['implied_ai_bn']:.0f}bn</b>, ~{ctx['ai_over_anchor']:.1f}&times; the xAI anchor. What you can underwrite is Starlink and the launch monopoly; what you get for free is the frontier optionality &mdash; including datacenters in space (Module N), gated on the Starship $/kg collapse SpaceX uniquely controls; what you cannot yet underwrite is the AI mark. The disciplined position is <b>sized by kill-criteria, not narrative</b>: participate below the anchor, trim into the top of the range, own the tape event-by-event, and treat the frontier legs as the free calls they are.</p>

    <table class="brtab">
      <thead><tr><th>When</th><th>Event</th><th>What to verify</th></tr></thead>
      <tbody>
        <tr><td class="num">7 Jul 2026</td><td>Nasdaq-100 inclusion at ~0.47&ndash;0.70% weight</td><td>Mechanical inflow into the first days; not a fundamental read &mdash; do not confuse the flow with a re-rating</td></tr>
        <tr><td class="num">Aug&ndash;Sep 2026</td><td>First post-IPO earnings print (Q2 2026)</td><td>Connectivity revenue y/y (need &gt;+30%); subs vs 12M target; blended ARPU trajectory vs Q1&rsquo;26&rsquo;s ~$100; segment EBITDA margin vs 63% baseline; any FAA/FCC/DoD commentary</td></tr>
        <tr><td class="num">Sep&ndash;Dec 2026</td><td>90&ndash;180-day lock-up wall (Founders Fund, DFJ, D1, Fidelity, Thrive, employees)</td><td>Actual sold volume vs disclosed intent; new institutional buyers absorbing supply; price behaviour into each unlock date</td></tr>
        <tr><td class="num">Q4 2026</td><td>Starship flight-test cadence; realised payload cost per kg</td><td>Whether full reuse is transitioning Starship from development to revenue &mdash; the hinge for the entire frontier leg (Module M)</td></tr>
        <tr><td class="num">2027</td><td>First MW-scale orbital-compute contract; lunar-manufacturing / ISRU demo; xAI 1M-GPU Colossus target</td><td>Whether the frontier tail starts printing revenue, and whether the ${ctx['implied_ai_bn']:.0f}bn AI mark has revenue underneath it</td></tr>
        <tr><td class="num">2028</td><td>NASA Artemis first crewed landing on Starship HLS</td><td>Cadence and cost &mdash; the proof point that anchors the moon-factory optionality</td></tr>
      </tbody>
    </table>

    <div class="cmp" style="margin-top:16px">
      <div class="cmpcard"><div style="font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--coral-deep);font-weight:600;margin-bottom:8px">Why the AI mark is the fragile leg</div>
        <div style="font-size:12.5px;line-height:1.6;color:var(--muted)">The mark did not appear from an arm&rsquo;s-length transaction &mdash; it came from a Feb-2026 all-stock merger between two Musk-controlled entities, then re-rated ~{ctx['ai_over_anchor']:.1f}&times; in the tape. Frontier-lab peer marks (OpenAI ~$500bn, Anthropic ~$183bn) are lower and themselves debated. The AI segment printed <b>-$6.35bn operating loss on $3.2bn revenue</b> in 2025 &mdash; capex intensity, not fraud, but capex intensity does not price at 300&times; sales. If one large frontier-lab peer marks down, or a related-party governance case is filed, the AI leg compresses and the operating segments cannot fill the gap.</div></div>
      <div class="cmpcard"><div style="font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--teal-deep);font-weight:600;margin-bottom:8px">Why the frontier legs are the asymmetric ones</div>
        <div style="font-size:12.5px;line-height:1.6;color:var(--muted)">Orbital datacenters (Module N) and other frontier (Module M) are marked at only ~{ctx['legs']['orbital'][2]+ctx['legs']['frontier'][2]:.0f}% of value at mode combined, yet their tails are worth ~${ctx['orbital_hi_ps']+ctx['frontier_hi_ps']:.0f}/share &mdash; and, unlike the AI mark, every step is a <b>physical, verifiable milestone</b> (realised $/kg, the first MW-scale orbital datacentre, a lunar-manufacturing demo, an Artemis landing). You are not paying up for this today; you own it as a call, gated on the Starship cost collapse SpaceX uniquely controls. That is the cleanest source of upside in the whole structure, and it is the part the earlier build priced at zero.</div></div>
    </div>

    <div class="note t" style="margin-top:14px"><b>Fastest information channel.</b> SEC EDGAR (CIK 1181412) for filings; the SpaceX IR site once stood up; Nasdaq notices for index rebalancing; FCC ECFS for spectrum; FAA for launch licences; NASA/USSF award notices for the frontier contracts. Sacra and Nasdaq Private Market discontinued SpaceX private-round tracking at IPO &mdash; the public tape is the price discovery now, which is why Modules I &amp; J start reading immediately even on a few weeks of history.</div>
    <p class="disc" style="font-size:11px;color:var(--faint);margin-top:12px">Modules K, L, M, N and &#10003; Conclusions synthesise the SpaceX build: five-leg priced-in decomposition, connectivity unit-economics, other-frontier optionality, orbital datacenters, and history/landscape context. For analysis and education only &mdash; not investment advice.</p>
  </section>
"""


# --------------------------------------------------------------------------
# Injection: idempotent replace-or-insert
# --------------------------------------------------------------------------

def inject() -> None:
    ctx = _live_context()
    frag_K = render_K(ctx)
    frag_L = render_L(ctx)
    frag_M = render_M(ctx)
    frag_N = render_N(ctx)
    frag_C = render_Conc(ctx)

    path = os.path.join(ROOT, "stocks", "spacex-analytics-pipeline.html")
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    # 0) Keep Module A's interactive engine on the live price: patch the JS
    #    PRICE constant to the live Yahoo spot (histogram/tornado/cards derive
    #    from it; the .jsprice spans are filled from it in JS).
    html = re.sub(r'const PRICE=[\d.]+', f'const PRICE={ctx["spot"]:.2f}', html, count=1)

    # 1) Insert / replace K, L, M, N just before the ∑ Scorecard section.
    for mid in ("mK", "mL", "mM", "mN"):
        html = re.sub(
            rf'\s*<!--[^>]*-->\s*<section class="mod" id="{mid}">.*?</section>\s*',
            '\n\n  ',
            html, flags=re.S,
        )
    scorecard_marker = '<section class="mod" id="mSum">'
    idx = html.find(scorecard_marker)
    if idx == -1:
        raise RuntimeError("Could not find mSum anchor in SpaceX HTML")
    html = (html[:idx] + frag_K + "\n" + frag_L + "\n" + frag_M + "\n" + frag_N
            + "\n  " + html[idx:])

    # 2) Insert / replace ✓ Conclusions between ∑ Scorecard and § Audit
    html = re.sub(
        r'\s*<!--[^>]*-->\s*<section class="mod" id="mConc">.*?</section>\s*',
        '\n\n  ',
        html, flags=re.S,
    )
    audit_marker = '<section class="audit" id="mAudit">'
    idx2 = html.find(audit_marker)
    if idx2 == -1:
        raise RuntimeError("Could not find mAudit anchor in SpaceX HTML")
    html = html[:idx2] + frag_C + "\n\n    " + html[idx2:]

    # 3) Stepper nav: remove any existing K/L/M/N entries, then insert fresh
    #    K/L/M/N after mJ (idempotent).
    for sid in ("mK", "mL", "mM", "mN"):
        html = re.sub(rf'\s*<a href="#{sid}">.*?</a>', '', html, flags=re.S)
    html = re.sub(
        r'(<a href="#mJ">[^<]*<span[^>]*>J</span>[^<]*</a>)',
        r'\1'
        r'\n    <a href="#mK"><span class="n">K</span>Priced-in</a>'
        r'\n    <a href="#mL"><span class="n">L</span>Starlink</a>'
        r'\n    <a href="#mM"><span class="n">M</span>Frontier</a>'
        r'\n    <a href="#mN"><span class="n">N</span>Orbital DC</a>',
        html, count=1,
    )
    if '<a href="#mConc">' not in html:
        html = re.sub(
            r'(<a href="#mSum">[^<]*<span[^>]*>∑</span>[^<]*</a>)',
            '\\1\n    <a href="#mConc"><span class="n">✓</span>Conclusions</a>',
            html, count=1,
        )

    # 4) Scorecard rows for K/L/M/N. Robustly remove any existing row for
    #    K/L/M/N (both &middot; and literal · forms) then insert fresh rows after
    #    the "J · Base rates" row.
    v_k = ("bear",  "BEAR",  "Five-leg SOTP: Starlink & AI co-equal pillars; AI still ~{p:.0f}% of mcap (${imp:.0f}bn implied vs $250bn xAI anchor)".format(
        p=ctx['mcap_share_of_ai_pct'], imp=ctx['implied_ai_bn']))
    v_l = ("mixed", "MIXED", "Starlink base mode reachable; Q1&rsquo;26 ARPU drop is the loudest signal in the S-1")
    v_m = ("mixed", "MIXED", "Other frontier (moon factories / payload-to-orbit / point-to-point): ~{fp:.0f}% at mode, ~${ft:.0f}/sh tail".format(
        fp=ctx['frontier_pct'], ft=ctx['frontier_hi_ps']))
    v_n = ("mixed", "MIXED", "Orbital datacenters (space-based AI compute): ~{op:.0f}% at mode, ~${ot:.0f}/sh tail &mdash; gated on Starship $/kg".format(
        op=ctx['orbital_pct'], ot=ctx['orbital_hi_ps']))
    for letter in ("K", "L", "M", "N"):
        html = re.sub(rf'\s*<tr><td>{letter} &middot;.*?</tr>', '', html, flags=re.S)
        html = re.sub(rf'\s*<tr><td>{letter} ·.*?</tr>', '', html, flags=re.S)
    new_rows = (
        f'\n        <tr><td>K &middot; Priced-in</td><td><span class="vchip {v_k[0]}">{v_k[1]}</span></td><td>{v_k[2]}</td></tr>'
        f'\n        <tr><td>L &middot; Unit-econ</td><td><span class="vchip {v_l[0]}">{v_l[1]}</span></td><td>{v_l[2]}</td></tr>'
        f'\n        <tr><td>M &middot; Frontier</td><td><span class="vchip {v_m[0]}">{v_m[1]}</span></td><td>{v_m[2]}</td></tr>'
        f'\n        <tr><td>N &middot; Orbital DC</td><td><span class="vchip {v_n[0]}">{v_n[1]}</span></td><td>{v_n[2]}</td></tr>'
    )
    html, n_ins = re.subn(
        r'(<tr><td>J &middot; Base rates</td>.*?</tr>)',
        lambda mo: mo.group(1) + new_rows,
        html, count=1, flags=re.S,
    )
    if n_ins == 0:
        # J row uses the literal · form (from utils/inject.py)
        html = re.sub(
            r'(<tr><td>J · Base rates</td>.*?</tr>)',
            lambda mo: mo.group(1) + new_rows,
            html, count=1, flags=re.S,
        )

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    inject()
    print("OK — spacex-analytics-pipeline.html: Modules K, L, M and ✓ Conclusions injected/refreshed; JS PRICE synced to live spot")
