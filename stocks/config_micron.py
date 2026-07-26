"""Micron Technology, Inc. (NASDAQ: MU) — pipeline configuration.

Kept in its own module (like SpaceX / Amazon / Tesla) and wired into
``stocks/config.py``. Micron is the US memory-semiconductor major (DRAM + NAND)
whose economics are being re-shaped by the AI build-out: high-bandwidth memory
(HBM) for GPU/accelerator systems is capacity-constrained, high-margin, and
sold out quarters ahead, dragging the whole memory complex into a super-cycle.

Valuation framing (Module A engine): memory is too cyclical to capitalise on
spot earnings, so the engine is a **through-cycle** one —

    fair value / share = EV/EBITDA multiple × (revenue × EBITDA margin) + net cash
                         ÷ diluted shares

with every driver a triangular whose range spans the trough-to-peak memory
cycle. The reverse-DCF then solves for the **through-cycle EBITDA margin** the
market is implying at spot — the single most contested Micron variable (is the
AI/HBM margin step-change durable, or does memory revert to its historically
thin through-cycle margins?).

All figures anchor to data fetched from Yahoo at build time (live price +
5-year tape for Modules I/J) and to Micron's own FY releases for the reported
annual history (FY ends late August). The FY2026 super-cycle figures are the
trailing-twelve-month values reported by Yahoo's fundamentals feed as of build.
"""
from __future__ import annotations
from typing import Any


# Diluted shares outstanding (m) — Yahoo sharesOutstanding, ~1.129bn.
_SHARES_M = 1129.4


def _make_micron_engine():
    """Through-cycle EBITDA × EV/EBITDA + net cash, per share.

    Same shape as the Konecranes engine (multiple × profit + net cash ÷ shares);
    here `rev` and `nc` are in $m, `mgn` is the EBITDA margin in %, `mult` is
    EV/EBITDA. Mirrors the page's JS `simulate()` exactly (see micron-pipeline
    Module A) — keep the two in lock-step if either is edited.
    """
    shares = _SHARES_M

    def engine(d: dict) -> float:
        ebitda = d["rev"] * d["mgn"] / 100.0          # $m
        ev = d["mult"] * ebitda                         # $m
        return (ev + d["nc"]) / shares                  # $/share

    return engine


MICRON_CONFIG: dict[str, Any] = {
    "ticker": "MU",
    "html_file": "micron-pipeline.html",
    "currency": "$",
    "pipeline_price": 848.95,          # live close at authoring (2026-07-19); re-synced each build
    "shares_m": _SHARES_M,
    "consensus_pt": 1491.95,           # 42-analyst mean target (Yahoo financialData), strong-buy
    "eps_ttm": 44.23,                  # trailing-twelve-month diluted EPS (Yahoo)
    # consensus EPS: current FY (~12m, FY2026 nearly done) $73.4, next FY (~24m, FY2027) $150.8
    "eps_fwd_12m": 73.39, "eps_fwd_24m": 150.77,


    "engine": _make_micron_engine(),
    # Through-cycle drivers. Ranges span the memory cycle trough→peak.
    "drivers": {
        # forward / through-cycle revenue ($m). TTM ≈ $90bn; mode $100bn.
        "rev":  {"lo": 72000, "md": 100000, "hi": 138000, "rho": 0.75},
        # through-cycle EBITDA margin (%). FY23 trough ~16, FY25 ~49, TTM ~76.
        "mgn":  {"lo": 44.0,  "md": 62.0,   "hi": 80.0,   "rho": 0.80},
        # EV/EBITDA multiple (×). Memory is capped by the market; cycle-position lever.
        "mult": {"lo": 8.5,   "md": 15.0,   "hi": 20.0,   "rho": 0.55},
        # net cash ($m). Super-cycle cash generation flipped MU to net cash.
        "nc":   {"lo": 8000,  "md": 20000,  "hi": 34000,  "rho": 0.25},
    },
    "reverse_dcf_target": "mgn",
    "reverse_dcf_label":  "Through-cycle EBITDA margin (at mode revenue / multiple / net cash)",
    "reverse_dcf_unit":   "%",

    # US-name benchmark & macro convention (matches Amazon / Tesla configs).
    "bench1_ticker": "^GSPC", "bench1_label": "S&P 500",
    "bench2_ticker": "^NDX",  "bench2_label": "Nasdaq 100",
    # Nvidia is the AI-capex bellwether that drives HBM demand — a genuine
    # demand-factor read for a memory name (more informative than rates here).
    "macro_ticker":  "NVDA",  "macro_label": "Nvidia (NVDA)",
    "peers": ["000660.KS", "WDC"],     # SK Hynix (HBM/DRAM arch-rival), Western Digital (NAND/HDD)

    "quality_score": 0.70,             # high current returns, but cyclical (FY23 loss) caps it

    "base_rates": {
        # inject.py appends " through the cycle" to this label — keep it short.
        "variable": "Company EBITDA margin (%)",
        "unit": "%",
        "series": [
            ("FY2022",            54.9, "prior up-cycle peak (EBITDA $16.9bn / rev $30.8bn)"),
            ("FY2023 trough",     16.0, "memory glut — GAAP gross margin turned negative"),
            ("FY2024",            38.2, "early recovery (EBITDA $9.6bn / rev $25.1bn)"),
            ("FY2025",            49.4, "up-cycle + first HBM ramp (EBITDA $18.5bn / rev $37.4bn)"),
            ("TTM (FY2026)",      75.6, "AI/HBM super-cycle peak (EBITDA $68.2bn / rev $90.3bn)"),
            ("through-cycle avg", 47.0, "blended mid-cycle normal — estimate"),
        ],
        "current_label": "TTM ≈ 75.6% (super-cycle peak)",
        "current_value": 75.6,
        "reversion_mid": 50.0,
    },
    # Owner earnings: trailing FCF, honestly flagged as suppressed by AI-era capex.
    "oe_anchor_m": 7639.0,
    "oe_note": ("trailing free cash flow ≈ $7.6bn — heavily suppressed by ~$16bn/yr "
                "AI-era fab & HBM capex (operating cash flow ran ~$51bn TTM); mid-cycle "
                "owner earnings on normalised capex would be materially higher"),

    "endpoints": [
        ("https://query1.finance.yahoo.com/v8/finance/chart/MU?range=5y&interval=1d",
         "Micron 5-year daily OHLC + regularMarketPrice",
         "I: realised vol / beta / momentum / drawdown / own-history percentile; Q: price-vs-EPS overlay"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/^GSPC?range=5y&interval=1d",
         "S&P 500 — US market benchmark for beta",
         "I: beta vs S&P 500"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/^NDX?range=5y&interval=1d",
         "Nasdaq 100 — tech-heavy benchmark for beta",
         "I: beta vs Nasdaq 100"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/NVDA?range=5y&interval=1d",
         "Nvidia — AI-capex bellwether / HBM demand factor",
         "I: beta vs Nvidia (AI-demand read for memory)"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/^TNX?range=1mo&interval=1d",
         "US 10-year Treasury yield — real-rate proxy",
         "J: owner-earnings yield vs real 10y"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/000660.KS?range=2y&interval=1d",
         "SK hynix (KRX) — HBM / DRAM arch-rival",
         "I: peer-relative 12m"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/WDC?range=2y&interval=1d",
         "Western Digital — NAND / storage peer",
         "I: peer-relative 12m"),
    ],
    "primary_sources": [
        ("Micron FY2025 annual results (fiscal year ended 28 Aug 2025)",
         "Revenue $37.4bn (+49% YoY), GAAP gross margin ~39.8%, operating income $9.8bn, "
         "EBITDA $18.5bn, net income $8.5bn, diluted EPS $7.59; operating cash flow $17.5bn, "
         "capex $15.9bn, FCF $1.7bn; total assets $82.8bn, equity $54.2bn, total debt $15.3bn, "
         "cash & short-term investments $10.3bn; HBM revenue ramping into an AI-driven demand step-up",
         "T thesis, Q quality, A engine, D forensics, E capital record"),
        ("Yahoo Finance fundamentals feed — Micron trailing-twelve-month (build time, FY2026 in progress)",
         "TTM revenue ≈ $90.3bn, EBITDA ≈ $68.2bn (~75.6% margin), gross margin ~72.6%, net margin ~55.9%, "
         "diluted EPS TTM $44.23, ROE ~66.6%, ROA ~34.9%; operating cash flow ≈ $51.4bn, FCF ≈ $7.6bn; "
         "total cash $26.0bn vs total debt $6.4bn (net cash ≈ +$19.6bn); current ratio 3.4×; beta 2.14; "
         "market cap ≈ $959bn; enterprise value ≈ $939bn; EV/EBITDA ≈ 13.8×; forward diluted EPS ≈ $150.8",
         "Q quality, A engine, D forensics, I asymmetry"),
        ("Micron annual history FY2022–FY2024 (Yahoo fundamentals-timeseries, fiscal years)",
         "FY2022 revenue $30.8bn / EPS $7.75; FY2023 revenue $15.5bn / EPS −$5.34 (the memory-glut trough, "
         "gross margin negative); FY2024 revenue $25.1bn / EPS $0.70 (early recovery) — the cycle the engine "
         "spans; balance-sheet, cash-flow and margin line items per year",
         "Q quality, C scenarios, J base rates"),
        ("Micron investor materials — HBM & data-center commentary",
         "HBM positioned as capacity-sold-out and gross-margin-accretive; DRAM ~70%+ of revenue, NAND the "
         "balance; data-center the fastest-growing end market on AI training/inference memory content growth; "
         "leading-edge DRAM (1-gamma) and HBM roadmap (HBM3E → HBM4) as the differentiation",
         "T thesis, B driver analysis"),
        ("Sell-side consensus (Yahoo financialData, 42 analysts, build time)",
         "Mean price target ≈ $1,492 (high $2,200 / low $361), aggregate rating strong-buy; forward P/E ≈ 5.6× "
         "on forward EPS ≈ $150.8 — the market pricing a cyclical peak that reverts, not a durable plateau",
         "F positioning, C scenarios"),
        ("Memory-oligopoly structure (industry reference)",
         "DRAM is a three-player oligopoly (Samsung, SK hynix, Micron); NAND more fragmented; consolidated, "
         "capital-disciplined supply is the structural case for shallower-than-historical down-cycles — the "
         "swing assumption behind the through-cycle margin",
         "T thesis, G peers, H kill-criteria"),
    ],
    "cut_replacements": (
        '<b>HBM / segment-level EBIT</b> — Micron discloses revenue by technology (DRAM vs NAND) and business '
        'unit, and gives HBM run-rate commentary, but not a standalone HBM or data-center <i>margin</i>; the '
        'engine therefore values the whole company on a through-cycle EBITDA multiple rather than splitting out '
        'an HBM leg on its own multiple — a deliberate simplification, not a hidden number. '
        '<b>Beneish M-score</b> — needs eight two-year ratios not cleanly disclosed across a loss year; a '
        'half-estimated score is worse than none. '
        '<b>Options-implied skew, precise borrow cost, and daily insider-flow</b> — not reliably fetchable from a '
        'public API. '
        '<b>An exact forward multiple</b> — the forward EPS is a consensus estimate, shown for context, not '
        'asserted as fact. '
        'Everything else previously "cut" (factor &amp; NVDA-demand betas, own-history percentile, momentum, '
        'realised vol, drawdown, peer 12m relative, base-rate frequencies, owner-earnings yield vs real rate) is '
        '<b>included</b> in Modules I &amp; J and computed live from the Yahoo Finance v8 chart API.'
    ),
    "strictbar_replacement": None,
    # T·Q·D·E·G·F·A·B·C·U·H·I·J = 13 reads. tallies.py counts the live page chips;
    # this is only the fallback (T + D authored bull, U injected bull; rest mixed).
    "tally": {"bull": 3, "mixed": 10, "bear": 0},

    # -------------------- Perfect-execution 10-year ceiling (Module U) --------------------
    "bull_case": {
        "horizon_years": 10,
        "label": "AI-memory secular winner, disciplined oligopoly, full cycle of execution",
        "narrative": (
            "Micron's ceiling is the AI-memory secular winner: HBM stays capacity-constrained and margin-"
            "accretive, the DRAM/NAND oligopoly holds supply discipline so down-cycles are shallow, memory "
            "content per AI system keeps compounding, and Micron sustains a structurally higher through-cycle "
            "margin than the 2015–2024 average — while the market still refuses to pay a rich multiple on a "
            "memory name, so the re-rate is modest and the compounding does the work."
        ),
        "method_note": (
            "revenue compounds at the assumed CAGR; EBITDA margin and EV/EBITDA ease from today to terminal via "
            "smoothstep; FCF = EBITDA × (1 − tax) × conversion (deliberately low — memory is fab-capex-heavy); "
            "split into dividend / buyback / retained cash; fair value = multiple × EBITDA + net cash, ÷ shares"
        ),
        "path": {
            "sales_0": 100000.0,     # $m — through-cycle revenue base (TTM ≈ $90bn, mode $100bn)
            "mgn_0": 62.0,           # % EBITDA margin (below the ~76% TTM super-peak)
            "mlt_0": 15.0,           # × EV/EBITDA (today-ish through-cycle)
            "nc_0": 20000.0,         # $m net cash
            "shares_0": _SHARES_M,   # m shares
            "sales_cagr": 0.10,      # 10% — AI memory content + bit-demand growth, perfect execution
            "mgn_term": 55.0,        # % — structurally elevated vs history, below current peak
            "mlt_term": 11.5,        # × — memory stays multiple-capped even as a secular winner
            "tax_rate": 0.15,        # low effective tax (credits / CHIPS-era incentives)
            "fcf_on_ebita": 0.45,    # LOW cash conversion — the memory-capex reality is the key guard
            "payout_ratio": 0.10,    # small dividend
            "buyback_ratio": 0.30,   # buybacks the main return of capital
            "discount_rate": 0.11,   # higher for a high-beta (2.1) cyclical
            "buyback_at_fv": True,
        },
        "milestones": [
            {"year": 2, "text": "HBM stays sold out and gross-margin-accretive; the DRAM/NAND cycle stays shallow (no negative-gross-margin quarter); through-cycle EBITDA margin holds above ~55%."},
            {"year": 5, "text": "Memory content per AI server keeps rising; revenue clearly above $150bn through-cycle; the market grudgingly re-rates memory toward a low-teens EV/EBITDA as down-cycle amplitude visibly compresses."},
            {"year": 8, "text": "Micron is the durable #2/#3 in HBM with leading-edge DRAM; capex intensity eases as the fab base matures, lifting FCF conversion; buybacks shrink the share count materially."},
            {"year": 10, "text": "Through-cycle EBITDA margin ~55%, revenue ~$260bn, an ~11–12× multiple the market now accepts for shallower cycles — the default terminal state this calculator prices."},
        ],
        "guards": [
            "Memory reverts to type: a classic glut (Samsung/SK hynix add HBM & DRAM supply) collapses pricing and the through-cycle margin back toward the historical 30–45% band.",
            "HBM commoditises — three vendors at scale competes the AI-memory premium away faster than content growth adds it.",
            "The fab-capex treadmill never eases: sustaining leading-edge DRAM/HBM keeps FCF conversion low, so earnings never fully become owner cash.",
            "The market is right to cap the multiple — a high-beta (2.1) name that just 7×'d prices a peak, and a de-rate on the first demand wobble unwinds years of compounding.",
        ],
    },
}
