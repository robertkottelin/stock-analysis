"""TE Connectivity plc (NYSE: TEL) — pipeline configuration.

Kept in its own module and wired into the STOCKS registry at the bottom of
stocks/config.py. No framework code under ../utils needs to know about it.

TE Connectivity is a global designer and manufacturer of connectors, sensors,
antennas and related connectivity systems. Two reportable segments:

  * Transportation Solutions  — automotive, commercial transport, EV/ADAS content
  * Industrial Solutions      — factory automation, energy, medical, aero/defence,
                                data-centre / AI power and high-speed connectivity

Investment horizon for this build is **ten years**. First principles: TE is a
capital-light-to-moderate industrial compounder whose economic engine is
*design-in content* (switching costs, multi-year platforms) × *secular volume*
(electrification, automation, AI infrastructure) × *operating leverage*. The
market prices that engine on EV/EBIT of through-cycle operating profit less net
debt — not on a single-year P/E distorted by tax and buyback timing.

ENGINE — single-leg EBIT × multiple, matching te-pipeline.html Module A:

    fair value  = (sales × EBIT_margin% / 100 × EV/EBIT − net_debt) / shares

DATA BASIS (sourced; live spot/betas re-fetched at build):
  - Spot ~$203.31 (Yahoo, 2026-07-17 close); 52w range $177–$253.
  - FY2025 (year ended Sep 2025): revenue $17.26bn (+8.9%); operating income
    $3.21bn (18.6% margin); EBITDA $4.05bn; FCF $3.20bn; diluted shares ~299m;
    diluted EPS $6.16 (tax-rate noise); net debt ~$4.44bn.
  - TTM (to ~Apr 2026): revenue $18.70bn; EBIT $3.69bn (19.7%); EBITDA $4.65bn;
    FCF $3.39bn; OCF $4.42bn; diluted shares ~297m; EPS $9.79; net debt $4.55bn;
    gross margin 36.1%; ROE ~22.7%.
  - Q2 FY2026 (quarter ended ~Mar 2026): sales $5.0bn (+25% reported / +10%
    organic); Transportation $2.5bn (+10% org); Industrial $2.5bn (+9% org);
    adj. EPS $2.66 (+49%); YTD FCF $1.3bn (+21%); FY2026 sales guidance raised
    to ~$19.5bn (+13%).
  - Capital return: multi-year buybacks ($1.2–2.0bn/yr) + rising dividend
    ($2.72 FY25, TTM $2.84); payout ~29% of earnings.
  - Consensus 12m PT ~$260 (blend of MarketWatch ~$264 / Chartmill ~$264 /
    MarketBeat ~$255); ~20 analysts, Buy/Overweight.
  - Peers: Amphenol (APH), Aptiv (APTV), Sensata (ST) — connector / auto-electrification set.
"""
from __future__ import annotations
from typing import Callable, Any


_SHARES_M = 297.0       # TTM diluted shares (millions); declining via buybacks
_NET_DEBT_M = 4500.0    # mode net debt $m (TTM ~4,545)


def _make_te_engine() -> Callable[[dict], float]:
    """Per-share fair value in USD from one draw of the four drivers.

    Classic quality industrial: EV = EBIT × EV/EBIT, equity = EV − net debt.
    EBIT = sales × margin% / 100. All figures in USD millions except per-share.
    """
    def engine(d: dict) -> float:
        ebit = d["sales"] * d["mgn"] / 100.0
        ev = d["mlt"] * ebit
        return (ev - d["nd"]) / _SHARES_M
    return engine


TE_CONFIG: dict[str, Any] = {
    # ---- identity & market ----
    "ticker":         "TEL",
    "html_file":      "te-pipeline.html",
    "currency":       "$",
    "pipeline_price": 203.31,
    "shares_m":       _SHARES_M,
    "consensus_pt":   260.0,           # ~$255–264 street blend
    "eps_ttm":        9.79,
    "eps_fwd_12m":    12.60, "eps_fwd_24m": 14.00,  # ~FY26/FY27 consensus path

    # ---- Module A engine ----
    "engine": _make_te_engine(),
    "drivers": {
        # Group net sales, $m. FY25 17,262; TTM 18,696; FY26 guidance ~19,500.
        # 10y thesis allows a wide right tail (AI power, industrial automation)
        # and a real left tail (auto cycle / destock).
        "sales": {"lo": 16500.0, "md": 19500.0, "hi": 22500.0, "rho": 0.68},
        # Operating (EBIT) margin %. FY23 trough 14.4%; FY25 18.6%; TTM 19.7%.
        # Adj. peaks have printed low-20s. Mode 19.5 near the live run-rate with
        # a genuine cycle floor and a mid-20s stretch if mix keeps enriching.
        "mgn":   {"lo": 15.0, "md": 19.5, "hi": 22.5, "rho": 0.70},
        # EV/EBIT multiple — reverse-DCF target. Quality industrials / connector
        # peers: APTV lower teens, APH often high-teens to 20s+. Mode 16.0 is a
        # through-cycle quality mark; tape at ~17× on guided EBIT.
        "mlt":   {"lo": 12.0, "md": 16.0, "hi": 20.0, "rho": 0.55},
        # Net debt $m. TTM ~4,545 after elevated M&A; FCF and buybacks pull down;
        # large deals re-lever. Rho negative vs common factor (good regime delever).
        "nd":    {"lo": 2500.0, "md": 4500.0, "hi": 7000.0, "rho": -0.30},
    },
    "reverse_dcf_target": "mlt",
    "reverse_dcf_label":  "EV/EBIT multiple (at mode sales / EBIT margin / net debt)",
    "reverse_dcf_unit":   "×",

    # ---- Module I regressions ----
    "bench1_ticker": "^GSPC", "bench1_label": "S&P 500",
    "bench2_ticker": "^STOXX", "bench2_label": "STOXX 600",
    "macro_ticker":  None,
    "macro_label":   None,
    "peers": ["APH", "APTV", "ST"],

    # ---- Module J ----
    # 0.82: high ROE (~23%), record-ish op margin, elite FCF conversion, disciplined
    # capital return — tempered by auto-cycle exposure and elevated goodwill post-M&A.
    "quality_score": 0.82,

    # Reference class: group operating margin through the cycle — the 10y story is
    # whether mid/high-teens is a floor and low-20s is sustainable, not a peak.
    "base_rates": {
        "variable": "Group operating (EBIT) margin (%)",
        "unit": "%",
        "series": [
            ("FY2021",     16.3, "reported — post-COVID recovery"),
            ("FY2022",     16.9, "reported"),
            ("FY2023",     14.4, "reported trough — industrial destock"),
            ("FY2024",     17.7, "reported — recovery"),
            ("FY2025",     18.6, "reported — mix + operating leverage"),
            ("TTM'26",     19.7, "TTM to ~Q2 FY26 — live run-rate"),
            ("cycle avg",  17.3, "FY21–25 mean — empirical reversion anchor"),
            ("10y ceiling", 22.0, "mix-shift ambition (AI/industrial + EV content)"),
        ],
        "current_label": "TTM = 19.7% (near-cycle high)",
        "current_value": 19.7,
        "reversion_mid": 18.0,
    },

    # Owner-earnings anchor, $m. FY2025 FCF $3,203m; TTM FCF $3,391m.
    # Capex is real (~$0.9–1.0bn) but FCF margin ~18% is elite for connectors.
    "oe_anchor_m": 3203.0,
    "oe_note": ("FY2025 free cash flow $3,203m (OCF $4,139m less capex ~$936m) as the "
                "owner-earnings proxy; TTM FCF $3,391m. Conversion has been consistently "
                "strong (FCF margin 15–19% since FY23). Note: acquisition cash ($2.5bn+ TTM) "
                "is investment, not maintenance — OE is before M&A spend."),

    # ---- § Audit appendix ----
    "endpoints": [
        ("https://query1.finance.yahoo.com/v8/finance/chart/TEL?range=5y&interval=1d",
         "TE Connectivity 5-year daily OHLC + regularMarketPrice + 52w range.",
         "I: realised vol / beta / momentum / drawdown / own-history percentile · J: base rates"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?range=5y&interval=1d",
         "S&P 500 — primary US benchmark for beta.", "I: beta vs S&P 500"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/%5ESTOXX?range=5y&interval=1d",
         "STOXX Europe 600 — pan-European industrial benchmark.", "I: beta vs STOXX 600"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/%5ETNX?range=1mo&interval=1d",
         "US 10-year Treasury yield — real-rate proxy.", "J: owner-earnings yield vs real 10y"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/APH?range=2y&interval=1d",
         "Amphenol — premier connector peer (quality / multiple ceiling).", "I: peer-relative 12m"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/APTV?range=2y&interval=1d",
         "Aptiv — auto-electrification / smart-vehicle peer.", "I: peer-relative 12m"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/ST?range=2y&interval=1d",
         "Sensata Technologies — sensors / industrial peer.", "I: peer-relative 12m"),
    ],
    "primary_sources": [
        ("TE Connectivity Q2 FY2026 earnings release (Apr 2026)",
         "Sales $5.0bn (+25% reported / +10% organic); Transportation $2.5bn (+10% org); "
         "Industrial $2.5bn (+9% org); adjusted EPS $2.66 (+49%); YTD FCF $1.3bn (+21%); "
         "FY2026 sales guidance raised to ~$19.5bn (+13% YoY).",
         "A engine, B drivers, C scenarios, E capital, H kill-criteria, Q dashboard"),
        ("TE Connectivity FY2025 Form 10-K / year-end results (fiscal year ended Sep 2025)",
         "Revenue $17.26bn (+8.9%); operating income $3.21bn (18.6%); EBITDA $4.05bn; "
         "FCF $3.20bn; diluted EPS $6.16; net debt ~$4.44bn; diluted shares ~299m; "
         "dividend $2.72; ~$1.35bn share repurchases.",
         "A engine, D forensics, E capital record, Q dashboard"),
        ("stockanalysis.com / Fiscal.ai — TEL multi-year financials (updated Apr 2026)",
         "TTM revenue $18.70bn; EBIT $3.69bn (19.7%); EBITDA $4.65bn; FCF $3.39bn; "
         "OCF $4.42bn; net debt $4.55bn; goodwill $7.4bn; diluted shares ~297m; EPS $9.79; "
         "gross margin 36.1%; FY21–25 operating-margin series.",
         "D forensics, Q dashboard, J base rates"),
        ("Yahoo Finance / screener quoteSummary (TEL, 2026)",
         "Spot, 52w range, beta ~1.17, ROE ~22.7%, debt/equity ~0.44, forward P/E ~16.1×, "
         "EV/EBITDA ~13.6×, ~20 analyst coverage, Buy consensus.",
         "F positioning, G peers, I live tape"),
        ("Street consensus (MarketWatch / Chartmill / MarketBeat, Jul 2026)",
         "Average 12m PT ~$255–264 (blend $260 used); FY2026 EPS estimates ~$11–12.6; "
         "no Sell ratings in most surveys; next print ~Jul 2026.",
         "F positioning, C scenarios"),
        ("Amphenol / Aptiv / Sensata peer context (2026)",
         "APH = quality/multiple ceiling for connectors; APTV = auto content peer (lower multiple, "
         "higher cycle beta); ST = sensors peer. Used for relative 12m and multiple band.",
         "G peers, I peer-relative"),
    ],

    "cut_replacements": (
        '<b>The single-leg EBIT × EV/EBIT engine is a transparent proxy, not a hidden number.</b> '
        'TE reports Transportation and Industrial segments but does not publish a full segment balance sheet; '
        'the market prices the group on consolidated operating profit. A two-leg SOTP would mainly reallocate '
        'the same EBIT. Net debt is interest-bearing debt less cash (~$4.5bn TTM). '
        '<b>Adjusted vs GAAP margin</b> — company adj. operating margins can run 100–200 bp above GAAP EBIT; '
        'this engine uses GAAP-consistent EBIT (TTM 19.7%) so multiples are not inflated. '
        '<b>Beneish M-score</b> — not computed; TE is a large multi-national with clean audits and no fraud thesis. '
        '<b>Options skew and precise borrow</b> — would slot in from a terminal; not required for the 10y compounder case. '
        'Modules I &amp; J include factor betas, own-history percentile, momentum, realised vol, drawdown, '
        'peer-relative returns, base-rate frequencies and owner-earnings yield vs real 10y — computed live.'
    ),
    "strictbar_replacement": (
        '<div class="strictbar"><b>What this build adds.</b> A first-principles <b>10-year compounder</b> frame for '
        'TE Connectivity: <b>sales × EBIT-margin × EV/EBIT − net debt</b>, with Transportation + Industrial treated '
        'as one design-in content engine (electrification, automation, AI power). Two institutional modules computed '
        'live from Yahoo Finance: <b>I — Price-asymmetry</b> (reverse-DCF on EV/EBIT, Kelly f*, payoff asymmetry, '
        'VaR/CVaR, betas vs S&amp;P 500 &amp; STOXX, APH/APTV/ST 12m relative) and <b>J — Base rates &amp; factors</b> '
        '(operating-margin reference class, return base-rates, V/Q/M/L composite, owner-earnings yield vs real 10y). '
        '<b>Module U</b> prices the perfect-execution 10y path (the stated investment horizon). Facts from FY2025 '
        '10-K, Q2 FY2026 release and Fiscal.ai TTM — nothing asserted from memory.</div>'
    ),
    "tally": {"bull": 4, "mixed": 7, "bear": 0},

    # ------------------------------------------------------------------
    # Perfect-execution / 10-year bull path — THE horizon for this name
    # Electrification + industrial automation + AI power content compound;
    # margin defends low-20s; multiple re-rates toward quality connector peers;
    # buybacks shrink the share count.
    # ------------------------------------------------------------------
    "bull_case": {
        "horizon_years": 10,
        "label": "Design-in compounder — electrification, automation, AI power",
        "narrative": (
            "TE's 10-year ceiling is a global connectivity platform that compounds mid-single-digit "
            "organic sales (plus tuck-in M&A), defends a low-20s EBIT margin on richer mix (EV/ADAS, "
            "factory automation, data-centre power), and re-rates modestly toward Amphenol-quality "
            "multiples — while buybacks retire ~2% of shares per year. Not a software multiple; not "
            "a zero-cycle path."
        ),
        "method_note": (
            "sales compound at assumed CAGR; EBIT margin and EV/EBIT ease from today to terminal via "
            "smoothstep; FCF = EBIT × (1 − tax) × conversion; split into dividend / buyback / cash; "
            "fair value = multiple × EBIT − net debt, ÷ shares"
        ),
        "path": {
            "sales_0": 19500.0,      # $m, FY26 guided path
            "mgn_0": 19.5,           # % EBIT
            "mlt_0": 16.0,           # × EV/EBIT
            "nc_0": -4500.0,         # $m net cash (= −net debt)
            "shares_0": 297.0,       # m shares
            "sales_cagr": 0.055,     # 5.5% — organic mid-single + bolt-ons
            "mgn_term": 22.0,        # % defended through-cycle peak mix
            "mlt_term": 18.0,        # × quality connector, still below APH peak
            "tax_rate": 0.20,
            "fcf_on_ebita": 0.85,    # after-tax cash conversion (historically strong)
            "payout_ratio": 0.28,    # of FCF → dividends
            "buyback_ratio": 0.45,   # of FCF → buybacks (TE's historical preference)
            "discount_rate": 0.09,
            "buyback_at_fv": True,
        },
        "milestones": [
            {"year": 2, "text": "FY sales ≥ $21bn; EBIT margin holds ≥ 19% through any soft auto quarter; AI/data-centre power content is a disclosed growth lane."},
            {"year": 5, "text": "Group sales clearly above $25bn; EBIT margin sustainably ≥ 20.5%; net debt/EBITDA ≤ 1.0×; share count down ≥ 10% from 2026 via buybacks."},
            {"year": 8, "text": "Industrial + energy + AI power are a larger share of mix; Transportation content/vehicle still rising; EV/EBIT re-rates through ~17× as the market accepts margin durability."},
            {"year": 10, "text": "Through-cycle EBIT margin ~22%, sales ~$33bn, quality multiple ~18×, smaller share count — the default terminal this calculator prices."},
        ],
        "guards": [
            "Global auto volumes double-dip for several years and TE's transportation content gains cannot offset — margin falls back to mid-teens.",
            "A large, value-destructive mega-deal re-levers the balance sheet and dilutes ROIC for a full cycle.",
            "Structural share loss in high-speed / AI power connectors to pure-play or Amphenol without TE matching the roadmap.",
            "Multiple never re-rates — the market permanently slots TEL with deep cyclicals (~12–13×) despite mix shift.",
        ],
    },
}
