"""Investor AB (Nasdaq Stockholm: INVE-B.ST) — pipeline configuration.

Northern Europe's flagship industrial holding company (Wallenberg sphere,
founded 1916). Three business areas:

  1. Listed Companies (~76% of assets) — significant minority stakes in
     ABB, Atlas Copco, AstraZeneca, SEB, Saab, Sobi, Epiroc, Nasdaq,
     Wärtsilä, Ericsson and smaller consumer names.
  2. Patricia Industries (~17%) — wholly-owned private subsidiaries
     (Mölnlycke, Nova Biomedical, Laborie, Sarnova, Permobil, Piab, …).
  3. Investments in EQT (~7%) — EQT AB stake + EQT fund commitments.

Valuation framing (Module A engine): a holding company is valued on
**adjusted net asset value**, not on consolidated earnings (IFRS revaluations
of listed stakes make trailing P/E unusable). Fair value per share =

    (listed + patricia + eqt − net debt) × 1 000 / shares
    × (1 − discount_to_NAV / 100)

The reverse-DCF solves for the **holding-company discount to adjusted NAV**
the market is implying — the single most contested Investor variable
(historically Nordic holdcos trade at a 5–20% discount; quality + track
record can compress that to par or a premium).

All figures anchor to Investor's Q2 2026 interim report (adjusted NAV
SEK 1,214.7bn / SEK 397 per share on 30 Jun 2026) and to live Yahoo
fundamentals for Investor and every material listed holding.
"""
from __future__ import annotations
from typing import Any


# Shares outstanding excl. repurchased (Investor Q2'26: NAV / NAV-per-share).
_SHARES_M = 3062.9


def _make_investor_engine():
    """Adjusted-NAV × (1 − holdco discount), per share.

    Drivers are in SEK bn (listed / patricia / eqt / net debt) and percent
    (discount). Mirrors the page's JS simulate() exactly — keep in lock-step.
    """
    shares = _SHARES_M

    def engine(d: dict) -> float:
        nav_bn = d["listed"] + d["patricia"] + d["eqt"] - d["nd"]
        nav_ps = nav_bn * 1000.0 / shares          # SEK per share
        return nav_ps * (1.0 - d["disc"] / 100.0)

    return engine


def _bull_year_engine(d: dict) -> float:
    """Bull-case year fair value: price/NAV multiple × NAV / shares.

    ``sales`` is adjusted NAV in SEK m; ``mlt`` is the P/NAV ratio
    (1.0 = at NAV); ``mgn`` is unused for valuation (it drives cash only).
    """
    sh = d["shares"]
    if sh <= 0:
        return 0.0
    return d["mlt"] * d["sales"] / sh


INVESTOR_CONFIG: dict[str, Any] = {
    "ticker": "INVE-B.ST",
    "html_file": "investor-pipeline.html",
    "currency": "kr",
    "pipeline_price": 397.0,           # live B-share close at authoring; re-synced each build
    "shares_m": _SHARES_M,
    "consensus_pt": 393.8,             # 5-analyst mean (Yahoo financialData) — near spot
    "eps_ttm": 85.67,                  # IFRS incl. reval gains — NOT a quality signal
    "eps_fwd_12m": 15.75, "eps_fwd_24m": 15.75,

    "engine": _make_investor_engine(),
    # NAV legs (SEK bn) + holdco discount (%). Ranges span a full equity cycle
    # for the listed book, a private-market re-rate for Patricia, and the
    # historical holdco-discount band for Nordic industrial conglomerates.
    "drivers": {
        # Listed Companies stake values at market (Q2'26 = SEK 946bn).
        "listed":   {"lo": 720.0, "md": 946.0, "hi": 1180.0, "rho": 0.80},
        # Patricia Industries estimated market values excl. cash (Q2'26 ≈ 208).
        "patricia": {"lo": 160.0, "md": 208.0, "hi": 270.0,  "rho": 0.45},
        # EQT AB stake + fund investments (Q2'26 = 88).
        "eqt":      {"lo":  55.0, "md":  88.0, "hi": 125.0,  "rho": 0.55},
        # Net debt (Q2'26 = 23.3); target leverage 0–10% of assets.
        "nd":       {"lo":  10.0, "md":  23.3, "hi":  55.0,  "rho": 0.20},
        # Holding-company discount to adjusted NAV (%). Negative = premium.
        # History: often 5–20%; currently ≈ 0% (price ≈ NAV/share).
        "disc":     {"lo":  -5.0, "md":   5.0, "hi":  20.0,  "rho": 0.35},
    },
    "reverse_dcf_target": "disc",
    "reverse_dcf_label":  "Holdco discount to adjusted NAV (at mode legs / net debt)",
    "reverse_dcf_unit":   "%",
    # Lower discount is "richer" pricing — invert so the gap reads correctly
    # (implied 0% vs mode 5% = market pricing a tighter discount than base).
    "reverse_dcf_invert_sign": True,

    # Nordic benchmarks + industrial macro.
    "bench1_ticker": "^OMX",   "bench1_label": "OMX Stockholm",
    "bench2_ticker": "^STOXX", "bench2_label": "STOXX Europe 600",
    "macro_ticker":  "ATCO-A.ST", "macro_label": "Atlas Copco (largest industrial holding)",
    "peers": ["INDU-C.ST", "LUND-B.ST"],   # Industrivärden, Lundbergföretagen

    "quality_score": 0.88,             # fortress track record, lean cost, low leverage

    "base_rates": {
        # inject.py appends " through the cycle" — keep the label short.
        "variable": "Holdco discount to adj. NAV (%)",
        "unit": "%",
        "series": [
            ("deep-discount era",  20.0, "historical Nordic holdco wide band"),
            ("mid-cycle typical",  12.0, "Industrivärden / Investor mid-2010s zone"),
            ("quality compression", 5.0, "post-2020 quality-holdco norm"),
            ("at-NAV (Q2'26)",      0.0, "price ≈ SEK 397 = adj. NAV/share"),
            ("premium (rare)",     -5.0, "brief premiums in euphoric tapes"),
            ("mode assumption",     5.0, "base-case engine mode"),
        ],
        "current_label": "≈ 0% (price at adjusted NAV)",
        "current_value": 0.0,
        "reversion_mid": 8.0,
    },
    # Owner earnings ≈ dividends + net distributions received, not IFRS NI.
    "oe_anchor_m": 17000.0,
    "oe_note": ("owner cash ≈ SEK 17bn/yr — H1'26 listed dividends SEK 13.3bn "
                "(run-rate) + Patricia distributions (~SEK 2–5bn) + EQT proceeds; "
                "NOT IFRS net income (SEK 157bn FY25, dominated by unrealised "
                "revaluations of listed stakes)"),

    "endpoints": [
        ("https://query1.finance.yahoo.com/v8/finance/chart/INVE-B.ST?range=5y&interval=1d",
         "Investor B 5-year daily OHLC + regularMarketPrice",
         "I: realised vol / beta / momentum / drawdown / own-history percentile; Q: price overlay"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/^OMX?range=5y&interval=1d",
         "OMX Stockholm — domestic market benchmark",
         "I: beta vs OMX"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/^STOXX?range=5y&interval=1d",
         "STOXX Europe 600 — European equity benchmark",
         "I: beta vs STOXX 600"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/ATCO-A.ST?range=5y&interval=1d",
         "Atlas Copco — largest industrial listed holding (demand factor)",
         "I: beta vs industrial end-markets"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/^TNX?range=1mo&interval=1d",
         "US 10-year Treasury yield — real-rate proxy",
         "J: owner-earnings yield vs real 10y"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/INDU-C.ST?range=2y&interval=1d",
         "Industrivärden C — Nordic industrial holdco peer",
         "I: peer-relative 12m"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/LUND-B.ST?range=2y&interval=1d",
         "Lundbergföretagen B — Swedish holdco / investment peer",
         "I: peer-relative 12m"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/ABB.ST?range=2y&interval=1d",
         "ABB — largest single listed holding by value",
         "I: portfolio concentration read"),
    ],
    "primary_sources": [
        ("Investor AB Interim report January–June 2026 (16 Jul 2026)",
         "Adjusted NAV SEK 1,214.7bn (SEK 397/share) on 30 Jun 2026, +9% in Q2 with dividend added back; "
         "TSR +15% (Q2) / +23% (H1) vs SIXRX +9% / +8%; Listed Companies SEK 946.2bn (76% of assets, TR +14%); "
         "Patricia Industries estimated MV excl. cash SEK 207.9bn (17%), major-sub sales +6% / organic +7% / adj. EBITA +16%; "
         "Investments in EQT SEK 88.4bn (7%, value −2%); net debt SEK 23.3bn, leverage 1.9%, gross cash SEK 28.8bn; "
         "management cost rolling-12m SEK 803m (0.07% of adj. NAV); consolidated net sales Q2 SEK 17.9bn, "
         "basic EPS SEK 38.28; 20-year avg annual total return 16.5% vs SIXRX 10.2%",
         "T thesis, P portfolio, A engine, D forensics, E capital record, Q quality"),
        ("Investor AB Year-end report 2025 / Annual report 2025",
         "FY2025 adjusted NAV SEK 1,087.1bn (SEK 355/share), +14% with dividend added back; TSR +15% vs SIXRX +13%; "
         "dividend SEK 5.60/share; Listed total return +22% for the year; Patricia estimated MV return −9% for 2025; "
         "ownership register and share-class structure (A/B dual class, Wallenberg Foundations ~23% capital / ~50% votes)",
         "T thesis, E capital, F positioning, Q quality"),
        ("Yahoo Finance fundamentals feed — Investor B + all material listed holdings (build time)",
         "INVE-B.ST: price ~SEK 397, mcap ~SEK 1,216bn, trailing P/E ~4.6× (IFRS reval-distorted), forward P/E ~25×, "
         "P/B ~1.24×, book ~SEK 321, beta ~0.78, div yield ~1.4%, ROE ~27% (IFRS), net debt/equity low; "
         "per-holding stake values, P/E, ROE, operating margins and growth for ABB, Atlas Copco, AstraZeneca, SEB, "
         "Saab, Sobi, Epiroc, Nasdaq, Wärtsilä, Ericsson, Electrolux, Husqvarna, Electrolux Professional, EQT AB",
         "P portfolio SOTP, Q quality, G peers, A engine"),
        ("Patricia Industries subsidiary disclosures (Q2'26 valuation overview)",
         "Mölnlycke SEK 75.3bn (EV/adj. LTM EBITDA 13.8×, org. sales +2%, EBITA margin 27.7%); "
         "Nova Biomedical SEK 31.4bn (17.2×, +10% org.); Laborie SEK 30.3bn (15.8×, +13% org.); "
         "Sarnova SEK 18.9bn; Permobil SEK 12.6bn; BraunAbility SEK 11.1bn (+12% org.); Piab SEK 11.0bn; "
         "Vectura SEK 4.0bn (+42% org.); Tre Skandinavien SEK 10.8bn (40% stake)",
         "P portfolio, T thesis, B driver analysis"),
        ("Sell-side consensus (Yahoo financialData, 5 analysts, build time)",
         "Mean PT ≈ SEK 394 (high 440 / low 327), aggregate rating hold — the street sees the stock as fairly "
         "priced at NAV, not a deep-value discount trade",
         "F positioning, C scenarios"),
        ("Nordic holdco peer context (Industrivärden, Lundbergföretagen, Kinnevik)",
         "Industrivärden and Lundbergs are the clean industrial-holdco comps; Kinnevik is a growth/tech holdco "
         "with a different risk profile (and a large 2022–25 drawdown). Discount-to-NAV is the common language "
         "across the peer set; Investor's multi-decade outperformance vs SIXRX is the quality differentiator",
         "G peers, J base rates"),
    ],
    "cut_replacements": (
        '<b>IFRS consolidated earnings / trailing P/E</b> — dominated by unrealised fair-value changes in listed '
        'stakes; a 4.6× trailing P/E is an accounting artefact, not a value signal. The engine therefore values '
        'Investor on <i>adjusted NAV × (1 − holdco discount)</i>, which is how the company and the market actually '
        'think about it. '
        '<b>Full private-company DCF for every Patricia subsidiary</b> — Investor discloses estimated market values '
        'and applied EV/EBITDA multiples for the majors; re-underwriting Mölnlycke from scratch would add noise, not '
        'signal. We use Investor\'s own estimated MVs as the Patricia leg and stress them in the MC. '
        '<b>Beneish M-score / manufacturing forensics</b> — meaningless on a holding-company balance sheet. '
        '<b>Options-implied skew, precise borrow cost, daily insider-flow</b> — not reliably fetchable from a public API. '
        'Everything else previously "cut" (factor betas, own-history percentile, momentum, realised vol, drawdown, '
        'peer 12m relative, base-rate frequencies, owner-earnings yield vs real rate) is <b>included</b> in Modules I '
        '&amp; J and computed live from the Yahoo Finance v8 chart API.'
    ),
    "strictbar_replacement": None,
    # T·P·Q·D·E·G·F·A·B·C·U·H·I·J — tallies.py counts live chips; this is fallback.
    # tallies.py counts live page chips (incl. injected I/J/U); this is fallback only.
    "tally": {"bull": 6, "mixed": 7, "bear": 1},

    # -------------------- Perfect-execution 10-year ceiling (Module U) --------------------
    "bull_case": {
        "horizon_years": 10,
        "label": "Best-in-class compounder, zero holdco discount, AI/automation portfolio fully recognised",
        "narrative": (
            "Investor's ceiling is the permanent compounder trading at a modest premium to NAV: the listed book "
            "(ABB automation, Atlas Copco / Epiroc electrification, Saab defence, AstraZeneca / Sobi health, "
            "Nasdaq market infrastructure) keeps compounding mid-teens through AI · automation · energy · defence "
            "cycles; Patricia's health-tech platforms (Mölnlycke, Laborie, Nova) re-rate as durable cash machines; "
            "EQT stays a top-quartile alternatives franchise; management cost stays sub-10 bp; and the market stops "
            "applying a holdco discount to a vehicle that has beaten the SIXRX by ~6 pp annualised for 20 years."
        ),
        "method_note": (
            "adjusted NAV compounds at the assumed CAGR; the P/NAV multiple eases from today (~1.0×) to a modest "
            "terminal premium via smoothstep; 'earnings yield' on NAV funds dividends (high payout) with a small "
            "buyback; fair value = P/NAV × NAV ÷ shares"
        ),
        "year_engine": _bull_year_engine,
        "path": {
            "sales_0": 1214700.0,    # SEK m adjusted NAV (Q2'26)
            "mgn_0": 1.5,            # % owner-cash yield on NAV (~SEK 18bn)
            "mlt_0": 1.00,           # × P/NAV (at par today)
            "nc_0": 0.0,             # net debt already inside NAV
            "shares_0": _SHARES_M,
            "sales_cagr": 0.11,      # 11% NAV CAGR — below 20y TSR, ambitious but not fantasy
            "mgn_term": 1.8,         # % — slightly higher cash conversion as Patricia matures
            "mlt_term": 1.08,        # × — modest premium for proven compounder
            "tax_rate": 0.0,         # already after-tax cash to the holdco
            "fcf_on_ebita": 1.0,     # yield is already cash
            "payout_ratio": 0.80,    # high dividend tradition
            "buyback_ratio": 0.05,   # small opportunistic buybacks
            "discount_rate": 0.09,
            "buyback_at_fv": True,
        },
        "milestones": [
            {"year": 2, "text": "Listed book keeps compounding; ABB/Atlas/Epiroc capture automation & electrification; holdco discount stays ≤5%; dividend grows with portfolio cash."},
            {"year": 5, "text": "Patricia health-tech platforms (Mölnlycke, Laborie, Nova) visibly re-rate; Saab defence backlog converts; NAV clearly above SEK 2,000bn; market accepts ~par-to-premium on the vehicle."},
            {"year": 8, "text": "EQT franchise + listed tech/industrials make Investor a pure-play on European industrial AI/automation; management cost still sub-10 bp of NAV."},
            {"year": 10, "text": "NAV ~SEK 3.4tn, P/NAV ~1.08×, steadily rising dividend — the default terminal state this calculator prices."},
        ],
        "guards": [
            "A broad equity bear market crushes the 76% listed book; holdco discount widens back to 15–20% as forced sellers appear.",
            "Patricia private multiples deflate (healthcare/tech EV/EBITDA compression) and estimated MVs prove optimistic.",
            "EQT has a multi-year fundraising/performance air-pocket; the 7% EQT leg and the alternatives narrative both hurt.",
            "Governance / Wallenberg control discount re-opens (dual-class backlash, related-party optics) even if operations are fine.",
            "Europe de-industrialises or AI-capex pauses long enough that ABB/Atlas/Epiroc — the growth spine — stall.",
        ],
    },
}
