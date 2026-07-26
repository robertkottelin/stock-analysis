"""Inission AB (publ) (Nasdaq Stockholm: INISS-B) — pipeline configuration.

Kept in its own module (same pattern as config_terveystalo.py / config_tesla.py)
and wired into the STOCKS registry at the bottom of stocks/config.py. No framework
code under ../utils needs to know about it.

Inission is a Nordic electronics manufacturing services (EMS) roll-up plus a
smaller power-electronics OEM (Inission Power, formerly Enedo). The market prices
it the way EMS industrial peers are priced: EV/EBITA on group operating profit
less interest-bearing net debt — not on earnings, which are geared by interest,
acquisition amortisation and working-capital swings.

ENGINE — a transparent single-leg EBITA × multiple model matching the JS engine
in inission-pipeline.html Module A exactly:

    fair value  = (sales × EBITA_margin% / 100 × EV/EBITA − net_debt) / shares

Net debt is the company-reported figure (incl. IFRS-16 leases). EBITA is post-
ROU depreciation, so the lease claim sits inside the multiple framework; ABG and
Yahoo both mark EV off the lease-inclusive net debt (~SEK 466m at Q1'26).

DATA BASIS (sourced; the pipeline re-fetches the live spot/betas itself):
  - Spot SEK 68.0 (Yahoo regularMarketPrice, 2026-07-20); 52w range SEK 36–78.8.
  - FY2025 year-end report (19 Feb 2026): net sales SEK 2,206m; EBITA SEK 111.1m
    (5.0% margin); adj. EBITA SEK 133.7m (6.1%); EBIT SEK 105.9m; net profit to
    common SEK 29.8m; EPS SEK 1.30; operating CF SEK 178.5m; FCF SEK 153.3m;
    net debt SEK 468.1m (ex-lease SEK 244.4m); equity ratio 39.7%; ~22.5m avg
    diluted shares.
  - Q1'26 interim (6 May 2026): net sales SEK 664.3m (+37.4%, organic +26.3%);
    EBITA SEK 46.7m (7.0% vs 4.1%); EBIT SEK 45.8m; order intake SEK 709.8m;
    backlog SEK 1,509m; book-to-bill 1.1; LTM sales SEK 2,387m / EBITA 137.8m
    (5.8%); net debt SEK 465.9m; equity ratio 40.2%; avg diluted shares 23.05m.
    Segments: EMS sales SEK 568.3m / EBITA 42.9m (7.5%); Power OEM sales SEK 96.0m
    / EBITA 3.8m (3.9%, turnaround from −3.6%).
  - Financial targets (19 Feb 2026): FY2026 sales SEK 2,300–2,500m, EBITA margin
    >6%; medium-term annual growth >15% (10% organic + 5% M&A), EBITA margin >9%.
  - ABG Sundal Collier (13 Apr 2026, pre-Q1): 2026e sales SEK 2,453m, adj. EBITA
    SEK 167m (6.8%), EPS SEK 4.51 / adj. 4.88; fair-value range SEK 50–90; trading
    12×–9× 2026–28e P/E vs peers 17×–13×.
  - Consensus 12m PT ~SEK 75 (MarketScreener / Google Finance blend, ~+10% upside).
"""
from __future__ import annotations
from typing import Callable, Any


_SHARES_M = 23.05       # Q1'26 average diluted shares (millions)
_NET_DEBT_M = 450.0     # mode net debt MSEK (Q1'26 reported 465.9; range in drivers)


def _make_inission_engine() -> Callable[[dict], float]:
    """Per-share fair value in SEK from one draw of the four drivers.

    Classic EMS industrial: EV = EBITA × EV/EBITA, equity = EV − net debt.
    EBITA = sales × margin% / 100. Net debt is the company-reported
    (lease-inclusive) figure.
    """
    def engine(d: dict) -> float:
        ebita = d["sales"] * d["mgn"] / 100.0     # MSEK
        ev = d["mlt"] * ebita                      # MSEK
        return (ev - d["nd"]) / _SHARES_M          # SEK/share
    return engine


INISSION_CONFIG: dict[str, Any] = {
    # ---- identity & market ----
    "ticker":         "INISS-B.ST",
    "html_file":      "inission-pipeline.html",
    "currency":       "kr",
    "pipeline_price": 68.0,            # authored spot; live spot re-fetched at build
    "shares_m":       _SHARES_M,
    "consensus_pt":   75.0,            # ~SEK 75 blend (Google Finance / MarketScreener)
    "eps_ttm":        2.70,            # LTM EPS after Q1'26 (company 2.7)
    "eps_fwd_12m":    4.51, "eps_fwd_24m": 5.35,   # ABG 2026e / 2027e EPS

    # ---- Module A engine ----
    "engine": _make_inission_engine(),
    "drivers": {
        # Group net sales, MSEK. FY2025 2,206; LTM 2,387; guidance 2,300–2,500;
        # ABG 2,453; Q1 run-rate + order book support mid-to-high 2,500s if
        # momentum holds. Mode 2,550 sits above guidance midpoint and near ABG,
        # with a genuine left tail if industrial demand rolls over.
        "sales": {"lo": 2100.0, "md": 2550.0, "hi": 2900.0, "rho": 0.70},
        # Group EBITA margin %. FY2025 reported 5.0% / adj. 6.1%; LTM 5.8%;
        # Q1'26 7.0%; target >6% (2026) then >9% medium-term. Mode 6.8 matches
        # ABG adj. and sits between LTM and the Q1 print — two-sided risk.
        "mgn":   {"lo": 4.0, "md": 6.8, "hi": 8.5, "rho": 0.72},
        # EV/EBITA multiple — the reverse-DCF target. Nordic EMS peers trade
        # roughly mid-teens on earnings; ABG marks ~11× adj. EV/EBITA. Mode 11.5
        # with a left tail if the re-rating from SEK 36 → 68 fades.
        "mlt":   {"lo": 7.5, "md": 11.5, "hi": 14.5, "rho": 0.60},
        # Net debt MSEK (company-reported, lease-inclusive). Q1'26 465.9;
        # ex-lease 213. Mode 450 allows for modest M&A re-levering or FCF delever.
        "nd":    {"lo": 280.0, "md": 450.0, "hi": 620.0, "rho": -0.25},
    },
    "reverse_dcf_target": "mlt",
    "reverse_dcf_label":  "EV/EBITA multiple (at mode sales / EBITA margin / net debt)",
    "reverse_dcf_unit":   "×",

    # ---- Module I regressions ----
    "bench1_ticker": "^OMX", "bench1_label": "OMX Stockholm",
    "bench2_ticker": "^STOXX", "bench2_label": "STOXX 600",
    "macro_ticker":  None,
    "macro_label":   None,
    "peers": ["HANZA.ST", "NOTE.ST", "AQ.ST"],   # Nordic EMS / electronics manufacturing peers

    # ---- Module J ----
    # 0.58 blends solid growth (Q1 +37%), improving margins and FCF conversion
    # against thin absolute profitability (FY25 EBITA 5%), inventory-heavy WC,
    # acquisition goodwill and a ~2.0× lease-adj ND/EBITDA.
    "quality_score": 0.58,

    # Reference class: group EBITA margin through the cycle — the operational
    # story and the mean-reversion risk around the medium-term >9% target.
    "base_rates": {
        "variable": "Group EBITA margin (%)",
        "unit": "%",
        "series": [
            ("2021",            5.2,  "reported (ABG history) — post-COVID rebuild"),
            ("2022",            4.7,  "reported — volume ramp, margin pressure"),
            ("2023",            7.4,  "reported peak — strong industrial demand"),
            ("2024",            5.8,  "reported — softer year, ~flat sales"),
            ("2025",            5.0,  "reported (adj. 6.1%) — listing/transfer costs"),
            ("LTM Q1'26",       5.8,  "company LTM after strong Q1 print"),
            ("2026E ABG",       6.8,  "ABG adj. EBITA margin — above company >6% target"),
            ("med-term target", 9.0,  "company medium-term EBITA margin ambition"),
        ],
        "current_label": "LTM = 5.8% (Q1'26 run-rate 7.0%)",
        "current_value": 5.8,
        "reversion_mid": 6.5,
    },

    # Owner-earnings anchor, MSEK. FY2025 FCF SEK 153.3m (OCF 178.5 − capex ~25);
    # LTM FCF ~SEK 171m. Capex is light for an EMS (factories are leased/owned
    # lean); the real cash sink is working capital and M&A.
    "oe_anchor_m": 153.0,
    "oe_note": ("FY2025 free cash flow SEK 153.3m (operating cash flow SEK 178.5m less "
                "capex ~SEK 25m; year-end report Feb 2026) as the owner-earnings proxy; "
                "LTM FCF ~SEK 171m after Q1'26. Cash conversion is genuine but lumpy — "
                "FY2024 FCF was −SEK 8m on WC absorption — so the yield is not a steady annuity."),

    # ---- § Audit appendix ----
    "endpoints": [
        ("https://query1.finance.yahoo.com/v8/finance/chart/INISS-B.ST?range=5y&interval=1d",
         "Inission 5-year daily OHLC + regularMarketPrice + 52w range.",
         "I: realised vol / beta / momentum / drawdown / own-history percentile · J: base rates"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/%5EOMX?range=5y&interval=1d",
         "OMX Stockholm All-Share — benchmark for local beta.", "I: beta vs OMX Stockholm"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/%5ESTOXX?range=5y&interval=1d",
         "STOXX Europe 600 — pan-European benchmark.", "I: beta vs STOXX 600"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/%5ETNX?range=1mo&interval=1d",
         "US 10-year Treasury yield — real-rate proxy.", "J: owner-earnings yield vs real 10y"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/HANZA.ST?range=2y&interval=1d",
         "HANZA (Nasdaq Stockholm) — Nordic EMS peer.", "I: peer-relative 12m"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/NOTE.ST?range=2y&interval=1d",
         "NOTE AB (Nasdaq Stockholm) — Nordic EMS peer.", "I: peer-relative 12m"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/AQ.ST?range=2y&interval=1d",
         "AQ Group (Nasdaq Stockholm) — Nordic electronics manufacturing peer.", "I: peer-relative 12m"),
    ],
    "primary_sources": [
        ("Inission AB Interim Report January–March 2026 (6 May 2026)",
         "Net sales SEK 664.3m (+37.4%, organic +26.3%, Selteka +SEK 53.4m); EBITA SEK 46.7m (7.0% vs 4.1%); "
         "EBIT SEK 45.8m; order intake SEK 709.8m; backlog SEK 1,509m; book-to-bill 1.1; LTM sales SEK 2,387m / "
         "EBITA 137.8m (5.8%); net debt SEK 465.9m (ex-lease 213.0); equity ratio 40.2%; avg diluted shares 23.05m; "
         "OCF SEK 43.6m. Segments: EMS SEK 568.3m / EBITA 42.9m (7.5%); Inission Power (ex-Enedo) SEK 96.0m / "
         "EBITA 3.8m (3.9%). FY2026 target sales SEK 2,300–2,500m, EBITA margin >6%; medium-term growth >15% and "
         "EBITA margin >9%.",
         "A engine, B driver analysis, C scenarios, D forensics, E capital, H kill-criteria, Q dashboard"),
        ("Inission AB Year-End Report 2025 (19 Feb 2026)",
         "Net sales SEK 2,206m (+2.6%); EBITA SEK 111.1m (5.0%); adj. EBITA SEK 133.7m (6.1%); EBIT SEK 105.9m; "
         "net profit to common SEK 29.8m; EPS SEK 1.30; OCF SEK 178.5m; FCF SEK 153.3m; net debt SEK 468.1m; "
         "equity ratio 39.7%; dividend SEK 0.60/share. New financial targets presented.",
         "A engine, D forensics, E capital record, Q dashboard"),
        ("ABG Sundal Collier — Inission equity research (13 Apr 2026)",
         "2026e sales SEK 2,453m, adj. EBITA SEK 167m (6.8%), EPS SEK 4.51 / adj. 4.88; 2027e EPS SEK 5.35; "
         "fair-value range SEK 50–90; trading 12×–9× 2026–28e P/E vs peers 17×–13×; ND/EBITDA ~1.7× lease-adj.",
         "B driver analysis, F positioning, G peers, C scenarios"),
        ("stockanalysis.com / Fiscal.ai — Inission financials (updated May 2026)",
         "Multi-year income statement, balance sheet and cash flow (FY2021–2025 + TTM); gross margin ~44%; "
         "inventory SEK ~590m; goodwill SEK 224m; tangible book ~SEK 18.5/share.",
         "D forensics, Q dashboard"),
        ("Inission largest-shareholders / ownership (2025–2026)",
         "Founder/insider-heavy (~52% insider ownership per Yahoo); free float ~44% (ABG); Chairman Olle Hulteberg "
         "sold 350k Class B shares Feb 2026 but remains a large long-term holder; shareholder count 2,145.",
         "F positioning"),
        ("MarketScreener / Google Finance — Inission consensus (2026)",
         "Consensus 12m PT ~SEK 75 (~+10% at SEK 68); limited coverage (≈1–2 brokers); Strong Buy/positive bias "
         "post-Q1 beat and guidance revision.",
         "F positioning"),
    ],

    # ---- footer & scorecard ----
    "cut_replacements": (
        '<b>The single-leg EBITA × EV/EBITA engine is a transparent proxy, not a hidden number.</b> '
        'Inission reports two segments (EMS + Power OEM) but the market prices the group on consolidated '
        'EBITA; segment-level SOTP would mainly re-allocate the same profit. Net debt is the '
        'company-reported lease-inclusive figure (~SEK 466m) — matching ABG/Yahoo EV construction — even '
        'though ex-lease net debt is only ~SEK 213m. Using ex-lease ND would lift fair value by ~SEK 10/share '
        'without changing the operational story. '
        '<b>Beneish M-score</b> — needs eight two-year ratios not fully disclosed for an acquisition-built EMS; '
        'a half-estimated score is worse than none. '
        '<b>Options skew, precise borrow cost, and detailed short-interest flow</b> — not reliably fetchable for a '
        'mid-cap Stockholm name from a public API; would slot in from a Bloomberg terminal. '
        'Everything else previously flagged as "cut" (factor betas, own-history percentile, momentum, realised vol, '
        'drawdown, 12-month peer relative return, base-rate frequencies, owner-earnings yield vs real rate) is '
        '<b>included</b> in Modules I &amp; J and computed live from the Yahoo Finance v8 chart API.'
    ),
    "strictbar_replacement": (
        '<div class="strictbar"><b>What this build adds.</b> A single-leg <b>sales × EBITA-margin × EV/EBITA − net debt</b> '
        'engine for a Nordic EMS roll-up (Inission EMS + Inission Power OEM), with the Q1\'26 demand surge '
        '(+37% sales, 7.0% EBITA margin) and the medium-term &gt;9% margin target carried as explicit drivers. '
        'Two institutional modules computed live from the Yahoo Finance v8 chart API: <b>I — Price-asymmetry '
        'layer</b> (reverse-DCF on the EV/EBITA multiple, Kelly f*, payoff-asymmetry, VaR/CVaR, realised vol, '
        'betas vs OMX Stockholm &amp; STOXX 600, own-history percentile, HANZA/NOTE/AQ 12m relative) and '
        '<b>J — Base rates &amp; factor composite</b> (the group\'s own EBITA-margin reference class, empirical '
        'return base-rates, V/Q/M/L factor score, owner-earnings yield vs real 10y). Balance-sheet and P&amp;L '
        'facts are from the FY2025 year-end and Q1\'26 interim releases; nothing is asserted from memory.</div>'
    ),
    # tallies.py counts the live chips on the page; this is only the fallback.
    "tally": {"bull": 4, "mixed": 6, "bear": 1},

    # ------------------------------------------------------------------
    # Perfect-execution / 10-year bull path (utils/bullcase.py → Module U)
    # Medium-term >9% EBITA margin achieved and held; mid-single-digit organic
    # plus bolt-on M&A; multiple re-rates toward quality EMS peers.
    # ------------------------------------------------------------------
    "bull_case": {
        "horizon_years": 10,
        "label": "Nordic EMS compounder — margin to 9%+, disciplined M&A",
        "narrative": (
            "Inission's ceiling is a Nordic EMS platform that compounds mid-to-high single digits organically, "
            "keeps adding bolt-ons at sensible multiples, and defends a high-single-digit EBITA margin through "
            "the cycle — re-rating toward quality manufacturing peers, not a software multiple."
        ),
        "method_note": (
            "sales compound at assumed CAGR; margin and EV/EBITA ease from today to terminal via smoothstep; "
            "FCF = EBITA × (1 − tax) × conversion; split into dividend / buyback / cash; "
            "fair value = multiple × EBITA − net debt, ÷ shares"
        ),
        "path": {
            "sales_0": 2550.0,       # MSEK, near mode / post-Q1 path
            "mgn_0": 6.8,            # % EBITA
            "mlt_0": 11.5,           # × EV/EBITA
            "nc_0": -450.0,          # MSEK net cash (= −net debt)
            "shares_0": 23.05,       # m shares
            "sales_cagr": 0.08,      # 8% — organic + bolt-on blend under the >15% ambition
            "mgn_term": 9.0,         # % company medium-term target
            "mlt_term": 13.0,        # × quality EMS, still below premium industrials
            "tax_rate": 0.22,
            "fcf_on_ebita": 0.70,    # after-tax cash conversion (WC-volatile EMS)
            "payout_ratio": 0.30,    # of FCF → dividends (policy up to ~30% of EAT)
            "buyback_ratio": 0.10,   # of FCF → buybacks
            "discount_rate": 0.10,   # higher than large-cap Nordics — mid-cap EMS risk
            "buyback_at_fv": True,
        },
        "milestones": [
            {"year": 2, "text": "EBITA margin sustainably ≥ 7% and book-to-bill ≥ 1.0 through a soft quarter; Power OEM profitable on an LTM basis."},
            {"year": 5, "text": "Group sales clearly above SEK 3.5bn; EBITA margin mid-to-high single digits; at least one material bolt-on integrated without leverage blow-out."},
            {"year": 8, "text": "Medium-term >9% EBITA margin delivered and held for two consecutive years; net debt/EBITDA ≤ 1.5× lease-adj."},
            {"year": 10, "text": "Through-cycle EBITA margin ~9%, sales ~SEK 5.5bn, quality multiple ~13× — the default terminal state this calculator prices."},
        ],
        "guards": [
            "Industrial / defence / data-centre demand double-dips and the 7% Q1 margin proves a peak, not a floor.",
            "A large, value-destructive acquisition re-levers the balance sheet and absorbs the FCF this path compounds.",
            "Power OEM (ex-Enedo) fails to sustain the Q1 turnaround and remains a permanent margin drag.",
            "Multiple never re-rates — the market permanently slots INISS with deep cyclicals (~7–9×) despite the mix shift.",
        ],
    },
}
