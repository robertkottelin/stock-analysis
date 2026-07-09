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
├── stocks/                               # stock-specific data + reports
│   ├── config.py                         # per-stock config (drivers, endpoints, sources, tally, ...)
│   ├── config_spacex.py                  # SpaceX config (wired into config.py)
│   ├── config_amazon.py                  # Amazon config (wired into config.py)
│   ├── config_tesla.py                   # Tesla config (wired into config.py)
│   ├── konecranes-pipeline.html          # the report files
│   ├── neste-analytics-pipeline.html
│   ├── sampo-pipeline.html
│   ├── mandatum-pipeline.html
│   ├── orion-pipeline.html
│   ├── spacex-analytics-pipeline.html
│   └── tesla-pipeline.html
└── utils/                                # reusable framework (no per-stock strings)
    ├── paths.py                          # path helpers
    ├── analytics.py                      # fetch + MC + metrics library
    ├── inject.py                         # renders Modules I & J
    ├── tallies.py                        # syncs the scorecard tally bars
    ├── finalize.py                       # build timestamp + footer patches
    ├── audit.py                          # § Audit data-sources appendix
    ├── verify.py                         # HTML parse + integrity check
    ├── build_one.py                      # build a SINGLE stock end-to-end
    └── refresh_all.py                    # orchestrator (delegated to by ../refresh_all.py)
```

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

The full pipeline runs in ~5–7 seconds. Every builder is idempotent — safe to
re-run any time (e.g. weekly).

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
| spacex       | SPCX      | Five-leg SOTP (Starlink / launch / orbital DC / frontier / AI) |
| amazon       | AMZN      | AWS + non-AWS two-block SOTP                                |
| **tesla**    | **TSLA**  | **Four-leg SOTP (auto core / energy / robotaxi / Optimus) + bull-case overlay.** Deep multi-year tape → every Module I/J window computes on a full sample (no `n/a` backfills). Config in `stocks/config_tesla.py`. |

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
| `utils/tallies.py`       | Refreshes the coloured Bull / Mixed / Bear tally bar               |
| `utils/finalize.py`      | Stamps build date, adds the "Built …" pill, refreshes footer notes |
| `utils/audit.py`         | Regenerates the § Audit data-sources & methodology appendix        |
| `utils/verify.py`        | HTML parse-tree check + integrity of injected sections             |
| `utils/paths.py`         | Shared path helpers                                               |

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
