"""Generic price + Monte-Carlo + asymmetry analytics.

Reads stock-specific configuration from ``stocks.config`` and never contains
per-stock values. Every downstream module in ``utils`` uses only the functions
here plus the STOCKS registry.
"""
from __future__ import annotations
import os, sys, json, math, time, urllib.request, random, datetime
from typing import Callable, Iterable

# Make the sibling stocks/ package importable no matter where this is invoked from
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from stocks.config import STOCKS, all_names, DATA_PROVIDER_NOTES  # noqa: E402

# Cache directory lives at the project root so all runs share it
CACHE = os.path.join(_ROOT, "cache")
os.makedirs(CACHE, exist_ok=True)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


# -------------------- Yahoo v8 chart fetch --------------------

# Cached payloads older than this are re-fetched, so a plain `refresh_all` run
# actually refreshes prices instead of silently re-serving last week's cache
# (override with STOCK_CACHE_MAX_AGE_H; --clear-cache still forces a full wipe).
CACHE_MAX_AGE_H = float(os.environ.get("STOCK_CACHE_MAX_AGE_H", "24"))


def _valid_chart(data: dict) -> bool:
    try:
        res = data["chart"]["result"][0]
        return bool(res["timestamp"]) and bool(res["indicators"]["quote"][0]["close"])
    except (KeyError, IndexError, TypeError):
        return False


def fetch_chart(symbol: str, rng: str = "5y") -> dict:
    """Fetch OHLC from Yahoo v8 chart API and cache on disk (24h TTL).

    A stale-but-valid cache is used as a fallback if the refetch fails, so an
    offline run degrades gracefully instead of crashing mid-build."""
    fname = os.path.join(CACHE, f"{symbol.replace('^', '_')}_{rng}.json")
    cached_ok = os.path.exists(fname) and os.path.getsize(fname) > 1000
    if cached_ok and (time.time() - os.path.getmtime(fname)) < CACHE_MAX_AGE_H * 3600:
        with open(fname, "r", encoding="utf-8") as f:
            return json.load(f)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={rng}&interval=1d"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            raw = r.read().decode("utf-8")
        data = json.loads(raw)
        if not _valid_chart(data):
            raise ValueError(f"Yahoo returned no usable series for {symbol}")
        with open(fname, "w", encoding="utf-8") as f:
            f.write(raw)
        return data
    except Exception as e:
        if cached_ok:
            print(f"[warn] {symbol}: refetch failed ({e}); using cached copy from "
                  f"{datetime.date.fromtimestamp(os.path.getmtime(fname))}")
            with open(fname, "r", encoding="utf-8") as f:
                return json.load(f)
        raise


def series(chart_json: dict):
    res = chart_json["chart"]["result"][0]
    ts = res["timestamp"]
    q = res["indicators"]["quote"][0]
    close = q["close"]
    adj = (res["indicators"].get("adjclose") or [{}])[0].get("adjclose")
    px = adj if adj else close
    t2, p2 = [], []
    for a, b in zip(ts, px):
        if b is None:
            continue
        t2.append(a); p2.append(b)
    return t2, p2


# -------------------- Return-series statistics --------------------

def log_returns(px: list[float]) -> list[float]:
    return [math.log(px[i] / px[i - 1]) for i in range(1, len(px)) if px[i - 1] > 0 and px[i] > 0]


def realised_vol_annual(rets: list[float], k: int = 252):
    if len(rets) < 2:
        return None
    m = sum(rets) / len(rets)
    v = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(v * k)


def max_drawdown(px: list[float]) -> float:
    peak = px[0]; mdd = 0.0
    for p in px:
        peak = max(peak, p)
        mdd = min(mdd, p / peak - 1)
    return mdd


def rolling_return(px: list[float], days: int):
    if len(px) <= days:
        return None
    return px[-1] / px[-1 - days] - 1


def percentile(x: float, xs: list[float]):
    if not xs:
        return None
    below = sum(1 for v in xs if v <= x)
    return below / len(xs)


def beta_and_r2(y: list[float], x: list[float]):
    n = len(y)
    if n < 30:
        return None, None
    mx = sum(x) / n; my = sum(y) / n
    sxx = sum((xi - mx) ** 2 for xi in x)
    sxy = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    syy = sum((yi - my) ** 2 for yi in y)
    if sxx <= 0:
        return None, None
    beta = sxy / sxx
    alpha = my - beta * mx
    ss_res = sum((yi - (alpha + beta * xi)) ** 2 for xi, yi in zip(x, y))
    r2 = 1 - ss_res / syy if syy > 0 else None
    return beta, r2


# -------------------- Correlated Monte-Carlo --------------------

def _randn_pair(rng: random.Random):
    u = max(rng.random(), 1e-16); v = rng.random()
    return (math.sqrt(-2 * math.log(u)) * math.cos(2 * math.pi * v),
            math.sqrt(-2 * math.log(u)) * math.sin(2 * math.pi * v))


def _phi(x: float) -> float:
    t = 1 / (1 + 0.2316419 * abs(x))
    d = 0.3989423 * math.exp(-x * x / 2)
    p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))))
    return 1 - p if x > 0 else p


def _tri_inv(u: float, a: float, m: float, b: float) -> float:
    c = (m - a) / (b - a) if b > a else 0.5
    if u < c:
        return a + math.sqrt(max(0, u * (b - a) * (m - a)))
    return b - math.sqrt(max(0, (1 - u) * (b - a) * (b - m)))


def mc_engine(drivers: dict, formula: Callable[[dict], float],
              corr: float = 0.60, tail: float = 0.06, n: int = 20000, seed: int = 1234) -> list[float]:
    """Correlated Monte-Carlo using a one-factor copula and a regime-shock mixture."""
    rng = random.Random(seed)
    keys = list(drivers.keys())
    rhos = [drivers[k]["rho"] for k in keys]
    fv = [0.0] * n
    for i in range(n):
        z1, _ = _randn_pair(rng)
        Z = z1
        if tail > 0 and rng.random() < tail:
            Z = z1 * 2.0 - 0.4
        draws = {}
        for k, rho in zip(keys, rhos):
            L = corr * rho
            e = _randn_pair(rng)[0]
            nn = L * Z + math.sqrt(max(0, 1 - L * L)) * e
            u = _phi(nn)
            d = drivers[k]
            draws[k] = _tri_inv(u, d["lo"], d["md"], d["hi"])
        fv[i] = formula(draws)
    fv.sort()
    return fv


def qtile(a: list[float], q: float):
    if not a:
        return None
    i = min(len(a) - 1, max(0, int(q * len(a))))
    return a[i]


def asymmetry_and_kelly(fv: list[float], price: float) -> dict:
    """Payoff-asymmetry ratio, Kelly f*, VaR & CVaR from an MC fair-value distribution."""
    ups = [f - price for f in fv if f > price]
    dns = [price - f for f in fv if f < price]
    n = len(fv)
    p_up = len(ups) / n if n else 0.5
    p_dn = 1 - p_up
    e_up = sum(ups) / len(ups) if ups else 0
    e_dn = sum(dns) / len(dns) if dns else 1e-9
    b = e_up / e_dn if e_dn > 0 else 0
    asym = (p_up * e_up) / (p_dn * e_dn) if (p_dn * e_dn) > 0 else float("inf")
    kelly = (b * p_up - p_dn) / b if b > 0 else -1.0
    losses_pct = sorted([f / price - 1 for f in fv])
    var10 = losses_pct[int(0.10 * n)]
    var05 = losses_pct[int(0.05 * n)]
    cvar10 = sum(losses_pct[:int(0.10 * n)]) / max(1, int(0.10 * n))
    cvar05 = sum(losses_pct[:int(0.05 * n)]) / max(1, int(0.05 * n))
    e_ret = sum(f / price - 1 for f in fv) / n
    return {
        "p_up": p_up, "p_dn": p_dn,
        "e_up_eur": e_up, "e_dn_eur": e_dn,
        "b_ratio": b, "asymmetry": asym, "kelly": kelly,
        "expected_return": e_ret,
        "var10": var10, "var05": var05,
        "cvar10": cvar10, "cvar05": cvar05,
        "median": qtile(fv, 0.5), "p10": qtile(fv, 0.10), "p90": qtile(fv, 0.90),
    }


# -------------------- Per-stock helpers driven by STOCKS registry --------------------

def run_mc(name: str, corr: float = 0.60, tail: float = 0.06) -> list[float]:
    """Runs the stock's declared engine over its declared driver ranges."""
    cfg = STOCKS[name]
    return mc_engine(cfg["drivers"], cfg["engine"], corr=corr, tail=tail)


def reverse_dcf(name: str, price: float, steps: int = 80) -> dict:
    """Grid-solve the stock's `reverse_dcf_target` driver for the value that
    reconciles the engine output — every other driver held at its mode — to
    the current price. `saturated` flags a solve that pinned to the modelled
    range boundary, i.e. the true implied value lies beyond the grid."""
    cfg = STOCKS[name]
    tgt = cfg["reverse_dcf_target"]
    driver = cfg["drivers"][tgt]
    lo, hi = driver["lo"], driver["hi"]
    mode_draw = {k: v["md"] for k, v in cfg["drivers"].items()}
    best = None
    engine = cfg["engine"]
    for i in range(steps + 1):
        x = lo + i * (hi - lo) / steps
        d = dict(mode_draw); d[tgt] = x
        f = engine(d)
        if best is None or abs(f - price) < abs(best[1] - price):
            best = (x, f, i)
    saturated = None
    if best[2] in (0, steps) and price > 0 and abs(best[1] - price) / price > 0.005:
        saturated = "hi" if best[2] == steps else "lo"
    return {
        "driver": cfg["reverse_dcf_label"],
        "unit":   cfg["reverse_dcf_unit"],
        "target": tgt,
        "implied": best[0],
        "at_mode": best[1],
        "mode_value": driver["md"],
        "range": (lo, hi),
        "saturated": saturated,
    }


# -------------------- Convenience CLI --------------------

def _print_summary(name: str) -> None:
    cfg = STOCKS[name]
    cur = cfg.get("currency", "€")
    chart = fetch_chart(cfg["ticker"], "5y")
    _, px = series(chart)
    spot = chart["chart"]["result"][0]["meta"].get("regularMarketPrice") or px[-1]
    fv = run_mc(name)
    ak = asymmetry_and_kelly(fv, spot)
    rd = reverse_dcf(name, spot)
    print(f"--- {name.upper()}  ({cfg['ticker']}) ---")
    print(f"  Live spot = {cur}{spot:.2f}   MC median = {cur}{ak['median']:.2f}   P10={cur}{ak['p10']:.2f}  P90={cur}{ak['p90']:.2f}")
    print(f"  Kelly f*  = {ak['kelly']*100:+.1f}%   Payoff asymm. = {ak['asymmetry']:.2f}×   E[return] = {ak['expected_return']*100:+.1f}%")
    print(f"  CVaR(10%) = {ak['cvar10']*100:.1f}%   CVaR(5%) = {ak['cvar05']*100:.1f}%")
    print(f"  Reverse-DCF: market implies {rd['driver']} = {rd['implied']:.2f}{rd['unit']}  (mode {rd['mode_value']}{rd['unit']})")
    print()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    for n in all_names():
        _print_summary(n)


if __name__ == "__main__":
    main()
