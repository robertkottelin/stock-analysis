"""Post-injection polish: eyebrow timestamp, build-stamp pill, refreshed
"What was cut" footer, and (where declared) a rewritten top-of-page strictbar.

All stock-specific text comes from stocks.config.STOCKS[name].
"""
from __future__ import annotations
import os, re, sys, datetime
from paths import html_path
from analytics import STOCKS, all_names


BUILD_DT   = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
BUILD_DATE = datetime.datetime.now().strftime("%Y-%m-%d")

BUILD_STAMP_HTML = f'''
  <div class="buildstamp" style="margin-top:16px;display:flex;flex-wrap:wrap;gap:10px;align-items:center;font-family:var(--mono);font-size:11px;color:var(--muted)">
    <span style="background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:6px 11px;display:inline-flex;align-items:center;gap:8px">
      <span style="width:8px;height:8px;border-radius:2px;background:var(--blue);display:inline-block"></span>
      <b style="color:var(--ink);font-weight:600">Built {BUILD_DT}</b>
    </span>
    <span style="background:var(--teal-wash);border:1px solid var(--teal);border-radius:8px;padding:6px 11px;color:var(--teal-deep);font-weight:500">
      Modules I (price asymmetry) + J (base rates / factor composite) &middot; live spot &amp; betas fetched at build time
    </span>
  </div>
'''


def patch(name: str) -> str:
    cfg = STOCKS[name]
    path = html_path(cfg)
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    # 1) Eyebrow build date
    new_eyebrow_suffix = f' · built {BUILD_DATE}'
    html, n1 = re.subn(r'( · ≈ June 2026)(?= *</div>)', new_eyebrow_suffix, html, count=1)
    if n1 == 0:
        html, _ = re.subn(r'( · built \d{4}-\d{2}-\d{2})(?= *</div>)', new_eyebrow_suffix, html, count=1)

    # 2) Build-stamp block (idempotent — single-</div> match, lookahead-bounded)
    if 'class="buildstamp"' in html:
        html = re.sub(
            r'<div class="buildstamp"[^>]*>[\s\S]*?</div>\s*(?=<)',
            BUILD_STAMP_HTML.strip() + '\n\n  ',
            html, count=1,
        )
    else:
        html = re.sub(
            r'(<div class="legend">.*?</div>)',
            r'\1' + BUILD_STAMP_HTML,
            html, count=1, flags=re.S,
        )

    # 3) Cut-list footer
    html = re.sub(
        r'<div class="cut">.*?</div>',
        f'<div class="cut"><b>Still legitimately excluded — this build kept these out, not faked:</b> {cfg["cut_replacements"]}</div>',
        html, count=1, flags=re.S,
    )
    html = html.replace('<h4>What was cut, not faked</h4>',   '<h4>Still excluded — post-Modules-I&amp;J audit</h4>')
    html = html.replace('<h4>What was removed and why</h4>',  '<h4>Still excluded — post-Modules-I&amp;J audit</h4>')

    # 4) Optional strictbar rewrite (Neste)
    if cfg.get("strictbar_replacement"):
        html = re.sub(r'<div class="strictbar">.*?</div>', cfg["strictbar_replacement"], html, count=1, flags=re.S)

    # 5) Disclaimer freshness
    html, _ = re.subn(
        r'Figures ≈ June 2026',
        f'Live spot &amp; factor exposures fetched {BUILD_DATE}; balance-sheet figures ≈ FY2025 / Q1\'26 releases',
        html, count=1,
    )

    # 6) Scorecard title — Modules I & J (and U, where configured) add rows, so
    #    the authored count word goes stale. Sync from the actual number of
    #    <tr> rows inside the REAL scorecard — the .scoretab with a Module
    #    column (Orion carries a second .scoretab, its release playbook, which
    #    must not drive this count). Any suffix after "reads" is preserved.
    row_count = None
    for tm in re.finditer(r'<table class="scoretab">(.*?)</table>', html, flags=re.S):
        if '<th>Module</th>' in tm.group(1):
            bm = re.search(r'<tbody>(.*?)</tbody>', tm.group(1), flags=re.S)
            if bm:
                row_count = len(re.findall(r'<tr>', bm.group(1)))
            break
    if row_count:
        _NUM_WORDS = {
            2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
            7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven",
            12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen",
            16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty",
        }
        n_word = _NUM_WORDS.get(row_count, str(row_count))
        html = re.sub(
            r'<h2>Scorecard — the(?: [a-z]+)? reads([^<]*)</h2>',
            lambda mo: f'<h2>Scorecard — the {n_word} reads{mo.group(1)}</h2>',
            html, count=1,
        )

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return f"OK — {cfg['html_file']}: finalize patch applied"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    for n in all_names():
        print(patch(n))
    print(f"\nBuild timestamp applied: {BUILD_DT}")


if __name__ == "__main__":
    main()
