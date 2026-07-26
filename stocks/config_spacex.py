"""SpaceX (NASDAQ: SPCX) — stock-specific configuration for the analytics toolkit.

HOW TO WIRE THIS IN (2 lines, no framework changes):
    At the bottom of stocks/config.py add:

        from stocks.config_spacex import SPACEX_CONFIG
        STOCKS["spacex"] = SPACEX_CONFIG

    Then:  python refresh_all.py

DATA BASIS (all figures sourced 2026-07-02, pre-run baseline — the pipeline
re-fetches the live spot/betas itself):
  - IPO 2026-06-12 on Nasdaq at a fixed $135/share, ~$75bn raised, ~$1.77tn
    IPO valuation (SEC Form 424B4 / CNBC).
  - Spot $170.86 (2026-07-01 close), market cap ≈ $2.25tn -> ~13,170m shares.
  - FY2025 (S-1): revenue $18.674bn, operating loss $2.589bn, adj. EBITDA
    $6.584bn, net loss $4.9bn. Q1'26: revenue $4.694bn (annualised $18.78bn).
  - Segments FY2025: Connectivity (Starlink) $11.4bn rev / ~$7.0bn EBITDA @63%
    / $4.4bn op profit; Space (launch) $4.086bn rev / -$657m op; AI (xAI + X)
    $3.2bn rev / -$6.35bn op loss. Long-term debt $29.1bn (Mar 2026).
  - Consensus 12m PT $187.80 (range $62-$310); EPS TTM -$2.94.
  - Sell-side 2030E revenue: Goldman $474bn, JPMorgan $470bn, Morgan Stanley
    $330bn vs Musk's ~$1tn aspiration; Starlink ~$144bn, launch ~$8.3bn, AI
    ~68% of the mix; group EBITDA ~$352bn by 2030 (Goldman).

ENGINE — sum-of-the-parts across FIVE value legs, discounted to today:
    equity ($bn) = [ ConnRev30 x ConnEBITDAmargin x EV/EBITDA          (Starlink)
                     + SpaceRev30 x EV/Sales ] / 1.10^4                (launch)
                   + [ OrbitalRev35 x EV/Sales                         (orbital DCs)
                     + FrontierRev35 x EV/Sales ] / 1.10^9             (other frontier)
                   + AI-segment EV (today, $bn)                        (xAI + X)
                   + net cash ~$25bn (post-$75bn raise less $29.1bn LT debt
                     and est. H1'26 burn — an explicit assumption)
    fair value / share = equity x 1000 / 13,170m shares

The 2025 build valued only three legs and let the AI mark absorb everything the
operating segments could not explain. This build prices SpaceX's stated deep-
space ambitions explicitly, in two frontier-class legs that share one EV/Sales
multiple (so splitting them revalues nothing at mode):
  - ORBITAL DATACENTERS (`orbital_rev`, Module N): space-based, solar-powered AI
    compute — the xAI "AI satellites" / moon-factory thesis. Its own leg because
    it is the most concrete frontier use-case, gated on Starship $/kg falling
    below ~$200-500 (Google: <$200/kg by 2035 if Starship hits ~180 launches/yr)
    — the payload-cost collapse SpaceX uniquely controls. Distinct from the
    ground Colossus already inside the AI segment, so no double-count.
  - OTHER FRONTIER (`frontier_rev`, Module M): lunar & in-space manufacturing
    ("moon factories"), payload-to-orbit new markets, point-to-point transport.
Both drivers are RISK-ADJUSTED 2035E revenue (TAM x SpaceX-capture x probability
already folded in) discounted a full nine years, so each is a genuine call
option — a material modal contribution with a long right tail, not a certainty.

The reverse-DCF (Module I) still grid-solves the AI-segment EV — the single
most-contested number and the natural residual — but Modules K, M & N now
decompose the price across all five legs so the AI mark is no longer the only
lens. xAI was acquired at ~$250bn in the Feb-2026 all-stock merger (the anchor).
"""
from __future__ import annotations

_SHARES_M    = 13170.0     # ~ $2.25tn mcap / $170.86 spot; 424B4 implies ~13.1bn post-split
_NET_CASH_BN = 25.0        # assumption: +$75bn IPO raise - $29.1bn LT debt - est. burn
_DISC_2030   = 1.10 ** 4   # operating legs (Starlink, launch) on 2030E, discounted 4y at 10%
_DISC_2035   = 1.10 ** 9   # frontier optionality on 2035E, discounted 9y at 10%


def _spacex_engine(d: dict) -> float:
    """Per-share fair value in USD from one draw of the nine drivers.

    Five value legs plus net cash:
      1. Connectivity / Starlink    — 2030E revenue x EBITDA margin x EV/EBITDA
      2. Space / launch + Starship  — 2030E revenue x EV/Sales
      3. Orbital datacenters        — 2035E risk-adj. revenue x EV/Sales
                                      (space-based, solar-powered AI compute;
                                       distinct from the ground Colossus already
                                       inside the AI segment)
      4. Other frontier optionality — 2035E risk-adj. revenue x EV/Sales
                                      (moon factories, payload-to-orbit new
                                       markets, point-to-point transport)
      5. AI segment (xAI + X)       — enterprise value drawn directly, today
    The two frontier-class legs (3, 4) share one EV/Sales multiple so splitting
    orbital datacenters out of the old single frontier lump revalues nothing at
    mode — it only makes the datacenter slice visible and separately tunable.
    """
    conn_ev_2030   = d["conn_rev"] * d["conn_margin"] * d["conn_mult"]   # $bn, 2030E
    launch_ev_2030 = d["space_rev"] * d["space_mult"]                    # $bn, 2030E
    orbital_ev_35  = d["orbital_rev"]  * d["frontier_mult"]             # $bn, 2035E
    frontier_ev_35 = d["frontier_rev"] * d["frontier_mult"]            # $bn, 2035E
    ev_bn = ((conn_ev_2030 + launch_ev_2030) / _DISC_2030
             + (orbital_ev_35 + frontier_ev_35) / _DISC_2035
             + d["ai_value"] + _NET_CASH_BN)                            # $bn, today
    return ev_bn * 1000.0 / _SHARES_M                                    # $/share


SPACEX_CONFIG = {
    # ---- identity & market ----
    "ticker":         "SPCX",
    "html_file":      "spacex-analytics-pipeline.html",
    "currency":       "$",            # used by the (updated) framework; € is the default
    "pipeline_price": 170.86,         # 2026-07-01 close; live spot re-fetched at build
    "shares_m":       _SHARES_M,
    "consensus_pt":   187.80,         # Investing.com consensus, 2026-07-01
    "eps_ttm":        -2.94,          # TTM GAAP; keeps P/E off (negative)
    # Forward P/E deliberately omitted (no eps_fwd_12m / eps_fwd_24m): SpaceX is
    # pre-IPO and this report values the private entity via a five-leg SOTP, so a
    # consensus forward EPS on the traded proxy vehicle is not on the same basis
    # as the modelled economics — the Module-I forward-P/E block self-absents.

    # ---- Module A engine ----
    "engine": _spacex_engine,
    "drivers": {
        # Connectivity (Starlink incl. direct-to-cell) revenue 2030E, $bn.
        # 2025 actual $11.4bn (+48% y/y); subs 8.9m YE25 -> 10.3m Mar'26.
        # Sell-side bull sees ~$144bn by 2030 (Goldman); mode kept at $70bn.
        "conn_rev":    {"lo": 45.0,  "md": 70.0,  "hi": 100.0, "rho": 0.80},
        # Connectivity EBITDA margin (63% reported in 2025).
        "conn_margin": {"lo": 0.52,  "md": 0.64,  "hi": 0.72,  "rho": 0.55},
        # EV/EBITDA applied to 2030E Connectivity EBITDA.
        "conn_mult":   {"lo": 16.0,  "md": 24.0,  "hi": 34.0,  "rho": 0.75},
        # Space (launch + Starship services) revenue 2030E, $bn (2025: $4.09bn).
        "space_rev":   {"lo": 8.0,   "md": 16.0,  "hi": 30.0,  "rho": 0.60},
        # EV/Sales on the Space segment (defence-prime to space-pure-play span).
        "space_mult":  {"lo": 4.0,   "md": 8.0,   "hi": 14.0,  "rho": 0.50},
        # Orbital datacenters — SpaceX's RISK-ADJUSTED 2035E revenue, $bn, from
        # space-based, solar-powered AI compute (the xAI "AI satellites" / moon-
        # factory thesis). Its own leg (Module N), split out of the old frontier
        # lump. Distinct from the ground Colossus already inside the AI segment,
        # so no double-count. Gated on Starship $/kg falling below ~$200-500 —
        # the payload-cost collapse SpaceX uniquely controls. Discounted 9y.
        "orbital_rev":   {"lo": 4.0,  "md": 25.0,  "hi": 120.0, "rho": 0.85},
        # Other frontier optionality — RISK-ADJUSTED 2035E revenue, $bn, from the
        # remaining deep-space markets: lunar & in-space manufacturing ("moon
        # factories"), payload-to-orbit new markets, point-to-point transport
        # (decomposed in Module M). Discounted 9y. Orbital + other-frontier mode
        # (25 + 25 = 50) reproduces the pre-split single frontier lump exactly.
        "frontier_rev":  {"lo": 4.0,  "md": 25.0,  "hi": 90.0,  "rho": 0.85},
        # EV/revenue applied to BOTH frontier-class legs (orbital + other),
        # early hyper-growth infra multiple span.
        "frontier_mult": {"lo": 3.0,  "md": 6.0,   "hi": 12.0,  "rho": 0.70},
        # AI segment (xAI + X + Colossus) enterprise value today, $bn.
        # Anchor: xAI merged in at ~$250bn (Feb 2026); frontier-lab marks span widely.
        "ai_value":    {"lo": 250.0, "md": 700.0, "hi": 1600.0, "rho": 0.90},
    },
    "reverse_dcf_target": "ai_value",
    "reverse_dcf_label":  "AI-segment enterprise value",
    "reverse_dcf_unit":   " $bn",

    # ---- Module I regressions ----
    # US benchmarks replace the Finnish defaults (framework update in utils/).
    "bench1_ticker": "^GSPC", "bench1_label": "S&P 500",
    "bench2_ticker": "^NDX",  "bench2_label": "Nasdaq-100",
    "macro_ticker":  "TSLA",  "macro_label":  "Tesla (Musk-complex proxy)",
    "peers": ["RKLB", "ASTS"],   # Rocket Lab; AST SpaceMobile (D2C satellite comp)

    # ---- Module J ----
    # No Piotroski/Altman trend is computable from one public year; 0.45 blends
    # the genuinely strong Starlink unit economics (63% segment EBITDA margin,
    # subs 2x in 2025) against GAAP losses, negative FCF and AI capex intensity.
    "quality_score": 0.45,

    # Reference class: what the market has paid per $1 of revenue at each
    # observable mark of SpaceX itself (private rounds -> IPO -> now).
    "base_rates": {
        "variable": "Group EV / annualised revenue at each observable mark",
        "unit": "×",
        "series": [
            ("Dec 2024 secondary ($350bn / FY24 rev $13.1bn)",      26.7, "Insider sale at $185 pre-split-basis (Sacra)."),
            ("Jul 2025 round ($400bn / ~$16bn run-rate)",           25.0, "Secondary at $212 (Sacra)."),
            ("Dec 2025 insider sale ($800bn / FY25 rev $18.7bn)",   42.8, "At $421; pre-xAI-merger (Sacra)."),
            ("IPO price Jun 2026 ($1.77tn / Q1'26 ann. $18.78bn)",  94.2, "Fixed $135 offer; largest IPO ever, $75bn raised."),
            ("Now ($2.25tn / Q1'26 annualised $18.78bn)",          119.8, "At $170.86 spot, 2026-07-01."),
        ],
        "current_value": 119.8,
        "current_label": "≈120× EV/rev",
    },

    # Owner-earnings anchor, $m. GAAP FY2025 net loss used as the OE proxy:
    # adj. EBITDA is +$6.58bn but capex (61% of it into the AI segment, 76% in
    # Q1'26) exceeds D&A, so true owner earnings sit at or below the GAAP loss.
    "oe_anchor_m": -4900.0,
    "oe_note": ("FY2025 GAAP net loss −$4.9bn (S-1) as a conservative owner-earnings proxy; "
                "adj. EBITDA +$6.58bn, but AI-heavy capex exceeds D&A so cash owner earnings "
                "are negative — the spread below is a cost of holding, not a yield"),

    # ---- § Audit appendix ----
    "endpoints": [
        ("https://query1.finance.yahoo.com/v8/finance/chart/SPCX?range=5y&interval=1d",
         "Daily OHLC, adjusted close + live spot since the 2026-06-12 IPO (Yahoo serves whatever history exists).", "I, J"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?range=5y&interval=1d",
         "S&P 500 daily series — benchmark beta (needs ≥60 overlapping sessions; n/a until the SPCX tape matures).", "I"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/%5ENDX?range=5y&interval=1d",
         "Nasdaq-100 daily series — second benchmark (SPCX joins the index 2026-07-07).", "I"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/TSLA?range=5y&interval=1d",
         "Tesla daily series — Musk-complex co-movement regression.", "I"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/RKLB?range=2y&interval=1d",
         "Rocket Lab — 12m peer relative return (n/a until SPCX has 12m of history).", "I"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/ASTS?range=2y&interval=1d",
         "AST SpaceMobile — direct-to-cell satellite comp, 12m peer relative.", "I"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/%5ETNX?range=1mo&interval=1d",
         "US 10y yield — real-rate proxy for the owner-earnings spread.", "J"),
    ],
    "primary_sources": [
        ("SpaceX Form S-1 / 424B4 prospectus — SEC EDGAR, CIK 1181412",
         "FY2025 revenue $18.674bn, op. loss $2.589bn, adj. EBITDA $6.584bn, net loss $4.9bn; Q1'26 revenue $4.694bn; "
         "segment split (Connectivity $11.4bn / Space $4.086bn / AI $3.2bn rev; AI op. loss −$6.35bn); LT debt $29.1bn; "
         "Starship dev spend >$15bn; 5-for-1 split; Class A/B/C structure", "A, D, E, F"),
        ("IPO pricing & allocation coverage (CNBC, Jun 2026)",
         "Fixed $135 offer, ~$75bn raised (largest IPO ever), ~$1.77tn IPO valuation, ~30% retail tranche; "
         "day-1 open $150 / close $160.95", "A, E, F"),
        ("S-1 ownership & related-party sections",
         "Musk control via 10×-vote Class B; Valor/Gracias entities ~7.3% of Class A; Tesla ~1% Class A (via Jan-2026 xAI "
         "investment); Shotwell 7.1m Class B; xAI merger eff. 2026-02-02 (~$1.25tn combined); Cursor option: $60bn in "
         "Class A stock, $1.5bn termination + $8.5bn deferred-services fees; Colossus compute rented to Anthropic", "E, F"),
        ("Nasdaq index notices",
         "SPCX added to the Nasdaq-100 effective 2026-07-07, bypassing seasoning requirements; est. 0.47–0.70% weight", "F"),
        ("Investing.com / TradingView consensus pages",
         "12m consensus PT $187.80 (high $310 / low $62); EPS TTM −$2.94; post-IPO ATH $225.64 (Jun 16) / ATL $147.11 (Jun 23)", "F, I"),
        ("Sacra / Nasdaq Private Market round history",
         "$350bn (Dec 2024, $185), $400bn (Jul 2025, $212), $800bn (Dec 2025, $421) private marks used in the "
         "Module-J reference class", "J"),
        ("Sell-side 2030E models (Goldman Sachs, JPMorgan, Morgan Stanley — IPO-roadshow coverage, Jun–Jul 2026)",
         "2030E group revenue $330bn (MS) / $470bn (JPM) / $474bn (GS) vs Musk's ~$1tn aspiration; Starlink ~$144bn, "
         "launch ~$8.3bn, AI ~68% of mix; group EBITDA ~$352bn by 2030 (GS). Calibrates the Module-A leg ranges and "
         "the Module-K decomposition.", "A, K, M"),
        ("SpaceX / xAI lunar & in-space manufacturing programme (Shotwell 'AI on the Moon' remarks; Musk 'city on the Moon'; press Mar–Jul 2026)",
         "Stated goal: manufacture solar-powered AI satellites / orbital data centres via lunar & in-space manufacturing "
         "('moon factories'); xAI merger ($1.25tn combined) framed around orbital compute; NASA Artemis first crewed "
         "landing on Starship HLS ~2028. Basis for the Module-N orbital-datacenter & Module-M frontier legs.", "M, N"),
        ("Starship payload & launch-cost targets (SpaceX technical statements; independent trackers, 2025–26)",
         "150 t reusable / 250 t expendable to LEO; cost-per-kg target ~$100–200 (aspirational $10) vs ~$1,500 today — "
         "the cost collapse that makes the frontier markets economically possible and gates orbital datacenters (Google: "
         "orbital compute needs <$200/kg by 2035, plausible if Starship reaches ~180 launches/yr). NASA HLS awards "
         "~$2.89bn + $1.15bn; USSF 'Rocket Cargo' point-to-point demo (~$102m, scalable).", "M, N"),
        ("Orbital-datacenter economics & market sizing (Starcloud 5 GW / NVIDIA H100 in orbit; Google 'Project Suncatcher'; industry TAMs, 2026)",
         "Space-based-datacenter market ~$1.8bn (2029) → ~$39bn (2035), $10–50bn/yr by 2030 on demand projections; "
         "Starcloud 5 GW single-site concept (4 km solar array); break-even ~$500/kg for GPU payloads, <$200/kg by 2035 "
         "for full viability — the pool and the gate for the Module-N orbital-datacenter leg.", "N"),
    ],

    # ---- footer & scorecard ----
    "cut_replacements": (
        "<b>Pre-IPO private marks as a return series</b> — Forge/Hiive/NPM marks are sparse, stale and never tradable at "
        "size; only the post-IPO tape (from 2026-06-12) feeds the return statistics, so long-window metrics read n/a until "
        "the history exists. <b>Options-implied skew &amp; vol surface</b> — SPCX options listed days ago; the surface is too "
        "thin to cite. <b>Short interest &amp; borrow cost</b> — the first post-IPO exchange short-interest print is not yet "
        "published. <b>Piotroski / Altman / Beneish</b> — each needs at least two audited public years; SpaceX has one S-1 "
        "basis (with the xAI/X common-control restatement), so a half-estimated score would be worse than none. "
        "<b>The frontier leg (Module M) is deliberately option-valued, not base-cased</b> — moon factories, orbital data "
        "centres and point-to-point are priced as a risk-adjusted 2035E revenue discounted nine years, so they add a "
        "material modal contribution with a long right tail rather than a certainty; as real contracts and cadence print, "
        "the leg is re-calibrated, not re-derived. All of these slot straight into stocks/config.py as the tape and "
        "filings mature."
    ),
    "tally": {"bull": 1, "mixed": 11, "bear": 2},

    "strictbar_replacement": (
        '<div class="strictbar"><b>What this build adds.</b> A five-leg sum-of-the-parts — <b>Starlink</b>, '
        '<b>launch/Starship</b>, <b>orbital datacenters</b> (space-based AI compute), <b>other frontier</b> (moon '
        'factories, payload-to-orbit, point-to-point) and the <b>AI segment</b> — so the price is decomposed across every '
        'driver, not just the AI mark. Two institutional modules computed live from the Yahoo Finance v8 chart API: '
        '<b>I — Price-asymmetry layer</b> (reverse-DCF on the AI-segment value, Kelly f*, payoff-asymmetry, VaR/CVaR, '
        'realised vol, betas vs S&amp;P 500 / Nasdaq-100 / Tesla, own-history percentile) and <b>J — Base rates &amp; '
        'factor composite</b>. Plus hand-authored <b>K — priced-in decomposition</b>, <b>L — Starlink unit-economics</b>, '
        '<b>M — frontier optionality</b> and <b>N — orbital datacenters</b> (the space-based-compute leg, gated on the '
        'Starship $/kg collapse, decomposed into GW × revenue/GW × capture). SpaceX listed <b>2026-06-12</b> — while the '
        'post-IPO tape is shorter than a metric\'s window, that metric honestly '
        'reports <b>n/a</b> rather than a backfilled guess; re-run <code>python refresh_all.py</code> weekly and the n/a '
        'cells fill themselves in as history accrues. Balance-sheet facts are from the S-1/424B4; nothing is asserted from '
        'memory.</div>'
    ),
}
