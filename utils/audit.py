"""Regenerates the Data Sources & Audit Trail appendix for each stock.
Endpoints, primary sources, formulas and methodology refs are pulled from
stocks/config.py; the CSS and framework text are shared.
"""
from __future__ import annotations
import os, re, sys, datetime
from paths import html_path
from analytics import STOCKS, all_names, DATA_PROVIDER_NOTES

BUILD_DT   = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
BUILD_DATE = datetime.datetime.now().strftime("%Y-%m-%d")

APPENDIX_CSS = """
  .audit{margin-top:24px;background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:clamp(16px,3vw,26px)}
  .audit h3{font-family:var(--disp);font-weight:600;font-size:20px;letter-spacing:-.01em;margin-bottom:6px}
  .audit .lead{font-size:13.5px;color:var(--muted);margin-bottom:16px;line-height:1.5}
  .audit h4{font-family:var(--mono);font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--blue-deep);font-weight:600;margin:18px 0 8px}
  .audit table{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:4px}
  .audit table th{text-align:left;font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--faint);padding:6px 8px;border-bottom:1px solid var(--line-strong);background:var(--surface-2)}
  .audit table td{padding:7px 8px;border-bottom:1px dashed var(--line);vertical-align:top;line-height:1.45}
  .audit table td.mono{font-family:var(--mono);font-size:11.5px;color:var(--ink);word-break:break-all}
  .audit table td.mods{font-family:var(--mono);font-size:10.5px;color:var(--blue-deep);font-weight:600}
  .audit ul{margin:6px 0 0 20px;font-size:12.5px;line-height:1.65;color:var(--ink)}
  .audit ul li{margin-bottom:4px}
  .audit ul li b{color:var(--ink)}
  .audit .fetchbox{background:var(--surface-2);border-left:3px solid var(--teal);border-radius:0 8px 8px 0;padding:11px 14px;margin-top:14px;font-size:12px;color:var(--muted);line-height:1.5}
  .audit .fetchbox b{color:var(--ink)}
  .audit .refs{background:var(--surface-2);border-radius:10px;padding:14px 16px;font-size:12.5px;line-height:1.6;margin-top:14px}
  .audit .refs cite{font-style:italic;color:var(--ink)}
"""


FORMULAS = [
    ("MC engine (Module A, re-used)",
     "Fair value per share = engine(driver draws) drawn from correlated triangulars with a one-factor copula and a regime-shock mixture. Exact formula per name is inside the pipeline's Module A footer."),
    ("Reverse-DCF (Module I)",
     "Solve engine(driver=x, all others at mode) = spot for x, by 80-step grid search over the driver's pipeline range. Reports x, the implied value at mode, and the % gap vs pipeline mode."),
    ("Payoff-asymmetry ratio (Module I)",
     "(P(FV&gt;price) × E[FV−price | FV&gt;price]) ÷ (P(FV&lt;price) × E[price−FV | FV&lt;price]). Values &gt; 1× = pay-off skew in your favour."),
    ("Win/loss ratio b (Module I)",
     "b = E[gain | FV&gt;price] ÷ E[loss | FV&lt;price], both in the stock's price currency."),
    ("Kelly f* (Module I)",
     "(b·p − q)/b, where p = P(FV&gt;price), q = 1−p. Fraction of bank-roll to size if the MC is truth. Half-Kelly (or lower) is the institutional convention."),
    ("VaR & CVaR (Module I)",
     "VaR<sub>α</sub> = the α-quantile of (FV/price − 1) — the loss threshold. CVaR<sub>α</sub> = mean of the α% worst paths — Expected Shortfall."),
    ("Realised volatility (Module I)",
     "SD of daily log-returns × √252, over trailing 1y (252 sessions) and 3y (756 sessions)."),
    ("Beta (Module I)",
     "OLS slope of daily stock log-returns on benchmark log-returns over trailing 252 sessions. R² reported alongside."),
    ("Max drawdown (Module I)",
     "min<sub>t</sub>(P<sub>t</sub>/max(P<sub>s≤t</sub>) − 1) over 5-year adjusted closes."),
    ("Momentum 1/3/6/12m (Module I)",
     "Simple return over trailing 21 / 63 / 126 / 252 sessions on adjusted close."),
    ("Own-history percentile (Module I)",
     "Fraction of trailing 5-year daily closes ≤ current spot."),
    ("Peer 12m relative return (Module I)",
     "Stock's 12m return minus peer's 12m return, both simple returns on adjusted close."),
    ("Return base rates (Module J)",
     "Empirical frequencies over the 5-year rolling windows: P(63-day return &lt; −10%), P(252-day return &lt; 0), P(252-day return &gt; +15%)."),
    ("Factor composite V/Q/M/L (Module J)",
     "V = 1 − price-percentile in own 5y history; Q = quality anchor from Module D (Piotroski / Altman / ROCE); M = logistic-scaled (12m − 1m) return; L = 1 − (1y realised vol / 45%). Simple mean × 100."),
    ("Owner-earnings yield − real rate (Module J)",
     "OE yield = pipeline Module D FCF / market cap; real rate = ^TNX (fetched at build) minus a 2.0% implied inflation. Spread in bp."),
]

METHODOLOGY_REFS = [
    ("Kelly, J. L. (1956)",                          "A New Interpretation of Information Rate",                    "Bell System Tech. Journal, 35: 917–926 — origin of the Kelly criterion."),
    ("Thorp, E. O. (1969)",                          "Optimal Gambling Systems for Favourable Games",                "Rev. Int. Stat. Inst., 37 — practitioner formulation used in Module I."),
    ("Mauboussin, M. J. &amp; Rappaport, A. (2001; 2021)", "Expectations Investing",                                  "Columbia Business School — the reverse-DCF / implied-expectations framework applied in Module I."),
    ("Rockafellar, R. T. &amp; Uryasev, S. (2000)",   "Optimization of Conditional Value-at-Risk",                   "Journal of Risk, 2(3): 21–41 — CVaR / Expected Shortfall used in Module I."),
    ("Piotroski, J. D. (2000)",                       "Value Investing: The Use of Historical Financial Statement Information", "Journal of Accounting Research, 38 — F-score used in Module D."),
    ("Altman, E. I. (1968)",                          "Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy", "Journal of Finance, 23(4) — Z-score used in Module D."),
    ("Sloan, R. G. (1996)",                           "Do Stock Prices Fully Reflect Information in Accruals and Cash Flows about Future Earnings?", "Accounting Review, 71(3) — accruals measure used in Module D."),
    ("Jegadeesh, N. &amp; Titman, S. (1993)",         "Returns to Buying Winners and Selling Losers",                "Journal of Finance, 48 — momentum factor used in Module J."),
    ("Fama, E. &amp; French, K. (1993)",              "Common Risk Factors in the Returns on Stocks and Bonds",       "Journal of Financial Economics, 33 — value factor rationale used in Module J."),
    ("Frazzini, A. &amp; Pedersen, L. H. (2014)",     "Betting Against Beta",                                        "Journal of Financial Economics, 111 — low-vol factor used in Module J."),
]


def render_appendix(name: str) -> str:
    cfg = STOCKS[name]
    endpoints_rows = "".join(
        f'<tr><td class="mono">{url}</td><td>{desc}</td><td class="mods">{mods}</td></tr>'
        for url, desc, mods in cfg["endpoints"]
    )
    primary_rows = "".join(
        f'<tr><td>{src}</td><td>{what}</td><td class="mods">{mods}</td></tr>'
        for src, what, mods in cfg["primary_sources"]
    )
    formulas_rows = "".join(
        f'<tr><td>{lbl}</td><td>{formula}</td></tr>' for lbl, formula in FORMULAS
    )
    refs = "".join(
        f'<li><cite>{a} — {t}.</cite> {j}</li>' for a, t, j in METHODOLOGY_REFS
    )
    return f"""
    <section class="audit" id="mAudit">
      <h3>Data sources &amp; audit trail</h3>
      <div class="lead">Every number in this report is either <b>sourced</b> (fetched from a specific, citable endpoint), <b>computed</b> from those sourced inputs, or an explicit <b>assumption</b> you set on the interactive controls. This appendix lists all three so any figure can be traced to its origin. Build stamp: <b>{BUILD_DT}</b>.</div>

      <h4>◆ Live-fetched endpoints (Yahoo Finance v8 chart API, build time {BUILD_DATE})</h4>
      <table>
        <thead><tr><th>Endpoint URL</th><th>What it delivers</th><th>Used in</th></tr></thead>
        <tbody>{endpoints_rows}</tbody>
      </table>
      <div class="fetchbox"><b>How the fetch works.</b> A single GET to each URL above returns an unauthenticated JSON payload containing daily timestamps, adjusted close, OHLC and volume. Series are aligned by timestamp before any beta or correlation regression. Payloads are cached in the local ./cache folder so repeated runs are idempotent. If Yahoo returns null for a session (holiday / suspension) that row is dropped from the regression, not filled.</div>

      <h4>◆ Primary-source citations (module-level facts)</h4>
      <table>
        <thead><tr><th>Source</th><th>Sourced facts used</th><th>Used in</th></tr></thead>
        <tbody>{primary_rows}</tbody>
      </table>

      <h4>◆ Data providers &amp; the audit rule</h4>
      {DATA_PROVIDER_NOTES}

      <h4>◆ Every metric computed here — formulas</h4>
      <table>
        <thead><tr><th>Metric</th><th>Formula / definition</th></tr></thead>
        <tbody>{formulas_rows}</tbody>
      </table>

      <h4>◆ Methodology references (peer-reviewed / practitioner)</h4>
      <div class="refs"><ul>{refs}</ul></div>

      <div class="fetchbox" style="border-left-color:var(--amber)"><b>Auditor's checklist.</b> To verify any number end-to-end: (1) re-hit the endpoint URL and confirm the same OHLC series comes back, (2) apply the formula from the metric table above, (3) cross-check the balance-sheet inputs against the primary-source citation. The framework code lives under <code>utils/</code>; the stock-specific data (drivers, ranges, endpoints, primary sources) lives under <code>stocks/config.py</code>. Re-running <code>python refresh_all.py</code> from the project root regenerates every computed value from a fresh Yahoo fetch.</div>
    </section>
"""


def patch(name: str) -> str:
    cfg = STOCKS[name]
    path = html_path(cfg)
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    if '.audit{margin-top:24px' not in html:
        head_close = html.find('</head>')
        if head_close != -1:
            html = html[:head_close] + f'<style>{APPENDIX_CSS}</style>\n' + html[head_close:]

    frag = render_appendix(name)
    if 'id="mAudit"' in html:
        html = re.sub(r'\s*<section class="audit" id="mAudit">.*?</section>\s*', '\n' + frag + '\n', html, count=1, flags=re.S)
    else:
        m = re.search(r'<footer>', html)
        if m:
            html = html[:m.start()] + frag + '\n\n  ' + html[m.start():]
        else:
            html = re.sub(r'(</div>\s*<script>)', frag + r'\n\n\1', html, count=1)

    # Stepper link (idempotent)
    if '<a href="#mAudit">' not in html:
        html = re.sub(
            r'(<a href="#mSum"[^>]*>[^<]*<span[^>]*>[\u2211][^<]*</span>[^<]*</a>)',
            r'\1\n    <a href="#mAudit"><span class="n">§</span>Audit</a>',
            html, count=1,
        )

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return f"OK — {cfg['html_file']}: audit appendix updated ({len(cfg['endpoints'])} endpoints, {len(cfg['primary_sources'])} sources, {len(FORMULAS)} formulas, {len(METHODOLOGY_REFS)} refs)"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    for n in all_names():
        print(patch(n))
    print(f"\nAppendix built {BUILD_DT}")


if __name__ == "__main__":
    main()
