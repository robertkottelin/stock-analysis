# Stock-Analysis Pipelines — Toolkit

Institutional-grade Monte-Carlo, asymmetry and base-rate analytics applied to a
small set of listed names. The framework is fully generic — to analyse a new
stock you only touch `stocks/config.py` (or a per-stock `config_*.py` wired in
there).

## Directory layout

```
.
├── refresh_all.py                       # one-command entry point at root
├── README.md
├── cache/                                # Yahoo JSON cache (auto-created, shared)
├── data/                                 # common tabular repository (generated)
│   ├── metrics_latest.csv                # screening row per name (Kelly, CVaR, …)
│   └── universe.csv                      # registry snapshot
├── dashboard/                            # central navigation UI (generated)
│   ├── index.html                        # open this first
│   └── universe.json
├── stocks/                               # stock-specific data + reports
│   ├── config.py                         # per-stock config (drivers, endpoints, sources, tally, ...)
│   ├── config_*.py                       # large-name configs wired into config.py
│   └── *-pipeline.html                   # per-name reports
└── utils/                                # reusable framework
    ├── analytics.py · inject.py · bullcase.py · export_universe.py · …
    ├── build_one.py · refresh_all.py · verify.py
    ├── universe_screener.py · screener_server.py # Universe screener — Nordics + S&P 500 (see below)
    └── paths.py
```

### Central dashboard

After any full build:

```powershell
python refresh_all.py
# then open:
#   dashboard/index.html
```

Or export metrics only (re-runs Yahoo + MC for every name):

```powershell
python utils/export_universe.py
```

The dashboard lists every registered stock, screens on Kelly / CVaR / composite /
OE spread / Module-I verdict, and links into each HTML report. Tabular twin:
`data/metrics_latest.csv`.

Everything is **path-relative**. No absolute paths appear in any script. You
can copy the whole tree into another environment and it just works.

## Quick start

```powershell
python refresh_all.py                     # from the project root
```

or, equivalently,

```powershell
python utils/refresh_all.py               # from anywhere
```

Options:
- `--clear-cache` — wipe `cache/` first (force a fresh Yahoo fetch)
- `--skip-verify` — skip the final HTML parse check

Cached Yahoo payloads expire automatically after 24 h (override with the
`STOCK_CACHE_MAX_AGE_H` env var), so a plain run always refreshes prices at
most a day old; if a refetch fails, the last good cache is used with a
warning. On a warm cache the full pipeline runs in ~5–7 seconds. Every
builder is idempotent — safe to re-run any time (e.g. weekly).

### Building a single stock

`refresh_all.py` runs **every** registered stock; that is the right weekly
default, but it fails if any registered stock has no HTML report yet. To
(re)build one name in isolation — same builders, same idempotence, just scoped:

```powershell
python utils/build_one.py tesla           # inject → tallies → finalize → audit → verify
python utils/build_one.py spacex --skip-verify
```

## Stocks currently wired in

| Key          | Ticker    | Model                                                        |
|--------------|-----------|-------------------------------------------------------------|
| konecranes   | KCR.HE    | EBITA × multiple + net cash                                 |
| neste        | NESTE.HE  | Renewable-margin refinery model                             |
| sampo        | SAMPO.HE  | Combined-ratio underwriting + investment                    |
| mandatum     | MANTA.HE  | Fee-business SOTP                                           |
| orion        | ORNBV.HE  | Nubeqa royalty stream + rest-of-Orion SOTP                  |
| kesko        | KESKOB.HE | Divisional EV/EBIT SOTP (grocery / building / car trade)    |
| spacex       | SPCX      | Five-leg SOTP (Starlink / launch / orbital DC / frontier / AI) |
| amazon       | AMZN      | AWS + non-AWS two-block SOTP                                |
| tesla        | TSLA      | Four-leg SOTP (auto core / energy / robotaxi / Optimus) + bull-case overlay. Config in `stocks/config_tesla.py`. |
| **terveystalo** | **TTALO.HE** | **Two-leg EV/EBIT SOTP (Healthcare Services core + Portfolio Businesses incl. Sweden).** The live 2026 demand downturn (Q1'26 revenue −11%, FY2026 adjusted-EBIT guidance cut to €135–165m) and the €574m Silmäasema eye-care acquisition are carried as explicit drivers / scenarios / kill-criteria. Config in `stocks/config_terveystalo.py`. |
| **micron** | **MU** | **Through-cycle EBITDA × EV/EBITDA + net cash memory-semiconductor engine (DRAM + NAND).** The AI/HBM super-cycle (TTM revenue ~$90bn, ~76% EBITDA margin) and the FY2023 memory-glut trough (negative gross margin) are both carried explicitly; the reverse-DCF solves for the through-cycle EBITDA margin the market implies. Config in `stocks/config_micron.py`; the data-heavy report is emitted by `stocks/_micron_build.py`. |
| **investor** | **INVE-B.ST** | **Adjusted-NAV × (1 − holdco discount) industrial holding-company engine** (Listed Companies + Patricia Industries + EQT − net debt). Wallenberg permanent-capital vehicle; portfolio look-through of every material holding with live fundamentals. Config in `stocks/config_investor.py`; data-heavy report emitted by `stocks/_investor_build.py`. |
| **inission** | **INISS-B.ST** | **Single-leg sales × EBITA-margin × EV/EBITA − net debt EMS industrial engine** (Inission EMS + Inission Power OEM). Nordic electronics manufacturing roll-up; Q1'26 demand surge and medium-term &gt;9% EBITA margin target carried as explicit drivers. Config in `stocks/config_inission.py`. |
| **te** | **TEL** | **Single-leg sales × EBIT-margin × EV/EBIT − net debt quality industrial compounder** (Transportation + Industrial connectors/sensors). **10-year horizon** first-principles build: electrification, automation, AI power content; Module U perfect-execution path is first-class. Config in `stocks/config_te.py`. |

## Universe screener — Nordics + S&P 500

A second, independent dashboard that goes wider instead of deeper: every listed
equity on Nasdaq Helsinki + Stockholm (incl. First North) plus the current S&P
500, fetched live, scored on fundamentals and ranked, to surface candidates for
the per-stock pipeline above. It does not touch the 10-name registry or
`refresh_all.py`.

```powershell
python utils/universe_screener.py          # fetch + score ~1,800 names (~2-3min cold, ~10-40s warm cache)
python utils/screener_server.py            # serve dashboard/screener.html with a live Refresh button
```

Or open `dashboard/screener.html` directly (works via `file://`, using whatever
`dashboard/screener_data.js` was last generated; the in-page **Refresh live
data** button additionally needs `screener_server.py` running so it can spawn
the fetch and stream progress back to the page).

What it does:
- **Universe** — enumerates every `EQUITY` Yahoo lists under exchange codes
  `HEL`/`STO` via the screener API (paginated, with a market-cap-banded
  fallback sweep if deep pagination is clipped), plus the current S&P 500
  constituent list (Wikipedia's maintained constituents table — Yahoo's
  screener has no index-membership filter; `--skip-sp500` fetches Nordics
  only). The constituent list itself is cached a week; fundamentals for every
  US name still come from the same Yahoo `quoteSummary` API as everything
  else, so the sector/industry taxonomy stays consistent across the whole
  universe.
- **Fundamentals** — per symbol, Yahoo's `quoteSummary` API (price,
  assetProfile, summaryDetail, defaultKeyStatistics, financialData), fetched
  concurrently, cached 24h (`cache/screener/`, `SCREENER_CACHE_MAX_AGE_H`
  overrides, stale-on-failure fallback — same convention as the chart cache).
  All monetary figures are converted to EUR at the latest spot FX. Multiples
  computed by Yahoo from a listing-currency price over a different reporting
  currency (e.g. a SEK-listed, USD-reporting name) are rescaled so they're
  comparable across the universe.
- **Scoring** — `fund_score` (0–100, percentile composite: Quality 35% /
  Growth 20% / Balance sheet 15% / Valuation 30%, computed once against the
  full combined Nordics + S&P 500 pool) and `ai_score` (0–100, an explicit,
  inspectable heuristic: industry base-rate + labor-intensity + gross-margin
  operating leverage — not fetched data). `overall` = 0.65×fund + 0.35×AI.
  Dual-listed share classes are flagged and de-duplicated (most-traded line
  kept primary — this also catches cross-region duplicates like GOOGL/GOOG).
- **Dashboard** (`dashboard/screener.html` + `screener_app.js`) — a
  fundamentals-×-AI-leverage quadrant scatter (bubble = market cap, colour by
  exchange or sector group) plus a table over every fetched field: full-text
  search, exchange/sector filters, click-to-sort on any visible column,
  toggleable column groups, and — for every visible column — its own min/max
  (or "contains") filter right in the header, so any fetched metric is both
  sortable and filterable. Per-row expand for the business summary and AI-fit
  rationale, plus a shortlist CSV export of whatever's currently filtered.
- **Outputs** — `dashboard/screener_data.json` / `.js` (dashboard payload),
  `data/screener_latest.csv` (flat twin for spreadsheets/LLM use).

This is a screen, not a verdict: use it to shortlist names, then bring the
interesting ones into `stocks/config.py` for the full Monte-Carlo pipeline.

## Adding a new stock

1. Add a new entry to `STOCKS` in `stocks/config.py` (or a `config_<name>.py`
   module wired in at the bottom of `config.py`, as SpaceX / Amazon / Tesla do).
   Copy an existing block and change:
   - `ticker`, `html_file`, `pipeline_price`, `shares_m`, `consensus_pt`, `eps_ttm`
   - The `engine` closure — a small callable that turns a dict of driver
     draws into a per-share fair value. Match the pipeline's own JS engine.
   - `drivers` — triangular ranges + copula ρ for each driver.
   - `reverse_dcf_target` — which driver key to grid-solve for.
   - `peers`, `bench1_ticker`/`bench2_ticker`, `macro_ticker`, `quality_score`
   - `base_rates` — historical reference-class series (from public releases).
   - `oe_anchor_m` + `oe_note` — owner-earnings anchor from the pipeline.
   - `endpoints`, `primary_sources` — audit-trail entries.
   - `cut_replacements`, `strictbar_replacement`, `tally` — footer + scorecard.
2. Drop the hand-authored HTML report file into `stocks/`. It must contain: a
   `</head>`, an executive summary, a stepper nav (with an `#mH` link and an
   `#mSum` link), Modules A–H, a `<section class="mod" id="mSum">` scorecard
   with a `<table class="scoretab">` (and an `H · Kill-criteria` row), a
   `<footer>`, a `<div class="cut">` placeholder, and a Module-A JS engine that
   defines `function simulate`. Modules I & J, the § Audit appendix, the build
   stamp and the footer/strictbar text are injected/refreshed by the framework.
3. `python refresh_all.py` (or `python utils/build_one.py <name>`)

No framework code changes.

## What each script does

| Script                   | Purpose                                                            |
|--------------------------|--------------------------------------------------------------------|
| `refresh_all.py` (root)  | Convenience wrapper — delegates to `utils/refresh_all.py`          |
| `utils/refresh_all.py`   | Orchestrator; runs inject → tallies → finalize → audit → verify (all stocks) |
| `utils/build_one.py`     | Same builders, scoped to a single stock name                      |
| `utils/analytics.py`     | Core library: Yahoo v8 fetch, correlated MC, asymmetry, Kelly, VaR, reverse-DCF |
| `utils/inject.py`        | Renders Modules I & J and updates the stepper nav + scorecard rows |
| `utils/bullcase.py`      | Perfect-execution 10y bull path (Module U) — config-driven ceiling price / CAGR / PV |
| `utils/export_universe.py` | Builds `data/metrics_latest.csv` + `dashboard/index.html` (central screen) |
| `utils/tallies.py`       | Refreshes the coloured Bull / Mixed / Bear tally bar (counts the live verdict chips in each page's own scorecard; config tally is only a fallback) |
| `utils/finalize.py`      | Stamps build date, adds the "Built …" pill, refreshes footer notes |
| `utils/audit.py`         | Regenerates the § Audit data-sources & methodology appendix        |
| `utils/verify.py`        | HTML parse-tree check + integrity of injected sections             |
| `utils/paths.py`         | Shared path helpers                                               |
| `utils/universe_screener.py` | Fetches + scores every Helsinki/Stockholm equity plus the S&P 500 → `dashboard/screener_data.*`, `data/screener_latest.csv` (see § Universe screener) |
| `utils/screener_server.py` | Local static+API server for `dashboard/screener.html`'s live Refresh button |

### Perfect-execution bull path (Module U)

Optional per-stock block `bull_case` in config. When present, `utils/bullcase.py`
(and `build_one` / `refresh_all`) injects **Module U**: a year-by-year path that
answers *if everything goes right for N years, what is a realistic best-case
price?* Defaults cover sales CAGR, terminal margin & multiple, FCF conversion,
dividends, buybacks, and a discount rate for PV. The HTML module includes live
sliders so assumptions can be stress-tested in the browser.

```powershell
python utils/bullcase.py konecranes           # compute + inject
python utils/bullcase.py konecranes --print   # numbers only
```

## Data flow

```
       Yahoo Finance v8 chart API                  stocks/config.py (STOCKS dict)
                    │                                        │
                    └──────► utils/analytics.py ◄────────────┘
                                   │
      ┌──────────┬─────────────────┼───────────────┬──────────────┐
      │          │                 │               │              │
  inject.py  tallies.py       finalize.py       audit.py      verify.py
      │          │                 │               │              │
      └──────────┴────► stocks/*.html ◄────────────┘              │
                                                                    verify only
```

## What lives in `stocks/config.py`

- `STOCKS` — dict keyed by short name. Every stock-specific value the toolkit
  needs is here: tickers, engines, driver ranges, peers, benchmark/macro
  tickers, base-rate series, owner-earnings anchor, endpoints for the audit
  trail, primary-source citations, cut-list text, tally counts, optional
  strictbar rewrite. Larger names (SpaceX / Amazon / Tesla) keep their config in
  a dedicated `config_<name>.py` module wired in at the bottom of `config.py`.
- `DATA_PROVIDER_NOTES` — general audit note shipped in every § Audit
  appendix (framework-wide, not per stock).
- `get(name)` / `all_names()` — small helpers.

## Data providers used

Every fetched URL is unauthenticated and public.

| Provider                            | What                              |
|-------------------------------------|-----------------------------------|
| Yahoo Finance v8 chart API          | Daily OHLC + live spot for every stock, indices (^OMXH25, ^STOXX, ^GSPC, ^NDX), ^TNX (real-rate proxy), commodity/FX macros (BZ=F, EURUSD=X) |
| Primary company releases            | Balance sheet / cash flow / KPIs (issuer IR + SEC EDGAR filings) |
| Solidium / Finnish Government       | State-ownership disclosures       |
| Simply Wall St / S&P                | Cross-check of derived ratios     |
| Investing.com / MarketScreener / MarketBeat / TipRanks | Consensus PTs (point-in-time) |
| Peer-reviewed methodology           | Kelly 1956, Thorp 1969, Mauboussin & Rappaport 2001/2021, Rockafellar-Uryasev 2000, Piotroski 2000, Altman 1968, Sloan 1996, Jegadeesh-Titman 1993, Fama-French 1993, Frazzini-Pedersen 2014 |

## Requirements

Python 3.9+ with **standard library only**. No pip dependencies. Tested on
Python 3.14.

## Legitimately excluded (still not fetchable via public APIs)

- Beneish M-score (needs eight two-year ratios not disclosed at that granularity)
- Options-implied skew and volatility surface
- Precise stock-borrow cost & sub-threshold short-position disclosures
- Insider transaction net flow at daily resolution

If you plug in a Bloomberg / Refinitiv terminal these become fetchable and can
be added to `stocks/config.py` without any framework changes.

## Disclaimer

For analysis and education only — not investment advice, not a recommendation,
not a price target. The model quantifies the uncertainty in a set of
assumptions; it does not make those assumptions correct. Verify all
primary-source figures against the underlying releases before acting.
