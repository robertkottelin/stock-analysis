"""Universe fundamentals screener — Nasdaq Helsinki + Stockholm, plus the S&P 500.

Fetches the full listed universe (Yahoo screener API for HEL/STO, the current
S&P 500 constituent list from Wikipedia for US names), then per-symbol
fundamentals from the v10 quoteSummary API (sector, industry, business summary,
margins, returns, growth, balance sheet, valuation), normalises money values to
EUR, and computes three ranking scores:

  fund_score  0-100  percentile composite: Quality 35 / Growth 20 /
                     Balance sheet 15 / Valuation 30
  ai_score    0-100  heuristic "AI leverage": industry base (75%) +
                     labor intensity (15%) + gross-margin operating leverage (10%)
  overall     0-100  0.65 * fund + 0.35 * ai (re-weightable in the dashboard)

Percentiles for fund_score are computed once, across the whole fetched universe
(Nordics + S&P 500 together) — a Nordic name's score reflects its rank against
the combined pool, not against Nordic peers only.

Writes:
  dashboard/screener_data.json    — full payload for the dashboard
  dashboard/screener_data.js      — same payload as window.SCREENER_DATA (file:// use)
  data/screener_latest.csv        — flat tabular twin
  data/screener_refresh_status.json — live progress (polled by screener_server)

Cache: cache/screener/<SYMBOL>.json, 24 h TTL (SCREENER_CACHE_MAX_AGE_H env
overrides; --clear-cache wipes). A failed refetch falls back to the stale copy,
matching the toolkit's chart-cache behaviour. The S&P 500 constituent list
itself (not the fundamentals — just which tickers are in it) is cached
separately for a week, since index membership rarely changes.

Usage:
    python utils/universe_screener.py                    # full refresh (universe + fundamentals)
    python utils/universe_screener.py --limit 25         # first 25 by mcap (smoke test)
    python utils/universe_screener.py --tickers NOKIA.HE,EVO.ST,AAPL
    python utils/universe_screener.py --universe-only    # just enumerate + counts
    python utils/universe_screener.py --clear-cache --workers 8
    python utils/universe_screener.py --skip-sp500       # Nordics only, skip the US leg

Standard library only, like the rest of the toolkit.
"""
from __future__ import annotations

import argparse
import bisect
import concurrent.futures
import datetime
import http.cookiejar
import json
import math
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from paths import ROOT, DATA_DIR, DASHBOARD_DIR, CACHE_DIR, ensure_data_dirs  # noqa: E402

SCREENER_CACHE = os.path.join(CACHE_DIR, "screener")
CACHE_MAX_AGE_H = float(os.environ.get("SCREENER_CACHE_MAX_AGE_H", "24"))

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

NORDIC_EXCHANGES = {"HEL": "Helsinki", "STO": "Stockholm"}  # valid Yahoo screener `exchange` codes
EXCHANGES = {**NORDIC_EXCHANGES, "US": "USA"}                # display labels, incl. the Wikipedia-sourced leg
QS_MODULES = "price,assetProfile,summaryDetail,defaultKeyStatistics,financialData"

SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
SP500_LIST_MAX_AGE_H = 168.0  # index membership changes rarely; cache a week

STATUS_PATH = os.path.join(DATA_DIR, "screener_refresh_status.json")

# -------------------- Yahoo session (cookie + crumb) --------------------

_session_lock = threading.Lock()
_opener = None
_crumb = None


def _new_session():
    """Fresh cookie jar + crumb. Yahoo gates quoteSummary/screener on both."""
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    op.addheaders = [("User-Agent", UA), ("Accept", "*/*"),
                     ("Accept-Language", "en-US,en;q=0.9")]
    try:
        op.open("https://fc.yahoo.com", timeout=20)
    except urllib.error.HTTPError:
        pass  # 404 is expected; the A3 cookie is what we came for
    crumb = op.open("https://query1.finance.yahoo.com/v1/test/getcrumb",
                    timeout=20).read().decode().strip()
    if not crumb or "<" in crumb:
        raise RuntimeError("could not obtain Yahoo crumb")
    return op, crumb


def _session():
    global _opener, _crumb
    with _session_lock:
        if _opener is None:
            _opener, _crumb = _new_session()
        return _opener, _crumb


def _reset_session():
    global _opener, _crumb
    with _session_lock:
        _opener, _crumb = None, None


def _request(url: str, body: bytes | None = None, tries: int = 4):
    """GET/POST with crumb auth, 429/401 backoff and one session reset."""
    last = None
    for attempt in range(tries):
        op, crumb = _session()
        u = url + ("&" if "?" in url else "?") + "crumb=" + urllib.parse.quote(crumb)
        req = urllib.request.Request(
            u, data=body,
            headers={"Content-Type": "application/json"} if body else {})
        try:
            time.sleep(random.uniform(0.05, 0.2))
            with op.open(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (401, 403):
                _reset_session()
            elif e.code == 404:
                raise
            time.sleep(1.5 ** attempt + random.uniform(0, 0.7))
        except Exception as e:  # timeouts, transient network
            last = e
            time.sleep(1.5 ** attempt + random.uniform(0, 0.7))
    raise RuntimeError(f"request failed after {tries} tries: {last}")


# -------------------- Universe enumeration --------------------

def _screen_page(query: dict, offset: int, size: int) -> dict:
    body = json.dumps({
        "size": size, "offset": offset,
        "sortField": "intradaymarketcap", "sortType": "DESC",
        "quoteType": "EQUITY", "query": query,
        "userId": "", "userIdType": "guid",
    }).encode()
    d = _request("https://query1.finance.yahoo.com/v1/finance/screener"
                 "?formatted=false&lang=en-US&region=US", body=body)
    return d["finance"]["result"][0]


def _screen_all(query: dict, label: str) -> dict[str, dict]:
    """Paginate one screener query; returns {symbol: quote}."""
    out: dict[str, dict] = {}
    offset, size = 0, 250
    total = None
    while True:
        try:
            res = _screen_page(query, offset, size)
        except Exception as e:
            print(f"  [warn] screener page offset={offset} failed ({e}); "
                  f"falling back to banded sweep")
            break
        total = res.get("total", 0) if total is None else total
        quotes = res.get("quotes", []) or []
        for q in quotes:
            sym = q.get("symbol")
            if sym and q.get("quoteType", "EQUITY") == "EQUITY":
                out.setdefault(sym, q)
        offset += size
        if not quotes or offset >= min(total, 9750):
            break
    print(f"  · {label}: {len(out)} of {total} symbols")
    return out


def fetch_universe() -> dict[str, dict]:
    """All EQUITY listings on HEL + STO. If plain pagination comes up short of
    the reported total, re-sweep in market-cap bands (the API caps deep offsets)."""
    universe: dict[str, dict] = {}
    for exch in NORDIC_EXCHANGES:
        q = {"operator": "eq", "operands": ["exchange", exch]}
        got = _screen_all(q, exch)
        want = _screen_page(q, 0, 1).get("total", 0)
        if len(got) < want * 0.97:
            print(f"  · {exch}: pagination clipped ({len(got)}/{want}) — sweeping mcap bands")
            bands = [0, 2e7, 5e7, 1e8, 2.5e8, 5e8, 1e9, 2.5e9, 1e10, 1e14]
            for lo, hi in zip(bands, bands[1:]):
                bq = {"operator": "and", "operands": [
                    {"operator": "eq", "operands": ["exchange", exch]},
                    {"operator": "btwn", "operands": ["intradaymarketcap", lo, hi]},
                ]}
                got.update(_screen_all(bq, f"{exch} mcap {lo:.0e}-{hi:.0e}"))
        for sym, quote in got.items():
            quote["_exch"] = exch
            universe[sym] = quote
    return universe


# -------------------- S&P 500 constituent list (Wikipedia) --------------------
# The Yahoo screener API has no "index membership" query field, so the S&P 500
# leg needs its ticker list from elsewhere. Wikipedia's constituents table is
# the standard public, unauthenticated source for this (kept current by the
# same crowd that treats it as the canonical reference); fundamentals for each
# ticker still come from Yahoo's quoteSummary, same as every other name here,
# so the sector/industry taxonomy stays consistent across the whole universe.

class _SP500TableParser(HTMLParser):
    """Extracts (symbol, name) from the '#constituents' wikitable's first two
    columns without needing an HTML/XML dependency beyond the stdlib."""

    def __init__(self):
        super().__init__()
        self._table_stack: list[bool] = []
        self._in_row = False
        self._in_cell = False
        self._cell_text: list[str] = []
        self._row_cells: list[str] = []
        self.rows: list[tuple[str, str]] = []

    def _active(self) -> bool:
        return bool(self._table_stack) and self._table_stack[-1]

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._table_stack.append(dict(attrs).get("id") == "constituents")
            return
        if not self._active():
            return
        if tag == "tr":
            self._in_row, self._row_cells = True, []
        elif tag == "td" and self._in_row:
            self._in_cell, self._cell_text = True, []

    def handle_endtag(self, tag):
        if self._active():
            if tag == "td" and self._in_cell:
                self._row_cells.append("".join(self._cell_text).strip())
                self._in_cell = False
            elif tag == "tr" and self._in_row:
                if len(self._row_cells) >= 2:
                    self.rows.append((self._row_cells[0], self._row_cells[1]))
                self._in_row = False
        if tag == "table" and self._table_stack:
            self._table_stack.pop()

    def handle_data(self, data):
        if self._in_cell:
            self._cell_text.append(data)


def fetch_sp500_universe() -> dict[str, dict]:
    """{symbol: quote} for the current S&P 500, tagged _exch='US'. Yahoo uses
    '-' for share classes where Wikipedia uses '.' (BRK.B -> BRK-B)."""
    fn = os.path.join(SCREENER_CACHE, "sp500_constituents.json")
    tickers = None
    if os.path.exists(fn) and time.time() - os.path.getmtime(fn) < SP500_LIST_MAX_AGE_H * 3600:
        tickers = json.load(open(fn, encoding="utf-8")).get("tickers")
    if tickers is None:
        try:
            req = urllib.request.Request(SP500_WIKI_URL, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=25) as r:
                html_text = r.read().decode("utf-8")
            parser = _SP500TableParser()
            parser.feed(html_text)
            if len(parser.rows) < 400:
                raise ValueError(f"only parsed {len(parser.rows)} rows — page structure may have changed")
            tickers = [{"symbol": sym.replace(".", "-").strip().upper(), "name": name.strip()}
                       for sym, name in parser.rows if sym.strip()]
            json.dump({"fetched_at": time.time(), "tickers": tickers}, open(fn, "w", encoding="utf-8"))
        except Exception as e:
            print(f"  [warn] S&P 500 constituent fetch failed ({e})", end="")
            if os.path.exists(fn):
                tickers = json.load(open(fn, encoding="utf-8")).get("tickers")
                print(f"; using cached list from {datetime.date.fromtimestamp(os.path.getmtime(fn))}")
            else:
                print("; no cached list available — skipping the S&P 500 leg")
                tickers = []
    universe: dict[str, dict] = {}
    for t in tickers:
        universe[t["symbol"]] = {"_exch": "US", "longName": t.get("name"), "currency": "USD"}
    return universe


# -------------------- FX (everything monetary → EUR) --------------------

_FX_MEMO: dict[str, float | None] = {}


def _fx_rate(ccy: str) -> float | None:
    """Units of `ccy` per 1 EUR, from the v8 chart API (cached 24 h + in-process memo)."""
    if ccy in ("EUR", None, ""):
        return 1.0
    if ccy in _FX_MEMO:
        return _FX_MEMO[ccy]
    pence = ccy in ("GBp", "GBX")
    pair = "GBP" if pence else ccy
    fn = os.path.join(SCREENER_CACHE, f"fx_EUR{pair}.json")
    rate = None
    if os.path.exists(fn) and time.time() - os.path.getmtime(fn) < CACHE_MAX_AGE_H * 3600:
        rate = json.load(open(fn, encoding="utf-8")).get("rate")
    if rate is None:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/EUR{pair}=X?range=5d&interval=1d"
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=25) as r:
                d = json.loads(r.read().decode())
            closes = [c for c in d["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
            rate = closes[-1]
            json.dump({"rate": rate}, open(fn, "w", encoding="utf-8"))
        except Exception as e:
            print(f"  [warn] FX EUR{pair}=X failed: {e}")
            if os.path.exists(fn):
                rate = json.load(open(fn, encoding="utf-8")).get("rate")
    out = rate * (100.0 if pence else 1.0) if rate is not None else None
    _FX_MEMO[ccy] = out
    return out


# -------------------- Per-symbol fundamentals --------------------

def _num(x):
    """Yahoo raw fields are plain numbers with formatted=false, but guard the
    occasional {raw: …} dict / empty dict / bool."""
    if isinstance(x, dict):
        x = x.get("raw")
    if isinstance(x, bool) or x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def fetch_quote_summary(symbol: str, clear: bool = False) -> dict | None:
    """quoteSummary payload for one symbol, disk-cached with 24 h TTL and
    stale-fallback on refetch failure. Returns the result dict or None."""
    fn = os.path.join(SCREENER_CACHE, symbol.replace("/", "_") + ".json")
    cached = None
    if os.path.exists(fn) and not clear:
        try:
            cached = json.load(open(fn, encoding="utf-8"))
        except Exception:
            cached = None
        if cached and time.time() - os.path.getmtime(fn) < CACHE_MAX_AGE_H * 3600:
            return cached.get("data")
    try:
        d = _request(
            "https://query1.finance.yahoo.com/v10/finance/quoteSummary/"
            + urllib.parse.quote(symbol)
            + "?modules=" + QS_MODULES
            + "&formatted=false&lang=en-US&region=US&corsDomain=finance.yahoo.com")
        res = (d.get("quoteSummary", {}).get("result") or [None])[0]
        if res:
            tmp = fn + ".tmp"
            json.dump({"fetched_at": time.time(), "data": res},
                      open(tmp, "w", encoding="utf-8"))
            os.replace(tmp, fn)
        return res
    except urllib.error.HTTPError as e:
        if e.code == 404:            # delisted between screener and fetch
            return None
        raise
    except Exception:
        if cached:
            return cached.get("data")
        raise


def build_row(symbol: str, quote: dict, qs: dict | None) -> dict:
    """Merge screener quote (fallback) + quoteSummary (primary) into one flat row."""
    qs = qs or {}
    prof = qs.get("assetProfile") or {}
    sd = qs.get("summaryDetail") or {}
    ks = qs.get("defaultKeyStatistics") or {}
    fin = qs.get("financialData") or {}
    px = qs.get("price") or {}

    ccy = px.get("currency") or quote.get("currency")
    fccy = fin.get("financialCurrency") or quote.get("financialCurrency") or ccy
    r_ccy, r_fccy = _fx_rate(ccy) if ccy else None, _fx_rate(fccy) if fccy else None

    # Yahoo computes P/B, P/S, EV/EBITDA and EV/Rev by dividing a listing-currency
    # numerator by a reporting-currency denominator (ABB.ST: SEK price / USD book).
    # Rescale by the cross rate so cross-currency listings are comparable.
    xccy = (r_ccy / r_fccy) if (r_ccy and r_fccy and ccy != fccy) else 1.0

    def eur(v, rate):
        return v / rate if (v is not None and rate) else None

    def xfix(v):
        return v / xccy if v is not None else None

    price = _num(px.get("regularMarketPrice")) or _num(quote.get("regularMarketPrice"))
    mcap = _num(px.get("marketCap")) or _num(quote.get("marketCap"))
    mcap_eur = eur(mcap, r_ccy)

    eps_ttm = _num(quote.get("epsTrailingTwelveMonths"))
    if eps_ttm is None:
        eps_ttm = _num(ks.get("trailingEps"))
    eps_fwd = _num(quote.get("epsForward")) or _num(ks.get("forwardEps"))

    pe = _num(sd.get("trailingPE")) or _num(quote.get("trailingPE"))
    pe_fwd = _num(sd.get("forwardPE")) or _num(quote.get("forwardPE"))
    ey = (eps_ttm / price) if (eps_ttm is not None and price) else (1 / pe if pe else None)
    ey_fwd = (eps_fwd / price) if (eps_fwd is not None and price) else (1 / pe_fwd if pe_fwd else None)

    div_y = _num(sd.get("dividendYield"))           # fraction
    if div_y is None:
        dq = _num(quote.get("dividendYield"))        # screener quote is in %
        div_y = dq / 100 if dq is not None else None

    w52 = _num(ks.get("52WeekChange"))
    if w52 is None:
        wq = _num(quote.get("fiftyTwoWeekChangePercent"))
        w52 = wq / 100 if wq is not None else None

    d2e = _num(fin.get("debtToEquity"))              # Yahoo reports in %
    d2e = d2e / 100 if d2e is not None else None

    cash = _num(fin.get("totalCash"))
    debt = _num(fin.get("totalDebt"))
    ebitda = _num(fin.get("ebitda"))
    revenue = _num(fin.get("totalRevenue"))
    fcf = _num(fin.get("freeCashflow"))
    net_debt = (debt - cash) if (debt is not None and cash is not None) else None
    nd_ebitda = (net_debt / ebitda) if (net_debt is not None and ebitda and ebitda > 0) else None

    fcf_eur = eur(fcf, r_fccy)
    fcf_yield = (fcf_eur / mcap_eur) if (fcf_eur is not None and mcap_eur) else None
    rev_eur = eur(revenue, r_fccy)

    employees = prof.get("fullTimeEmployees")
    employees = int(employees) if isinstance(employees, (int, float)) and employees > 0 else None
    rev_emp_keur = (rev_eur / employees / 1e3) if (rev_eur and employees) else None

    adv = _num(sd.get("averageVolume")) or _num(quote.get("averageDailyVolume3Month"))
    adv_eur_k = (adv * price / r_ccy / 1e3) if (adv and price and r_ccy) else None

    target = _num(fin.get("targetMeanPrice"))
    upside = (target / price - 1) if (target and price) else None

    summary = (prof.get("longBusinessSummary") or "").strip()
    if len(summary) > 1500:
        summary = summary[:1497] + "…"

    return {
        # identity
        "symbol": symbol,
        "name": px.get("longName") or px.get("shortName")
                or quote.get("longName") or quote.get("shortName") or symbol,
        "exch": quote.get("_exch"),
        "exch_name": EXCHANGES.get(quote.get("_exch"), quote.get("_exch")),
        "currency": ccy,
        "fin_currency": fccy,
        "sector": prof.get("sector"),
        "industry": prof.get("industry"),
        "country": prof.get("country"),
        "website": prof.get("website"),
        "employees": employees,
        "desc": summary,
        # size & trading
        "price": price,
        "mcap_eur_m": mcap_eur / 1e6 if mcap_eur else None,
        "adv_eur_k": adv_eur_k,
        "beta": _num(sd.get("beta")),
        "w52_change": w52,
        # valuation
        "pe_ttm": pe,
        "pe_fwd": pe_fwd,
        "earnings_yield": ey,
        "fwd_earnings_yield": ey_fwd,
        "ev_ebitda": xfix(_num(ks.get("enterpriseToEbitda"))),
        "ev_rev": xfix(_num(ks.get("enterpriseToRevenue"))),
        "pb": xfix(_num(ks.get("priceToBook")) or _num(quote.get("priceToBook"))),
        "ps": xfix(_num(sd.get("priceToSalesTrailing12Months"))),
        "fcf_yield": fcf_yield,
        "div_yield": div_y,
        "payout": _num(sd.get("payoutRatio")),
        "analyst_upside": upside,
        "n_analysts": _num(fin.get("numberOfAnalystOpinions")),
        "rec_key": fin.get("recommendationKey"),
        # quality & growth (fractions)
        "roe": _num(fin.get("returnOnEquity")),
        "roa": _num(fin.get("returnOnAssets")),
        "gm": _num(fin.get("grossMargins")),
        "om": _num(fin.get("operatingMargins")),
        "nm": _num(fin.get("profitMargins")),
        "rev_growth": _num(fin.get("revenueGrowth")),
        "eps_growth": _num(fin.get("earningsGrowth")),
        # balance sheet
        "nd_ebitda": nd_ebitda,
        "net_cash_eur_m": eur(-net_debt, r_fccy) / 1e6 if net_debt is not None and r_fccy else None,
        "debt_equity": d2e,
        "current_ratio": _num(fin.get("currentRatio")),
        "rev_eur_m": rev_eur / 1e6 if rev_eur else None,
        "rev_emp_keur": rev_emp_keur,
        "insider_pct": _num(ks.get("heldPercentInsiders")),
        # meta
        "has_summary": bool(qs),
    }


# -------------------- AI-leverage heuristic --------------------
# Structural fit of each industry for applying AI to internal efficiency or to
# the product itself. This is an explicit, inspectable heuristic — not fetched
# data. First keyword match wins; sector default as fallback.

AI_INDUSTRY_RULES: list[tuple[str, int, str]] = [
    ("software",                    92, "Software economics — AI compounds both the product and dev productivity"),
    ("information technology",      90, "IT services — delivery is labor-hours that AI directly automates"),
    ("internet content",            88, "Digital platform — data-rich, AI-native product surface"),
    ("internet retail",             82, "E-commerce — recommendation, logistics and support automation"),
    ("electronic gaming",           85, "Gaming — content pipelines and live-ops are AI-automatable"),
    ("credit services",             82, "Credit — underwriting and collections are data decisions at scale"),
    ("capital markets",             80, "Capital markets — research, ops and compliance are text-heavy"),
    ("asset management",            80, "Asset management — research and back-office automation"),
    ("banks",                       82, "Banking — document-heavy processes, fraud/KYC, service automation"),
    ("insurance",                   82, "Insurance — claims, underwriting and pricing are data workflows"),
    ("financial data",              88, "Financial data — the product is information processing"),
    ("staffing",                    85, "Staffing — matching and admin are directly AI-automatable"),
    ("consulting",                  84, "Professional services — knowledge work with billable-hour leverage"),
    ("specialty business services", 82, "Business services — back-office process automation"),
    ("security & protection",       72, "Security services — monitoring scales with AI, guarding less so"),
    ("telecom",                     70, "Telecom — network ops and service automation, capital-heavy core"),
    ("advertising",                 80, "Advertising — targeting, creative and buying are AI-disrupted/enabled"),
    ("publishing",                  76, "Publishing — content production economics shift with AI"),
    ("broadcasting",                74, "Media — production and personalisation upside, disruption risk too"),
    ("entertainment",               72, "Entertainment — content pipeline productivity"),
    ("health information",          80, "Health IT — records and diagnostics are data problems"),
    ("medical care facilities",     76, "Care delivery — scheduling, triage and admin absorb most cost"),
    ("diagnostics & research",      74, "Diagnostics — imaging and lab interpretation are AI-tractable"),
    ("medical devices",             66, "Devices — embedded intelligence differentiates hardware"),
    ("medical instruments",         66, "Instruments — software layer increasingly the differentiator"),
    ("drug manufacturers",          62, "Pharma — AI aids discovery but cycles are long and regulated"),
    ("biotech",                     60, "Biotech — discovery upside, binary science risk dominates"),
    ("pharmaceutical retail",       64, "Pharmacy — inventory and advice workflows"),
    ("semiconductor",               78, "Semis — rides the AI capex cycle and design automation"),
    ("computer hardware",           74, "Hardware — AI demand pull plus design productivity"),
    ("communication equipment",     74, "Network equipment — AI traffic drives demand, ops automate"),
    ("electronic components",       68, "Components — factory automation and quality inspection"),
    ("scientific & technical instruments", 68, "Instruments — measurement + software attach"),
    ("consumer electronics",        66, "Consumer electronics — on-device AI features"),
    ("aerospace & defense",         72, "Defence — autonomy and sensor fusion are budget priorities"),
    ("engineering & construction",  66, "Engineering — design, tendering and site planning automate"),
    ("industrial distribution",     64, "Distribution — pricing, inventory and sales automation"),
    ("specialty industrial machinery", 62, "Machinery — predictive maintenance and embedded software"),
    ("farm & heavy construction",   60, "Heavy equipment — autonomy retrofit is slow but real"),
    ("electrical equipment",        60, "Electrical — electrification tailwind, moderate AI angle"),
    ("auto parts",                  58, "Auto supply — factory automation, EV/AI transition risk"),
    ("auto manufacturers",          60, "Autos — autonomy optionality against capital intensity"),
    ("railroads",                   55, "Rail — network optimisation on a fixed asset base"),
    ("marine shipping",             46, "Shipping — routing helps at the margin; the ship is the cost"),
    ("airlines",                    55, "Airlines — pricing/scheduling optimise, fuel and fleet dominate"),
    ("integrated freight",          62, "Logistics — routing, pricing and warehouse automation"),
    ("trucking",                    58, "Trucking — dispatch automation, driver cost exposure"),
    ("airports",                    50, "Infrastructure — throughput optimisation on fixed assets"),
    ("waste management",            52, "Waste — route and sorting automation"),
    ("pollution & treatment",       55, "Environmental services — monitoring automation"),
    ("rental & leasing",            58, "Rental — utilisation and pricing optimisation"),
    ("conglomerates",               58, "Conglomerate — mixed exposure"),
    ("specialty retail",            64, "Retail — inventory, pricing and service automation"),
    ("department stores",           60, "Retail — margin rescue via inventory/labor automation"),
    ("grocery stores",              62, "Grocery — thin margins make automation gains material"),
    ("food distribution",           62, "Food distribution — logistics optimisation"),
    ("discount stores",             62, "Discount retail — supply-chain automation at scale"),
    ("apparel",                     60, "Apparel — demand forecasting and design assistance"),
    ("footwear",                    60, "Apparel — demand forecasting and design assistance"),
    ("luxury goods",                58, "Luxury — brand-led; service and clienteling AI at the edge"),
    ("furnishings",                 55, "Furnishings — design tools and logistics"),
    ("restaurants",                 55, "Restaurants — ordering and kitchen workflow automation"),
    ("leisure",                     58, "Leisure — dynamic pricing and personalisation"),
    ("travel services",             68, "Travel — booking, pricing and service are digital workflows"),
    ("gambling",                    70, "Gaming/betting — risk, personalisation and CRM are data problems"),
    ("casinos",                     68, "Gaming — CRM and risk automation"),
    ("lodging",                     58, "Lodging — revenue management and service automation"),
    ("residential construction",    52, "Construction — planning automation, execution stays physical"),
    ("beverages",                   55, "Consumer staples — demand forecasting and trade-spend optimisation"),
    ("packaged foods",              55, "Consumer staples — demand forecasting and trade-spend optimisation"),
    ("confectioners",               55, "Consumer staples — demand forecasting"),
    ("farm products",               50, "Agriculture — precision farming at the margin"),
    ("household & personal",        55, "Staples — marketing and supply-chain optimisation"),
    ("tobacco",                     48, "Tobacco — limited AI surface"),
    ("education",                   72, "Education — content generation and personalised delivery"),
    ("real estate",                 40, "Real estate — asset returns dominate; admin automation marginal"),
    ("reit",                        38, "REIT — financial asset; minimal AI operating leverage"),
    ("utilities",                   48, "Utilities — grid optimisation inside a regulated envelope"),
    ("renewable",                   52, "Renewables — forecasting and trading optimisation"),
    ("solar",                       55, "Solar — manufacturing automation and grid software"),
    ("oil & gas",                   48, "Oil & gas — commodity price dominates; ops optimisation real but capped"),
    ("thermal coal",                40, "Coal — commodity economics, no AI angle"),
    ("uranium",                     45, "Uranium — commodity economics"),
    ("gold",                        42, "Mining — commodity price dominates"),
    ("copper",                      44, "Mining — commodity price dominates; autonomy in pits helps"),
    ("industrial metals",           44, "Mining/metals — process optimisation at the margin"),
    ("other precious metals",       42, "Mining — commodity price dominates"),
    ("steel",                       46, "Steel — process and energy optimisation"),
    ("aluminum",                    46, "Metals — process optimisation"),
    ("coking coal",                 40, "Coal — commodity economics"),
    ("specialty chemicals",         55, "Chemicals — formulation R&D and process control"),
    ("chemicals",                   52, "Chemicals — process optimisation"),
    ("agricultural inputs",         52, "Agri inputs — precision-ag data services"),
    ("lumber",                      45, "Forestry — commodity economics"),
    ("paper",                       46, "Paper — process/energy optimisation in a commodity market"),
    ("packaging",                   52, "Packaging — plant automation and design"),
    ("building materials",          52, "Materials — logistics and process automation"),
    ("building products",           54, "Building products — configure-to-order automation"),
]

AI_SECTOR_DEFAULT = {
    "Technology": 80, "Communication Services": 72, "Financial Services": 78,
    "Healthcare": 66, "Industrials": 58, "Consumer Cyclical": 60,
    "Consumer Defensive": 55, "Basic Materials": 46, "Energy": 48,
    "Real Estate": 40, "Utilities": 48,
}


def ai_base(sector: str | None, industry: str | None) -> tuple[int, str]:
    norm = re.sub(r"[—–\-—–]+", " ", (industry or "").lower())
    norm = re.sub(r"\s+", " ", norm)
    for key, score, note in AI_INDUSTRY_RULES:
        if key in norm:
            return score, note
    if sector in AI_SECTOR_DEFAULT:
        return AI_SECTOR_DEFAULT[sector], f"{sector} sector default"
    return 50, "No sector data — neutral"


# -------------------- Scoring --------------------

FUND_PILLARS = {          # pillar -> (weight, [(row key, higher_is_better)])
    "quality":   (0.35, [("roe", True), ("om", True), ("gm", True), ("roa", True)]),
    "growth":    (0.20, [("rev_growth", True), ("eps_growth", True)]),
    "balance":   (0.15, [("nd_ebitda", False), ("debt_equity", False), ("current_ratio", True)]),
    "valuation": (0.30, [("earnings_yield", True), ("fcf_yield", True), ("ev_ebitda", False)]),
}
N_INPUTS = sum(len(m) for _, m in FUND_PILLARS.values())


def _pct_rank(values: list[float]):
    """Return f(x) -> percentile in [0,1] of x within `values` (mid-rank ties)."""
    s = sorted(values)
    n = len(s)
    def f(x):
        lo = bisect.bisect_left(s, x)
        hi = bisect.bisect_right(s, x)
        return (lo + hi) / 2 / n if n else 0.5
    return f

def _cap_current_ratio(v):
    return min(v, 3.0)


def compute_scores(rows: list[dict]) -> None:
    """Adds fund_score (+ pillar breakdown), ai_score (+ parts), overall, ranks."""
    # percentile functions per metric over the whole universe
    pct = {}
    for _, (w, metrics) in FUND_PILLARS.items():
        for key, _hib in metrics:
            vals = [r[key] for r in rows if r.get(key) is not None]
            if key == "current_ratio":
                vals = [_cap_current_ratio(v) for v in vals]
            pct[key] = _pct_rank(vals) if len(vals) >= 20 else None
    for aux in ("rev_emp_keur", "gm"):
        vals = [r[aux] for r in rows if r.get(aux) is not None]
        pct["_ai_" + aux] = _pct_rank(vals) if len(vals) >= 20 else None

    for r in rows:
        pillars, n_avail = {}, 0
        for name, (w, metrics) in FUND_PILLARS.items():
            ps = []
            for key, hib in metrics:
                v = r.get(key)
                if v is None or pct.get(key) is None:
                    continue
                if key == "current_ratio":
                    v = _cap_current_ratio(v)
                p = pct[key](v)
                ps.append(p if hib else 1 - p)
                n_avail += 1
            pillars[name] = round(100 * sum(ps) / len(ps), 1) if ps else None
        wsum = sum(w for name, (w, _) in FUND_PILLARS.items() if pillars[name] is not None)
        fund = (sum(FUND_PILLARS[name][0] * pillars[name]
                    for name in pillars if pillars[name] is not None) / wsum) if wsum else None
        r["pillar_quality"] = pillars["quality"]
        r["pillar_growth"] = pillars["growth"]
        r["pillar_balance"] = pillars["balance"]
        r["pillar_valuation"] = pillars["valuation"]
        r["fund_score"] = round(fund, 1) if fund is not None else None
        r["coverage"] = round(n_avail / N_INPUTS, 2)

        base, note = ai_base(r.get("sector"), r.get("industry"))
        labor_p = 0.5
        if r.get("rev_emp_keur") is not None and pct.get("_ai_rev_emp_keur"):
            labor_p = 1 - pct["_ai_rev_emp_keur"](r["rev_emp_keur"])   # labor-heavy ⇒ more upside
        gm_p = 0.5
        if r.get("gm") is not None and pct.get("_ai_gm"):
            gm_p = pct["_ai_gm"](r["gm"])                              # margin ⇒ gains drop through
        r["ai_base"] = base
        r["ai_note"] = note
        r["ai_labor_pts"] = round(15 * labor_p, 1)
        r["ai_margin_pts"] = round(10 * gm_p, 1)
        r["ai_score"] = round(min(100.0, 0.75 * base + 15 * labor_p + 10 * gm_p), 1)

        r["overall"] = (round(0.65 * r["fund_score"] + 0.35 * r["ai_score"], 1)
                        if r["fund_score"] is not None else None)


# -------------------- Share-class dedup --------------------

_CLASS_PAT = re.compile(
    r"\s+(ser\.?\s*[a-d1-2]\.?|class\s*[a-d]|sdb|adr|pref(erence)?s?\.?|[abcd])$",
    re.IGNORECASE)


def _dedup_key(name: str) -> str:
    k = re.sub(r"\s*\((publ|adr|sdb)\.?\)", "", (name or "").lower()).strip()
    prev = None
    while prev != k:
        prev, k = k, _CLASS_PAT.sub("", k).strip().rstrip(".,")
    return re.sub(r"\s+", " ", k)


def mark_duplicate_classes(rows: list[dict]) -> None:
    """Same company listed as several share classes / on both exchanges:
    keep the most-traded line as primary, flag the rest (UI hides them by default)."""
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(_dedup_key(r["name"]), []).append(r)
    for key, g in groups.items():
        if len(g) < 2:
            g[0]["dup_class"] = False
            continue
        primary = max(g, key=lambda r: (r.get("adv_eur_k") or 0, r.get("mcap_eur_m") or 0))
        for r in g:
            r["dup_class"] = r is not primary
            if r is not primary:
                r["dup_of"] = primary["symbol"]


def assign_ranks(rows: list[dict]) -> None:
    ranked = sorted((r for r in rows if r.get("overall") is not None and not r.get("dup_class")),
                    key=lambda r: -r["overall"])
    for i, r in enumerate(ranked, 1):
        r["rank"] = i
    for r in rows:
        r.setdefault("rank", None)


# -------------------- Progress / status --------------------

_status_lock = threading.Lock()
_status: dict = {}
_status_last_write = 0.0


def write_status(force: bool = False, **kw) -> None:
    global _status_last_write
    with _status_lock:
        _status.update(kw, updated=datetime.datetime.now().isoformat(timespec="seconds"))
        if not force and time.time() - _status_last_write < 1.0:
            return
        _status_last_write = time.time()
        tmp = STATUS_PATH + ".tmp"
        json.dump(_status, open(tmp, "w", encoding="utf-8"), indent=1)
        os.replace(tmp, STATUS_PATH)


# -------------------- Output --------------------

CSV_ORDER = [
    "rank", "symbol", "name", "exch_name", "sector", "industry", "country",
    "mcap_eur_m", "price", "currency", "overall", "fund_score", "ai_score",
    "pillar_quality", "pillar_growth", "pillar_balance", "pillar_valuation",
    "pe_ttm", "pe_fwd", "ev_ebitda", "ev_rev", "pb", "ps", "earnings_yield",
    "fwd_earnings_yield", "fcf_yield", "div_yield", "payout", "analyst_upside",
    "n_analysts", "rec_key", "roe", "roa", "gm", "om", "nm", "rev_growth",
    "eps_growth", "nd_ebitda", "net_cash_eur_m", "debt_equity", "current_ratio",
    "rev_eur_m", "employees", "rev_emp_keur", "insider_pct", "beta",
    "w52_change", "adv_eur_k", "coverage", "ai_base", "ai_note", "dup_class",
]


def write_outputs(rows: list[dict], meta: dict) -> None:
    ensure_data_dirs()
    payload = {"meta": meta, "rows": rows}
    js_path = os.path.join(DASHBOARD_DIR, "screener_data.js")
    json_path = os.path.join(DASHBOARD_DIR, "screener_data.json")
    csv_path = os.path.join(DATA_DIR, "screener_latest.csv")

    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(blob)
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("window.SCREENER_DATA = " + blob + ";\n")

    import csv as _csv
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=CSV_ORDER, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda x: (x.get("rank") is None, x.get("rank") or 0)):
            rr = dict(r)
            for k, v in rr.items():
                if isinstance(v, float):
                    rr[k] = round(v, 5)
            w.writerow(rr)
    print(f"  → {json_path}\n  → {js_path}\n  → {csv_path}")


# -------------------- Main --------------------

def run(args) -> int:
    os.makedirs(SCREENER_CACHE, exist_ok=True)
    ensure_data_dirs()
    t0 = time.time()
    write_status(force=True, running=True, phase="universe", done=0, total=None,
                 errors=0, started=datetime.datetime.now().isoformat(timespec="seconds"))
    try:
        if args.clear_cache:
            for fn in os.listdir(SCREENER_CACHE):
                os.remove(os.path.join(SCREENER_CACHE, fn))
            print("  · cache cleared")

        print("Enumerating Nasdaq Helsinki + Stockholm universe…")
        universe = fetch_universe()
        print(f"  · Nordics: {len(universe)} equities")

        if not args.skip_sp500:
            print("Enumerating S&P 500 constituents (Wikipedia)…")
            sp500 = fetch_sp500_universe()
            print(f"  · S&P 500: {len(sp500)} equities")
            universe.update(sp500)
        print(f"  · combined universe: {len(universe)} equities")

        if args.tickers:
            keep = {t.strip().upper() for t in args.tickers.split(",")}
            universe = {s: q for s, q in universe.items() if s.upper() in keep}
        # S&P 500 quotes have no pre-fetch marketCap (Wikipedia doesn't carry
        # one) — index membership itself implies large-cap, so rank them ahead
        # of anything with a real-but-small screener mcap for --limit smoke tests.
        def _sort_key(s):
            mc = _num(universe[s].get("marketCap"))
            if mc is not None:
                return mc
            return 1e15 if universe[s].get("_exch") == "US" else 0
        symbols = sorted(universe, key=lambda s: -_sort_key(s))
        if args.limit:
            symbols = symbols[:args.limit]
        if args.universe_only:
            write_status(force=True, running=False, phase="done",
                         total=len(symbols), done=0)
            return 0

        print(f"Fetching fundamentals for {len(symbols)} symbols "
              f"({args.workers} workers, cache TTL {CACHE_MAX_AGE_H:.0f}h)…")
        write_status(force=True, phase="fundamentals", total=len(symbols))
        results: dict[str, dict | None] = {}
        errors = 0
        lock = threading.Lock()

        def work(sym):
            nonlocal errors
            try:
                qs = fetch_quote_summary(sym, clear=False)
            except Exception as e:
                qs = None
                with lock:
                    errors += 1
                if errors <= 15:
                    print(f"  [warn] {sym}: {e}")
            with lock:
                results[sym] = qs
                write_status(done=len(results), errors=errors,
                             last_symbol=sym, phase="fundamentals")

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
            list(ex.map(work, symbols))

        print(f"  · fetched {len(results)} ({errors} errors) in {time.time()-t0:.0f}s")
        write_status(force=True, phase="compute")

        rows = [build_row(s, universe[s], results.get(s)) for s in symbols]
        rows = [r for r in rows if r.get("mcap_eur_m") or r.get("price")]
        mark_duplicate_classes(rows)
        compute_scores(rows)
        assign_ranks(rows)

        n_full = sum(1 for r in rows if r["has_summary"])
        meta = {
            "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "n": len(rows), "n_full": n_full, "errors": errors,
            "n_hel": sum(1 for r in rows if r["exch"] == "HEL"),
            "n_sto": sum(1 for r in rows if r["exch"] == "STO"),
            "n_us": sum(1 for r in rows if r["exch"] == "US"),
            "cache_ttl_h": CACHE_MAX_AGE_H,
            "weights": {"quality": 0.35, "growth": 0.20, "balance": 0.15,
                        "valuation": 0.30, "overall_fund": 0.65, "overall_ai": 0.35},
            "runtime_s": round(time.time() - t0, 1),
        }
        write_outputs(rows, meta)
        write_status(force=True, running=False, phase="done", done=len(results),
                     errors=errors, ok=True,
                     finished=datetime.datetime.now().isoformat(timespec="seconds"))
        print(f"OK — {len(rows)} rows ({n_full} with full fundamentals) "
              f"in {time.time()-t0:.0f}s")
        return 0
    except Exception as e:
        write_status(force=True, running=False, phase="failed", ok=False, error=str(e)[:300])
        raise


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, help="only the N largest by mcap")
    ap.add_argument("--tickers", help="comma-separated symbols to fetch")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--clear-cache", action="store_true")
    ap.add_argument("--universe-only", action="store_true")
    ap.add_argument("--skip-sp500", action="store_true", help="Nordics only, skip the S&P 500 leg")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
