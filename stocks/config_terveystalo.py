"""
Terveystalo Oyj (Nasdaq Helsinki: TTALO) — stock-specific configuration.

Kept in its own module (same pattern as config_spacex.py / config_amazon.py /
config_tesla.py) and wired into the STOCKS registry at the bottom of
stocks/config.py. No framework code under ../utils needs to know about it.

Terveystalo is the largest private healthcare services company in Finland (and
one of the largest in the Nordics): a clinic network plus occupational-health,
digital and outsourcing businesses, with a smaller Swedish operation. It is a
classic capital-light services roll-up, so the market prices it on an EV/EBIT
(EV/EBITA) multiple of divisional operating profit less net debt — not on
earnings, which are geared by acquisition amortisation and lease interest.

ENGINE — a transparent TWO-leg sum-of-the-parts on adjusted operating profit,
matching the JS engine in terveystalo-pipeline.html Module A exactly. Terveystalo
reports two operating segments:

    core value  = Healthcare Services (Finland) adjusted EBIT €m x EV/EBIT      (the moat)
    portfolio   = Portfolio Businesses (incl. Sweden, staffing, wellbeing) rev x EV/Sales
    fair value  = (core + portfolio - central cost - net debt) / shares

Healthcare Services is the defensive, market-leading core and gets its own
EV/EBIT multiple (the reverse-DCF target and the single most-contested number).
Portfolio Businesses run near break-even at the EBIT line, so — like Orion's
rest-of-group leg and Tesla's energy leg — that half is valued on EV/Sales
rather than a meaningless EV/EBIT on ~zero profit. Net debt is the reported
interest-bearing figure EXCLUDING IFRS-16 lease liabilities (the ~EUR 203m lease
liability is matched by right-of-use assets and the clinic rent already sits
inside each segment's post-IFRS-16 EBIT via right-of-use depreciation — the same
lease treatment used for Kesko, flagged in Module A and the footer).

DATA BASIS (sourced; the pipeline re-fetches the live spot/betas itself):
  - Spot EUR 8.20 anchored to the Silmaasema share-consideration price and the
    52-week low EUR 7.40 (52-week high EUR 12.32); the stock de-rated hard through
    2026 on the demand shock. Live spot is re-fetched at build time.
  - FY2025 (financial statements release, 12 Feb 2026): revenue EUR 1,281m
    (-4.1% YoY); adjusted EBITA EUR 179.3m (+4.8%), a record 14.0% margin (2024:
    12.8%); adjusted EBIT EUR 156.3m (12.2% margin, 2024: EUR 140.5m); EPS EUR 0.73
    (+29%); operating cash flow EUR 207m, capex EUR 30.8m, FCF EUR 176m; net debt
    EUR 508m incl. leases / EUR 305.4m ex-IFRS-16; net debt/adj. EBITDA 2.0x;
    dividend proposal EUR 0.64/share (88% payout); ~126.655m shares; ROE ~16.4%;
    >15,500 professionals. Segment: Healthcare Services adjusted EBIT EUR 154.6m
    (+7.6%, 15.0% margin); Portfolio Businesses ~break-even at EBIT after central
    costs; Sweden ~EUR 85m revenue.
  - Q1'26 (interim report, Apr 2026): revenue EUR 308.2m (-11.2% YoY, "exceptionally
    weak demand environment"); adjusted EBIT EUR 33.7m (-29.6%, 10.9% margin vs
    13.8%); Healthcare Services revenue EUR 253.6m (-9.6%). FY2026 guidance:
    adjusted EBIT EUR 135-165m (2025: EUR 156m) — a step DOWN, and management
    flagged the outcome as "rather below than above" the EUR 150m midpoint.
  - Catalyst: Terveystalo agreed to acquire Silmaasema (leading Finnish private
    eye-health provider) — EV ~EUR 574m (EV/adj. EBIT 2025 11.5x), funded with
    EUR 275m cash + 36.5m new Terveystalo shares at EUR 8.20; Coronaria becomes the
    largest shareholder at ~15.1%. Silmaasema 2025: revenue EUR 267m, adjusted EBIT
    EUR 37m. The base engine values Terveystalo STANDALONE (126.655m shares); the
    deal is treated as an explicit driver/scenario/kill-criterion, not baked in.
  - Consensus 12m PT ~EUR 9.2-9.7 (Inderes "Accumulate"; blend EUR 9.40 used).
"""
from __future__ import annotations
from typing import Callable, Any


_SHARES_M   = 126.655      # shares outstanding at end-2025 (standalone, pre-Silmaasema)
_NET_DEBT_M = 305.4        # interest-bearing net debt EXCLUDING IFRS-16 leases (FY2025)
_CENTRAL_M  = 30.0         # capitalised group-common / unallocated cost (an explicit assumption)


def _make_terveystalo_engine() -> Callable[[dict], float]:
    """Per-share fair value in EUR from one draw of the four drivers.

    Two value legs less central cost and net debt:
      1. Healthcare Services (Finland)  — adjusted EBIT x EV/EBIT   (the moat)
      2. Portfolio Businesses (incl. Sweden) — revenue x EV/Sales   (thin-margin turnaround)
    Portfolio Businesses run ~break-even at the EBIT line, so that half is valued
    on EV/Sales rather than an unstable EV/EBIT on near-zero profit.
    """
    def engine(d: dict) -> float:
        core      = d["hs_ebit"] * d["hs_mult"]        # EUR m — Healthcare Services EV
        portfolio = d["pb_sales"] * d["pb_mult"]       # EUR m — Portfolio Businesses EV
        ev = core + portfolio - _CENTRAL_M             # EUR m — group EV
        return (ev - _NET_DEBT_M) / _SHARES_M          # EUR/share
    return engine


TERVEYSTALO_CONFIG: dict[str, Any] = {
    # ---- identity & market ----
    "ticker":         "TTALO.HE",
    "html_file":      "terveystalo-pipeline.html",
    "currency":       "€",
    "pipeline_price": 8.20,            # authored spot; live spot re-fetched at build
    "shares_m":       _SHARES_M,
    "consensus_pt":   9.40,            # blend of Inderes Accumulate / MarketScreener (range 9.2-9.7)
    "eps_ttm":        0.64,            # FY2025 EPS 0.73 stepped down through the weak Q1'26
    "eps_fwd_12m":    0.75, "eps_fwd_24m": 0.76,   # consensus curr./next-FY EPS (Yahoo, build-time)

    # ---- Module A engine ----
    "engine": _make_terveystalo_engine(),
    "drivers": {
        # Healthcare Services (Finland) adjusted EBIT, EUR m. FY2025 EUR 154.6m (15.0%
        # margin); Q1'26 run-rate softer on the demand shock, FY2026 group guidance
        # 135-165m. Mode 140 normalises the record 2025 DOWN toward the 2026 downturn —
        # deliberately below the reported peak, with genuine two-sided risk.
        "hs_ebit":  {"lo": 116.0, "md": 140.0, "hi": 158.0, "rho": 0.66},
        # Healthcare Services EV/EBIT multiple — the core value driver, the reverse-DCF
        # target. Sector/deal comps ~11-12x (Silmaasema bought at 11.5x EV/EBIT); the
        # de-rated tape currently implies ~8.5x. Mode 9.0 with a LEFT tail (further
        # de-rating risk if the demand downturn deepens) — deliberately left-skewed.
        "hs_mult":  {"lo":   6.3, "md":  9.00, "hi":  11.0, "rho": 0.64},
        # Portfolio Businesses (incl. Sweden) revenue, EUR m. ~EUR 248m run-rate.
        "pb_sales": {"lo": 210.0, "md": 248.0, "hi": 282.0, "rho": 0.48},
        # Portfolio Businesses EV/Sales — thin-margin turnaround, so a low multiple.
        "pb_mult":  {"lo":   0.32, "md":  0.70, "hi":  1.08, "rho": 0.43},
    },
    "reverse_dcf_target": "hs_mult",
    "reverse_dcf_label":  "Healthcare Services core EV/EBIT multiple (at mode HS-EBIT / portfolio / central)",
    "reverse_dcf_unit":   "×",

    # ---- Module I regressions ----
    "bench1_ticker": "^OMXH25", "bench1_label": "OMX Helsinki 25",
    "bench2_ticker": "^STOXX",  "bench2_label": "STOXX 600",
    "macro_ticker":  None,
    "macro_label":   None,
    "peers": ["ATT.ST", "AMBEA.ST"],   # Attendo, Ambea — the closest listed Nordic health-services comps

    # ---- Module J ----
    # 0.62 blends strong profitability (ROE ~16.4%) and cash conversion (FCF EUR 176m)
    # against a goodwill-heavy acquisition-built balance sheet, 2.0x net-debt/EBITDA
    # and the 2026 demand downgrade.
    "quality_score": 0.62,

    # Reference class: the group's own adjusted EBITA margin through the cycle — the
    # margin-transformation story and, at a 14.0% record, the mean-reversion risk into
    # the 2026 demand downturn. This is the empirical anchor that balances the cheap
    # cash multiple against a peak-margin print.
    "base_rates": {
        "variable": "Group adjusted EBITA margin (%)",
        "unit": "%",
        "series": [
            ("2022",             8.4,  "efficiency programme early days — reported"),
            ("2023",             9.8,  "operational-efficiency ramp — reported"),
            ("2024",            12.8,  "reported"),
            ("2025",            14.0,  "reported all-time record"),
            ("2026E guidance",  11.5,  "adj. EBIT 135-165m on ~1.25bn revenue — company guidance, midpoint-ish"),
            ("cycle average",   11.3,  "2022-2025 mean — the empirical reversion anchor"),
        ],
        "current_label": "2025 = 14.0% (record; 2026 guided lower)",
        "current_value": 14.0,
        "reversion_mid": 11.5,
    },

    # Owner-earnings anchor, EUR m. FY2025 free cash flow EUR 176m (operating cash flow
    # EUR 207m less EUR 31m capex). The honest wrinkle: under IFRS-16 this figure is
    # BEFORE lease-principal repayments (clinic rents ~EUR 40m/yr sit in financing), so
    # true owner earnings are lower — the OE yield below is generous on that account.
    "oe_anchor_m": 176.0,
    "oe_note": ("FY2025 free cash flow EUR 176m (operating cash flow EUR 207m less EUR 31m capex; "
                "financial statements release 12 Feb 2026) as the owner-earnings proxy; under IFRS-16 "
                "this is before ~EUR 40m of annual lease-principal repayment, so the real cash yield is "
                "thinner than the headline figure implies"),

    # ---- § Audit appendix ----
    "endpoints": [
        ("https://query1.finance.yahoo.com/v8/finance/chart/TTALO.HE?range=5y&interval=1d",
         "Terveystalo 5-year daily OHLC + regularMarketPrice + 52w range.",
         "I: realised vol / beta / momentum / drawdown / own-history percentile · J: base rates"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/%5EOMXH25?range=5y&interval=1d",
         "OMX Helsinki 25 index — benchmark for local beta.", "I: beta vs OMXH25"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/%5ESTOXX?range=5y&interval=1d",
         "STOXX Europe 600 — pan-European benchmark.", "I: beta vs STOXX 600"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/%5ETNX?range=1mo&interval=1d",
         "US 10-year Treasury yield — real-rate proxy.", "J: owner-earnings yield vs real 10y"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/ATT.ST?range=2y&interval=1d",
         "Attendo (Nasdaq Stockholm) — Nordic care-services peer.", "I: peer-relative 12m"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/AMBEA.ST?range=2y&interval=1d",
         "Ambea (Nasdaq Stockholm) — Nordic care-services peer.", "I: peer-relative 12m"),
    ],
    "primary_sources": [
        ("Terveystalo Group Financial Statements Release 2025 (12 Feb 2026)",
         "Revenue EUR 1,281m (-4.1%); adjusted EBITA EUR 179.3m (+4.8%, record 14.0% margin vs 12.8%); "
         "adjusted EBIT EUR 156.3m (12.2%, 2024: EUR 140.5m); EPS EUR 0.73 (+29%); operating cash flow "
         "EUR 207m, capex EUR 30.8m, FCF EUR 176m; net debt EUR 508m incl. leases / EUR 305.4m ex-IFRS-16; "
         "net debt/adj. EBITDA 2.0x; dividend proposal EUR 0.64 (88% payout); ~126.655m shares; ROE ~16.4%; "
         ">15,500 professionals. Segment: Healthcare Services adjusted EBIT EUR 154.6m (+7.6%, 15.0% margin)",
         "A engine, D forensics, E capital record, Q dashboard"),
        ("Terveystalo Group Interim Report January-March 2026 (Apr 2026)",
         "Revenue EUR 308.2m (-11.2% YoY, 'exceptionally weak demand environment'); adjusted EBIT EUR 33.7m "
         "(-29.6%, 10.9% margin vs 13.8%); Healthcare Services revenue EUR 253.6m (-9.6%); FY2026 guidance "
         "adjusted EBIT EUR 135-165m (2025: EUR 156m), flagged 'rather below than above' the EUR 150m midpoint",
         "B driver analysis, C scenarios, H kill-criteria"),
        ("Inside information: Terveystalo to acquire Silmaasema (2026)",
         "Share purchase agreement to buy Silmaasema (leading Finnish private eye-health provider); EV ~EUR 574m "
         "(EV/adj. EBIT 2025 11.5x) funded with EUR 275m cash + 36.5m new Terveystalo shares at EUR 8.20; Coronaria "
         "becomes largest shareholder at ~15.1%. Silmaasema 2025: revenue EUR 267m, adjusted EBIT EUR 37m, ~15% of "
         "the publicly-funded eye-health market",
         "B driver analysis, C scenarios, F positioning, H kill-criteria"),
        ("Terveystalo largest-shareholders & ownership register (2025-2026)",
         "Rettig Investment, Varma, OP, Hartwall Capital (HC Holding), Ilmarinen and Elo together ~59.3% of shares; "
         "predominantly Finnish institutional. Post-Silmaasema, Coronaria the largest holder at ~15.1%",
         "F positioning"),
        ("stockanalysis.com / Simply Wall St — Terveystalo profile (2026)",
         "ROE ~16.4%, ROIC ~10.5%; cash EUR 75m, gross debt EUR 581m (net EUR 506m incl. leases); Debt/Equity ~0.99; "
         "TTM revenue EUR 1.28bn, net profit EUR 92.6m, FCF EUR 176m — cross-checks on the reported ratios",
         "D forensics, Q dashboard"),
        ("Inderes / MarketScreener — Terveystalo consensus (2026)",
         "Inderes 'Accumulate'; consensus 12m PT ~EUR 9.2-9.7 (blend EUR 9.40 used); Ambea EV/EBITDA ~8x, "
         "adjusted EBITA margin ~9.6% — Nordic care-services peer context",
         "F positioning, G peers"),
    ],

    # ---- footer & scorecard ----
    "cut_replacements": (
        '<b>The two-leg EV/EBIT sum-of-the-parts is a transparent proxy, not a hidden number.</b> Terveystalo '
        'discloses segment adjusted operating profit but not a segment balance sheet, so Healthcare Services is '
        'valued on EV/EBIT, Portfolio Businesses (near break-even at EBIT) on EV/Sales, and IFRS-16 lease liabilities '
        '(~&euro;203m) are excluded from net debt — matched by right-of-use assets, with the clinic rent already inside '
        'segment EBIT via right-of-use depreciation. Valuing on lease-inclusive EV/EBITDA instead would move the mix, '
        'not the conclusion. '
        '<b>The Silmaasema acquisition is modelled as an explicit driver/scenario, not baked into the base engine</b> — '
        'the 36.5m new shares (~+29% count) and &euro;275m cash consideration change the equity story materially and the '
        'deal was still completing, so the base case values Terveystalo standalone (126.655m shares) and Modules B/C/H '
        'carry the pro-forma math openly. '
        '<b>Beneish M-score</b> — needs eight two-year ratios not fully disclosed for an acquisition-built P&amp;L; a '
        'half-estimated score is worse than none. '
        '<b>Options skew, precise borrow cost, and detailed insider transaction flow</b> — not reliably fetchable for a '
        'Nasdaq Helsinki name from a public API; would slot in from a Bloomberg terminal. '
        'Everything else previously flagged as "cut" (factor betas, own-history percentile, momentum, realised vol, '
        'drawdown, 12-month peer relative return, base-rate frequencies, owner-earnings yield vs real rate) is '
        '<b>included</b> in Modules I &amp; J and computed live from the Yahoo Finance v8 chart API.'
    ),
    "strictbar_replacement": (
        '<div class="strictbar"><b>What this build adds.</b> A two-leg sum-of-the-parts — <b>Healthcare Services</b> '
        '(Finland core, EV/EBIT) and <b>Portfolio Businesses</b> (incl. Sweden, EV/Sales) — so the price is decomposed '
        'across the defensive clinic moat and the thin-margin turnaround, not a single P/E on acquisition-geared '
        'earnings. Two institutional modules computed live from the Yahoo Finance v8 chart API: <b>I — Price-asymmetry '
        'layer</b> (reverse-DCF on the core EV/EBIT multiple, Kelly f*, payoff-asymmetry, VaR/CVaR, realised vol, betas '
        'vs OMXH25 &amp; STOXX 600, own-history percentile, Attendo/Ambea 12m relative) and <b>J — Base rates &amp; '
        'factor composite</b> (the group\'s own adjusted-EBITA-margin reference class, empirical return base-rates, '
        'V/Q/M/L factor score, owner-earnings yield vs real 10y). The live demand downturn (Q1\'26 revenue -11%, FY2026 '
        'adjusted-EBIT guidance cut to &euro;135-165m) and the &euro;574m Silmaasema eye-care acquisition are carried '
        'openly as drivers, scenarios and kill-criteria. Balance-sheet facts are from the FY2025 / Q1\'26 releases; '
        'nothing is asserted from memory.</div>'
    ),
    # 10 graded reads counted in the tally (A-H + injected I,J). Q is a dashboard, not
    # scored. Verdicts net to broadly MIXED: a cheap cash multiple and a positive
    # reverse-DCF vs the Silmaasema deal price, against a record-high margin due to
    # mean-revert and a cut 2026 outlook.
    # tallies.py counts the live chips on the page; this is only the fallback.
    "tally": {"bull": 3, "mixed": 6, "bear": 1},
}
