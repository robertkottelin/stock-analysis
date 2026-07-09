"""Injects/updates Module I (Price Asymmetry Layer) and Module J
(Base Rates & Factor Composite) inside each stock's HTML report.

Idempotent — safe to re-run.
"""
from __future__ import annotations
import os, re, sys, math, datetime

from paths import STOCKS_DIR, html_path
from analytics import (
    STOCKS, all_names, fetch_chart, series, log_returns, realised_vol_annual,
    max_drawdown, rolling_return, percentile, beta_and_r2,
    run_mc, asymmetry_and_kelly, reverse_dcf,
)


# -------------------- CSS additions --------------------

CSS_ADDITIONS = """
<style>
  /* Additions for Modules I (asymmetry) and J (base rates) */
  .kg{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:14px 0}
  @media(max-width:780px){.kg{grid-template-columns:repeat(2,1fr)}}
  .kg .kgi{background:var(--surface-2);border:1px solid var(--line);border-radius:11px;padding:11px 13px}
  .kg .kgi .k{font-family:var(--mono);font-size:9.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--faint)}
  .kg .kgi .v{font-family:var(--mono);font-weight:600;font-size:16px;margin-top:3px;line-height:1.15;color:var(--ink)}
  .kg .kgi .v small{font-size:11px;font-weight:400;color:var(--muted);margin-left:4px}
  .kg .kgi.pos .v{color:var(--teal-deep)} .kg .kgi.neg .v{color:var(--coral-deep)}
  .rev{border:1px dashed var(--line-strong);border-radius:12px;padding:14px 16px;background:var(--surface-2);margin-top:14px}
  .rev .rt{font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--blue-deep);font-weight:600;margin-bottom:6px}
  .rev .rv{display:flex;flex-wrap:wrap;gap:14px;align-items:baseline;margin-top:6px}
  .rev .rv .n{font-family:var(--disp);font-size:22px;font-weight:600;color:var(--blue-deep)}
  .rev .rv .n.pos{color:var(--teal-deep)} .rev .rv .n.neg{color:var(--coral-deep)}
  .rev .rv .l{font-size:13px;color:var(--ink)} .rev .rv .l b{color:var(--ink)}
  .rev .rv .m{font-family:var(--mono);font-size:11px;color:var(--muted)}
  .kelly{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:10px;margin-top:12px}
  @media(max-width:680px){.kelly{grid-template-columns:1fr 1fr}}
  .kbox{background:var(--surface);border:1px solid var(--line);border-radius:11px;padding:13px 15px}
  .kbox.hot{border:1.5px solid var(--coral)}
  .kbox.good{border:1.5px solid var(--teal)}
  .kbox .t{font-family:var(--mono);font-size:10px;letter-spacing:.05em;text-transform:uppercase;color:var(--faint)}
  .kbox .n{font-family:var(--disp);font-size:22px;font-weight:600;margin-top:3px;line-height:1.05}
  .kbox .d{font-size:11.5px;color:var(--muted);margin-top:4px;line-height:1.4}
  .kbox .n.pos{color:var(--teal-deep)} .kbox .n.neg{color:var(--coral-deep)}
  .brtab{width:100%;border-collapse:collapse;margin-top:10px;font-size:12.5px}
  .brtab th{text-align:left;font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--faint);padding:6px 8px;border-bottom:1px solid var(--line-strong)}
  .brtab td{padding:6px 8px;border-bottom:1px dashed var(--line);vertical-align:top}
  .brtab td.num{font-family:var(--mono);text-align:right;font-weight:500}
  .brtab td.cur{background:var(--teal-wash)}
  .brtab td.now{font-family:var(--mono);color:var(--teal-deep);font-weight:600}
  .cbar{position:relative;height:16px;background:var(--surface-2);border-radius:8px;overflow:hidden;margin-top:6px;border:1px solid var(--line)}
  .cbar .fl{position:absolute;top:0;bottom:0;background:linear-gradient(90deg,var(--coral) 0%,var(--amber) 50%,var(--teal) 100%);opacity:.28}
  .cbar .mk{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--ink)}
  .cbar .lb{position:absolute;top:100%;font-family:var(--mono);font-size:9.5px;color:var(--muted);margin-top:2px;transform:translateX(-50%);white-space:nowrap}
  .fac{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:12px}
  @media(max-width:780px){.fac{grid-template-columns:repeat(2,1fr)}}
  .fac .fi{background:var(--surface);border:1px solid var(--line);border-radius:11px;padding:12px}
  .fac .fi.hot{background:var(--teal-wash);border-color:var(--teal)}
  .fac .fi .fk{font-family:var(--mono);font-size:9.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--faint)}
  .fac .fi .fv{font-family:var(--disp);font-size:20px;font-weight:600;margin-top:4px}
  .fac .fi .fd{font-size:11px;color:var(--muted);margin-top:3px;line-height:1.35}
  .barsrow{display:grid;grid-template-columns:120px 1fr 60px;gap:8px;font-size:12px;padding:4px 0;align-items:center}
  .barsrow .bl{color:var(--muted);font-family:var(--mono);font-size:10.5px}
  .barsrow .bb{position:relative;height:12px;background:var(--surface-2);border-radius:6px;overflow:hidden;border:1px solid var(--line)}
  .barsrow .bb .bi{position:absolute;top:0;bottom:0;background:var(--blue);opacity:.65}
  .barsrow .bv{font-family:var(--mono);text-align:right;font-weight:600}
</style>
"""


IMPLIED_INFL = 2.0   # Bond real-rate proxy


def _fmt_pct(x, dp=1, sign=False):
    if x is None: return "n/a"
    return (f"{{:{'+' if sign else ''}.{dp}f}}%").format(x * 100)


def _fmt_num(x, dp=1, sign=False):
    if x is None: return "n/a"
    return (f"{{:{'+' if sign else ''}.{dp}f}}").format(x)


def verdict_from_metrics(kelly, asym, price_pct, rdcf_gap, pt_gap, mom12):
    """BULL / MIXED / BEAR verdict from Module I composite signals."""
    score = 0
    if kelly is not None:
        if   kelly >  0.15: score += 2
        elif kelly >  0.0:  score += 1
        elif kelly > -0.15: score -= 1
        else:               score -= 2
    if asym is not None:
        if   asym > 1.5: score += 1
        elif asym < 0.7: score -= 1
    if price_pct is not None:
        if   price_pct > 0.85: score -= 1
        elif price_pct < 0.30: score += 1
    if rdcf_gap is not None:
        if   rdcf_gap < -0.05: score += 1
        elif rdcf_gap >  0.10: score -= 1
    if pt_gap is not None:
        if   pt_gap >  0.15: score += 1
        elif pt_gap < -0.05: score -= 1
    if mom12 is not None:
        if   mom12 < -0.15: score += 1
        elif mom12 >  0.50: score -= 1
    if score >=  3: return "bull", "BULL"
    if score <= -3: return "bear", "BEAR"
    return "mixed", "MIXED"


def gather(name: str) -> dict:
    """Fetch prices, run engines, and return every number needed for I & J."""
    cfg = STOCKS[name]
    chart = fetch_chart(cfg["ticker"], "5y")
    ts, px = series(chart)
    meta = chart["chart"]["result"][0]["meta"]
    spot = meta.get("regularMarketPrice") or px[-1]
    hi52 = meta.get("fiftyTwoWeekHigh") or max(px); lo52 = meta.get("fiftyTwoWeekLow") or min(px)
    n_days = len(px)

    rets = log_returns(px)
    # Honour the framework's stated design intent: report n/a when the tape is
    # shorter than the metric window, rather than backfilling on the short
    # sample. Momentum and betas already do this — vol did not.
    vol1y = realised_vol_annual(rets[-252:]) if len(rets) >= 252 else None
    vol3y = realised_vol_annual(rets[-756:]) if len(rets) >= 756 else None
    mom_1m  = rolling_return(px, 21)
    mom_3m  = rolling_return(px, 63)
    mom_6m  = rolling_return(px, 126)
    mom_12m = rolling_return(px, 252)
    mdd = max_drawdown(px)
    price_pct = percentile(spot, px)

    def _beta_to(bts, bret):
        # Align by UTC-date rather than raw Unix timestamp — different markets
        # (FX vs equity vs commodity vs rates) close at different hours, so
        # exact-timestamp matching returns zero rows across those pairs even
        # though every trading day lines up perfectly on the calendar.
        m = {}
        for t, r in zip(bts[1:], bret):
            m[datetime.date.fromtimestamp(t)] = r
        yy, xx = [], []
        for t, r in zip(ts[1:], rets):
            d = datetime.date.fromtimestamp(t)
            if d in m:
                yy.append(r); xx.append(m[d])
        if len(yy) < 60: return None, None
        return beta_and_r2(yy[-252:], xx[-252:])

    b1_tkr = cfg.get("bench1_ticker", "^OMXH25"); b1_lab = cfg.get("bench1_label", "OMX Helsinki 25")
    b2_tkr = cfg.get("bench2_ticker", "^STOXX");  b2_lab = cfg.get("bench2_label", "STOXX 600")
    omx = fetch_chart(b1_tkr, "5y"); omx_ts, omx_px = series(omx); omx_ret = log_returns(omx_px)
    st  = fetch_chart(b2_tkr, "5y"); st_ts,  st_px  = series(st);  st_ret  = log_returns(st_px)
    beta_omx, r2_omx = _beta_to(omx_ts, omx_ret)
    beta_st,  r2_st  = _beta_to(st_ts,  st_ret)

    beta_m = r2_m = None
    macro_label = cfg.get("macro_label")
    if cfg.get("macro_ticker"):
        mc = fetch_chart(cfg["macro_ticker"], "5y")
        mt, mp = series(mc); mr = log_returns(mp)
        beta_m, r2_m = _beta_to(mt, mr)

    tnx = fetch_chart("^TNX", "1mo")
    _, tnx_px = series(tnx)
    real_rate_pct = tnx_px[-1] - IMPLIED_INFL

    peer_rel = {}
    for p in cfg.get("peers", []):
        try:
            pc = fetch_chart(p, "2y")
            _, ppx = series(pc)
            if len(ppx) > 252 and mom_12m is not None:
                peer_rel[p] = mom_12m - (ppx[-1] / ppx[-253] - 1)
        except Exception:
            peer_rel[p] = None

    fv = run_mc(name, spot)
    ak = asymmetry_and_kelly(fv, spot)
    rd = reverse_dcf(name, spot)

    rdcf_gap = (rd["implied"] - rd["mode_value"]) / rd["mode_value"] if rd["mode_value"] else None
    if cfg.get("reverse_dcf_invert_sign") and rdcf_gap is not None:
        rdcf_gap = -rdcf_gap

    pt_gap = (cfg["consensus_pt"] / spot) - 1

    quarterly_returns = [px[i]/px[i-63] - 1 for i in range(63, len(px))]
    frac_q_down = sum(1 for r in quarterly_returns if r < -0.10) / len(quarterly_returns) if quarterly_returns else None
    annual_returns = [px[i]/px[i-252] - 1 for i in range(252, len(px))]
    frac_y_down = sum(1 for r in annual_returns if r < 0)      / len(annual_returns) if annual_returns else None
    frac_y_gt15 = sum(1 for r in annual_returns if r > 0.15)  / len(annual_returns) if annual_returns else None

    oe = cfg["oe_anchor_m"]
    mcap = spot * cfg["shares_m"]
    oe_yield = oe / mcap
    real_spread_bp = (oe_yield - real_rate_pct / 100) * 10000

    value_score = 1 - price_pct if price_pct is not None else 0.5
    quality_score = cfg["quality_score"]
    m121 = (mom_12m - mom_1m) if (mom_12m is not None and mom_1m is not None) else 0
    momentum_score = 1 / (1 + math.exp(-3 * m121)) if (mom_12m is not None and mom_1m is not None) else 0.5
    # Neutral 0.5 when vol_1y is unavailable (short tape) — avoids falsely
    # scoring "no data" as "ideal low-volatility".
    lv_score = max(0, 1 - vol1y / 0.45) if vol1y is not None else 0.5
    composite = (value_score + quality_score + momentum_score + lv_score) / 4

    return {
        "name": name, "ticker": cfg["ticker"], "shares_m": cfg["shares_m"],
        "spot": spot, "hi52": hi52, "lo52": lo52, "n_days": n_days,
        "vol_1y": vol1y, "vol_3y": vol3y,
        "mom_1m": mom_1m, "mom_3m": mom_3m, "mom_6m": mom_6m, "mom_12m": mom_12m,
        "mdd": mdd, "price_pct": price_pct,
        "beta_omx": beta_omx, "r2_omx": r2_omx, "bench1_label": b1_lab, "bench1_ticker": b1_tkr,
        "beta_stoxx": beta_st, "r2_stoxx": r2_st, "bench2_label": b2_lab, "bench2_ticker": b2_tkr,
        "cur": cfg.get("currency", "\u20ac"),
        "beta_macro": beta_m, "r2_macro": r2_m, "macro_label": macro_label,
        "macro_ticker": cfg.get("macro_ticker"),
        "peer_rel": peer_rel,
        "mc_median": ak["median"], "mc_p10": ak["p10"], "mc_p90": ak["p90"],
        "p_up": ak["p_up"], "asymmetry": ak["asymmetry"], "b_ratio": ak["b_ratio"],
        "kelly": ak["kelly"], "expected_return": ak["expected_return"],
        "var10": ak["var10"], "cvar10": ak["cvar10"],
        "var05": ak["var05"], "cvar05": ak["cvar05"],
        "reverse_dcf": rd, "rdcf_gap": rdcf_gap,
        "pt_gap": pt_gap, "consensus_pt": cfg["consensus_pt"],
        "eps_ttm": cfg["eps_ttm"], "pe_ttm": (spot/cfg["eps_ttm"]) if cfg["eps_ttm"] else None,
        "frac_q_down_10": frac_q_down, "frac_y_down": frac_y_down, "frac_y_gt15": frac_y_gt15,
        "oe_m": oe, "mcap_m": mcap, "oe_yield": oe_yield,
        "real_rate_pct": real_rate_pct, "real_spread_bp": real_spread_bp,
        "value_score": value_score, "quality_score": quality_score,
        "momentum_score": momentum_score, "lv_score": lv_score,
        "composite": composite,
        "build_date": datetime.date.today().isoformat(),
    }


def render_module_I(m: dict) -> str:
    cur = m.get("cur", "\u20ac")
    v, v_txt = verdict_from_metrics(m["kelly"], m["asymmetry"], m["price_pct"], m["rdcf_gap"], m["pt_gap"], m["mom_12m"])
    kelly_cls = "good" if m["kelly"] and m["kelly"] > 0 else "hot"
    asym_cls  = "good" if m["asymmetry"] and m["asymmetry"] > 1 else "hot"
    rdcf = m["reverse_dcf"]
    rdcf_direction = "below" if m["rdcf_gap"] and m["rdcf_gap"] < 0 else "above"
    rdcf_dir_class = "pos" if m["rdcf_gap"] and m["rdcf_gap"] < 0 else "neg"

    kelly_pct = m["kelly"] * 100 if m["kelly"] is not None else 0
    kelly_show = f"{kelly_pct:+.1f}%"
    asym_show = f"{m['asymmetry']:.2f}×" if m["asymmetry"] is not None else "n/a"
    b_show = f"{m['b_ratio']:.2f}" if m['b_ratio'] is not None else "n/a"
    rdcf_gap_show = f"{m['rdcf_gap']*100:+.1f}%" if m['rdcf_gap'] is not None else "n/a"

    peer_rows = ""
    for p, rel in (m["peer_rel"] or {}).items():
        if rel is None: continue
        peer_rows += (
            f'<div class="barsrow"><div class="bl">vs {p}</div>'
            f'<div class="bb"><div class="bi" style="left:50%;width:{min(45,abs(rel)*100):.1f}%;'
            f'{"transform:translateX(-100%);" if rel<0 else ""}background:{"var(--teal)" if rel>0 else "var(--coral)"}"></div></div>'
            f'<div class="bv">{rel*100:+.1f}%</div></div>'
        )

    macro_row = ""
    if m["beta_macro"] is not None:
        macro_row = f'<tr><td>Beta vs {m["macro_label"]}</td><td class="num">{m["beta_macro"]:.2f}</td><td>R² = {m["r2_macro"]:.2f}. 252-day OLS on daily log-returns.</td></tr>'

    verdict_text = {
        "bull": "The distribution, own-history and reverse-DCF all point to a favourable pay-off — a positive asymmetry the market has not fully priced.",
        "bear": "The composite metrics flag a negative pay-off asymmetry — expected loss dominates expected gain, and the market is already pricing above-base assumptions.",
        "mixed": "The pay-off distribution is broadly symmetric to price — no institutional edge without additional evidence.",
    }[v]

    # Note text about the reverse-DCF driver
    macro_source_note = f", {m['macro_ticker']}" if m.get('macro_ticker') else ""

    return f"""
  <section class="mod" id="mI">
    <div class="mod-head"><div class="mod-no">I</div>
      <div class="ht"><h2>Price-asymmetry layer — the institutional edge check</h2><div class="hq">Reverse-DCF · payoff asymmetry · Kelly · CVaR · own-history percentile · live betas.</div></div>
      <span class="tagchip c">Computed from live &amp; sourced data</span>
    </div>
    <div class="verdict {v}"><span class="vchip">{v_txt}</span><span class="vtext">{verdict_text} Live spot <b>{cur}{m['spot']:.2f}</b> · MC median <b>{cur}{m['mc_median']:.2f}</b> (P10 {cur}{m['mc_p10']:.2f}, P90 {cur}{m['mc_p90']:.2f}) · P(FV &gt; price) <b>{m['p_up']*100:.0f}%</b>.</span></div>

    <p class="body">The pipeline's own engine (Module A) is a distribution, not a point. This layer squeezes six institutional read-outs from that distribution and from real fetched price history so the buy/sell asymmetry becomes visible at a glance. Every number here is either <b>sourced</b> (Yahoo v8 chart API at build time, {m['build_date']}) or <b>computed</b> from those inputs and the pipeline's own MC. No assumptions were added.</p>

    <div class="kg">
      <div class="kgi"><div class="k">Live spot ({m['ticker']})</div><div class="v">{cur}{m['spot']:.2f} <small>as of {m['build_date']}</small></div></div>
      <div class="kgi"><div class="k">52-week range</div><div class="v">{cur}{m['lo52']:.2f}–{cur}{m['hi52']:.2f}</div></div>
      <div class="kgi{' pos' if (m['price_pct'] or 0) < 0.4 else (' neg' if (m['price_pct'] or 0) > 0.85 else '')}"><div class="k">Price percentile · own 5y</div><div class="v">{m['price_pct']*100:.0f}%</div></div>
      <div class="kgi"><div class="k">Consensus PT gap</div><div class="v">{m['pt_gap']*100:+.1f}% <small>PT {cur}{m['consensus_pt']:.2f}</small></div></div>
    </div>

    <div class="rev">
      <div class="rt">◆ Reverse-DCF — what is the market implying today?</div>
      <div class="rv">
        <div class="n {rdcf_dir_class}">{rdcf['implied']:.2f}{rdcf['unit']}</div>
        <div class="l">is the value of <b>{rdcf['driver']}</b> that reconciles the median MC fair value to today's <b>{cur}{m['spot']:.2f}</b> price. That is <b>{rdcf_gap_show} {rdcf_direction}</b> the pipeline's base-case mode of <b>{rdcf['mode_value']}{rdcf['unit']}</b>.</div>
      </div>
      <div class="rv" style="margin-top:4px"><div class="m">Solved by holding every other driver at its pipeline mode and iterating the master-driver grid — an implied-expectations read, in the Mauboussin/Baupost sense. Buy when this implied value is lower than the base you underwrite; sell when it is higher.</div></div>
    </div>

    <p class="body" style="margin-top:16px"><b>Pay-off distribution — from the pipeline's own MC (20,000 paths, live spot).</b> The distribution tells us how the up-side compares to the down-side in probability-weighted euros — the true "buy/sell asymmetry" a hedge fund would grade.</p>
    <div class="kelly">
      <div class="kbox {kelly_cls}"><div class="t">Kelly f* — optimal sizing</div><div class="n {'pos' if kelly_pct>0 else 'neg'}">{kelly_show}</div><div class="d">Fraction of bank-roll a Kelly bettor would allocate <i>if</i> the MC engine were literally true. Positive = edge exists; negative = the market's price is dominant. Half-Kelly is the institutional rule of thumb.</div></div>
      <div class="kbox {asym_cls}"><div class="t">Payoff asymmetry</div><div class="n {'pos' if (m['asymmetry'] or 0)>1 else 'neg'}">{asym_show}</div><div class="d">(P<sub>up</sub> × E[gain]) ÷ (P<sub>dn</sub> × E[loss]). &gt; 1× = pay-off skew in your favour.</div></div>
      <div class="kbox"><div class="t">Win / loss ratio</div><div class="n">{b_show}</div><div class="d">E[gain | fv &gt; price] ÷ E[loss | fv &lt; price], in {cur}.</div></div>
      <div class="kbox"><div class="t">E[return to FV]</div><div class="n {'pos' if (m['expected_return'] or 0)>0 else 'neg'}">{m['expected_return']*100:+.1f}%</div><div class="d">Simple mean of (fv/price − 1) across all paths.</div></div>
    </div>

    <p class="body" style="margin-top:16px"><b>Downside quantification — VaR and CVaR (Expected Shortfall) from the same MC.</b> A regulator-grade risk read that the pipeline's original P10 alone doesn't give you.</p>
    <div class="kelly">
      <div class="kbox"><div class="t">VaR<sub>10%</sub> (loss threshold)</div><div class="n neg">{m['var10']*100:.1f}%</div><div class="d">10% of MC paths lose at least this much versus price.</div></div>
      <div class="kbox"><div class="t">CVaR<sub>10%</sub> (Expected Shortfall)</div><div class="n neg">{m['cvar10']*100:.1f}%</div><div class="d">Average loss in the worst 10% of paths — the tail you actually eat.</div></div>
      <div class="kbox"><div class="t">VaR<sub>5%</sub></div><div class="n neg">{m['var05']*100:.1f}%</div><div class="d">Deep-tail loss threshold.</div></div>
      <div class="kbox"><div class="t">CVaR<sub>5%</sub></div><div class="n neg">{m['cvar05']*100:.1f}%</div><div class="d">Average loss in the worst 5% of paths.</div></div>
    </div>

    <p class="body" style="margin-top:16px"><b>Realised risk &amp; factor exposure — from fetched daily price history ({m['n_days']} sessions available).</b> The regressions the earlier version cut "because we couldn't download prices" — now computed.{" <b>Note:</b> the listing history is shorter than the metric windows — cells report n/a rather than a backfilled guess, and fill in automatically on future re-runs as the tape accrues." if m['n_days'] < 260 else ""}</p>
    <table class="brtab">
      <thead><tr><th>Signal</th><th style="text-align:right">Reading</th><th>Interpretation</th></tr></thead>
      <tbody>
        <tr><td>Realised volatility 1y (ann.)</td><td class="num">{_fmt_pct(m['vol_1y'])}</td><td>SD of daily log-returns × √252, trailing 252 sessions.</td></tr>
        <tr><td>Realised volatility 3y (ann.)</td><td class="num">{_fmt_pct(m['vol_3y'])}</td><td>Same, trailing 756 sessions — for regime comparison.</td></tr>
        <tr><td>Max drawdown ({'available history' if m['n_days'] < 260 else '5y'})</td><td class="num">{_fmt_pct(m['mdd'])}</td><td>Peak-to-trough on adjusted close.</td></tr>
        <tr><td>Momentum 1m / 3m / 6m / 12m</td><td class="num">{_fmt_pct(m['mom_1m'], sign=True)} / {_fmt_pct(m['mom_3m'], sign=True)} / {_fmt_pct(m['mom_6m'], sign=True)} / {_fmt_pct(m['mom_12m'], sign=True)}</td><td>Simple returns over trailing windows.</td></tr>
        <tr><td>Beta vs {m['bench1_label']}</td><td class="num">{_fmt_num(m['beta_omx'], 2)}</td><td>R² = {_fmt_num(m['r2_omx'], 2)}. 252-day OLS.</td></tr>
        <tr><td>Beta vs {m['bench2_label']}</td><td class="num">{_fmt_num(m['beta_stoxx'], 2)}</td><td>R² = {_fmt_num(m['r2_stoxx'], 2)}. 252-day OLS.</td></tr>
        {macro_row}
      </tbody>
    </table>

    { ('<p class="body" style="margin-top:16px"><b>Relative performance vs peers (12m).</b> Positive bar = outperformed on total return.</p><div>' + peer_rows + '</div>') if peer_rows else '' }

    <div class="note b"><b>How to read this module.</b> Use the Kelly f* and payoff asymmetry as a two-column decision matrix: both positive = the MC is telling you to lean in (size below Kelly, always); both negative = the MC is telling you the market has already reached — or over-shot — your base case. The reverse-DCF line above translates the same distribution into a concrete driver value ("is a {rdcf['driver']} of <b>{rdcf['implied']:.2f}{rdcf['unit']}</b> defensible?") so the buy/sell debate becomes a question about that single input, not the price. The VaR/CVaR block bounds the downside you have to be willing to absorb before the thesis is right.
      <div class="src">Sources: Yahoo Finance v8 chart API ({m['ticker']}, {m['bench1_ticker']}, {m['bench2_ticker']}{macro_source_note}) — fetched {m['build_date']}. MC engine identical to Module A; asymmetry, Kelly, CVaR and reverse-DCF computed from the same 20,000 paths.</div>
    </div>
  </section>
"""


def render_module_J(m: dict) -> str:
    cur = m.get("cur", "\u20ac")
    cfg = STOCKS[m["name"]]
    br = cfg["base_rates"]
    rows = ""
    values = [v for _, v, _ in br["series"]]
    lo, hi = min(values), max(values)
    for lab, val, note in br["series"]:
        is_cur = (val == br["current_value"])
        cls_attr = " class='cur'" if is_cur else ""
        num_cls = " now" if is_cur else ""
        rows += f'<tr{cls_attr}><td>{lab}</td><td class="num{num_cls}">{val:.2f}{br["unit"]}</td><td>{note}</td></tr>'
    span = hi - lo if hi > lo else 1
    pos = (br["current_value"] - lo) / span

    frac_q_show = _fmt_pct(m["frac_q_down_10"], 0) if m["frac_q_down_10"] is not None else "n/a"
    frac_y_show = _fmt_pct(m["frac_y_down"], 0) if m["frac_y_down"] is not None else "n/a"
    frac_gt15   = _fmt_pct(m["frac_y_gt15"], 0) if m["frac_y_gt15"] is not None else "n/a"

    comp_pct = m["composite"] * 100
    oe_cls = "pos" if m["real_spread_bp"] > 0 else "neg"

    v_j = "bull" if comp_pct > 65 else ("bear" if comp_pct < 40 else "mixed")
    v_j_txt = v_j.upper()

    return f"""
  <section class="mod" id="mJ">
    <div class="mod-head"><div class="mod-no">J</div>
      <div class="ht"><h2>Base rates &amp; factor composite — the empirical anchor</h2><div class="hq">Own-history distribution of the master variable · return base-rates from 5y prices · V/Q/M/L factor score · owner-earnings yield vs real rate.</div></div>
      <span class="tagchip a">Sourced + computed</span>
    </div>
    <div class="verdict {v_j}"><span class="vchip">{v_j_txt}</span><span class="vtext">Composite <b>{comp_pct:.0f}/100</b> across value, quality, momentum and low-vol factors. Base-rate anchor: current master variable is at the {pos*100:.0f}<sup>th</sup> percentile of its multi-year range.</span></div>

    <p class="body">Mauboussin's rule: every point estimate should be checked against the base rate of the reference class. Here the reference classes are the company's own history for the master variable and the stock's own fetched return history for the pay-off distribution. Both are empirical, not assumed.</p>

    <div style="font-family:var(--mono);font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--blue-deep);font-weight:600;margin:16px 0 6px">◆ Reference class — {br['variable']} through the cycle</div>
    <table class="brtab">
      <thead><tr><th>Point</th><th style="text-align:right">Value</th><th>Note</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    <div class="cbar" style="margin-top:14px">
      <div class="fl" style="left:0;right:0"></div>
      <div class="mk" style="left:{pos*100:.1f}%"></div>
      <div class="lb" style="left:{pos*100:.1f}%">now · {br['current_label']}</div>
    </div>
    <div style="height:24px"></div>

    <p class="body" style="margin-top:8px"><b>Return base-rates — from fetched daily prices ({m['n_days']} sessions).</b> The empirical frequency of drawdowns and recoveries, not a scenario tree.</p>
    <div class="kg">
      <div class="kgi"><div class="k">P(quarterly drawdown &gt; 10%)</div><div class="v">{frac_q_show}</div></div>
      <div class="kgi"><div class="k">P(12m rolling return &lt; 0)</div><div class="v">{frac_y_show}</div></div>
      <div class="kgi"><div class="k">P(12m rolling return &gt; +15%)</div><div class="v">{frac_gt15}</div></div>
      <div class="kgi"><div class="k">Realised skew (crude)</div><div class="v">{'n/a' if (m['frac_y_gt15'] is None or m['frac_y_down'] is None) else ('positive' if m['frac_y_gt15'] > m['frac_y_down'] else 'negative')}</div></div>
    </div>

    <p class="body" style="margin-top:16px"><b>Owner-earnings yield vs real 10y — the cross-asset asymmetry check (Buffett/Munger).</b> If the stock's real cash yield exceeds the real risk-free, you are paid to wait even if fair value is uncertain.</p>
    <div class="rev">
      <div class="rt">◆ Owner-earnings spread</div>
      <div class="rv">
        <div class="n {oe_cls}">{m['real_spread_bp']:+.0f} bp</div>
        <div class="l"><b>Owner-earnings yield {m['oe_yield']*100:.2f}%</b> ({cur}{m['oe_m']:.0f}m ÷ {cur}{m['mcap_m']:.0f}m market cap) minus <b>real 10y ≈ {m['real_rate_pct']:.2f}%</b> (^TNX at build time minus a 2.0% implied inflation).</div>
      </div>
      <div class="rv" style="margin-top:4px"><div class="m">Positive spread = paid to hold the stock over the risk-free real yield. Owner earnings from pipeline Module D: {cfg['oe_note']}. ^TNX proxy is a US Treasury benchmark — a conservative substitute for Bund real yield, which is not reliably fetchable here. If you prefer the Bund view, subtract ~150 bp.</div></div>
    </div>

    <p class="body" style="margin-top:16px"><b>Multi-factor composite (V · Q · M · L).</b> AQR-style style-factor score, each scaled 0–1. Simple mean, no proprietary weights.</p>
    <div class="fac">
      <div class="fi{' hot' if m['value_score']>0.6 else ''}"><div class="fk">Value</div><div class="fv">{m['value_score']*100:.0f}</div><div class="fd">Inverse of price-percentile within own 5y — cheap in own history.</div></div>
      <div class="fi{' hot' if m['quality_score']>0.6 else ''}"><div class="fk">Quality</div><div class="fv">{m['quality_score']*100:.0f}</div><div class="fd">Aggregated from Module D forensic scores (Piotroski / Altman / ROCE / coverage).</div></div>
      <div class="fi{' hot' if m['momentum_score']>0.6 else ''}"><div class="fk">Momentum</div><div class="fv">{m['momentum_score']*100:.0f}</div><div class="fd">12-1m return, logistic-scaled. Captures the classic Jegadeesh-Titman signal.</div></div>
      <div class="fi{' hot' if m['lv_score']>0.6 else ''}"><div class="fk">Low-vol</div><div class="fv">{m['lv_score']*100:.0f}</div><div class="fd">1 − realised 1y vol / 45%. Low-vol has been an outperforming factor in Nordics.</div></div>
      <div class="fi{' hot' if m['composite']>0.6 else ''}" style="border:1.5px solid var(--blue)"><div class="fk">Composite</div><div class="fv">{comp_pct:.0f}</div><div class="fd">Simple mean of the four. &gt;65 = broadly favourable factor stack.</div></div>
    </div>

    <div class="note c"><b>How to read this module.</b> The reference-class table answers "how unusual is today?" and the base-rate frequencies answer "how often does this stock lose 10% in a quarter, or spend a year in the red?" The owner-earnings spread is the cross-asset asymmetry — you are paid <b>{m['real_spread_bp']:+.0f} bp</b> in real cash yield over the risk-free rate for holding this business. The factor composite is the systematic-style read of the same evidence; a high composite plus a positive owner-earnings spread plus a favourable Module-I asymmetry is the traditional trifecta hedge-fund PMs look for before sizing.
      <div class="src">Sources: pipeline Module A base-case ranges &amp; Module D forensics (sourced); Yahoo v8 chart API for prices and ^TNX; base-rates and factor scores computed from those inputs on {m['build_date']}.</div>
    </div>
  </section>
"""


def inject(name: str) -> str:
    cfg = STOCKS[name]
    path = html_path(cfg)
    m = gather(name)
    frag_I = render_module_I(m)
    frag_J = render_module_J(m)

    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    # CSS additions
    if ".kg{display:grid" not in html:
        head_close = html.find("</head>")
        if head_close != -1:
            html = html[:head_close] + CSS_ADDITIONS + "\n" + html[head_close:]

    # Modules I & J — replace if present, else insert before ∑ Scorecard
    marker = '<section class="mod" id="mSum">'
    idx = html.find(marker)
    if idx == -1:
        raise RuntimeError(f"Could not find scorecard marker in {path}")
    if 'id="mI"' in html:
        html = re.sub(r'\s*<section class="mod" id="mI">.*?</section>\s*', '\n\n  ', html, flags=re.S)
        html = re.sub(r'\s*<section class="mod" id="mJ">.*?</section>\s*', '\n\n  ', html, flags=re.S)
        idx = html.find(marker)
    html = html[:idx] + frag_I + "\n" + frag_J + "\n  " + html[idx:]

    # Stepper nav — idempotent
    if '<a href="#mI">' not in html:
        stepper_re = re.compile(r'(<a href="#mH"[^>]*>[^<]*<span[^>]*>H</span>[^<]*</a>)')
        if stepper_re.search(html):
            html = stepper_re.sub(
                r'\1\n    <a href="#mI"><span class="n">I</span>Asymmetry</a>\n    <a href="#mJ"><span class="n">J</span>Base rates</a>',
                html, count=1
            )
        else:
            html = re.sub(
                r'(<a href="#mSum">)',
                r'<a href="#mI"><span class="n">I</span>Asymmetry</a>\n    <a href="#mJ"><span class="n">J</span>Base rates</a>\n    \1',
                html, count=1
            )

    # Scorecard rows — idempotent (insert once, update every time thereafter)
    v_i, v_i_txt = verdict_from_metrics(m["kelly"], m["asymmetry"], m["price_pct"], m["rdcf_gap"], m["pt_gap"], m["mom_12m"])
    v_j = "bull" if m["composite"] > 0.65 else ("bear" if m["composite"] < 0.40 else "mixed")
    v_j_txt = v_j.upper()
    rdcf_gap_show = f"{m['rdcf_gap']*100:+.1f}%" if m['rdcf_gap'] is not None else "n/a"
    kelly_show = f"{m['kelly']*100:+.0f}%" if m['kelly'] is not None else "n/a"
    row_i = f'<tr><td>I · Asymmetry</td><td><span class="vchip {v_i}">{v_i_txt}</span></td><td>Kelly f* {kelly_show}, asymmetry {m["asymmetry"]:.2f}×, market implies {rdcf_gap_show} vs pipeline mode</td></tr>'
    row_j = f'<tr><td>J · Base rates</td><td><span class="vchip {v_j}">{v_j_txt}</span></td><td>Composite {m["composite"]*100:.0f}/100 · OE-yield spread {m["real_spread_bp"]:+.0f} bp real</td></tr>'
    if '<td>I · Asymmetry</td>' not in html:
        kill_row_re = re.compile(r'(<tr><td>H · Kill-criteria</td>.*?</tr>)', re.S)
        if kill_row_re.search(html):
            html = kill_row_re.sub(r'\1\n        ' + row_i + '\n        ' + row_j, html, count=1)
        else:
            html = re.sub(r'(<table class="scoretab">.*?</tbody>)',
                          lambda mo: mo.group(1).replace('</tbody>', row_i + row_j + '</tbody>'),
                          html, count=1, flags=re.S)
    else:
        html = re.sub(r'<tr><td>I · Asymmetry</td>.*?</tr>', row_i, html, count=1, flags=re.S)
        html = re.sub(r'<tr><td>J · Base rates</td>.*?</tr>', row_j, html, count=1, flags=re.S)

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return f"OK — {name}: Modules I+J updated. Kelly={kelly_show}, asymmetry={m['asymmetry']:.2f}×, composite={m['composite']*100:.0f}/100, I={v_i_txt}, J={v_j_txt}"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which == "all":
        for n in all_names():
            print(inject(n))
    else:
        if which not in STOCKS:
            print(f"Unknown target: {which}. Known: {list(STOCKS)}")
            sys.exit(1)
        print(inject(which))


if __name__ == "__main__":
    main()
