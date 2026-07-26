"""
Tesla, Inc. (NASDAQ: TSLA) — stock-specific configuration.

Kept in its own module (same pattern as config_spacex.py / config_amazon.py) and
wired into the STOCKS registry at the bottom of stocks/config.py. No framework
code under ../utils needs to know about it.

Unlike the Helsinki names and even SpaceX, Tesla has a deep, liquid, multi-year
public tape — so every long-window metric in Modules I & J (1y/3y realised vol,
252-day betas vs S&P 500 / Nasdaq 100 / rates, 12-month momentum & peer-relative,
5-year own-history percentile, quarterly/annual return base-rates) computes on a
FULL sample rather than reporting n/a. That is the whole point of running this
build on Tesla: the price-asymmetry and base-rate layers finally have the history
they were designed for.

ENGINE — a transparent FOUR-leg sum-of-the-parts, matching the JS engine in
tesla-pipeline.html Module A exactly. Tesla is no longer valuable as a car maker
on its earnings alone (it trades at ~370x trailing EPS); the market prices it as
a bundle of one shrinking-but-cash-generative core and three call options:

    core value      = (auto+services 2028E net income $bn x P/E)
                      + (energy 2028E revenue $bn x EV/Sales)
    autonomy value  = robotaxi/FSD risk-adjusted 2030E EV $bn   / 1.10^5   (Module M)
    robotics value  = Optimus risk-adjusted 2030E EV $bn        / 1.10^5   (Module N)
    fair value/share= (core + autonomy + robotics + net cash ~$30bn) x 1000 / 3510m

The two frontier legs (robotaxi, Optimus) are RISK-ADJUSTED 2030E enterprise
values (TAM x Tesla-capture x probability already folded in) discounted five
years at 10%, so each is priced as a genuine call option — a material modal
contribution with a long right tail, not a certainty. The reverse-DCF (Module I)
grid-solves the ROBOTAXI leg — the single most-contested number and the natural
residual between the fundamentals and the tape.

DATA BASIS (sourced; the pipeline re-fetches the live spot/betas itself):
  - Spot $404.38 (2026-07-09, NasdaqGS); 52-week range $297.82 - $498.83.
  - FY2025 (8-K, 28 Jan 2026): revenue $94.8bn (-2.9% YoY); automotive $69.53bn;
    energy generation & storage $12.8bn (+26.6%, record gross profit); services &
    other ~$12.5bn. GAAP net income $3.79bn (-47%), diluted EPS $1.08; Q4 gross
    margin 20.1% (two-year high), auto GM ex-credits ~17.9%. FY2025 FCF +$6.2bn;
    cash & investments $44.1bn (+$7.5bn). Deliveries 1.64m (-8.6% from 1.79m) —
    a second consecutive annual decline, the first back-to-back drop on record.
  - Q1'26 (8-K, 22 Apr 2026): revenue $22.39bn (+16% YoY); 358k deliveries; gross
    margin 21.1% (auto GM ex-credits 19.2%, aided by ~$230m warranty true-downs +
    tariff relief); GAAP EPS $0.13; energy revenue $2.41bn, 8.8 GWh deployed (down
    from a record 14.2 GWh in Q4'25); FCF turned negative on the capex ramp, with
    warranty-reserve releases, tariff-refund windfalls, a 10-day supplier-payment
    stretch and new debt flagged as earnings-quality items.
  - Robotaxi: unsupervised across the Austin metro; unsupervised launched in
    Dallas & Houston (Apr'26); ~9 US markets by mid-2026; targeting a dozen states
    by year-end. Optimus Gen-3 mass production started Fremont (Jan'26); a
    dedicated Giga Texas line targets 10m units/yr; public sales ~end-2027 at
    $20-30k. Cybercab volume production began ~Apr'26. FSD moving subscription-only.
  - Consensus 12m PT ~$395-424 across providers (S&P Global 47-analyst avg $424;
    MarketBeat $408.52; TipRanks $399.71; Benzinga $395.41) — $415 used as a blend.
  - Bull anchor: ARK Invest 2026 expected value ~$4,600/share (robotaxi-led).
"""
from __future__ import annotations
from typing import Callable, Any


_SHARES_M    = 3510.0        # diluted (FY2025 net income $3.79bn / EPS $1.08)
_NET_CASH_BN = 30.0          # $44.1bn cash & investments less ~$14bn debt (Q1'26 added debt) — an explicit assumption
_DISC_2030   = 1.10 ** 5     # frontier legs on 2030E, discounted 5y at 10%


def _make_tesla_engine() -> Callable[[dict], float]:
    """Per-share fair value in USD from one draw of the six drivers.

    Four value legs plus net cash:
      1. Core auto + services  — 2028E net income x P/E
      2. Energy gen & storage  — 2028E revenue x EV/Sales
      3. Robotaxi / autonomy   — risk-adj. 2030E EV, discounted 5y (Module M)
      4. Optimus / robotics    — risk-adj. 2030E EV, discounted 5y (Module N)
    Legs 3 & 4 are already probability-weighted, so each is a call option: a
    modest modal contribution with a long right tail, not a base-case certainty.
    """
    def engine(d: dict) -> float:
        core_ev  = d["auto_ni"] * d["auto_pe"] + d["energy_rev"] * d["energy_mult"]   # $bn
        option_ev = (d["robotaxi_val"] + d["optimus_val"]) / _DISC_2030               # $bn, today
        ev_bn = core_ev + option_ev + _NET_CASH_BN
        return ev_bn * 1000.0 / _SHARES_M                                             # $/share
    return engine


TESLA_CONFIG: dict[str, Any] = {
    # ---- identity & market ----
    "ticker":         "TSLA",
    "html_file":      "tesla-pipeline.html",
    "currency":       "$",
    "pipeline_price": 404.38,          # 2026-07-09 spot; live spot re-fetched at build
    "shares_m":       _SHARES_M,
    "consensus_pt":   415.00,          # blend of S&P/MarketBeat/TipRanks/Benzinga (range $395-424)
    "eps_ttm":        1.09,            # FY2025 $1.08 - Q1'25 $0.12 + Q1'26 $0.13 -> ~371x P/E at spot
    "eps_fwd_12m":    2.13, "eps_fwd_24m": 2.55,   # consensus curr./next-FY EPS (Yahoo, build-time)

    # ---- Module A engine ----
    "engine": _make_tesla_engine(),
    "drivers": {
        # Core automotive + services 2028E NET INCOME, $bn. FY2025 group GAAP NI
        # was $3.79bn (incl. energy); the auto+services slice is ~$2-4bn today.
        # Mode $10bn assumes a margin/volume recovery to 2028; wide band both ways.
        "auto_ni":     {"lo": 5.0,   "md": 10.0,  "hi": 18.0,  "rho": 0.70},
        # Blended P/E applied to that core-earnings stream.
        "auto_pe":     {"lo": 14.0,  "md": 24.0,  "hi": 34.0,  "rho": 0.65},
        # Energy generation & storage 2028E revenue, $bn (FY2025 $12.8bn, +26.6%).
        "energy_rev":  {"lo": 20.0,  "md": 34.0,  "hi": 58.0,  "rho": 0.55},
        # EV/Sales on the energy segment (high-growth, record-margin infra).
        "energy_mult": {"lo": 3.5,   "md": 6.5,   "hi": 11.0,  "rho": 0.50},
        # Robotaxi / autonomy (FSD) — Tesla's RISK-ADJUSTED 2030E enterprise value,
        # $bn (TAM x capture x probability). The reverse-DCF target and the single
        # biggest swing. Discounted 5y. ARK's bull frames this leg at multiples of
        # the mode; the bear frames it near zero if unsupervised autonomy stalls.
        "robotaxi_val":{"lo": 0.0,   "md": 450.0, "hi": 1700.0,"rho": 0.90},
        # Optimus / robotics — RISK-ADJUSTED 2030E enterprise value, $bn. Deeper
        # optionality than robotaxi (further from revenue), longer right tail.
        "optimus_val": {"lo": 0.0,   "md": 220.0, "hi": 1500.0,"rho": 0.85},
    },
    "reverse_dcf_target": "robotaxi_val",
    "reverse_dcf_label":  "Robotaxi/autonomy risk-adjusted 2030E enterprise value",
    "reverse_dcf_unit":   " $bn",

    # ---- Module I regressions (deep US tape — every window computes) ----
    "bench1_ticker": "^GSPC", "bench1_label": "S&P 500",
    "bench2_ticker": "^NDX",  "bench2_label": "Nasdaq 100",
    "macro_ticker":  "^TNX",  "macro_label":  "US 10y yield (^TNX)",
    "peers": ["BYDDY", "TM"],   # BYD (ADR); Toyota — the volume-EV and legacy-auto comps

    # ---- Module J ----
    # 0.55 blends a fortress balance sheet ($44bn cash, positive FY FCF) and record
    # energy margins against compressed auto margins, two years of falling
    # deliveries and the Q1'26 earnings-quality flags (warranty releases, tariff
    # windfalls, supplier-payment stretch, new debt, negative TTM FCF).
    "quality_score": 0.55,

    # Reference class: Tesla's own trailing P/E at each cycle mark — how richly the
    # market has valued $1 of its earnings through time. Today (~371x) sits at the
    # top of the post-2020-mania range, which is the Module-G BEAR read in one line.
    "base_rates": {
        "variable": "Trailing P/E multiple at each cycle mark",
        "unit": "×",
        "series": [
            ("End 2022 ($123 / $3.62 EPS)",     34.0,  "post-selloff trough multiple"),
            ("End 2023 ($248 / $4.30 EPS)",     58.0,  "recovery (2023 EPS flattered by a one-off tax benefit)"),
            ("End 2024 ($403 / $2.23 EPS)",    181.0,  "EPS rolling over while the price held flat"),
            ("End 2021 ($352 / $1.63 EPS)",    216.0,  "prior-cycle peak, ex the 2020 mania"),
            ("Now ($404 / $1.09 TTM EPS)",     371.0,  "at $404.38 spot, 2026-07-09"),
        ],
        "current_value": 371.0,
        "current_label": "≈371× trailing P/E",
        "reversion_mid": 100.0,
    },

    # Owner-earnings anchor, $m. FY2025 free cash flow +$6.2bn (last clean full
    # year) as the OE proxy. The honest wrinkle: the 2026 capex ramp turned TTM
    # FCF negative by Q1'26, so the OE-yield spread below is thin-to-negative — the
    # cost of holding a growth-capex story, not a coupon.
    "oe_anchor_m": 6200.0,
    "oe_note": ("FY2025 free cash flow +$6.2bn (8-K, 28 Jan 2026) as the owner-earnings proxy; "
                "the 2026 capex ramp (robotaxi/Optimus/AI compute) turned TTM FCF negative by "
                "Q1'26, so the real cash yield is thinner than the FY2025 figure implies"),

    # ---- § Audit appendix ----
    "endpoints": [
        ("https://query1.finance.yahoo.com/v8/finance/chart/TSLA?range=5y&interval=1d",
         "Tesla 5-year daily OHLC + adjusted close + live spot (deep, liquid tape — every window computes).",
         "I: realised vol / beta / momentum / drawdown / own-history percentile · J: base rates"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?range=5y&interval=1d",
         "S&P 500 index — broad-market benchmark.", "I: beta vs S&P 500"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/%5ENDX?range=5y&interval=1d",
         "Nasdaq 100 — mega-cap growth benchmark (Tesla is a top constituent).", "I: beta vs Nasdaq 100"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/%5ETNX?range=5y&interval=1d",
         "US 10-year Treasury yield — rate-duration macro factor + real-rate proxy.",
         "I: beta vs rates · J: owner-earnings yield vs real 10y"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/BYDDY?range=2y&interval=1d",
         "BYD (ADR) — the volume-EV peer that overtook Tesla on unit sales.", "I: peer-relative 12m"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/TM?range=2y&interval=1d",
         "Toyota — legacy-auto scale peer.", "I: peer-relative 12m"),
    ],
    "primary_sources": [
        ("Tesla Q4/FY2025 update & 8-K (Ex-99.1, 28 Jan 2026)",
         "FY2025 revenue $94.8bn (-2.9%); automotive $69.53bn; energy gen & storage $12.8bn (+26.6%, record "
         "gross profit); services & other ~$12.5bn; GAAP net income $3.79bn (-47%), diluted EPS $1.08; Q4 gross "
         "margin 20.1% (two-year high), auto GM ex-credits ~17.9%; FY FCF +$6.2bn; cash & investments $44.1bn "
         "(+$7.5bn); deliveries 1.64m (-8.6%, second straight annual decline)",
         "A engine, D forensics, E capital record, G valuation"),
        ("Tesla Q1 2026 update & 8-K (Ex-99.1, 22 Apr 2026)",
         "Revenue $22.39bn (+16% YoY); 358k deliveries; gross margin 21.1% (auto GM ex-credits 19.2%, aided by "
         "~$230m warranty true-downs + tariff relief); GAAP EPS $0.13; energy revenue $2.41bn, 8.8 GWh deployed "
         "(down from a record 14.2 GWh in Q4'25); FCF turned negative on the capex ramp; warranty-reserve releases, "
         "tariff-refund windfalls, a 10-day supplier-payment stretch and new debt flagged as earnings-quality items",
         "A engine, B driver analysis, D forensics, H kill-criteria"),
        ("Tesla FY2025 vehicle-delivery & production reports (Jan 2026; Q1'26 report Apr 2026)",
         "Full-year 2025 deliveries 1.64m vs 1.79m in 2024 (-8.6%); Q1'26 deliveries ~358k (a miss vs consensus, "
         "the steepest 2026 delivery drop) — the unit-decline that Module L's ASP x volume grid keys on",
         "L unit-economics, C scenarios"),
        ("Robotaxi / Cybercab rollout coverage (Tesla, Electrek, Teslarati, Forbes; Jan-Jun 2026)",
         "Unsupervised robotaxi across the Austin metro; unsupervised launched in Dallas & Houston (Apr'26); ~9 US "
         "markets by mid-2026; targeting a dozen states by year-end; Cybercab volume production began ~Apr'26; FSD "
         "moving to subscription-only with record net new subscriptions in Q1 — the basis for the Module-M autonomy leg",
         "M robotaxi optionality, C scenarios"),
        ("Optimus programme coverage (Tesla, Teslarati, Seeking Alpha; Jan-Jun 2026)",
         "Optimus Gen-3 mass production started at Fremont (Jan'26); a dedicated Giga Texas line targets 10m "
         "units/yr; public sales ~end-2027 at $20-30k; 2025-2026 capex signalled at >$25bn — the basis for the "
         "Module-N robotics leg",
         "N Optimus optionality, E capital record"),
        ("Analyst consensus & price targets (S&P Global, MarketBeat, TipRanks, Benzinga; early Jul 2026)",
         "12m consensus PT ~$395-424 across providers (S&P Global 47-analyst avg $424.01; MarketBeat $408.52; "
         "TipRanks $399.71 with a $600 high / $24.86 low; Benzinga $395.41); consensus rating Hold-to-Buy; "
         "$415 used as the blended anchor",
         "F positioning, I asymmetry"),
        ("ARK Invest — Tesla 2026 valuation model",
         "ARK's 2026 expected value ~$4,600/share, driven overwhelmingly by an at-scale robotaxi network — the "
         "explicit bull anchor for the Module-O perfect-execution overlay and the upper tail of the Module-M leg",
         "M robotaxi optionality, O bull case"),
        ("Peer & valuation context (stockanalysis.com / Macrotrends; Jul 2026)",
         "TSLA ~371x trailing P/E on $1.09 TTM EPS, an order of magnitude above legacy auto (Toyota ~9x, BYD ~19x) "
         "and rich even against the Mag-7 — the multiple only reconciles if the autonomy/robotics legs are real",
         "G valuation, K priced-in"),
    ],

    # ---- footer & scorecard ----
    "cut_replacements": (
        '<b>Beneish M-score</b> — needs eight two-year ratios Tesla does not break out cleanly per segment; a '
        'half-estimated score is worse than none. '
        '<b>Segment operating income for energy and services</b> — Tesla discloses segment gross profit but not a '
        'clean segment net income, which is why the engine values a single core earnings block plus an energy '
        'EV/Sales leg rather than four fully-separated P&amp;Ls — a modelling simplification, not a hidden number. '
        '<b>A clean ex-one-off Q1\'26 margin</b> — the ~$230m warranty true-down and tariff refunds sit inside the '
        'reported 19.2% auto GM ex-credits; stripping them requires an allocation this build does not assert. '
        '<b>Options-implied skew, daily short-interest and insider-transaction net flow</b> — fetchable for a US '
        'mega-cap from paid terminals but not from the Yahoo v8 chart endpoint this toolkit standardises on. '
        'Everything else previously flagged as "cut" (factor betas vs S&amp;P 500 / Nasdaq 100 / rates, price-history '
        'percentile, momentum, realised vol, drawdown, BYD/Toyota 12m relative, base-rate frequencies, '
        'owner-earnings yield vs real rate) is <b>included</b> in Modules I &amp; J and computed live from the Yahoo '
        'Finance v8 chart API — and, unlike SpaceX, on a full multi-year sample.'
    ),
    "strictbar_replacement": (
        '<div class="strictbar"><b>What this build adds.</b> A four-leg sum-of-the-parts — <b>core auto+services</b>, '
        '<b>energy</b>, <b>robotaxi/autonomy</b> and <b>Optimus/robotics</b> — so the price is decomposed across '
        'the shrinking cash core and the three call options the market is actually paying for, not a single P/E. Two '
        'institutional modules computed live from the Yahoo Finance v8 chart API: <b>I — Price-asymmetry layer</b> '
        '(reverse-DCF on the robotaxi value, Kelly f*, payoff-asymmetry, VaR/CVaR, realised vol, betas vs S&amp;P 500 / '
        'Nasdaq 100 / rates, own-history percentile, BYD/Toyota 12m relative) and <b>J — Base rates &amp; factor '
        'composite</b>. Plus hand-authored <b>K — priced-in decomposition</b>, <b>L — auto unit-economics</b> '
        '(deliveries × ASP × margin), <b>M — robotaxi/autonomy optionality</b>, <b>N — Optimus/robotics '
        'optionality</b> and <b>O — perfect-execution bull case</b> (the ARK-anchored right tail, priced end-to-end). '
        'Because Tesla has a deep multi-year tape, every long-window metric computes on a full sample — no n/a '
        'backfills. Balance-sheet facts are from the FY2025 / Q1\'26 releases; nothing is asserted from memory.</div>'
    ),
    # 14 graded reads counted in the tally (A-H + K,L,M,N + injected I,J); Module O
    # is a bull-case OVERLAY shown in the scorecard but not counted in the net —
    # tallies.py recognises the "Bull case overlay" label and skips that row.
    # tallies.py counts the live chips on the page; this is only the fallback.
    "tally": {"bull": 0, "mixed": 11, "bear": 3},
}
