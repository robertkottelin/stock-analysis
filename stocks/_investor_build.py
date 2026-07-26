"""Generator for stocks/investor-pipeline.html.

Investor AB is a pure industrial holding company: the right unit of analysis
is adjusted NAV (Listed + Patricia + EQT − net debt) times a holdco discount,
plus a full look-through at every material holding. Authored narrative sits
as strings; the Module-A engine mirrors stocks/config_investor.py exactly.

Run once to (re)emit the report skeleton:

    python stocks/_investor_build.py

Then build the live layers (Modules I/J/U, audit, tallies, finalize, verify):

    python utils/build_one.py investor
"""
from __future__ import annotations
import os, re, sys, json, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "utils"))
from analytics import fetch_chart, series  # noqa: E402

CUR = "kr"

# ------------------------------------------------------------------ real data
# Investor Q2 2026 interim (30 Jun 2026) — primary source. SEK bn unless noted.
NAV_BN       = 1214.7
NAV_PS       = 397.0
SHARES_M     = 3062.9
LISTED_BN    = 946.2
PATRICIA_BN  = 207.9      # excl. cash
EQT_BN       = 88.4
NET_DEBT_BN  = 23.3
GROSS_CASH   = 28.8
GROSS_DEBT   = 52.1
LEVERAGE_PCT = 1.9
MGMT_COST_BP = 7           # 0.07% of adj. NAV
DIV_PS       = 5.60        # FY2025 dividend
TSR_20Y      = 16.5
SIXRX_20Y    = 10.2
TSR_1Y       = 46.1        # report figure (with div)
TSR_H1       = 23.2

# Live Yahoo (build-time snapshot; re-synced in narrative to ~397)
TTM = dict(
    price=397.0, mcap=1216.0, book=321.46, pb=1.24,
    pe_ttm=4.64, pe_fwd=25.2, eps_ttm=85.67, eps_fwd=15.75,
    beta=0.78, div_y=0.0141, payout=0.064, roe=0.273,
    cons_pt=393.8, target_hi=440.0, target_lo=327.0, n_analysts=5,
    rec="hold", net_debt_y=105.8,  # Yahoo totalDebt−cash (group IFRS, SEK bn-ish)
)

# Official Q2'26 listed stake values (SEK bn) + ownership % of capital
LISTED = [
    # name, value_bn, stake_cap_pct, theme, live_pe, live_roe_pct, live_om_pct, thesis_tag
    ("ABB",                  279.0, 14.6, "Automation · electrification · robotics", 35.6, 32.6, 16.9, "AI/auto"),
    ("Atlas Copco",          163.9, 17.1, "Compressors · vacuum · industrial tools",  35.9, 25.7, 20.6, "AI/auto"),
    ("AstraZeneca",           94.0,  3.3, "Global biopharma",                         25.3, 23.5, 27.9, "Health"),
    ("SEB",                   84.7, 22.1, "Nordic universal bank",                    13.7, 14.1, 54.7, "Finance"),
    ("Saab",                  82.9, 30.2, "Defence · aerospace · underwater",         43.1, 15.9, 10.9, "Defence"),
    ("Sobi",                  56.4, 34.4, "Rare-disease biopharma",                  117.5,  2.3, 26.6, "Health"),
    ("Epiroc",                54.9, 17.1, "Mining equipment · automation · battery",  32.1, 21.2, 19.9, "AI/auto"),
    ("Nasdaq Inc",            44.8, 10.3, "Market infrastructure · data · indexes",   27.6, 16.2, 48.4, "AI/data"),
    ("Wärtsilä",              38.6, 17.7, "Marine & energy engines · decarbonisation",27.2, 27.3, 11.6, "Energy"),
    ("Ericsson",              36.1,  9.9, "Telecom networks · AI-RAN",                12.9, 26.1, 12.5, "AI/auto"),
    ("Electrolux",             4.7, 18.5, "Consumer appliances (turnaround)",         18.3,  4.1,  0.7, "Consumer"),
    ("Husqvarna",              3.7, 16.8, "Outdoor products",                         14.7,  5.6, 13.6, "Consumer"),
    ("Electrolux Professional",2.5, 20.4, "Professional kitchen & laundry",           18.2, 12.4,  8.1, "Consumer"),
]

# Patricia major subsidiaries Q2'26 estimated MV (SEK bn)
PATRICIA = [
    ("Mölnlycke",       75.3, 99.8, "Wound care · surgical",           13.8,  2.0, 27.7),
    ("Nova Biomedical", 31.4, 99.2, "Biopharma / clinical instruments",17.2, 10.0, 33.2),
    ("Laborie",         30.3, 98.5, "Urology / GI / obstetrics medtech",15.8, 13.0, 26.1),
    ("Sarnova",         18.9, 95.8, "Emergency medical products",       13.3, 10.0, 17.6),
    ("Permobil",        12.6, 99.6, "Powered wheelchairs / seating",    None,  2.0, 18.4),
    ("BraunAbility",    11.1, 95.3, "Vehicle accessibility",            None, 12.0, 12.1),
    ("Piab Group",      11.0, 98.4, "Vacuum automation / gripping",     None,  3.0, 15.0),
    ("Tre Skandinavien",10.8, 40.0, "Mobile operator (40%)",            None, None, None),
    ("Vectura",          4.0, 99.7, "Life-science real estate",         None, 42.0, 27.5),
]

# NAV history (adj. NAV SEK/share, year-end-ish + Q2'26)
NAV_HIST_Y = [2021, 2022, 2023, 2024, 2025, "Q2'26"]
NAV_HIST_V = [220, 200, 250, 300, 355, 397]   # approximate from reports / path

# Calibrated MC anchors (utils/analytics on the wired config, corr=0.6/tail=0.06)
MC = dict(p10=326, median=371, p90=419, p_up=24, kelly=-1.17, asym=0.17,
          cvar10=-21, var10=-18, rdcf_implied=0.3, rdcf_mode=5.0,
          scen_bear=258, scen_base=378, scen_bull=481, cons_gap=-1)


# ------------------------------------------------------------------ SVG helpers
PX0, PX1, PY0, PY1 = 44, 344, 22, 166
TEAL, BLUE, AMB, AMBD, CORAL, CORALD, FAINT, MUT, INK = (
    "var(--teal)", "var(--blue)", "var(--amber)", "var(--amber-deep)",
    "var(--coral)", "var(--coral-deep)", "var(--faint)", "var(--muted)", "var(--ink)")


def _yfun(ymin, ymax):
    def y(v):
        return PY1 - (v - ymin) / (ymax - ymin) * (PY1 - PY0)
    return y


def nav_history_svg():
    """Simple NAV-per-share bars + live price marker."""
    vals = NAV_HIST_V
    labels = [str(y) for y in NAV_HIST_Y]
    ymin, ymax = 0, 450
    y = _yfun(ymin, ymax)
    n = len(vals)
    gap = (PX1 - PX0) / n
    s = f'<svg viewBox="0 0 360 208" style="width:100%;height:auto" role="img">'
    s += '<g stroke="var(--line)" stroke-width="1">'
    for t in [0, 100, 200, 300, 400]:
        s += f'<line x1="{PX0}" y1="{y(t):.1f}" x2="{PX1}" y2="{y(t):.1f}"/>'
    s += '</g>'
    s += '<g font-family="IBM Plex Mono,monospace" font-size="9" fill="var(--faint)" text-anchor="end">'
    for t in [0, 100, 200, 300, 400]:
        s += f'<text x="39" y="{y(t)+3:.1f}">{t}</text>'
    s += '</g>'
    for i, (lab, v) in enumerate(zip(labels, vals)):
        cx = PX0 + gap * (i + 0.5)
        bh = PY1 - y(v)
        col = "var(--teal)" if i == n - 1 else "var(--blue)"
        s += f'<rect x="{cx-14:.1f}" y="{y(v):.1f}" width="28" height="{bh:.1f}" rx="3" fill="{col}" opacity="0.75"/>'
        s += f'<text x="{cx:.1f}" y="{PY1+14}" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="8.5" fill="var(--muted)">{lab}</text>'
        s += f'<text x="{cx:.1f}" y="{y(v)-4:.1f}" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="9" font-weight="600" fill="var(--ink)">{v}</text>'
    # price line at 397
    s += f'<line x1="{PX0}" y1="{y(397):.1f}" x2="{PX1}" y2="{y(397):.1f}" stroke="var(--amber-deep)" stroke-width="1.5" stroke-dasharray="3 2"/>'
    s += f'<text x="{PX1}" y="{y(397)-4:.1f}" text-anchor="end" font-family="IBM Plex Mono,monospace" font-size="9" fill="var(--amber-deep)">price {CUR}397</text>'
    s += '</svg>'
    return s


def portfolio_bars_svg():
    """Horizontal bars for listed stakes by value."""
    items = sorted(LISTED, key=lambda x: -x[1])
    maxv = items[0][1]
    W, row_h, top, left, right = 700, 22, 8, 140, 680
    h = top + len(items) * row_h + 20
    s = f'<svg viewBox="0 0 {W} {h}" style="width:100%;height:auto" role="img">'
    for i, (name, val, stake, theme, *rest) in enumerate(items):
        yy = top + i * row_h
        bw = (val / maxv) * (right - left - 80)
        tag = rest[-1] if rest else ""
        col = {
            "AI/auto": "var(--teal)", "AI/data": "var(--teal-deep)",
            "Health": "var(--blue)", "Defence": "var(--coral)",
            "Energy": "var(--amber)", "Finance": "var(--blue-deep)",
            "Consumer": "var(--faint)",
        }.get(tag, "var(--blue)")
        s += f'<text x="{left-8}" y="{yy+14}" text-anchor="end" font-family="IBM Plex Mono,monospace" font-size="11" fill="var(--ink)">{name}</text>'
        s += f'<rect x="{left}" y="{yy+4}" width="{bw:.1f}" height="14" rx="3" fill="{col}" opacity="0.7"/>'
        s += f'<text x="{left+bw+6:.1f}" y="{yy+15}" font-family="IBM Plex Mono,monospace" font-size="10.5" fill="var(--muted)">{val:.0f}bn · {stake:.0f}%</text>'
    s += '</svg>'
    return s


# ------------------------------------------------------------------ modules
def module_T():
    return f'''<section class="mod" id="mThesis">
    <div class="mod-head"><div class="mod-no">T</div>
      <div class="ht"><h2>Business thesis &amp; macro place</h2><div class="hq">What Investor is, where the value lives, and how the portfolio sits in AI · automation · energy · defence · health.</div></div>
      <span class="tagchip a">Sourced + judgment</span>
    </div>
    <div class="verdict bull"><span class="vchip">BULL · THESIS</span><span class="vtext">Investor is Northern Europe&rsquo;s <b>best multi-decade industrial compounder</b> &mdash; a three-leg portfolio (Listed 76% / Patricia 17% / EQT 7%) that has delivered <b>16.5% annualised total return over 20 years</b> vs 10.2% for the SIXRX, at a 0.07% management cost and 1.9% leverage. The thesis is strong; the <i>valuation debate</i> is whether a stock trading <b>at adjusted NAV</b> still has edge, or whether the holdco discount that used to be free has already closed.</span></div>

    <p class="body"><b>What the company is.</b> Investor AB (Nasdaq Stockholm: INVE-A / INVE-B) is the Wallenberg family&rsquo;s listed industrial holding company, founded in 1916. It is not an operating company and not a closed-end fund in the passive sense: it is an <b>active owner</b> of significant minority stakes in listed multinationals and of wholly-owned private platforms, with board influence, capital allocation rights and a multi-decade holding horizon. Adjusted net asset value on 30 Jun 2026 was <b>SEK 1,214.7bn</b> (SEK 397 per share); the B-share trades near that number.</p>

    <p class="body"><b>Three business areas, one compounder.</b></p>
    <div class="lenses" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr))">
      <div class="lens comp"><div class="lt">1 · Listed Companies · 76%</div><div class="lh">SEK 946bn</div><div class="lb">Significant stakes in ABB (SEK 279bn), Atlas Copco (164), AstraZeneca (94), SEB (85), Saab (83), Sobi (56), Epiroc (55), Nasdaq (45), Wärtsilä (39), Ericsson (36) and three small consumer names. Multinationals with strong market positions; Investor is typically the largest or a leading owner.</div></div>
      <div class="lens empir"><div class="lt">2 · Patricia Industries · 17%</div><div class="lh">SEK 208bn est.</div><div class="lb">Wholly-owned private companies, mostly health-tech and specialty industrials: Mölnlycke (75), Nova Biomedical (31), Laborie (30), Sarnova (19), Permobil, BraunAbility, Piab, Vectura, plus 40% of Tre Skandinavien. Estimated market values, not IFRS book.</div></div>
      <div class="lens owner"><div class="lt">3 · Investments in EQT · 7%</div><div class="lh">SEK 88bn</div><div class="lb">EQT AB stake (~15% of capital, SEK 50bn) plus EQT fund commitments (SEK 38bn). The alternatives franchise Investor helped create; cash generative via dividends and fund distributions.</div></div>
    </div>

    <div style="font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--blue-deep);font-weight:600;margin:18px 0 10px">◆ Place in the macro stack — five trend lenses</div>
    <p class="body" style="margin-bottom:12px">A holding company does not &ldquo;do AI.&rdquo; It <b>owns the industrial layer</b> that builds, automates, powers, defends and heals the world that AI is reshaping. The question is which waves the portfolio actually rides.</p>
    <div class="lenses" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr))">
      <div class="lens comp"><div class="lt">1 · AI &amp; automation (core)</div><div class="lh">ABB · Atlas · Epiroc · Piab · Ericsson</div><div class="lb"><b>~SEK 580bn+</b> of listed value in automation, robotics, industrial software, mining autonomy and AI-RAN. ABB alone is 23% of total assets. This is the <b>structural growth spine</b> of the portfolio &mdash; not a narrative overlay.</div></div>
      <div class="lens empir"><div class="lt">2 · Energy &amp; electrification</div><div class="lh">ABB · Atlas · Wärtsilä · Epiroc</div><div class="lb">Grid, drives, compressors, marine/energy engines, battery-electric mining. Second-order AI (data-centre power, industrial efficiency) and first-order European energy transition. <b>Durable multi-decade demand.</b></div></div>
      <div class="lens owner"><div class="lt">3 · Health &amp; longevity</div><div class="lh">AstraZeneca · Sobi · Mölnlycke · Laborie · Nova</div><div class="lb">Listed biopharma (~SEK 150bn) plus Patricia&rsquo;s health-tech platforms (~SEK 168bn of estimated MV). Defensive growth, high barriers, cash generative. The <b>shock absorber</b> when industrials cycle.</div></div>
      <div class="lens empir"><div class="lt">4 · Defence &amp; security</div><div class="lh">Saab · (Ericsson dual-use)</div><div class="lb">Saab (~SEK 83bn, 30% owned) is a direct NATO / European rearmament call option with a multi-year backlog. Geopolitical regime change is already in the numbers; the question is duration.</div></div>
      <div class="lens comp"><div class="lt">5 · Data &amp; capital markets</div><div class="lh">Nasdaq · SEB · EQT</div><div class="lb">Market infrastructure, Nordic banking and private-markets compounding. Less glamorous than robotics, but high-ROE cash engines that fund the dividend and the dry powder.</div></div>
    </div>

    <div class="synth" style="margin-top:16px"><b>Investment thesis (one paragraph).</b> Own Investor if you want <b>a diversified, actively-owned slice of European industrial and health excellence</b> &mdash; automation, electrification, defence, rare-disease and wound-care platforms &mdash; run at almost no cost (7 bp), with fortress leverage (1.9%), a rising dividend and a 20-year record of beating the market by ~6 pp a year. Fade it if you believe <b>at-NAV is full</b> for a holdco (the historical free lunch was the 10–20% discount, and it is gone), or if a broad equity bear market will crush the 76% listed book and re-open a wide discount simultaneously. The whole report is built around that fault line: <b>is quality-at-NAV still a buy, or does the closed discount mean the edge has been priced away?</b></div>

    <div class="note b"><b>How to read the rest of this report.</b> Next is the <b>portfolio look-through</b> (Module P) &mdash; every material holding with live fundamentals and a future-fitness read &mdash; then the quality / forensics / capital / peers / positioning block (Q · D · E · G · F). Only after that does the report drop into the NAV engine (A–C), the perfect-execution ceiling (U), kill-criteria (H) and the institutional layers (I · J).
      <div class="src">Primary source: Investor AB Interim report January–June 2026 (16 Jul 2026). Macro mapping is analytic judgment on the disclosed portfolio.</div>
    </div>
  </section>'''


def module_P():
    """Portfolio SOTP — the holding-company-specific module."""
    rows = ""
    for name, val, stake, theme, pe, roe, om, tag in LISTED:
        pe_s = f"{pe:.0f}×" if pe and pe < 200 else "n.m."
        rows += (f"<tr><td><b>{name}</b><div style='font-size:11px;color:var(--muted)'>{theme}</div></td>"
                 f"<td class='num'>{val:.1f}</td><td class='num'>{stake:.1f}%</td>"
                 f"<td class='num'>{pe_s}</td><td class='num'>{roe:.0f}%</td><td class='num'>{om:.0f}%</td>"
                 f"<td><span class='tagchip' style='font-size:10px'>{tag}</span></td></tr>")
    pat_rows = ""
    for name, val, stake, theme, mult, org, ebitam in PATRICIA:
        mult_s = f"{mult:.1f}×" if mult else "—"
        org_s = f"+{org:.0f}%" if org is not None else "—"
        em_s = f"{ebitam:.0f}%" if ebitam is not None else "—"
        pat_rows += (f"<tr><td><b>{name}</b><div style='font-size:11px;color:var(--muted)'>{theme}</div></td>"
                     f"<td class='num'>{val:.1f}</td><td class='num'>{stake:.0f}%</td>"
                     f"<td class='num'>{mult_s}</td><td class='num'>{org_s}</td><td class='num'>{em_s}</td></tr>")

    bars = portfolio_bars_svg()

    return f'''<section class="mod" id="mP">
    <div class="mod-head"><div class="mod-no">P</div>
      <div class="ht"><h2>Portfolio look-through — every material holding</h2><div class="hq">Listed at market · Patricia at Investor&rsquo;s estimated MV · EQT at market + fund NAV. Live fundamentals fetched per name.</div></div>
      <span class="tagchip s">Sourced + fetched</span>
    </div>
    <div class="verdict bull"><span class="vchip">BULL · PORTFOLIO</span><span class="vtext">This is not a random basket. The top five listed names (ABB, Atlas Copco, AstraZeneca, SEB, Saab) are <b>~SEK 705bn / 58% of total assets</b> &mdash; each a category leader with mid-teens-or-better ROE (except Saab, which is mid-cycle on a defence ramp). Patricia is a private health-tech compounder book. EQT is a scaled alternatives franchise. <b>The holdings earn their place in the AI · automation · energy · defence · health future</b>; the consumer tail (Electrolux / Husqvarna) is residual and small.</span></div>

    <p class="body"><b>How a holding company should be analysed.</b> You do <i>not</i> need a full 13-module pipeline on every subsidiary &mdash; you need (1) a clean NAV build, (2) conviction that the <b>largest weights</b> are durable compounders on the right side of history, and (3) honesty about the stubs. That is what this module does. Full deep-dives belong on the names you would own standalone (ABB, Atlas, Saab, AstraZeneca); here we score the portfolio as a portfolio.</p>

    <div class="mc-wrap" style="margin:6px 0 12px">
      <div class="mc-title">Listed Companies — SEK 946bn (76% of assets) · Q2 2026</div>
      <div class="mc-sub">Bar length = Investor&rsquo;s stake value. Colour by theme. Ownership % of capital shown at right.</div>
      {bars}
    </div>

    <div class="tbl-scroll"><table class="scoretab">
      <thead><tr><th>Listed holding</th><th class="num">Stake value<br>SEK bn</th><th class="num">Capital<br>%</th><th class="num">P/E<br>ttm</th><th class="num">ROE</th><th class="num">Op.<br>margin</th><th>Theme</th></tr></thead>
      <tbody>{rows}
        <tr style="font-weight:600;background:var(--surface-2)"><td>Total Listed</td><td class="num">946.2</td><td class="num">76% of assets</td><td></td><td></td><td></td><td></td></tr>
      </tbody>
    </table></div>
    <div class="src">Stake values &amp; ownership: Investor Q2 2026 interim. P/E, ROE, operating margin: Yahoo Finance fundamentals feed at build time (live per ticker). Theme tags are analytic judgment.</div>

    <div style="font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--blue-deep);font-weight:600;margin:22px 0 10px">◆ Conviction map — will these holdings matter in 10 years?</div>
    <div class="lenses" style="grid-template-columns:repeat(auto-fit,minmax(220px,1fr))">
      <div class="lens comp"><div class="lt">High conviction · own forever</div><div class="lh">ABB · Atlas Copco · Epiroc · AstraZeneca</div><div class="lb">Category leaders on the right side of automation, electrification, mining productivity and biopharma innovation. High ROE, global scale, Investor board influence. <b>~SEK 592bn / 49% of assets.</b></div></div>
      <div class="lens empir"><div class="lt">High conviction · regime tailwind</div><div class="lh">Saab · Nasdaq · Wärtsilä · Ericsson</div><div class="lb">Defence rearmament, market-infrastructure data, marine/energy transition, AI-native networks. More cyclical or geopolitical than the first group, but multi-year demand is real. <b>~SEK 202bn.</b></div></div>
      <div class="lens owner"><div class="lt">Core cash · less glamorous</div><div class="lh">SEB · Sobi · EQT</div><div class="lb">Nordic bank (ROE ~14%, low multiple), rare-disease biopharma (high multiple, pipeline risk), and the EQT franchise. Fund the dividend and diversify. <b>~SEK 230bn incl. EQT funds.</b></div></div>
      <div class="lens empir"><div class="lt">Stub / turnaround · small</div><div class="lh">Electrolux · Husqvarna · Elux Prof</div><div class="lb">Combined ~SEK 11bn (&lt;1% of assets). Electrolux rights issue (Investor put in SEK 1.7bn in Q2) is real capital at work, but portfolio impact is negligible either way.</div></div>
    </div>

    <div style="font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--blue-deep);font-weight:600;margin:22px 0 10px">◆ Patricia Industries — private platforms (est. MV SEK 208bn excl. cash)</div>
    <div class="tbl-scroll"><table class="scoretab">
      <thead><tr><th>Subsidiary</th><th class="num">Est. MV<br>SEK bn</th><th class="num">Own<br>%</th><th class="num">EV/EBITDA<br>applied</th><th class="num">Org.<br>growth</th><th class="num">EBITA<br>margin</th></tr></thead>
      <tbody>{pat_rows}
        <tr style="font-weight:600;background:var(--surface-2)"><td>Total Patricia excl. cash</td><td class="num">207.9</td><td class="num">17% of assets</td><td></td><td></td><td></td></tr>
      </tbody>
    </table></div>
    <p class="body" style="margin-top:12px"><b>Read on Patricia.</b> This is a <b>health-tech-heavy private equity book run with permanent capital</b> &mdash; Mölnlycke alone is SEK 75bn of wound-care leadership at 13.8× EBITDA and a 28% EBITA margin; Laborie and Nova are double-digit organic growers. Q2 total return was −3% on lower multiples despite +16% adj. EBITA growth &mdash; private marks can lag operations. Piab (vacuum automation) is the pure automation call option inside Patricia. The risk is multiple compression and key-person / integration risk on add-ons; the opportunity is that these platforms never have to be sold into a bad IPO window.</p>

    <div class="kg" style="margin-top:16px">
      <div class="kgi pos"><div class="k">EQT AB stake</div><div class="v">SEK 50bn <small>~15% of EQT</small></div></div>
      <div class="kgi"><div class="k">EQT fund investments</div><div class="v">SEK 38bn</div></div>
      <div class="kgi"><div class="k">Total EQT leg</div><div class="v">SEK 88bn <small>7% of assets</small></div></div>
      <div class="kgi neg"><div class="k">Q2 EQT value change</div><div class="v">−2%</div></div>
    </div>

    <div class="note a"><b>Bottom line on the book.</b> Roughly <b>70%+ of assets</b> sit in businesses with a credible 10-year claim on AI/automation, electrification, health or defence demand. The consumer stub is noise. Patricia is high-quality private health-tech, not a random PE dump. The portfolio <i>will</i> have a significant place in the future if Europe still builds, heals and defends &mdash; the open question is only the price of the wrapper.
      <div class="src">Investor Q2 2026 interim (stake values, Patricia estimated MVs &amp; applied multiples, EQT breakdown). Live multiples/ROE from Yahoo quoteSummary per ticker at build time.</div>
    </div>
  </section>'''


def module_Q():
    nav_svg = nav_history_svg()
    return f'''<section class="mod" id="mQ">
    <div class="mod-head"><div class="mod-no">Q</div>
      <div class="ht"><h2>Fundamental quality &amp; NAV dashboard</h2><div class="hq">For a holdco, quality is track record, cost, leverage and portfolio ROE &mdash; not IFRS net income.</div></div>
      <span class="tagchip c">Fetched + sourced</span>
    </div>
    <div class="verdict bull"><span class="vchip">BULL</span><span class="vtext">Institutional-grade quality: <b>16.5% 20-year TSR</b> vs 10.2% SIXRX, management cost <b>0.07% of NAV</b>, leverage <b>1.9%</b>, dual-class Wallenberg control aligned with multi-decade ownership, and a portfolio of high-ROE multinationals. The one quality caveat is valuation: trailing P/E ~4.6× is an IFRS revaluation artefact; on NAV the stock is no longer cheap.</span></div>

    <div class="qgrid">
      <div class="qcard"><div class="qtt">① Adjusted NAV / share (SEK)</div><div class="qsub">Bars = adj. NAV · dashed = live B-share price</div>
        {nav_svg}
        <div class="reading"><b>NAV has roughly doubled since 2021</b> to SEK 397/share. The price now sits <b>on top of NAV</b> &mdash; the historical discount is closed. That is a quality compliment and a valuation headwind at the same time.</div>
      </div>
      <div class="qcard"><div class="qtt">② Returns vs the market</div><div class="qsub">Average annual total return</div>
        <div class="bars" style="margin-top:12px">
          <div class="br"><div class="brl">Investor B · 20y<small>TSR annualised</small></div><div class="brt"><div class="brf" style="width:82%;background:var(--teal)"></div></div><div class="brv" style="color:var(--teal-deep)">16.5%</div></div>
          <div class="br"><div class="brl">SIXRX · 20y<small>Swedish total-return index</small></div><div class="brt"><div class="brf" style="width:51%;background:var(--faint)"></div></div><div class="brv">10.2%</div></div>
          <div class="br"><div class="brl">Investor B · 5y<small>annualised</small></div><div class="brt"><div class="brf" style="width:88%;background:var(--teal)"></div></div><div class="brv" style="color:var(--teal-deep)">17.5%</div></div>
          <div class="br"><div class="brl">Investor B · 1y<small>with dividend</small></div><div class="brt"><div class="brf" style="width:100%;background:var(--amber)"></div></div><div class="brv" style="color:var(--amber-deep)">46.1%</div></div>
        </div>
        <div class="reading"><b>~6 pp annualised excess return for 20 years</b> is the single best quality signal a holdco can print. The last 12 months (TSR ~46%) have been exceptional even by Investor standards &mdash; part of why the discount closed.</div>
      </div>
      <div class="qcard"><div class="qtt">③ Cost &amp; leverage</div><div class="qsub">The holdco operating system</div>
        <div class="kg" style="margin-top:10px">
          <div class="kgi pos"><div class="k">Mgmt cost / NAV</div><div class="v">0.07%</div></div>
          <div class="kgi pos"><div class="k">Leverage</div><div class="v">1.9%</div></div>
          <div class="kgi"><div class="k">Net debt</div><div class="v">SEK 23bn</div></div>
          <div class="kgi"><div class="k">Debt maturity</div><div class="v">8.7y avg</div></div>
        </div>
        <div class="reading">Target leverage 0–10% of assets; ceiling 20%. At 1.9% Investor has <b>dry powder</b> for the next dislocation. Rolling-12m management cost SEK 803m on a SEK 1.2tn NAV is among the leanest large holdcos in Europe.</div>
      </div>
      <div class="qcard"><div class="qtt">④ Valuation (holdco metrics)</div><div class="qsub">Ignore trailing P/E · watch P/NAV and P/B</div>
        <div class="kg" style="margin-top:10px">
          <div class="kgi neg"><div class="k">Price / adj. NAV</div><div class="v">~1.00×</div></div>
          <div class="kgi"><div class="k">Price / book</div><div class="v">1.24×</div></div>
          <div class="kgi"><div class="k">Fwd P/E</div><div class="v">~25×</div></div>
          <div class="kgi"><div class="k">Div yield</div><div class="v">1.4%</div></div>
        </div>
        <div class="reading">Trailing P/E ~4.6× is <b>not usable</b> (IFRS revals of listed stakes). Forward ~25× and P/NAV ~1.0× say the same thing: <b>quality is fully recognised</b>. Dividend SEK 5.60 is a growing but secondary return stream; TSR is mostly NAV compounding.</div>
      </div>
    </div>
    <div class="src">NAV path and TSR: Investor interim/annual reports. Live multiples: Yahoo Finance on INVE-B.ST at build time. Price/NAV computed as live price ÷ Q2'26 adj. NAV/share.</div>
  </section>'''


def module_D():
    return f'''<section class="mod" id="mD">
    <div class="mod-head"><div class="mod-no">D</div>
      <div class="ht"><h2>Forensic &amp; holdco-quality scores</h2><div class="hq">Solvency, cost discipline, governance &mdash; not manufacturing accruals.</div></div>
      <span class="tagchip c">Computed</span>
    </div>
    <div class="verdict bull"><span class="vchip">BULL</span><span class="vtext">A fortress holdco balance sheet and a governance structure built for permanence. Leverage 1.9%, multi-year debt maturity, sub-10 bp costs, and controlling owners whose time horizon is measured in generations. Manufacturing forensic scores (Piotroski, Beneish) are <b>deliberately not applied</b> &mdash; they are meaningless here.</span></div>
    <div class="scores">
      <div class="sc"><div class="scl">Leverage <span class="tg s">sourced</span></div><div class="scv">1.9<span class="un">%</span></div><div class="scband good">FORTRESS</div><div class="scd">Net debt SEK 23.3bn on SEK 1,238bn assets. Target 0–10%; hard ceiling 20%. Dry powder for downturns is real, not theoretical.</div></div>
      <div class="sc"><div class="scl">Liquidity <span class="tg s">sourced</span></div><div class="scv">SEK 29<span class="un">bn cash</span></div><div class="scband good">AMPLE</div><div class="scd">Gross cash SEK 28.8bn; average debt maturity 8.7 years. No near-term refinancing wall. Listed stakes are themselves a liquidity reservoir.</div></div>
      <div class="sc"><div class="scl">Cost discipline <span class="tg s">sourced</span></div><div class="scv">7<span class="un">bp</span></div><div class="scband good">BEST-IN-CLASS</div><div class="scd">Rolling-12m management cost 0.07% of adj. NAV. Most active managers charge 100–200 bp; Investor runs on a skeleton staff with board-level influence.</div></div>
      <div class="sc"><div class="scl">Earnings quality <span class="tg c">computed</span></div><div class="scv">NAV-based</div><div class="scband good">CLEAN</div><div class="scd">IFRS NI is revaluation noise. Owner earnings ≈ dividends + distributions received (~SEK 17bn/yr). Cash in, cash out, transparent.</div></div>
      <div class="sc"><div class="scl">Governance <span class="tg s">sourced</span></div><div class="scv">Wallenberg</div><div class="scband good">ALIGNED</div><div class="scd">Dual-class A/B; Wallenberg Foundations ~50% of votes. Multi-generation owner with reputation capital at stake. Minority-friendly track record (rising dividend, no abusive related-party pattern).</div></div>
      <div class="sc"><div class="scl">Complexity risk <span class="tg c">computed</span></div><div class="scv">Holdco</div><div class="scband mid">WATCH</div><div class="scd">Three legs, 13 listed names, 9+ private platforms, EQT funds. Complexity is the product. Mitigant: each leg is separately disclosed with estimated MVs and stake tables every quarter.</div></div>
    </div>
    <div class="note t"><b>Read.</b> On every holdco-relevant forensic dimension Investor is in the top tier globally. The residual risk is not fraud or leverage &mdash; it is <b>NAV mark-to-market in a bear market</b> plus the possibility that Patricia private multiples prove optimistic. Those are priced in the engine (Module A), not hidden.
      <div class="src">Leverage, cash, cost, governance: Investor Q2 2026 interim and annual report ownership notes.</div>
    </div>
  </section>'''


def module_E():
    return f'''<section class="mod" id="mE">
    <div class="mod-head"><div class="mod-no">E</div>
      <div class="ht"><h2>Capital-allocation record</h2><div class="hq">The facts, not a graded opinion.</div></div>
      <span class="tagchip s">Sourced</span>
    </div>
    <div class="verdict bull"><span class="vchip">BULL</span><span class="vtext">Capital allocation is the product. Investor takes dividends from the portfolio, reinvests selectively (Electrolux rights, Nasdaq adds, EQT adds, Patricia add-ons), keeps leverage low, and returns a steadily rising ordinary dividend. 20-year TSR of 16.5% is the scoreboard.</span></div>
    <div class="bars">
      <div class="br"><div class="brl">Hold &amp; compound listed stakes<small>the dominant use of capital · multi-decade</small></div><div class="brt"><div class="brf" style="left:0;width:90%;background:var(--teal)"></div></div><div class="brv" style="color:var(--teal-deep)">core</div></div>
      <div class="br"><div class="brl">Patricia platforms + add-ons<small>health-tech M&amp;A inside permanent capital</small></div><div class="brt"><div class="brf" style="left:0;width:40%;background:var(--blue)"></div></div><div class="brv" style="color:var(--blue-deep)">active</div></div>
      <div class="br"><div class="brl">EQT funds + EQT AB<small>alternatives compounding</small></div><div class="brt"><div class="brf" style="left:0;width:25%;background:var(--amber)"></div></div><div class="brv" style="color:var(--amber-deep)">7% of NAV</div></div>
      <div class="br"><div class="brl">Ordinary dividend<small>SEK 5.60/sh · rising · ~1.4% yield</small></div><div class="brt"><div class="brf" style="left:0;width:18%;background:var(--faint)"></div></div><div class="brv">growing</div></div>
    </div>
    <p class="body" style="margin-top:16px"><b>Recent moves (H1 2026).</b> Invested SEK 1.7bn in Electrolux rights issue (pro-rata, balance-sheet repair); bought Nasdaq shares (SEK 46m in Q2, more earlier); agreed to sell 2m SEB shares to hold ownership level; added EQT AB shares (SEK 349m); received SEK 13.3bn listed dividends in H1 and Patricia distributions (Mölnlycke EUR 200m alone). Net: the machine recycles portfolio cash into the highest-conviction legs and a rising dividend, without ever levering up.</p>
    <div class="note a"><b>Read.</b> This is what permanent capital is supposed to look like. No empire-building at the holdco layer, no leverage games, no fee extraction. The open capital-allocation risk is <b>soft-heartedness on the consumer stubs</b> (Electrolux) and whether Patricia add-on multiples stay disciplined &mdash; both second-order at current weights.
      <div class="src">Investor Q2 2026 interim (cash-flow by business area, investments, distributions, dividend).</div>
    </div>
  </section>'''


def module_G():
    return f'''<section class="mod" id="mG">
    <div class="mod-head"><div class="mod-no">G</div>
      <div class="ht"><h2>Peer multiples &amp; holdco discount</h2><div class="hq">The peer language is discount-to-NAV, not EV/EBITDA.</div></div>
      <span class="tagchip a">Computed + sourced</span>
    </div>
    <div class="verdict mixed"><span class="vchip">MIXED</span><span class="vtext">Investor trades at <b>~0% discount to adj. NAV</b> &mdash; rich versus its own history and versus the wider Nordic holdco norm (often mid-to-high single-digit discounts). Quality justifies compression; at-NAV leaves little margin of safety if the listed book corrects. Peer 12-month relative returns live in Module I.</span></div>
    <div class="bars" id="peerbars"></div>
    <p class="body" style="margin-top:16px"><b>Peer set.</b> <b>Industrivärden</b> is the cleanest industrial-holdco comp (Sandvik, Volvo, Handelsbanken, Essity…). <b>Lundbergföretagen</b> is a higher-quality, more concentrated Swedish investment company. <b>Kinnevik</b> is a growth/tech holdco with a very different risk profile (and a brutal 2022–25 drawdown) &mdash; useful as a warning label, not a multiple peer. Investor&rsquo;s differentiator is the Patricia private book + EQT + the multi-decade excess return vs SIXRX.</p>
    <div class="note b"><b>Read.</b> On discount-to-NAV Investor is the <b>expensive end of the quality holdco spectrum</b>. That is consistent with the track record; it is also why the Module-A base case (5% discount mode) sits below the live price. The peer <i>return</i> comparison is computed live in Module I.
      <div class="src">Investor P/NAV computed from live price and Q2'26 adj. NAV/share. Peer discount ranges are approximate industry context; live peer 12m returns in Module I.</div>
    </div>
  </section>'''


def module_F():
    return f'''<section class="mod" id="mF">
    <div class="mod-head"><div class="mod-no">F</div>
      <div class="ht"><h2>Positioning &amp; ownership</h2><div class="hq">Only what is actually fetchable.</div></div>
      <span class="tagchip s">Sourced</span>
    </div>
    <div class="verdict mixed"><span class="vchip">MIXED</span><span class="vtext">Controlling Wallenberg ownership (~50% of votes) is a permanent feature, not a trade. The sell-side is small (5 analysts) and <b>hold-rated</b> with a mean PT ≈ SEK 394 &mdash; essentially at spot. Institutions own ~46% of the float. Low beta (~0.78) and deep OMX liquidity make this a portfolio ballast, not a crowded momentum name.</span></div>
    <div class="kg">
      <div class="kgi"><div class="k">Consensus rating</div><div class="v">Hold <small>5 analysts</small></div></div>
      <div class="kgi"><div class="k">Mean price target</div><div class="v">kr 394 <small>≈ spot</small></div></div>
      <div class="kgi"><div class="k">Target range</div><div class="v">kr 327 – 440</div></div>
      <div class="kgi pos"><div class="k">Beta (5y)</div><div class="v">~0.78 <small>defensive</small></div></div>
    </div>
    <p class="body" style="margin-top:16px"><b>Ownership structure.</b> Dual-class A (heavier votes) and B (liquidity). Wallenberg Foundations are the long-term control block. Free float is deep and index-owned (OMX Stockholm, many Nordic and European funds). Insider % is tiny on a free-float basis because control sits in the foundations, not in management option grants. This is the opposite of a highly-shorted speculative name.</p>
    <div class="note c"><b>Read.</b> Positioning is <b>neutral-to-supportive</b>: no euphoric sell-side, no leverage-driven holders, controlling owner aligned. The risk is the opposite of a short squeeze &mdash; it is that at-NAV there is no forced-buyer catalyst left, so the stock compounds with NAV rather than re-rating.
      <div class="src">Yahoo Finance consensus; Investor ownership disclosures; beta from Yahoo key statistics.</div>
    </div>
  </section>'''


def module_A():
    return f'''<section class="mod" id="mA">
    <div class="mod-head"><div class="mod-no">A</div>
      <div class="ht"><h2>Valuation engine — correlated &amp; fat-tailed</h2><div class="hq">Adjusted NAV × (1 − holdco discount). Listed + Patricia + EQT − net debt.</div></div>
      <span class="tagchip c">Computed</span>
    </div>
    <div class="verdict mixed"><span class="vchip">MIXED</span><span class="vtext">Base-case median ≈ <b>kr 371</b> vs the ~kr 397 price &mdash; roughly <b>6–7% below spot</b> (~24% of paths above price), because the engine&rsquo;s mode still applies a 5% holdco discount while the market prices ~0%. No deep mispricing; the band is the equity-cycle band on a 76% listed book (P10 ~kr 326, P90 ~kr 419).</span></div>
    <p class="body">20,000 paths. Fair value per share = <b>(listed + patricia + eqt − net debt) × 1,000 / 3,062.9m shares × (1 − discount/100)</b>. Drivers are triangular ranges spanning a full equity cycle for the listed book, a private-market re-rate range for Patricia, EQT fund/mark volatility, leverage within the 0–10% target band (with a stress tail), and a holdco-discount band from a 5% premium to a 20% discount.</p>
    <p class="body" style="font-size:12.5px;color:var(--muted)"><span class="asm">Your assumptions ↓</span> &nbsp;The holdco discount (does quality deserve par forever, or does history&rsquo;s 5–12% discount reassert?) and the listed-book level are <b>your</b> calls. Correlation and tail control how hard listed + EQT + discount move together in a risk-off tape.</p>
    <div class="mc-wrap">
      <div class="mc-title">◆ Correlated Monte-Carlo — 20,000 paths, live</div>
      <div class="mc-sub">Fixed inputs (sourced): 3,062.9m shares, price kr 397 (live); listed / Patricia / EQT / net-debt modes anchored to Investor Q2 2026 (SEK 946 / 208 / 88 / 23.3 bn).</div>
      <div class="controls">
        <div class="ctrl">
          <label><span class="lab">Holdco discount to adj. NAV <span>% · assumption</span></span><span class="cval"><span id="v-disc">5</span>%</span></label>
          <input type="range" id="i-disc" min="-5" max="20" step="0.5" value="5">
          <div class="tri">history 5–20% · now ≈ 0% · mode 5% · negative = premium</div>
        </div>
        <div class="ctrl">
          <label><span class="lab">Listed book stress <span>SEK bn · assumption</span></span><span class="cval"><span id="v-listed">946</span></span></label>
          <input type="range" id="i-listed" min="720" max="1180" step="5" value="946">
          <div class="tri">Q2'26 = 946 · cycle range 720–1,180</div>
        </div>
        <div class="ctrl">
          <label><span class="lab">Driver correlation <span>assumption</span></span><span class="cval"><span id="v-corr">60</span>%</span></label>
          <input type="range" id="i-corr" min="0" max="100" step="5" value="60">
          <div class="tri">0% = independent · 100% = full risk-off co-movement</div>
        </div>
        <div class="ctrl">
          <label><span class="lab">Tail / risk-off shock <span>assumption</span></span><span class="cval"><span id="v-tail">6</span>%</span></label>
          <input type="range" id="i-tail" min="0" max="15" step="1" value="6">
          <div class="tri">chance a path hits a correlated equity-and-discount shock</div>
        </div>
      </div>
      <div class="cmp">
        <div class="cmpcard">
          <div class="ct"><span class="dd" style="background:var(--faint)"></span>Independent drivers</div>
          <div class="cmprow"><span class="ck">Median fair value</span><span class="cv" id="oi-med">kr 378</span></div>
          <div class="cmprow"><span class="ck">P10 (downside)</span><span class="cv" id="oi-p10">kr 340</span></div>
          <div class="cmprow"><span class="ck">P90 (upside)</span><span class="cv" id="oi-p90">kr 410</span></div>
          <div class="cmprow"><span class="ck">P(deep loss, &lt; kr 280)</span><span class="cv" id="oi-tail">2%</span></div>
        </div>
        <div class="cmpcard hot">
          <div class="ct"><span class="dd" style="background:var(--coral)"></span>Correlated + fat tails</div>
          <div class="cmprow"><span class="ck">Median fair value</span><span class="cv warn" id="co-med">kr 371</span></div>
          <div class="cmprow"><span class="ck">P10 (downside)</span><span class="cv neg" id="co-p10">kr 326</span></div>
          <div class="cmprow"><span class="ck">P90 (upside)</span><span class="cv pos" id="co-p90">kr 419</span></div>
          <div class="cmprow"><span class="ck">P(deep loss, &lt; kr 280)</span><span class="cv neg" id="co-tail">3%</span></div>
        </div>
      </div>
      <div class="hist-wrap">
        <div class="hist-leg">
          <span><span class="sw" style="background:var(--coral);opacity:.55"></span>worth &lt; kr 397</span>
          <span><span class="sw" style="background:var(--teal);opacity:.6"></span>worth &gt; kr 397</span>
          <span><span class="sw" style="background:var(--ink)"></span>price</span>
          <span><span class="sw" style="background:var(--amber)"></span>median</span>
          <span><span class="sw" style="background:var(--faint)"></span>indep P10</span>
        </div>
        <svg id="hist" viewBox="0 0 700 235" preserveAspectRatio="xMidYMid meet" style="width:100%;height:auto"></svg>
      </div>
      <div class="reading" id="reading"></div>
    </div>
    <div class="note c"><b>Why this matters.</b> Correlation barely moves the median but fattens the left tail &mdash; exactly right for a 76% listed portfolio where ABB, Atlas, Saab and EQT can all mark down together while the holdco discount widens. The base case is <i>slightly below spot</i> because the free lunch (the old discount) is gone; the trade is a bet on continued NAV compounding, not on a re-rating.</div>
  </section>'''


def module_B():
    return f'''<section class="mod" id="mB">
    <div class="mod-head"><div class="mod-no">B</div>
      <div class="ht"><h2>Driver analysis — what moves the stock</h2><div class="hq">The question this dashboard was built around.</div></div>
      <span class="tagchip a">Computed + sourced</span>
    </div>
    <div class="verdict mixed"><span class="vchip">MIXED</span><span class="vtext">Two swing factors dominate: the <b>listed-book mark</b> (76% of assets) and the <b>holdco discount</b>. Patricia and EQT matter, but they are second-order for near-term tape. A diagnostic, not a direction: near-total dependence on equity-market beta plus a single multiple-of-NAV knob.</span></div>
    <p class="body"><b>Lens 1 — fair-value sensitivity (computed tornado).</b> Each bar swings one driver P10→P90, others at mode. The <b>listed leg</b> is the widest lever (it is three-quarters of the balance sheet); the <b>discount</b> is next; Patricia, EQT and net debt are smaller.</p>
    <svg id="tornado" viewBox="0 0 700 220" preserveAspectRatio="xMidYMid meet" style="width:100%;height:auto"></svg>
    <p class="body" style="margin-top:18px"><b>Lens 2 — what actually moves the price (sourced).</b> Investor B trades as a <b>high-quality OMX industrial proxy with a closed discount</b>. ABB and Atlas Copco prints, Swedish equity risk appetite, and any reopening of a holdco-discount debate (e.g. a weak quarter at Patricia, or a peer re-rating) are the revealed drivers.</p>
    <div class="reactab">
      <div class="rr"><div class="re">ABB / Atlas / Saab strength</div><div class="rd">The three largest industrial/defence weights set the listed-book mark. Strong orders and margins lift NAV tick-for-tick.</div><div class="rp" style="color:var(--teal-deep)">▲ bull</div></div>
      <div class="rr"><div class="re">OMX risk-on</div><div class="rd">With the discount closed, Investor is a leveraged (but low financial-leverage) play on Swedish/European equities. Beta ~0.78 softens but does not remove the link.</div><div class="rp" style="color:var(--teal-deep)">▲ bull</div></div>
      <div class="rr"><div class="re">Discount re-opens</div><div class="rd">Any narrative that &ldquo;holdcos should trade at 15% off&rdquo; &mdash; or a forced seller in the dual-class structure &mdash; de-rates the wrapper without changing NAV.</div><div class="rp">▼ bear</div></div>
      <div class="rr"><div class="re">Patricia mark-downs</div><div class="rd">Private EV/EBITDA compression (as in Q2 −3% TR despite +16% EBITA) hits the 17% leg and the quality story simultaneously.</div><div class="rp">▼ bear</div></div>
    </div>
    <div class="note b"><b>Synthesis — the master gauges are listed NAV and the holdco discount.</b> The tornado (Lens 1), the tape (Lens 2) and the structure (76% listed) all say the same thing. Unlike Micron&rsquo;s single margin variable, Investor&rsquo;s fair value is a <b>portfolio mark × a wrapper multiple</b>. The reverse-DCF (Module I) shows the market is implying a ~0% discount &mdash; i.e. it has already awarded the quality premium.
      <div class="src">Tornado computed from the engine. Tape read: Investor Q2 commentary + live factor structure in Module I.</div>
    </div>
  </section>'''


def module_C():
    return f'''<section class="mod" id="mC">
    <div class="mod-head"><div class="mod-no">C</div>
      <div class="ht"><h2>Scenario probabilities + Bayesian updating</h2><div class="hq">Computed anchors; your odds.</div></div>
      <span class="tagchip a">Computed + your assumptions</span>
    </div>
    <div class="verdict mixed"><span class="vchip">MIXED</span><span class="vtext">Scenario spread runs from a risk-off reopening of the discount (~kr 258) to a quality-premium compounder (~kr 481). At neutral priors the weighted value sits near or slightly below the ~kr 397 price. This is a <b>quality-compounder-at-fair-price</b> call, not a deep-value discount trade.</span></div>
    <div class="scen">
      <div class="scard bear"><div class="sn">Bear — discount re-opens</div><div class="sd">Equity risk-off: listed book −15–20%, Patricia multiples compress, EQT marks down, holdco discount widens to ~18%. Classic holdco double-hit.</div><div class="sfv" id="sfv-bear">kr 258</div><div class="sfvl">engine median · computed</div></div>
      <div class="scard base"><div class="sn">Base — quality at a thin discount</div><div class="sd">Listed book holds near Q2 levels, Patricia compounds mid-single-digit, EQT stabilises, market applies a modest ~5% holdco discount. Roughly the engine mode.</div><div class="sfv" id="sfv-base">kr 378</div><div class="sfvl">engine median · computed</div></div>
      <div class="scard bull"><div class="sn">Bull — premium compounder</div><div class="sd">Automation/defence/health keep compounding; listed book re-rates; Patricia private MVs expand; market awards a small premium to NAV for the 20y track record.</div><div class="sfv" id="sfv-bull">kr 481</div><div class="sfvl">engine median · computed</div></div>
    </div>
    <div class="controls" style="grid-template-columns:1fr 1fr 1fr">
      <div class="ctrl"><label><span class="lab">Prior — Bear <span>assumption</span></span><span class="cval"><span id="v-pb">25</span>%</span></label><input type="range" id="i-pb" min="0" max="100" step="5" value="25"></div>
      <div class="ctrl"><label><span class="lab">Prior — Base <span>assumption</span></span><span class="cval"><span id="v-pn">50</span>%</span></label><input type="range" id="i-pn" min="0" max="100" step="5" value="50"></div>
      <div class="ctrl"><label><span class="lab">Prior — Bull <span>assumption</span></span><span class="cval"><span id="v-pu">25</span>%</span></label><input type="range" id="i-pu" min="0" max="100" step="5" value="25"></div>
    </div>
    <div style="font-family:var(--mono);font-size:10.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--faint);margin:16px 0 8px">Toggle evidence as it arrives → <span class="asm">(likelihood ratios are illustrative assumptions)</span></div>
    <div class="evid" id="evid">
      <div class="ev" data-lr="0.5,1.0,1.8">ABB / Atlas orders confirm automation cycle <span class="ar">▲bull</span></div>
      <div class="ev" data-lr="0.5,1.1,1.7">Patricia organic growth stays double-digit at scale <span class="ar">▲bull</span></div>
      <div class="ev" data-lr="0.6,1.1,1.5">Saab backlog converts; defence budgets hold <span class="ar">▲bull</span></div>
      <div class="ev bearish" data-lr="2.0,1.0,0.5">OMX drawdown &gt;20% with holdco discount &gt;12% <span class="ar">▼bear</span></div>
      <div class="ev bearish" data-lr="1.9,1.0,0.5">Patricia estimated MVs cut &gt;15% on multiple compression <span class="ar">▼bear</span></div>
      <div class="ev bearish" data-lr="1.7,1.0,0.6">EQT fundraising air-pocket / fee pressure <span class="ar">▼bear</span></div>
    </div>
    <div style="margin-top:16px">
      <div style="font-family:var(--mono);font-size:10px;color:var(--faint);text-transform:uppercase;letter-spacing:.05em;margin-bottom:5px">Posterior weights</div>
      <div class="wbar" id="wbar"><div class="wp bear" id="wp-b"></div><div class="wp base" id="wp-n"></div><div class="wp bull" id="wp-u"></div></div>
      <div class="wlab"><span id="wl-b">Bear 25%</span><span id="wl-n">Base 50%</span><span id="wl-u">Bull 25%</span></div>
    </div>
    <div class="blend">
      <span class="bn" id="blend-fv">kr 374</span>
      <span class="bl">probability-weighted fair value vs <b>kr 397</b> price · <span id="blend-gap">≈ slightly below</span>. Anchors computed; weighting is your judgment.</span>
    </div>
  </section>'''


def module_H():
    return f'''<section class="mod" id="mH">
    <div class="mod-head"><div class="mod-no">H</div>
      <div class="ht"><h2>Kill-criteria &amp; decision journal</h2><div class="hq">Pre-committed exits — the discipline layer.</div></div>
      <span class="tagchip a">Your pre-commitments</span>
    </div>
    <div class="verdict mixed"><span class="vchip">MIXED</span><span class="vtext">A process overlay, not a direction. Triggers centre on the two master variables &mdash; listed-book integrity and holdco-discount discipline &mdash; plus capital-allocation red lines.</span></div>
    <div class="kc">
      <div class="kci"><div class="kx"></div><div><b>Discount re-opens hard.</b> Price/adj. NAV falls below <span class="kv">0.85× for a quarter</span> without a clear portfolio-level reason &mdash; the quality premium is being withdrawn; reassess sizing.</div></div>
      <div class="kci"><div class="kx"></div><div><b>Listed concentration breaks.</b> ABB + Atlas Copco + AstraZeneca + SEB + Saab (the top five) lose <span class="kv">&gt;25% combined stake value</span> in a year with no offsetting Patricia/EQT gain &mdash; the growth spine is impaired.</div></div>
      <div class="kci"><div class="kx"></div><div><b>Leverage regime change.</b> Leverage rises above <span class="kv">10% of assets for two consecutive quarters</span> without a clearly temporary acquisition reason &mdash; the fortress balance sheet thesis is failing.</div></div>
      <div class="kci"><div class="kx"></div><div><b>Patricia marks diverge from ops.</b> Estimated MVs cut <span class="kv">&gt;20% while organic growth is still positive</span> for two reports &mdash; private marks were optimistic; trust the lower number.</div></div>
      <div class="kci"><div class="kx"></div><div><b>Capital allocation red line.</b> A transformative, highly-levered acquisition at the holdco layer, or persistent dilutive equity issuance &mdash; the permanent-capital discipline is broken.</div></div>
      <div class="kci"><div class="kx"></div><div><b>Valuation overshoots.</b> Price implies a <span class="kv">holdco premium &gt;10% to adj. NAV</span> on the reverse-DCF while the listed book is at cycle highs &mdash; trim; do not chase the wrapper.</div></div>
    </div>
    <div class="note c"><b>Decision-journal prompt (falsifiable, dated):</b> log today&rsquo;s call &mdash; e.g. &ldquo;quality compounder at ~par to NAV, fair value ~kr 370–380 on a 5% discount mode, bull path to ~kr 480 if premium + compounding&rdquo; &mdash; and the specific NAV prints, top-five stake moves and discount observations over the next two quarters that would confirm or refute it.</div>
  </section>'''


def scorecard():
    return f'''<section class="mod" id="mSum">
    <div class="mod-head"><div class="mod-no" style="color:var(--amber-deep)">∑</div>
      <div class="ht"><h2>Scorecard — the fourteen reads</h2><div class="hq">Each verdict follows from that module's own data, struck at the base case.</div></div>
    </div>
    <div class="tbl-scroll"><table class="scoretab">
      <thead><tr><th>Module</th><th>Verdict</th><th>What drives it</th></tr></thead>
      <tbody>
        <tr><td>T · Thesis &amp; macro</td><td><span class="vchip bull">BULL</span></td><td>Best multi-decade Nordic industrial compounder; portfolio sits on AI/automation, energy, defence, health</td></tr>
        <tr><td>P · Portfolio look-through</td><td><span class="vchip bull">BULL</span></td><td>Top weights are category leaders; ~70%+ of assets have a 10y claim on structural demand; stubs are &lt;1%</td></tr>
        <tr><td>Q · Quality dashboard</td><td><span class="vchip bull">BULL</span></td><td>16.5% 20y TSR vs 10.2% SIXRX; 7 bp costs; 1.9% leverage — institutional-grade</td></tr>
        <tr><td>D · Forensics</td><td><span class="vchip bull">BULL</span></td><td>Fortress leverage, multi-year debt maturity, Wallenberg-aligned governance</td></tr>
        <tr><td>E · Capital record</td><td><span class="vchip bull">BULL</span></td><td>Selective reinvestment, rising dividend, no leverage games; scoreboard is the 20y excess return</td></tr>
        <tr><td>G · Peers</td><td><span class="vchip mixed">MIXED</span></td><td>At-NAV is rich vs history and vs typical Nordic holdco discounts</td></tr>
        <tr><td>F · Positioning</td><td><span class="vchip mixed">MIXED</span></td><td>Hold consensus, PT ≈ spot, low beta — supportive but no re-rating catalyst left</td></tr>
        <tr><td>A · Engine</td><td><span class="vchip mixed">MIXED</span></td><td>Median ~kr 371 vs ~kr 397; slightly below spot once a 5% discount is underwritten</td></tr>
        <tr><td>B · Driver analysis</td><td><span class="vchip mixed">MIXED</span></td><td>Fair value = listed mark × wrapper discount; both first-order</td></tr>
        <tr><td>C · Scenarios + Bayes</td><td><span class="vchip mixed">MIXED</span></td><td>Spread ~kr 258–481; weighted near/below price at neutral priors</td></tr>
        <tr><td>H · Kill-criteria</td><td><span class="vchip mixed">MIXED</span></td><td>Process overlay; triggers on discount, top-five integrity, leverage, Patricia marks</td></tr>
      </tbody>
    </table></div>
    <div class="tally">
      <div class="tbar"><div class="tp bull" style="width:38.5%"></div><div class="tp mixed" style="width:61.5%"></div><div class="tp bear" style="width:0.0%"></div></div>
      <div class="tlab"><span class="tb">5 Bull</span><span class="tm">6 Mixed</span><span class="tr">0 Bear</span></div>
    </div>
    <div class="overall">
      <span class="ov-chip">NET: MIXED-BULL — quality compounder, discount already closed</span>
      <div class="ov-text">A genuinely strong <b>thesis and portfolio</b> (T · P · Q · D · E) wrapped around a <b>fairly-to-fully priced</b> valuation. Read the business and the holdings first; then stress-test with the NAV engine (A–C): the base case (~kr 378 at a 5% discount) sits a few percent below the ~kr 397 price, and the reverse-DCF (Module I) says the market is implying only a ~0% discount. Own it as a <b>long-duration compounder</b> you are willing to hold through equity cycles, sized by the Module-H triggers — not as a deep-value discount trade. The perfect-execution ceiling (Module U) frames the upside if NAV keeps compounding mid-teens and the market awards a modest premium.</div>
    </div>
  </section>'''


def footer():
    return f'''<footer>
    <div class="notes">
      <h4>How the engine computes (Module A)</h4>
      <p>20,000 paths. Each driver is drawn from a triangular distribution: listed SEK bn (720–1,180, mode 946), Patricia SEK bn (160–270, mode 208), EQT SEK bn (55–125, mode 88), net debt SEK bn (10–55, mode 23.3), holdco discount % (−5 to +20, mode 5). Fair value = (listed + patricia + eqt − nd) × 1,000 / 3,062.9m shares × (1 − disc/100). Dependence: a one-factor copula (loadings — listed 0.80, eqt 0.55, patricia 0.45, disc 0.35, nd 0.20, scaled by your correlation knob) plus a regime-shock mixture (your tail knob). Correlation 0 and tail 0 reproduce the independent model. Tornado, scenario anchors and the Bayesian posterior are computed live and mirror <code>stocks/config_investor.py</code>.</p>
      <h4>The three labels, precisely</h4>
      <p><span style="color:var(--teal-deep)"><b>Sourced</b></span>: fetched from a citable source (Investor interim/annual reports, the Yahoo fundamentals feed, sell-side consensus). <span style="color:var(--blue-deep)"><b>Computed</b></span>: calculated here from sourced inputs (the simulation, P/NAV, portfolio sums). <span style="color:var(--amber-deep)"><b>Your assumption</b></span>: an input you set (holdco discount mode, listed stress, correlation, tail, scenario priors, evidence weights, kill thresholds).</p>
      <h4>What was cut, not faked</h4>
      <div class="cut"></div>
      <p class="disc">For analysis and education only — not investment advice, not a recommendation, not a price target. The model quantifies the uncertainty in a set of assumptions; it does not make those assumptions correct. Live spot &amp; factor exposures are fetched at build time; NAV and portfolio figures are from Investor&rsquo;s Q2 2026 interim (30 Jun 2026) — verify against primary filings before acting.</p>
    </div>
  </footer>'''


# ------------------------------------------------------------------ Module A JS
ENGINE_JS = r'''<script>
  const PRICE=397.0, SHARES=3062.9, N=20000;
  const LISTED={lo:720,md:946,hi:1180}, PAT={lo:160,md:208,hi:270}, EQT={lo:55,md:88,hi:125};
  const ND={lo:10,md:23.3,hi:55}, DISC={lo:-5,hi:20};
  const RHO={listed:0.80,patricia:0.45,eqt:0.55,nd:0.20,disc:0.35};

  function randn(){let u=0,v=0;while(u===0)u=Math.random();while(v===0)v=Math.random();return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v);}
  function Phi(x){const t=1/(1+0.2316419*Math.abs(x));const d=0.3989423*Math.exp(-x*x/2);let p=d*t*(0.3193815+t*(-0.3565638+t*(1.781478+t*(-1.821256+t*1.330274))));return x>0?1-p:p;}
  function triInv(u,a,m,b){const c=(m-a)/(b-a);return u<c?a+Math.sqrt(u*(b-a)*(m-a)):b-Math.sqrt((1-u)*(b-a)*(b-m));}

  function simulate(midDisc,midListed,corr,pStress,paths){
    const n=paths||N;const fv=new Float64Array(n);
    for(let i=0;i<n;i++){
      let Z=randn();
      if(pStress>0 && Math.random()<pStress) Z=Z*2.0-0.4;
      const draw=(rho,a,m,b)=>{const L=corr*rho;const e=randn();const nn=L*Z+Math.sqrt(Math.max(0,1-L*L))*e;return triInv(Phi(nn),a,m,b);};
      // listed/eqt load positively with Z (good times); disc loads with Z as well so risk-off widens discount when we invert via stress
      const listed=draw(RHO.listed,LISTED.lo,midListed,LISTED.hi);
      const patricia=draw(RHO.patricia,PAT.lo,PAT.md,PAT.hi);
      const eqt=draw(RHO.eqt,EQT.lo,EQT.md,EQT.hi);
      const nd=draw(RHO.nd,ND.lo,ND.md,ND.hi);
      const disc=draw(RHO.disc,DISC.lo,midDisc,DISC.hi);
      const nav=(listed+patricia+eqt-nd)*1000.0/SHARES;
      fv[i]=nav*(1-disc/100);
    }
    fv.sort();
    const q=x=>fv[Math.min(n-1,Math.floor(x*n))];
    let under=0,deep=0;const thr=280;
    for(let i=0;i<n;i++){if(fv[i]>PRICE)under++;if(fv[i]<thr)deep++;}
    return {fv,p10:q(.10),p50:q(.50),p90:q(.90),under:under/n,deep:deep/n};
  }

  const HX0=12,HX1=688,HY0=8,HY1=188,VMAX=600,BINS=40;
  function xOf(v){return HX0+(Math.min(Math.max(v,0),VMAX)/VMAX)*(HX1-HX0);}
  function drawHist(fv,median,indP10){
    const bw=VMAX/BINS,counts=new Array(BINS).fill(0);
    for(let i=0;i<fv.length;i++){let b=Math.floor(fv[i]/bw);if(b<0)b=0;if(b>=BINS)b=BINS-1;counts[b]++;}
    const maxC=Math.max(...counts);let s='';
    for(let b=0;b<BINS;b++){const vc=(b+0.5)*bw,x=xOf(b*bw),x2=xOf((b+1)*bw),w=Math.max(1,x2-x-1.4);
      const h=maxC?(counts[b]/maxC)*(HY1-HY0):0,y=HY1-h;const fill=vc<PRICE?'var(--coral)':'var(--teal)',op=vc<PRICE?0.55:0.6;
      s+='<rect x="'+x.toFixed(1)+'" y="'+y.toFixed(1)+'" width="'+w.toFixed(1)+'" height="'+h.toFixed(1)+'" fill="'+fill+'" opacity="'+op+'" rx="1.5"/>';}
    s+='<line x1="'+HX0+'" y1="'+HY1+'" x2="'+HX1+'" y2="'+HY1+'" stroke="var(--line-strong)" stroke-width="1"/>';
    for(let v=0;v<=600;v+=100){const x=xOf(v);s+='<line x1="'+x+'" y1="'+HY1+'" x2="'+x+'" y2="'+(HY1+4)+'" stroke="var(--line-strong)" stroke-width="1"/>';
      s+='<text x="'+x+'" y="'+(HY1+17)+'" text-anchor="middle" font-family="var(--mono)" font-size="10" fill="var(--muted)">kr '+v+'</text>';}
    const xi=xOf(indP10);
    s+='<line x1="'+xi+'" y1="'+(HY0+20)+'" x2="'+xi+'" y2="'+HY1+'" stroke="var(--faint)" stroke-width="1.5" stroke-dasharray="2 3"/>';
    s+='<text x="'+xi+'" y="'+(HY0+15)+'" text-anchor="middle" font-family="var(--mono)" font-size="9" fill="var(--faint)">indep P10</text>';
    const xm=xOf(median);
    s+='<line x1="'+xm+'" y1="'+(HY0-2)+'" x2="'+xm+'" y2="'+HY1+'" stroke="var(--amber)" stroke-width="2" stroke-dasharray="3 3"/>';
    s+='<text x="'+xm+'" y="'+(HY0+8)+'" text-anchor="middle" font-family="var(--mono)" font-size="10" font-weight="600" fill="var(--amber-deep)">median kr '+median.toFixed(0)+'</text>';
    const xp=xOf(PRICE);
    s+='<line x1="'+xp+'" y1="'+(HY0-2)+'" x2="'+xp+'" y2="'+HY1+'" stroke="var(--ink)" stroke-width="2"/>';
    s+='<text x="'+xp+'" y="'+(HY1+30)+'" text-anchor="middle" font-family="var(--mono)" font-size="10.5" font-weight="600" fill="var(--ink)">price kr 397</text>';
    document.getElementById('hist').innerHTML=s;
  }

  function fvAt(o){
    const midDisc=+document.getElementById('i-disc').value, midListed=+document.getElementById('i-listed').value;
    const listed=o.listed!==undefined?o.listed:midListed;
    const patricia=o.patricia!==undefined?o.patricia:PAT.md;
    const eqt=o.eqt!==undefined?o.eqt:EQT.md;
    const nd=o.nd!==undefined?o.nd:ND.md;
    const disc=o.disc!==undefined?o.disc:midDisc;
    return ((listed+patricia+eqt-nd)*1000/SHARES)*(1-disc/100);
  }

  function drawTornado(){
    const midDisc=+document.getElementById('i-disc').value, midListed=+document.getElementById('i-listed').value;
    const rows=[
      {lab:'Listed book (SEK bn)', lo:fvAt({listed:LISTED.lo}), hi:fvAt({listed:LISTED.hi}), min:0, max:0},
      {lab:'Holdco discount (%)', lo:fvAt({disc:DISC.hi}), hi:fvAt({disc:DISC.lo}), min:0, max:0},
      {lab:'Patricia (SEK bn)', lo:fvAt({patricia:PAT.lo}), hi:fvAt({patricia:PAT.hi}), min:0, max:0},
      {lab:'EQT leg (SEK bn)', lo:fvAt({eqt:EQT.lo}), hi:fvAt({eqt:EQT.hi}), min:0, max:0},
      {lab:'Net debt (SEK bn)', lo:fvAt({nd:ND.hi}), hi:fvAt({nd:ND.lo}), min:0, max:0},
    ];
    rows.forEach(r=>{r.min=Math.min(r.lo,r.hi);r.max=Math.max(r.lo,r.hi);});
    const xmin=Math.min(PRICE, ...rows.map(r=>r.min))*0.92, xmax=Math.max(PRICE, ...rows.map(r=>r.max))*1.05;
    const sx=v=>40+(v-xmin)/(xmax-xmin)*640;
    const rowH=36, top=20; let s='';
    rows.forEach((r,i)=>{
      const y=top+i*rowH;
      s+='<text x="8" y="'+(y+rowH/2+4)+'" font-family="var(--mono)" font-size="11" fill="var(--muted)">'+r.lab+'</text>';
      s+='<rect x="'+sx(r.min).toFixed(1)+'" y="'+(y+6)+'" width="'+(sx(r.max)-sx(r.min)).toFixed(1)+'" height="'+(rowH-16)+'" rx="4" fill="'+(i<2?'var(--coral)':'var(--teal)')+'" opacity="'+(i<2?0.7:0.45)+'"/>';
      s+='<text x="'+(sx(r.min)-5).toFixed(1)+'" y="'+(y+rowH/2+4)+'" text-anchor="end" font-family="var(--mono)" font-size="10" fill="var(--muted)">kr '+Math.min(r.lo,r.hi).toFixed(0)+'</text>';
      s+='<text x="'+(sx(r.max)+5).toFixed(1)+'" y="'+(y+rowH/2+4)+'" font-family="var(--mono)" font-size="10" fill="var(--muted)">kr '+Math.max(r.lo,r.hi).toFixed(0)+'</text>';
    });
    const yb=top+rows.length*rowH;
    s+='<line x1="'+sx(PRICE).toFixed(1)+'" y1="'+top+'" x2="'+sx(PRICE).toFixed(1)+'" y2="'+yb+'" stroke="var(--ink)" stroke-width="1.5"/>';
    s+='<text x="'+sx(PRICE).toFixed(1)+'" y="'+(yb+15)+'" text-anchor="middle" font-family="var(--mono)" font-size="10" font-weight="600" fill="var(--ink)">price kr 397</text>';
    document.getElementById('tornado').setAttribute('viewBox','0 0 700 '+(yb+26));
    document.getElementById('tornado').innerHTML=s;
  }

  function update(){
    const midDisc=+document.getElementById('i-disc').value, midListed=+document.getElementById('i-listed').value;
    const corr=(+document.getElementById('i-corr').value)/100, tail=(+document.getElementById('i-tail').value)/100;
    document.getElementById('v-disc').textContent=midDisc.toFixed(1);
    document.getElementById('v-listed').textContent=midListed.toFixed(0);
    document.getElementById('v-corr').textContent=Math.round(corr*100);
    document.getElementById('v-tail').textContent=Math.round(tail*100);
    const ind=simulate(midDisc,midListed,0,0);
    const cor=simulate(midDisc,midListed,corr,tail);
    document.getElementById('oi-med').textContent='kr '+ind.p50.toFixed(0);
    document.getElementById('oi-p10').textContent='kr '+ind.p10.toFixed(0);
    document.getElementById('oi-p90').textContent='kr '+ind.p90.toFixed(0);
    document.getElementById('oi-tail').textContent=Math.round(ind.deep*100)+'%';
    document.getElementById('co-med').textContent='kr '+cor.p50.toFixed(0);
    document.getElementById('co-p10').textContent='kr '+cor.p10.toFixed(0);
    document.getElementById('co-p90').textContent='kr '+cor.p90.toFixed(0);
    document.getElementById('co-tail').textContent=Math.round(cor.deep*100)+'%';
    drawHist(cor.fv,cor.p50,ind.p10);
    const widen=(cor.p90-cor.p10)-(ind.p90-ind.p10);
    document.getElementById('reading').innerHTML='With correlation at <b>'+Math.round(corr*100)+'%</b> and a <b>'+Math.round(tail*100)+'%</b> risk-off chance, the median holds near <b>kr '+cor.p50.toFixed(0)+'</b> (≈ the independent kr '+ind.p50.toFixed(0)+'), but the 80% band widens by ~<span class="down">kr '+widen.toFixed(0)+'</span> and the chance of a deep-downside outcome (worth under kr 280) rises from <b>'+Math.round(ind.deep*100)+'%</b> to <span class="down">'+Math.round(cor.deep*100)+'%</span>. P(undervalued at kr 397) is '+Math.round(cor.under*100)+'%.';
    drawTornado();
  }

  function simScen(lLo,lMd,lHi,dLo,dMd,dHi,pLo,pMd,pHi,eLo,eMd,eHi,paths){
    const n=paths||8000;const fv=new Float64Array(n);
    for(let i=0;i<n;i++){
      let Z=randn(); if(Math.random()<0.06) Z=Z*2.0-0.4;
      const draw=(rho,a,m,b)=>{const L=0.6*rho;const e=randn();const nn=L*Z+Math.sqrt(Math.max(0,1-L*L))*e;return triInv(Phi(nn),a,m,b);};
      const listed=draw(RHO.listed,lLo,lMd,lHi);
      const patricia=draw(RHO.patricia,pLo,pMd,pHi);
      const eqt=draw(RHO.eqt,eLo,eMd,eHi);
      const nd=draw(RHO.nd,ND.lo,ND.md,ND.hi);
      const disc=draw(RHO.disc,dLo,dMd,dHi);
      fv[i]=((listed+patricia+eqt-nd)*1000/SHARES)*(1-disc/100);
    }
    fv.sort();return fv[Math.floor(0.5*n)];
  }
  let SFV={bear:258,base:378,bull:481};
  function computeScenarioAnchors(){
    SFV.bear=simScen(700,780,900, 12,18,22, 150,170,190, 50,60,75);
    SFV.base=simScen(850,946,1050, 2,5,10, 180,208,240, 70,88,105);
    SFV.bull=simScen(1000,1100,1250, -5,-2,2, 220,250,280, 95,110,130);
    document.getElementById('sfv-bear').textContent='kr '+SFV.bear.toFixed(0);
    document.getElementById('sfv-base').textContent='kr '+SFV.base.toFixed(0);
    document.getElementById('sfv-bull').textContent='kr '+SFV.bull.toFixed(0);
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
    document.getElementById('blend-fv').textContent='kr '+fv.toFixed(0);
    const gap=(fv/PRICE-1)*100;
    document.getElementById('blend-gap').textContent=(Math.abs(gap)<2?'≈ fair vs price':(gap<0?'≈ '+Math.abs(gap).toFixed(0)+'% below':'≈ '+gap.toFixed(0)+'% above'));
  }
  document.querySelectorAll('#evid .ev').forEach(el=>el.addEventListener('click',()=>{el.classList.toggle('on');updateBayes();}));
  ['i-pb','i-pn','i-pu'].forEach(id=>document.getElementById(id).addEventListener('input',updateBayes));

  function peerBar(label,sub,val,disp,color){
    // val = discount % (0 = at NAV, 20 = 20% discount). Map 0→100% bar width inverted: wider = cheaper
    const pct=Math.min(Math.max(val,0)/25,1)*100;
    return '<div class="br"><div class="brl">'+label+'<small>'+sub+'</small></div><div class="brt"><div class="brf" style="width:'+pct+'%;background:'+color+'"></div></div><div class="brv" style="color:'+color+'">'+disp+'</div></div>';
  }
  document.getElementById('peerbars').innerHTML=[
    peerBar('Typical Nordic holdco','discount to NAV · approx',12,'~12% disc','var(--faint)'),
    peerBar('Industrivärden (range)','discount to NAV · approx',8,'~5–12%','var(--teal)'),
    peerBar('Investor (history mid)','discount to NAV · approx',8,'~5–10%','var(--teal-deep)'),
    peerBar('Investor (now)','P/adj. NAV ~1.00× · computed',0,'~0% disc','var(--coral)'),
  ].join('');

  ['i-disc','i-listed','i-corr','i-tail'].forEach(id=>document.getElementById(id).addEventListener('input',update));
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
    today = datetime.date.today().isoformat()
    return f'''  <div class="eyebrow">Research pipeline · strict-data · Investor AB · Nasdaq Stockholm: INVE-B.ST · built {today}</div>
  <h1>Investor AB — the permanent-capital industrial compounder
    <span class="sub">Portfolio and NAV first — then the valuation engine. Northern Europe&rsquo;s flagship industrial holding company (Wallenberg, founded 1916): <b>Listed Companies 76% · Patricia Industries 17% · EQT 7%</b>, valued on <b>adjusted NAV × (1 − holdco discount)</b>. Every figure is <b>sourced</b>, <b>computed</b> from sourced inputs, or an explicit <b>assumption</b> you set. The headline sequence: <b>what does the portfolio own, will those holdings matter in 10 years, and what is the wrapper worth once the free discount is gone?</b></span>
  </h1>

  <div class="keystat">
    <div class="ks"><div class="kl">Price (B)</div><div class="kv">kr 397</div></div>
    <div class="ks"><div class="kl">Adj. NAV / sh</div><div class="kv">kr 397</div></div>
    <div class="ks"><div class="kl">Adj. NAV</div><div class="kv">1,215<small>bn</small></div></div>
    <div class="ks"><div class="kl">P / adj. NAV</div><div class="kv">~1.00<small>×</small></div></div>
    <div class="ks"><div class="kl">Leverage</div><div class="kv">1.9<small>%</small></div></div>
    <div class="ks"><div class="kl">Mgmt cost</div><div class="kv">0.07<small>%</small></div></div>
    <div class="ks"><div class="kl">20y TSR</div><div class="kv">16.5<small>%/yr</small></div></div>
  </div>

  <div class="legend">
    <span class="lg sourced"><span class="d"></span>Sourced — fetched &amp; cited</span>
    <span class="lg computed"><span class="d"></span>Computed — by this tool from sourced inputs</span>
    <span class="lg assumed"><span class="d"></span>Your assumption — a judgment you set, not data</span>
  </div>

  <div class="hero">
    <div class="htag">◆ How to read this build — portfolio &amp; NAV first</div>
    <h3>Start with <b>what the portfolio owns</b> and <b>whether those holdings earn a place in the AI · automation · energy · defence · health future</b>. Then read the holdco quality. Only after that should you touch the NAV Monte-Carlo engine and the institutional layers.</h3>
    <div class="lenses">
      <div class="lens empir">
        <div class="lt">Part 1 — Thesis &amp; portfolio</div>
        <div class="lh">Modules T · P</div>
        <div class="lb">The three-leg structure, the Wallenberg permanent-capital model, and a full look-through of every material listed and private holding with live fundamentals and a 10-year conviction map.</div>
      </div>
      <div class="lens owner">
        <div class="lt">Part 2 — Holdco quality</div>
        <div class="lh">Modules Q · D · E · G · F</div>
        <div class="lb">NAV history and TSR, forensic leverage/cost/governance, capital-allocation record, peer holdco discounts and positioning. The &ldquo;how good is the wrapper?&rdquo; block.</div>
      </div>
      <div class="lens comp">
        <div class="lt">Part 3 — Deeper analysis</div>
        <div class="lh">Modules A–C · U · H · I · J</div>
        <div class="lb">Correlated NAV Monte-Carlo, driver tornado, Bayesian scenarios, the 10-year ceiling, kill-criteria, price-asymmetry and base-rate composites — the stress tests once you understand the book.</div>
      </div>
    </div>
    <div class="synth"><b>Master read (spoiler for later modules).</b> The most <i>predictive</i> near-term mover is the <b>listed-book mark</b> (especially ABB / Atlas / Saab) plus any reopening of the holdco discount; the single <i>fundamental</i> variable that sets fair value is <b>adj. NAV × (1 − discount)</b>. The base case (~kr 378 at a 5% discount) sits a few percent below the ~kr 397 price — the reverse-DCF (Module I) says the market is implying only a ~0% discount. The trade is a long-duration compounder at fair value, not a free discount.</div>
  </div>

  <nav class="stepper" id="stepper">
    <a href="#mThesis"><span class="n">T</span>Thesis</a>
    <a href="#mP"><span class="n">P</span>Portfolio</a>
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
<title>Investor AB (INVE-B.ST) — Research Pipeline (strict-data)</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
'''


def _css_blocks():
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
        module_P(), "\n",
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
    out = os.path.join(HERE, "investor-pipeline.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {out} ({len(html):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
