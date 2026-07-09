"""
Amazon.com (NASDAQ: AMZN) — stock-specific configuration.

Kept in its own module (same pattern as config_spacex.py) and wired into the
STOCKS registry at the bottom of stocks/config.py. No framework code under
../utils needs to know about it.

Engine: a transparent two-block sum-of-the-parts, matching the JS engine in
amazon-pipeline.html Module A exactly:

    AWS value        = AWS FY26e revenue ($bn) x AWS op margin (%) x EV/EBIT multiple
    Non-AWS value    = non-AWS operating income ($bn: NA + International, ads embedded)
                       x earnings multiple
    Fair value/share = (AWS value + non-AWS value + net cash ~$12bn) x 1000 / 10,837m shares

Sourced anchors (see primary_sources below):
    FY2025: net sales $716.9bn (+12%); AWS $128.7bn (+20%, op income $45.6bn);
            NA $426.3bn (op income $29.6bn); Intl $161.9bn (op income $4.7bn);
            total op income $80.0bn; net income $77.7bn; diluted EPS $7.17;
            TTM OCF $139.5bn; capex $128.3bn; FCF $11.2bn (-71% YoY).
    Q1'26:  revenue $181.5bn (+17%); AWS $37.6bn (+28%, op income $14.2bn,
            37.7% margin, $150bn run-rate); op income $23.9bn (13.1% record
            margin); EPS $2.78 incl. $16.8bn pre-tax Anthropic gains;
            TTM FCF $1.2bn; Q1 capex $43.2bn; FY26 capex plan ~$200bn;
            AWS backlog $364bn (ex the incremental $100bn OpenAI commitment).
"""
from __future__ import annotations
from typing import Callable, Any


def _make_amazon_engine() -> Callable[[dict], float]:
    shares_m, net_cash_bn = 10837.0, 12.0   # diluted shares FY2025; cash+ST inv ~$143bn - debt ~$131bn
    def engine(d):
        aws_ebit_bn = d["awsrev"] * d["awsmgn"] / 100.0
        ev_bn = aws_ebit_bn * d["awsmlt"] + d["retoi"] * d["retmlt"] + net_cash_bn
        return ev_bn * 1000.0 / shares_m
    return engine


AMAZON_CONFIG: dict[str, Any] = {
    "ticker": "AMZN",
    "html_file": "amazon-pipeline.html",
    "currency": "$",
    "pipeline_price": 243.0,          # spot at authoring, 2026-07-06 (~$243.7 on Jul 2)
    "shares_m": 10837.0,              # FY2025 diluted (net income $77.7bn / EPS $7.17)
    "consensus_pt": 313.0,            # Investing.com, 62 analysts, avg $312.99 (high $370 / low $207)
    "eps_ttm": 8.36,                  # $7.17 FY25 - $1.59 Q1'25 + $2.78 Q1'26 (incl. Anthropic mark-up gains)
    "engine": _make_amazon_engine(),
    "drivers": {
        # FY2026e AWS revenue, $bn — FY25 $128.7bn, Q1'26 run-rate $150bn at +28%
        "awsrev": {"lo": 150.0, "md": 161.0, "hi": 172.0, "rho": 0.75},
        # AWS operating margin, % — FY25 35.4%, Q1'26 37.7%; lo = depreciation-wave stress
        "awsmgn": {"lo": 30.0,  "md": 35.0,  "hi": 39.0,  "rho": 0.55},
        # EV/EBIT multiple on AWS — the master valuation driver (reverse-DCF target)
        "awsmlt": {"lo": 18.0,  "md": 28.0,  "hi": 38.0,  "rho": 0.70},
        # Non-AWS (NA + Intl, advertising embedded) FY26e operating income, $bn —
        # FY25 $34.3bn; Q1'26 run-rate ~$39bn and ads (+24%) mixing margins up
        "retoi":  {"lo": 34.0,  "md": 42.0,  "hi": 50.0,  "rho": 0.65},
        # Earnings multiple on the non-AWS block
        "retmlt": {"lo": 14.0,  "md": 20.0,  "hi": 26.0,  "rho": 0.55},
    },
    "reverse_dcf_target": "awsmlt",
    "reverse_dcf_label":  "AWS EV/EBIT multiple (at mode AWS revenue/margin and non-AWS block)",
    "reverse_dcf_unit":   "\u00d7",
    "peers": ["MSFT", "GOOGL"],
    "bench1_ticker": "^GSPC", "bench1_label": "S&P 500",
    "bench2_ticker": "^NDX",  "bench2_label": "Nasdaq 100",
    "macro_ticker": "^TNX",
    "macro_label":  "US 10y yield (^TNX)",
    "quality_score": 0.85,
    "base_rates": {
        "variable": "AWS revenue growth (% YoY)",
        "unit": "%",
        "series": [
            ("2019",   36.5, "cloud land-grab era"),
            ("2020",   29.5, "Covid acceleration"),
            ("2021",   37.1, "peak of the last cycle"),
            ("2022",   28.8, "optimization cycle begins"),
            ("2023",   13.3, "cloud-optimization trough"),
            ("2024",   18.5, "recovery / early AI demand"),
            ("2025",   19.6, "FY2025 reported — sourced"),
            ("Q4'25",  23.6, "acceleration quarter — sourced"),
            ("Q1'26",  28.4, "15-quarter high, $150bn run-rate — sourced"),
        ],
        "current_label": "Q1'26 = +28.4% (fastest in 15 quarters)",
        "current_value": 28.4,
        "reversion_mid": 22.0,
    },
    # Owner earnings: FY2025 TTM free cash flow per the Q4'25 release. The
    # honest wrinkle: the ~$200bn 2026 AI-capex plan crushed TTM FCF to
    # ~$1.2bn by Q1'26 — Module J's negative OE-yield spread is the point,
    # not a bug. (Using OCF $139.5bn instead would assume all capex is
    # growth capex — an assumption, so we don't.)
    "oe_anchor_m": 11194.0,
    "oe_note": "TTM FCF $11,194m per the Q4'25 release (Q1'26 TTM fell to ~$1.2bn on the ~$200bn AI-capex plan — sourced)",
    "endpoints": [
        ("https://query1.finance.yahoo.com/v8/finance/chart/AMZN?range=5y&interval=1d",
         "Amazon 5-year daily OHLC + regularMarketPrice",
         "I: realised vol / beta / momentum / drawdown / own-history percentile"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/^GSPC?range=5y&interval=1d",
         "S&P 500 index — broad-market benchmark",
         "I: beta vs S&P 500"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/^NDX?range=5y&interval=1d",
         "Nasdaq 100 — mega-cap growth benchmark",
         "I: beta vs Nasdaq 100"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/^TNX?range=5y&interval=1d",
         "US 10-year Treasury yield — rate-duration macro factor + real-rate proxy",
         "I: beta vs rates \u00b7 J: owner-earnings yield vs real 10y"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/MSFT?range=2y&interval=1d",
         "Microsoft — hyperscaler peer (Azure)",
         "I: peer-relative 12m"),
        ("https://query1.finance.yahoo.com/v8/finance/chart/GOOGL?range=2y&interval=1d",
         "Alphabet — hyperscaler peer (Google Cloud)",
         "I: peer-relative 12m"),
    ],
    "primary_sources": [
        ("Amazon Q4/FY2025 earnings release (8-K Ex-99.1, 5 Feb 2026)",
         "FY25 net sales $716.9bn (+12%); segment sales NA $426.3bn / Intl $161.9bn / AWS $128.7bn (+20%); segment operating income NA $29.6bn / Intl $4.7bn / AWS $45.6bn; total operating income $80.0bn; net income $77.7bn, diluted EPS $7.17; TTM operating CF $139.5bn, capex $128.3bn, FCF $11.2bn (\u221271%); Q4 special charges ~$2.4bn (Italy tax, severance, store impairments); Q4 AWS +24% at 35.0% margin; ads Q4 $21.3bn (+22%)",
         "A engine, D forensics, E capital record"),
        ("Amazon Q1 2026 earnings release + call (29 Apr 2026)",
         "Revenue $181.5bn (+17%); AWS $37.6bn (+28%, 15-quarter high, op income $14.2bn / 37.7% margin, $150bn run-rate); NA $104.1bn (+12%), Intl $39.8bn; operating income $23.9bn (record 13.1% margin); EPS $2.78 incl. $16.8bn pre-tax Anthropic investment gains; TTM FCF ~$1.2bn; Q1 capex $43.2bn, FY26 plan ~$200bn; AWS backlog $364bn ex the $100bn OpenAI expansion; ads $17.2bn (+24%, TTM >$70bn)",
         "A engine, B driver analysis, C scenarios, H kill-criteria"),
        ("Amazon FY2025 Form 10-K balance sheet (via S&P aggregators)",
         "Total assets ~$818bn, stockholders' equity $411.1bn, cash & equivalents $86.8bn, long-term debt $65.6bn (D/E 0.16); current assets $229.1bn; ROE 18.9%, ROA 9.5%; shares out 10.73bn (+1.3% YoY)",
         "D forensics"),
        ("CNBC hyperscaler round-up (29 Apr 2026)",
         "Q1'26 cloud growth: AWS +28% vs Azure +40% vs Google Cloud +63%; OpenAI expanded its $38bn AWS commitment by $100bn over eight years; Amazon plans to invest $50bn in OpenAI",
         "C scenarios, G peers, H kill-criteria"),
        ("Investing.com — AMZN consensus (early Jul 2026)",
         "62-analyst average PT $312.99 (high $370 / low $207), Strong Buy (63 buy / 4 hold / 0 sell); ~+29% vs spot",
         "F positioning"),
        ("stockanalysis.com / Macrotrends / fullratio — peer multiples (2\u20134 Jul 2026)",
         "MSFT trailing P/E 23.2\u00d7 (fwd ~20\u201321\u00d7, EV/EBITDA 16.0\u00d7, price ~$390); GOOGL trailing P/E 27.5\u00d7; AMZN trailing P/E computed 29.1\u00d7 on $8.36 TTM EPS (flattered by the $16.8bn Anthropic mark-up)",
         "G peers"),
        ("Simply Wall St — Amazon health snapshot (Q1'26 basis)",
         "Equity $441.9bn, total debt $130.6bn (D/E 29.6%), cash + ST investments $143.1bn; net interest income (coverage n.m.); ~$200bn 2026 capex committed to AI infrastructure incl. Trainium silicon and Leo satellites",
         "D forensics, E capital record"),
    ],
    "cut_replacements": (
        '<b>Beneish M-score</b> \u2014 needs eight two-year ratios at a granularity Amazon does not break out per segment; a half-estimated score is worse than none. '
        '<b>Advertising segment operating income</b> \u2014 embedded in the North America / International segments and never disclosed, which is why the engine values a single non-AWS block instead of ads separately \u2014 a modelling simplification, not a hidden number. '
        '<b>Options skew, stock-borrow cost, and daily insider-transaction net flow</b> \u2014 fetchable for a US mega-cap from paid terminals but not from the Yahoo v8 chart endpoint this toolkit standardises on; they would slot in without framework changes. '
        '<b>A clean ex-AI-gains TTM EPS</b> \u2014 the $16.8bn Q1\'26 Anthropic mark-up sits inside reported EPS; stripping it requires a tax-rate assumption this build does not assert. '
        'Everything else previously flagged as "cut" (factor betas vs S&amp;P 500 / Nasdaq 100 / rates, price-history percentile, momentum, realised vol, drawdown, peer 12m relative, base-rate frequencies, owner-earnings yield vs real rate) is <b>included</b> in Modules I &amp; J and computed live from the Yahoo Finance v8 chart API.'
    ),
    "strictbar_replacement": (
        '<div class="strictbar"><b>What this build adds.</b> Two institutional modules: '
        '<b>I \u2014 Price-asymmetry layer</b> (reverse-DCF on the AWS multiple, Kelly f*, payoff-asymmetry ratio, VaR/CVaR, realised vol / beta vs S&amp;P 500 &amp; Nasdaq 100 &amp; rates, momentum, own-history percentile, MSFT/GOOGL 12m relative \u2014 all computed live from the Yahoo Finance v8 chart API) and '
        '<b>J \u2014 Base rates &amp; factor composite</b> (reference-class distribution of AWS growth through the cycle, empirical return base-rates from 5y prices, V/Q/M/L factor composite, owner-earnings yield vs real 10y \u2014 which for Amazon in mid-capex-cycle is deliberately ugly) '
        '\u2014 plus three chat-layer modules: <b>K \u2014 Priced-in audit</b>, <b>L \u2014 War &amp; geopolitics overlay</b> and <b>M \u2014 Margin model</b> (the depreciation wave, decomposed). '
        'The single question every module keys on: does the ~$200bn/yr AI build earn its cost of capital \u2014 i.e. is the AWS re-acceleration (+28% Q1\'26) durable enough to justify the multiple the market is paying for it?</div>'
    ),
    # 13 scorecard rows: A-H authored (1 bull / 7 mixed / 0 bear) + K/L/M
    # authored (3 mixed) + I & J placeholders (bear / mixed). After the first
    # live run, sync I and J to the verdicts inject.py prints (it reports
    # "I=..., J=..." on stdout), then re-run tallies.py (refresh_all does
    # this ordering for you on the next pass).
    "tally": {"bull": 1, "mixed": 11, "bear": 1},
}
