"""
Stock-specific configuration for the pipeline toolkit.

All per-stock data lives here. The generic framework under ../utils reads this
dict and never contains stock-specific values. To analyse a new stock, add a
new key to STOCKS with the same schema. No framework code needs to change.

Schema per stock:
  ticker              Yahoo Finance ticker
  html_file           Report filename inside this stocks/ directory
  pipeline_price      Price the original pipeline was authored at
  shares_m            Diluted shares outstanding (millions)
  consensus_pt        Consensus analyst target price
  eps_ttm             Trailing 12-month EPS
  engine              Callable(driver_draws) -> per-share fair value
  drivers             {driver_name: {"lo","md","hi","rho"}} for the MC
  peers               List of Yahoo peer tickers used for 12m relative return
  macro_ticker        Yahoo ticker for the dominant macro factor, or None
  macro_label         Human-readable label for the macro factor
  quality_score       0..1 anchor from Module D forensics (aggregated)
  reverse_dcf_target  Which driver key to grid-search for the reverse-DCF
  base_rates          Historical reference-class series
  oe_anchor_m         Owner-earnings anchor (EUR millions) from Module D
  oe_note             Citation for the owner-earnings anchor
  endpoints           Yahoo URLs fetched at build time (audit trail)
  primary_sources     Company releases / IR / etc (audit trail)
  cut_replacements    HTML for the "Still legitimately excluded" footer
  strictbar_replacement HTML for the top "What this build adds" strip, or None
  tally               {"bull","mixed","bear"} counts across all 10 modules

Every callable in this file is intentionally small (no imports beyond stdlib).
"""
from __future__ import annotations
from typing import Callable, Any


# -------------------- Engine helpers (per-stock closures) --------------------

def _make_konecranes_engine() -> Callable[[dict], float]:
    shares = 237.64
    def engine(d):
        return (d["mlt"] * (d["sales"] * d["mgn"] / 100) + d["nc"]) / shares
    return engine


def _make_neste_engine() -> Callable[[dict], float]:
    shares, netdebt, fx = 769.21, 3600.0, 1.10
    def engine(d):
        fixed = 500 + 68 * d["vol"]
        renew = d["mgn"] * d["vol"] / fx - fixed
        ebitda = renew + d["oil"] + d["ms"]
        return (d["mult"] * ebitda - netdebt) / shares
    return engine


def _make_sampo_engine() -> Callable[[dict], float]:
    shares, tax = 2650.0, 0.22
    def engine(d):
        underwriting = d["ir"] * (1 - d["cr"]/100) * 1000
        pretax = underwriting + d["inv"]
        net = pretax * (1 - tax)
        return net * d["pe"] / shares
    return engine


def _make_mandatum_engine() -> Callable[[dict], float]:
    shares, tax = 503.0, 0.22
    def engine(d):
        return (d["clp"] * (1 - tax) * d["fm"] + d["dc"]) / shares
    return engine


def _make_orion_engine() -> Callable[[dict], float]:
    """Sum-of-the-parts, split the way the market actually splits Orion:
    the Nubeqa/Innovative-Medicines royalty-and-product-sales stream (high
    growth, high margin, patent-protected -- priced on its own multiple) plus
    the rest of the group (Branded Products + Generics & Consumer Health +
    Animal Health + Fermion -- mature, diversified, priced on a plain
    generics/specialty multiple) plus a small R&D-pipeline optionality term,
    less net debt. Orion reports a single IFRS 8 segment, so no divisional
    EBIT is disclosed -- both halves are valued on EV/Sales, not EV/EBIT,
    which is why each half gets its own explicit multiple driver.
    """
    shares, netdebt = 140.69, 144.4
    def engine(d):
        innovative_medicines = d["nub"] * d["nmlt"]
        rest_of_orion = d["base"] * d["bmlt"]
        return (innovative_medicines + rest_of_orion + d["pipe"] - netdebt) / shares
    return engine


def _make_kesko_engine() -> Callable[[dict], float]:
    """Sum-of-the-parts, split the way the market actually splits Kesko: three
    reported divisions on their own EV/EBIT multiples --

      * Grocery trade      -- stable, market-leading, defensive (staples multiple)
      * Building & technical trade -- deeply cyclical, priced off the construction
                              cycle; the swing factor and the reverse-DCF target
      * Car trade          -- small, thin-margin; valued at a fixed dealer multiple

    less a small capitalised group-common / eliminations cost (group comparable
    operating profit is ~EUR 25m below the sum of the three divisions), less
    interest-bearing net debt EXCLUDING IFRS-16 lease liabilities. Leases are
    excluded because the ~EUR 2.1bn lease liability is matched by right-of-use
    assets and the rent charge already sits inside each division's post-IFRS-16
    EBIT via right-of-use depreciation -- so it is not an extra claim on equity
    in this EBIT framework. That lease treatment is the one modelling choice,
    flagged in Module A and the footer.
    """
    shares, netdebt, central_cap, car_mult = 398.08, 1308.9, 300.0, 10.0
    def engine(d):
        grocery  = d["gp"] * d["gmlt"]
        building = d["bp"] * d["bmlt"]
        car      = d["cp"] * car_mult
        ev = grocery + building + car - central_cap
        return (ev - netdebt) / shares
    return engine


# -------------------- STOCKS registry --------------------

STOCKS: dict[str, dict[str, Any]] = {
    "konecranes": {
        "ticker": "KCR.HE",
        "html_file": "konecranes-pipeline.html",
        "pipeline_price": 27.30,
        "shares_m": 237.64,
        "consensus_pt": 34.0,
        "eps_ttm": 1.68,
        "engine": _make_konecranes_engine(),
        "drivers": {
            "mgn":   {"lo": 10.5, "md": 14.0, "hi": 16.0, "rho": 0.75},
            "sales": {"lo": 3950, "md": 4250, "hi": 4650, "rho": 0.70},
            "mlt":   {"lo":  7.5, "md": 11.0, "hi": 14.5, "rho": 0.65},
            "nc":    {"lo":   50, "md":  185, "hi":  400, "rho": 0.20},
        },
        "reverse_dcf_target": "mlt",
        "reverse_dcf_label":  "EV/EBITA multiple (at mode margin/sales/net-cash)",
        "reverse_dcf_unit":   "×",
        "peers": ["ATCO-A.ST", "KGX.DE"],
        "macro_ticker": None,
        "macro_label": None,
        "quality_score": 0.85,
        "base_rates": {
            "variable": "Comparable EBITA margin (%)",
            "unit": "%",
            "series": [
                ("2022", 10.5, "trailing self-help start"),
                ("2023", 12.0, "programme mid-point"),
                ("2024", 13.1, "reported (pipeline module A)"),
                ("2025", 14.0, "reported record (pipeline module A)"),
                ("trough risk", 11.0, "pipeline stated downside anchor"),
            ],
            "current_label": "2025 = 14.0%",
            "current_value": 14.0,
            "reversion_mid": 12.5,
        },
        "oe_anchor_m": 500.0,
        "oe_note": "operating CF ~€0.5bn (pipeline module D)",
        "endpoints": [
            ("https://query1.finance.yahoo.com/v8/finance/chart/KCR.HE?range=5y&interval=1d",
             "Konecranes 5-year daily OHLC + regularMarketPrice",
             "I: realised vol / beta / momentum / drawdown / own-history percentile"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/^OMXH25?range=5y&interval=1d",
             "OMX Helsinki 25 index — benchmark for local beta",
             "I: beta vs OMXH25"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/^STOXX?range=5y&interval=1d",
             "STOXX Europe 600 — pan-European benchmark",
             "I: beta vs STOXX 600"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/^TNX?range=1mo&interval=1d",
             "US 10-year Treasury yield — real-rate proxy",
             "J: owner-earnings yield vs real 10y"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/ATCO-A.ST?range=2y&interval=1d",
             "Atlas Copco (quality peer) — 12-month relative performance",
             "I: peer-relative 12m"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/KGX.DE?range=2y&interval=1d",
             "KION Group (cyclical peer)",
             "I: peer-relative 12m"),
        ],
        "primary_sources": [
            ("Konecranes FY2025 financial statement release",
             "Sales €4.25bn, comparable EBITA €588m (13.8%), net cash €185m, ROCE 20.7% (comparable 22.1%), operating CF ~€0.5bn, net profit €399.8m, dividend €0.75/sh post-split (+36%)",
             "A engine, D forensics, E capital record, G peers"),
            ("Konecranes Q1 2026 interim report",
             "Record 11.6% Q1 margin, order book at 3-yr high, book-to-bill 1.2, net sales −4.8%, net cash €185m",
             "B driver analysis, H kill-criteria"),
            ("Solidium (Finnish State holding co) holdings page",
             "11.0% stake in Konecranes; largest holder; nomination-board chair",
             "F positioning"),
            ("Simply Wall St / S&amp;P Global Market Intelligence (Konecranes profile)",
             "Balance-sheet items (total assets €4.8bn, equity €1.97bn, current assets €2.7bn, current liabilities €2.0bn); interest coverage 18×",
             "D forensics"),
            ("Investing.com — Konecranes news &amp; consensus",
             "Consensus PT €34 (~+25% at build); reaction coverage for Feb'26 and Apr'26 releases",
             "B driver analysis, F positioning"),
            ("GuruFocus — machinery-industry EV/EBITDA median",
             "Median ~11× used as multiple-band anchor; Atlas Copco ~17×, KION ~7×",
             "A engine, G peers"),
        ],
        "cut_replacements": (
            '<b>Beneish M-score</b> — needs eight two-year ratios not fully disclosed; a half-estimated score is worse than none. '
            '<b>Options skew, precise borrow cost, and detailed insider transaction flow</b> — not reliably fetchable for a Nasdaq Helsinki name from a public API; would slot in from a Bloomberg terminal. '
            '<b>An exact forward multiple</b> — needs a consensus forward-EBITDA figure not asserted as fact. '
            'Everything else previously flagged as "cut" (factor betas, positioning realised-vol, own-history percentile, 12-month peer relative return, base-rate frequencies, owner-earnings yield vs real rate) is now <b>included</b> in Modules I &amp; J and computed live from the Yahoo Finance v8 chart API.'
        ),
        "strictbar_replacement": None,
        "tally": {"bull": 3, "mixed": 7, "bear": 0},
    },

    "neste": {
        "ticker": "NESTE.HE",
        "html_file": "neste-analytics-pipeline.html",
        "pipeline_price": 27.0,
        "shares_m": 769.21,
        "consensus_pt": 25.69,
        "eps_ttm": 0.18,
        "engine": _make_neste_engine(),
        "drivers": {
            "mgn":  {"lo": 370, "md": 630, "hi": 770, "rho": 0.78},
            "vol":  {"lo": 4.5, "md": 5.5, "hi": 6.8, "rho": 0.35},
            "oil":  {"lo": 340, "md": 620, "hi": 1040, "rho": 0.70},
            "mult": {"lo": 6.0, "md": 7.5, "hi": 9.0, "rho": 0.45},
            "ms":   {"lo": 105, "md": 125, "hi": 150, "rho": 0.10},
        },
        "reverse_dcf_target": "mgn",
        "reverse_dcf_label":  "Renewable margin $/ton (at mode volume/oil/mktg/multiple)",
        "reverse_dcf_unit":   "$/ton",
        "peers": [],
        "macro_ticker": "BZ=F",
        "macro_label":  "Brent (BZ=F)",
        "quality_score": 0.75,
        "base_rates": {
            "variable": "Renewable sales margin ($/ton)",
            "unit": "$/ton",
            "series": [
                ("2019 peak",      650, "pre-Covid cycle peak"),
                ("2020",           450, "Covid year"),
                ("2021",           580, "recovery"),
                ("2022",           780, "energy shock, biofuel scarcity"),
                ("2023 peak",      863, "pipeline module A — sourced"),
                ("2024 avg",       500, "reversion year"),
                ("Q4'24 trough",   242, "pipeline module A — sourced"),
                ("2025 avg",       411, "pipeline module A — sourced"),
                ("2026 (Inderes)", 690, "analyst forward assumption"),
            ],
            "current_label": "2025 = $411/ton (Q1'26 running higher)",
            "current_value": 411,
            "reversion_mid": 550,
        },
        "oe_anchor_m": 759.0,
        "oe_note": "FCF +€759m (pipeline module D — sourced)",
        "endpoints": [
            ("https://query1.finance.yahoo.com/v8/finance/chart/NESTE.HE?range=5y&interval=1d",
             "Neste 5-year daily OHLC + regularMarketPrice",
             "I: realised vol / beta / momentum / drawdown / own-history percentile"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/^OMXH25?range=5y&interval=1d",
             "OMX Helsinki 25 index",
             "I: beta vs OMXH25"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/^STOXX?range=5y&interval=1d",
             "STOXX Europe 600",
             "I: beta vs STOXX 600"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/BZ=F?range=5y&interval=1d",
             "Brent crude oil front month — commodity macro factor",
             "I: beta vs Brent (macro read for a refiner)"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/^TNX?range=1mo&interval=1d",
             "US 10-year Treasury yield — real-rate proxy",
             "J: owner-earnings yield vs real 10y"),
        ],
        "primary_sources": [
            ("Neste FY2025 financial statement release",
             "Renewable margin history (Q4'24 trough $242, 2023 peak $863, 2025 avg $411), total assets €15.7bn, equity €7.3bn, EBIT €466m, operating CF ~€1.7bn, FCF +€759m, leverage 34.3%",
             "A engine, D forensics, E capital record"),
            ("Neste FY2024 financial statement release",
             "Cash-out investments €1,566m; dividend policy formally cancelled Feb 2025; 2024 dividend €0.20/sh",
             "E capital record"),
            ("Finnish Government / Prime Minister's Office — State ownership register",
             "44.2% strategic-interest holding in Neste, one-share-one-vote, no golden shares",
             "F positioning"),
            ("Inderes — Neste research note",
             "Bull-case forward assumption ≈ $690/ton renewable margin",
             "C scenarios"),
            ("Simply Wall St — Neste profile",
             "Balance-sheet items (current assets €5.8bn, LT liabilities €5.4bn); EBIT-coverage 3.8×",
             "D forensics"),
            ("Zacks refining-industry commentary / Marathon Petroleum EV/EBITDA (S&amp;P via Yahoo)",
             "Peer multiple context; MPC ~7× vs Neste ~14.5×",
             "G peers"),
            ("Darling Ingredients Q1'26 8-K",
             "Diamond Green Diesel adjusted EBITDA $406.8m (Q1'26) vs $195.8m (Q1'25) — read on renewable-fuel peer margin",
             "G peers"),
        ],
        "cut_replacements": (
            '<b>Beneish M-score</b> — needs eight two-year ratios not fully disclosed; a half-estimated score is worse than none. '
            '<b>Options skew, EU net-short positions below the 0.5% disclosure threshold, and precise borrow cost</b> — not reliably fetchable via a public API for a Helsinki-listed foreign private issuer. '
            'Everything else previously flagged as "cut" (factor &amp; macro betas including Brent, price-history percentile, momentum, realised vol, drawdown history, base-rate frequencies, owner-earnings yield vs real rate) is now <b>included</b> in Modules I &amp; J and computed live from the Yahoo Finance v8 chart API.'
        ),
        "strictbar_replacement": (
            '<div class="strictbar"><b>What this build adds.</b> Two new institutional modules: '
            '<b>I — Price-asymmetry layer</b> (reverse-DCF, Kelly f*, payoff-asymmetry ratio, VaR/CVaR, realised vol / beta vs OMXH25 &amp; STOXX &amp; Brent, momentum, own-history percentile, peer 12m relative — all computed live from the Yahoo Finance v8 chart API) and '
            '<b>J — Base rates &amp; factor composite</b> (reference-class distribution of the master driver, empirical return base-rates from 5y prices, V/Q/M/L factor composite, owner-earnings yield vs real 10y). '
            'Previously "cut, not faked" items (factor betas, macro/Brent regression, price-history percentile, momentum, realised vol, drawdown, base-rate frequencies) are now included where the data was available — see footer for the still-legitimate exclusions. Ownership stays at the official 44.2% state anchor; peer multiples remain live.</div>'
        ),
        "tally": {"bull": 1, "mixed": 7, "bear": 2},
    },

    "sampo": {
        "ticker": "SAMPO.HE",
        "html_file": "sampo-pipeline.html",
        "pipeline_price": 9.00,
        "shares_m": 2650.0,
        "consensus_pt": 10.5,
        "eps_ttm": 0.62,
        "engine": _make_sampo_engine(),
        "drivers": {
            "ir":  {"lo": 8.6,  "md": 9.0,  "hi": 9.5,  "rho": 0.35},
            "cr":  {"lo": 81.0, "md": 84.0, "hi": 88.0, "rho": 0.70},
            "inv": {"lo": 450,  "md": 650,  "hi": 850,  "rho": 0.55},
            "pe":  {"lo": 11.5, "md": 14.5, "hi": 19.0, "rho": 0.65},
        },
        "reverse_dcf_target": "cr",
        "reverse_dcf_label":  "Combined ratio % (at mode revenue/investment/multiple)",
        "reverse_dcf_unit":   "%",
        "reverse_dcf_invert_sign": True,   # for CR, lower = better
        "peers": ["TRYG.CO", "GJF.OL"],
        "macro_ticker": "^TNX",
        "macro_label":  "US 10y yield (^TNX)",
        "quality_score": 0.90,
        "base_rates": {
            "variable": "Combined ratio (%)",
            "unit": "%",
            "series": [
                ("2019",           86.0, "pre-Topdanmark full ownership"),
                ("2020",           85.4, "Covid, benign frequency"),
                ("2021",           84.0, "hard-market normalisation"),
                ("2022",           85.0, "inflation year"),
                ("2023",           84.5, "post-demerger baseline"),
                ("2024",           83.9, "reported (pipeline module A)"),
                ("9M'25",          83.4, "reported (pipeline module A)"),
                ("target ceiling", 86.0, "management target < 86%"),
            ],
            "current_label": "9M'25 = 83.4% (below <86% target)",
            "current_value": 83.4,
            "reversion_mid": 85.0,
        },
        "oe_anchor_m": 1400.0,
        "oe_note": "operating earnings ~€1.4bn post-Topdanmark (pipeline module E — sourced)",
        "endpoints": [
            ("https://query1.finance.yahoo.com/v8/finance/chart/SAMPO.HE?range=5y&interval=1d",
             "Sampo 5-year daily OHLC + regularMarketPrice",
             "I: realised vol / beta / momentum / drawdown / own-history percentile"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/^OMXH25?range=5y&interval=1d",
             "OMX Helsinki 25 index",
             "I: beta vs OMXH25"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/^STOXX?range=5y&interval=1d",
             "STOXX Europe 600",
             "I: beta vs STOXX 600"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/^TNX?range=5y&interval=1d",
             "US 10-year Treasury yield — real-rate proxy",
             "I: beta vs rates · J: owner-earnings yield vs real 10y"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/TRYG.CO?range=2y&interval=1d",
             "Tryg — Danish Nordic P&amp;C peer",
             "I: peer-relative 12m"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/GJF.OL?range=2y&interval=1d",
             "Gjensidige — Norwegian Nordic P&amp;C peer",
             "I: peer-relative 12m"),
        ],
        "primary_sources": [
            ("Sampo FY2025 financial statement release",
             "Combined ratio ~83–84%, underwriting result ~€1.5bn (+12%), Solvency II 174%, operating EPS +7%, reported EPS +65% (one-off €540m gain), financial leverage 23.6%, dividend €0.36 (+6%)",
             "A engine, D forensics, E capital record"),
            ("Sampo Q1 2026 interim report",
             "Insurance revenue +8%, underwriting result +9%, guidance raised, €350m buyback, −€46m reported net loss from investment/debt one-offs",
             "B driver analysis"),
            ("Sampo IR — capital-return history and strategy",
             "Nordea sell-down; Mandatum demerger (2023); full ownership of Topdanmark (2024); rolling buybacks €150m / €200m / €350m; €355m NOBA IPO proceeds returned",
             "E capital record"),
            ("MarketScreener — Sampo consensus",
             "Buy consensus 9 buys / 0 sells; consensus PT €10.5",
             "F positioning"),
            ("Simply Wall St / S&amp;P — Sampo profile",
             "Peer P&amp;C multiples (Tryg / Gjensidige ~18–19× P/E), Sampo trailing ~14.5×",
             "G peers"),
        ],
        "cut_replacements": (
            '<b>Manufacturing forensics</b> (Piotroski, Altman, Sloan) — meaningless on an insurer\'s balance sheet, kept replaced by combined-ratio / solvency / reserving / operating-EPS gauges. '
            '<b>A segment-level model</b> (If vs Topdanmark vs Hastings) — needs per-unit disclosures not fully machine-readable; the group build stays a transparent proxy. '
            '<b>Options skew, precise insider holdings, and detailed borrow cost</b> — not reliably fetchable for a Helsinki name via a public API. '
            'Everything else previously flagged as "cut" (factor &amp; macro betas, price-history percentile, momentum, realised vol, drawdown, peer 12m relative, base-rate frequencies, owner-earnings yield vs real rate) is now <b>included</b> in Modules I &amp; J and computed live from the Yahoo Finance v8 chart API.'
        ),
        "strictbar_replacement": None,
        "tally": {"bull": 2, "mixed": 8, "bear": 0},
    },

    "mandatum": {
        "ticker": "MANTA.HE",
        "html_file": "mandatum-pipeline.html",
        "pipeline_price": 5.52,
        "shares_m": 503.0,
        "consensus_pt": 5.50,
        "eps_ttm": 0.35,
        "engine": _make_mandatum_engine(),
        "drivers": {
            "clp": {"lo":  78, "md":  92, "hi":  118, "rho": 0.65},
            "fm":  {"lo": 17.0,"md":25.5, "hi":34.0,  "rho": 0.75},
            "dc":  {"lo": 550, "md":1000, "hi":1500,  "rho": 0.35},
        },
        "reverse_dcf_target": "fm",
        "reverse_dcf_label":  "Fee-business P/E multiple (at mode capital-light profit/DC)",
        "reverse_dcf_unit":   "×",
        "peers": [],
        "macro_ticker": "^TNX",
        "macro_label":  "US 10y yield (^TNX)",
        "quality_score": 0.70,
        "base_rates": {
            "variable": "Client AUM (€bn)",
            "unit": "€bn",
            "series": [
                ("2023 Q4",     11.6, "post-demerger baseline"),
                ("2024 Q4",     12.5, "growth year"),
                ("2025 Q3",     14.9, "pipeline module B — sourced"),
                ("2026 Q1",     15.3, "post-Saxo (pipeline module F)"),
                ("target 2028", 18.0, "management ambition"),
            ],
            "current_label": "Q1'26 = €15.3bn (record)",
            "current_value": 15.3,
            "reversion_mid": 13.5,
        },
        "oe_anchor_m": 301.0,
        "oe_note": "organic capital generation €301m (pipeline module B)",
        "endpoints": [
            ("https://query1.finance.yahoo.com/v8/finance/chart/MANTA.HE?range=5y&interval=1d",
             "Mandatum 5-year daily OHLC + regularMarketPrice",
             "I: realised vol / beta / momentum / drawdown / own-history percentile"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/^OMXH25?range=5y&interval=1d",
             "OMX Helsinki 25 index",
             "I: beta vs OMXH25"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/^STOXX?range=5y&interval=1d",
             "STOXX Europe 600",
             "I: beta vs STOXX 600"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/^TNX?range=5y&interval=1d",
             "US 10-year Treasury yield — real-rate proxy",
             "I: beta vs rates · J: owner-earnings yield vs real 10y"),
        ],
        "primary_sources": [
            ("Mandatum FY2025 financial statement release + Q3'25 / Q1'26 interims",
             "Client AUM Q3'25 €14.9bn, Q1'26 €15.3bn (post-Saxo); fee result +20% (Q3), +35% capital-light profit growth (Q1), cost/income 49%, solvency 203% post-Saxo, organic capital generation €301m / €0.60 per share; reported EPS €0.31",
             "A engine, B driver analysis, D forensics"),
            ("Investing.com / SEB — Altor secondary placement announcement (Feb 2026)",
             "35m share block (7% of capital) at €6.80, ~7% discount — the −8% share reaction",
             "B driver analysis, F positioning"),
            ("Simply Wall St — Mandatum ownership breakdown",
             "T. Rowe Price ~6%, Varma ~4%, Ilmarinen ~3% — top institutional holders",
             "F positioning"),
            ("Inderes — Mandatum DDM valuation research",
             "DDM-based fair-value frame; sell-side houses value the stock as a DDM/yield instrument",
             "B driver analysis, C scenarios"),
            ("MarketScreener — Mandatum consensus PT",
             "Consensus PT ≈ €5.50 (near price); mixed rating distribution",
             "F positioning"),
        ],
        "cut_replacements": (
            '<b>Manufacturing forensics</b> (Piotroski, Altman, Sloan) — meaningless on an insurer\'s balance sheet, kept replaced by solvency / capital-generation / efficiency gauges. '
            '<b>A precise DDM</b> — needs a full multi-year dividend and cost-of-equity schedule; the SOTP stays a transparent proxy. '
            '<b>Options skew and precise borrow cost</b> — not reliably fetchable via a public API for a Helsinki name. '
            'Everything else previously flagged as "cut" (factor betas, price-history percentile, momentum, realised vol, drawdown, base-rate frequencies, owner-earnings yield vs real rate) is now <b>included</b> in Modules I &amp; J and computed live from the Yahoo Finance v8 chart API.'
        ),
        "strictbar_replacement": None,
        "tally": {"bull": 2, "mixed": 7, "bear": 1},
    },

    "orion": {
        "ticker": "ORNBV.HE",
        "html_file": "orion-pipeline.html",
        "pipeline_price": 70.00,
        "shares_m": 140.69,
        "consensus_pt": 74.33,
        "eps_ttm": 3.56,
        "engine": _make_orion_engine(),
        "drivers": {
            "nub":  {"lo":  700, "md":  900, "hi": 1050, "rho": 0.75},
            "nmlt": {"lo":  5.5, "md":  7.0, "hi":  9.0, "rho": 0.55},
            "base": {"lo": 1030, "md": 1110, "hi": 1200, "rho": 0.25},
            "bmlt": {"lo":  1.8, "md":  2.6, "hi":  3.5, "rho": 0.20},
            "pipe": {"lo":    0, "md":  150, "hi":  500, "rho": 0.15},
        },
        "reverse_dcf_target": "nub",
        "reverse_dcf_label":  "Orion-booked Nubeqa® net sales run-rate (royalties + product sales, at mode multiple/base/pipeline)",
        "reverse_dcf_unit":   "€m",
        "peers": ["GMAB.CO", "REC.MI"],
        "macro_ticker": "EURUSD=X",
        "macro_label":  "EUR/USD (EURUSD=X)",
        "quality_score": 0.80,
        "base_rates": {
            "variable": "Orion-booked Nubeqa® net sales (€m, royalties + product sales)",
            "unit": "€m",
            "series": [
                ("2024",                    368.3, "FY2024 reported — royalties + product sales to Bayer"),
                ("2025",                     609.8, "FY2025 reported — royalties €432.5m + product sales €177.3m"),
                ("Q4'25 run-rate ×4",        850.4, "Q4'25 print (€212.6m) annualised — computed, not a forecast"),
                ("2026 sell-side consensus", 915.0, "≈+50% YoY per analyst consensus cited on the Q1'26 call — estimate, not company guidance"),
                ("2030 company ambition",   1000.0, "Orion's stated \"potential to exceed €1bn by the end of the decade\" (14 Jan 2026)"),
            ],
            "current_label": "2025 = €609.8m (Q4'25 annualised ≈ €850m)",
            "current_value": 609.8,
            "reversion_mid": 800.0,
        },
        "oe_anchor_m": 218.2,
        "oe_note": "cash flow from operating + investing activities +€218.2m FY2025 (pipeline module — sourced)",
        "endpoints": [
            ("https://query1.finance.yahoo.com/v8/finance/chart/ORNBV.HE?range=5y&interval=1d",
             "Orion (B share) 5-year daily OHLC + regularMarketPrice",
             "I: realised vol / beta / momentum / drawdown / own-history percentile"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/^OMXH25?range=5y&interval=1d",
             "OMX Helsinki 25 index",
             "I: beta vs OMXH25"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/^STOXX?range=5y&interval=1d",
             "STOXX Europe 600",
             "I: beta vs STOXX 600"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/EURUSD=X?range=5y&interval=1d",
             "EUR/USD spot — Orion discloses that USD moves on Nubeqa® income drive real P&L swings",
             "I: beta vs EUR/USD (macro read for a USD-royalty payer)"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/^TNX?range=1mo&interval=1d",
             "US 10-year Treasury yield — real-rate proxy",
             "J: owner-earnings yield vs real 10y"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/GMAB.CO?range=2y&interval=1d",
             "Genmab (Nasdaq Copenhagen) — Nordic royalty-economics oncology peer",
             "I: peer-relative 12m"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/REC.MI?range=2y&interval=1d",
             "Recordati (Borsa Italiana) — diversified specialty-pharma peer",
             "I: peer-relative 12m"),
        ],
        "primary_sources": [
            ("Orion Group Financial Statement Release 1–12/2025 (12 Feb 2026)",
             "Net sales €1,889.5m (+22.5%), operating profit €631.6m (+51.6%), EPS €3.56, dividend €1.80 proposed; balance sheet (assets €2,009.8m, equity €1,284.5m, interest-bearing net liabilities €144.4m, equity ratio 64.1%, gearing 11.2%, ROE 43.7%, ROCE 43.8%); net-sales split by business division (Innovative Medicines €812.7m, Branded Products €314.6m, Generics &amp; Consumer Health €552.8m, Animal Health €140.9m, Fermion €68.7m); Nubeqa® split (royalties €432.5m / product sales €177.3m); Bayer/MSD/Tenax licensing terms; shares 141,134,278; market cap €8,944.0m",
             "A engine, D forensics, E capital record, F positioning"),
            ("Orion Group Interim Report 1–3/2026 (23 Apr 2026)",
             "Q1 2026 net sales €417.7m (+17.8%), operating profit €114.8m (+47.3%, 27.5% margin); Innovative Medicines division +~54%; FY2026 outlook raised to €1.95–2.10bn net sales / €600–750m operating profit; DASL-HiCaP darolutamide read-out expected 2028",
             "B driver analysis, C scenarios"),
            ("Bayer media release, Feb 2022 (ASCO GU / ARASENS data) &amp; FDA approval releases 2024–2025",
             "Nubeqa® global peak-sales estimate raised to &gt;€3bn (from &gt;€1bn); average total royalty rate to Orion ~20–25% of in-market sales including product sales to Bayer, tiered upward as sales grow; mHSPC label expansion (ADT+docetaxel 2022, ADT-only EU 2025/US 2025, China NMPA 2026)",
             "A engine, C scenarios"),
            ("Jefferies research note via Investing.com (30 Jan 2026)",
             "Downgrade to Hold from Buy — \"Nubeqa upside is priced in\"; worldwide Nubeqa peak-sales estimate raised to €4.6bn (from €4.2bn); risk-reward called neutral over 12 months despite the estimate upgrade",
             "F positioning, G peers"),
            ("Investing.com — Orion Oyj B (ORNBV) quote &amp; consensus (28 Jun 2026)",
             "Spot €70.00 (prev. close €70.25), 52-week range €56.50–75.30; 6-analyst consensus PT €74.33 (high €81 / low €55); consensus rating Buy (4 buy / 1 sell)",
             "F positioning"),
            ("DrugPatentWatch / Grokipedia darolutamide patent trackers",
             "US patent estate (9 filings, none expired) points to generic entry ≈2038–2042; EU core compound patents ~2027–2030 with per-country SPC extensions pushing effective exclusivity into the mid-2030s in most member states",
             "H kill-criteria"),
            ("Fiscal.ai &amp; Investing.com Pro — Recordati (BIT:REC) EV/EBITDA (28 Jun 2026)",
             "Fiscal.ai: trailing EV/EBITDA 13.27&times; for FY2025; Investing.com Pro's own build (EV €11.94bn ÷ EBITDA €871.7m) computes to 13.7&times; — two independent aggregators converge on ≈13–14&times;. Genmab's multiple was checked against the same two providers plus Yahoo Finance and StockAnalysis.com and excluded: the four disagreed materially (≈11&times;–16&times;) with inconsistent per-share bases, likely reflecting Genmab's April 2026 share-capital reduction working through TTM figures at different speeds across providers",
             "G peers"),
        ],
        "cut_replacements": (
            '<b>Genmab EV/EBITDA</b> — public trackers disagree materially on the current multiple (roughly 11&times; to 16&times; across Fiscal.ai / StockAnalysis.com / Yahoo Finance snapshots, with Yahoo\'s own GMAB vs GMAB.CO listings showing inconsistent trailing EPS bases at time of write — likely muddied by Genmab\'s April 2026 share-capital reduction). Rather than pick one, Genmab is left out of the numeric peer chart in Module G; the read leans on the live 12-month relative <i>return</i> in Module I instead, which has no such ambiguity. '
            '<b>Segment-level EBIT</b> — Orion reports one IFRS 8 segment; only segment <i>net sales</i> are disclosed, which is why the engine values both halves on EV/Sales rather than EV/EBIT — a modelling simplification, not a hidden number. '
            '<b>Beneish M-score</b> — needs eight two-year ratios not fully disclosed; a half-estimated score is worse than none. '
            '<b>Options skew, insider transaction flow, and precise borrow cost</b> — not reliably fetchable for a dual-class Nasdaq Helsinki name from a public API. '
            'Everything else previously flagged as "cut" (factor &amp; FX betas, price-history percentile, momentum, realised vol, drawdown, peer 12m relative, base-rate frequencies, owner-earnings yield vs real rate) is <b>included</b> in Modules I &amp; J and computed live from the Yahoo Finance v8 chart API.'
        ),
        "strictbar_replacement": None,
        "tally": {"bull": 2, "mixed": 7, "bear": 1},
    },

    "kesko": {
        "ticker": "KESKOB.HE",
        "html_file": "kesko-pipeline.html",
        "pipeline_price": 19.58,
        "shares_m": 398.08,
        "consensus_pt": 20.83,
        "eps_ttm": 1.03,
        "engine": _make_kesko_engine(),
        "drivers": {
            "gp":   {"lo":  380, "md":  418, "hi":  455, "rho": 0.35},
            "gmlt": {"lo": 12.5, "md": 15.3, "hi": 18.0, "rho": 0.45},
            "bp":   {"lo":  116, "md":  180, "hi":  320, "rho": 0.80},
            "bmlt": {"lo":  9.0, "md": 12.0, "hi": 15.0, "rho": 0.65},
            "cp":   {"lo":   65, "md":   83, "hi":  100, "rho": 0.55},
        },
        "reverse_dcf_target": "bp",
        "reverse_dcf_label":  "Building &amp; technical trade comparable operating profit (€m, at mode grocery / car / multiples)",
        "reverse_dcf_unit":   "€m",
        "peers": ["AXFO.ST", "KGF.L"],
        "macro_ticker": None,
        "macro_label": None,
        "quality_score": 0.68,
        "base_rates": {
            "variable": "Building &amp; technical trade comparable operating profit (€m)",
            "unit": "€m",
            "series": [
                ("2021",             318.0, "construction-boom level — reported"),
                ("2022",             340.0, "cycle peak — reported"),
                ("2023",             212.5, "cycle rolling over — reported"),
                ("2024 trough",      116.3, "reported FY2024 comparable — the low"),
                ("2025",             178.6, "reported FY2025 comparable — recovering"),
                ("mid-cycle normal", 280.0, "analyst normalised mid-cycle — estimate"),
            ],
            "current_label": "2025 = €178.6m (recovering off the 2024 trough)",
            "current_value": 178.6,
            "reversion_mid": 260.0,
        },
        "oe_anchor_m": 377.0,
        "oe_note": "free cash flow +€377m FY2025 (Yahoo fundamentals — after elevated store-site &amp; acquisition capex; operating cash flow €879.7m)",
        "endpoints": [
            ("https://query1.finance.yahoo.com/v8/finance/chart/KESKOB.HE?range=5y&interval=1d",
             "Kesko B-share 5-year daily OHLC + regularMarketPrice",
             "I: realised vol / beta / momentum / drawdown / own-history percentile"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/^OMXH25?range=5y&interval=1d",
             "OMX Helsinki 25 index — benchmark for local beta",
             "I: beta vs OMXH25"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/^STOXX?range=5y&interval=1d",
             "STOXX Europe 600 — pan-European benchmark",
             "I: beta vs STOXX 600"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/^TNX?range=1mo&interval=1d",
             "US 10-year Treasury yield — real-rate proxy",
             "J: owner-earnings yield vs real 10y"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/AXFO.ST?range=2y&interval=1d",
             "Axfood (Nasdaq Stockholm) — Nordic grocery-retail peer",
             "I: peer-relative 12m"),
            ("https://query1.finance.yahoo.com/v8/finance/chart/KGF.L?range=2y&interval=1d",
             "Kingfisher (LSE) — European building/DIY-retail peer",
             "I: peer-relative 12m"),
        ],
        "primary_sources": [
            ("Kesko financial statements release 1.1.–31.12.2025 (4 Feb 2026)",
             "Net sales €12,474.7m (+comparable 2.3%), comparable operating profit €654.9m (+€4.8m); divisional comparable operating profit — grocery trade €418.1m (net sales €6,447.7m, 6.5% margin), building &amp; technical trade €178.6m (2024: €116.3m), car trade €83.1m (5.9% margin); comparable EPS €1.07 / reported €1.02; ROCE (comparable) 10.4%, ROE (comparable) 15.3%; operating cash flow €879.7m; interest-bearing net debt excl. leases €1,308.9m (2024: €857.2m), lease liabilities €2,098m, net debt/EBITDA 1.6×; dividend proposal €0.90/share (~€358m); FY2026 outlook comparable operating profit €650–750m",
             "A engine, B driver analysis, D forensics, E capital record"),
            ("Kesko interim report Q1/2026 (23 Apr 2026)",
             "Growth across all three divisions; grocery gaining market share; car trade comparable operating profit €83.1m / 5.9% on a rolling-12-month basis; continued but gradual building-trade recovery",
             "B driver analysis, C scenarios, H kill-criteria"),
            ("Yahoo Finance fundamentals-timeseries (KESKOB.HE, annual 2022–2025)",
             "Income statement, balance sheet and cash-flow line items (revenue, gross profit, EBIT/EBITDA, net income, diluted EPS &amp; shares, equity, total debt incl. leases, cash, operating &amp; free cash flow, capex, interest expense, current assets/liabilities, inventory)",
             "D forensics, Q fundamental dashboard"),
            ("Kesko largest-shareholders &amp; ownership register (1 Sep 2025 / 31 Dec 2024)",
             "A shares 31.7% of capital but ~82% of votes (10 votes vs 1 for B); K-Retailers' Association ~7.54% of shares / 19.56% of votes (largest by votes); Ilmarinen &amp; Varma pension funds ~2–3% each; nominee-registered ~25%; &gt;113,000 registered holders",
             "F positioning"),
            ("MarketScreener / Investing.com — Kesko consensus",
             "Consensus PT ≈ €20.8 (high €22.5 / low €18), rating Buy/Accumulate; 2026 sell-side EPS ≈ €1.17 (+15%)",
             "F positioning"),
            ("Inderes — Kesko research note (30 Apr 2026)",
             "Accumulate recommendation; construction-cycle turn is the key swing factor for the building &amp; technical trade division",
             "B driver analysis, F positioning"),
        ],
        "cut_replacements": (
            '<b>The divisional EV/EBIT sum-of-the-parts is a transparent proxy, not a hidden number.</b> Kesko discloses divisional comparable operating profit but not a divisional balance sheet, so each division is valued on its own EV/EBIT multiple and IFRS-16 lease liabilities (~€2.1bn) are excluded from net debt — they are matched by right-of-use assets and the rent already reduces divisional EBIT via right-of-use depreciation. Valuing on lease-inclusive EV/EBITDA instead would move the mix, not the conclusion. '
            '<b>Beneish M-score</b> — needs eight two-year ratios not fully disclosed; a half-estimated score is worse than none. '
            '<b>Options skew, precise borrow cost, and detailed insider transaction flow</b> — not reliably fetchable for a Nasdaq Helsinki name from a public API; would slot in from a Bloomberg terminal. '
            'Everything else previously flagged as "cut" (factor betas, own-history percentile, momentum, realised vol, drawdown, 12-month peer relative return, base-rate frequencies, owner-earnings yield vs real rate) is now <b>included</b> in Modules I &amp; J and computed live from the Yahoo Finance v8 chart API.'
        ),
        "strictbar_replacement": None,
        "tally": {"bull": 2, "mixed": 8, "bear": 0},
    },
}


# SpaceX (NASDAQ: SPCX) — kept in its own module for readability; wire it in here
# so no framework code needs to know about it.
from stocks.config_spacex import SPACEX_CONFIG  # noqa: E402
STOCKS["spacex"] = SPACEX_CONFIG

# Amazon.com (NASDAQ: AMZN) — same pattern: config lives in its own module,
# wired in here so no framework code needs to change.
from stocks.config_amazon import AMAZON_CONFIG  # noqa: E402
STOCKS["amazon"] = AMAZON_CONFIG

# Tesla, Inc. (NASDAQ: TSLA) — same pattern. Deep multi-year tape means every
# Module I/J long-window metric computes on a full sample (no n/a backfills).
from stocks.config_tesla import TESLA_CONFIG  # noqa: E402
STOCKS["tesla"] = TESLA_CONFIG

# Terveystalo Oyj (Nasdaq Helsinki: TTALO) — same pattern: config lives in its own
# module, wired in here so no framework code needs to change. Two-leg EV/EBIT SOTP
# (Healthcare Services + Portfolio Businesses) with the Silmaasema deal and 2026
# demand downturn carried as explicit drivers/scenarios.
from stocks.config_terveystalo import TERVEYSTALO_CONFIG  # noqa: E402
STOCKS["terveystalo"] = TERVEYSTALO_CONFIG


# -------------------- Framework-wide (data-provider notes) --------------------
# These are shared across all stocks and shipped alongside every audit
# appendix so each report is self-contained.

DATA_PROVIDER_NOTES = """
<ul>
  <li><b>Yahoo Finance v8 chart API</b> — public, non-authenticated JSON endpoint. Returns adjusted close, OHLC, volume and meta (regular-market-price, 52w range). Rate-limited but reliable for cash equities and major indices; used as the single source of truth for all live-fetched price series in Modules I &amp; J.</li>
  <li><b>Primary company releases</b> — direct company disclosures (Finnish issuers publish concurrently in Finnish and English, ESMA-compliant). Every balance-sheet, income-statement and cash-flow figure inside Modules A / D / E traces to a release listed above.</li>
  <li><b>Solidium / Finnish State ownership</b> — the State's holding company and Prime Minister's Office publish the strategic-interest register directly.</li>
  <li><b>Simply Wall St (S&amp;P Global Market Intelligence)</b> — used to cross-check balance-sheet ratios (coverage, gearing) where the primary release aggregates line items.</li>
  <li><b>Analyst consensus</b> — pulled from Investing.com and MarketScreener at time of write; consensus PTs are point-in-time and can move.</li>
</ul>
"""


def get(name: str) -> dict:
    return STOCKS[name]


def all_names() -> list[str]:
    return list(STOCKS.keys())
