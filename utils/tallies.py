"""Refresh the scorecard tally bar under Module ∑.

The Bull / Mixed / Bear counts are derived from the report's OWN scorecard —
the .scoretab table with the Module/Verdict header — so the bar can never
drift from the verdicts actually shown on the page (Modules I & J are
re-graded live on every inject run). Rows whose label marks them as an
overlay (e.g. Tesla's "O · Bull case overlay") stay visible in the table but
are excluded from the net count, matching the authors' convention. The static
``tally`` block in stocks/config.py is only a fallback for a page whose
scorecard cannot be parsed.
"""
from __future__ import annotations
import os, re, sys
from paths import html_path
from analytics import STOCKS, all_names


def _scorecard_tbody(html: str) -> str | None:
    """tbody of the real scorecard (thead has a Module column); Orion also
    carries a second .scoretab (the release playbook) that must be skipped."""
    for tm in re.finditer(r'<table class="scoretab">(.*?)</table>', html, re.S):
        block = tm.group(1)
        if "<th>Module</th>" in block:
            bm = re.search(r"<tbody>(.*?)</tbody>", block, re.S)
            if bm:
                return bm.group(1)
    return None


# Row labels that mark a non-graded bull-case OVERLAY (shown in the table,
# excluded from the net count — e.g. Tesla's "O · Bull case overlay").
# Deliberately narrow: Neste's "L · War overlay" is a graded read and counts.
_OVERLAY_MARKERS = ("bull case overlay", "bull-case overlay")


def counted_tally(html: str) -> dict | None:
    """Count vchip verdicts in the scorecard; None if not parseable."""
    tbody = _scorecard_tbody(html)
    if tbody is None:
        return None
    counts = {"bull": 0, "mixed": 0, "bear": 0}
    for row in re.findall(r"<tr>(.*?)</tr>", tbody, re.S):
        first_td = re.search(r"<td[^>]*>(.*?)</td>", row, re.S)
        label = re.sub(r"<[^>]+>", "", first_td.group(1)).lower() if first_td else ""
        if any(mk in label for mk in _OVERLAY_MARKERS):
            continue
        vm = re.search(r"vchip (bull|mixed|bear)", row)
        if vm:
            counts[vm.group(1)] += 1
    return counts if sum(counts.values()) else None


def update_one(name: str) -> str:
    cfg = STOCKS[name]
    path = html_path(cfg)
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    t = counted_tally(html)
    src = "scorecard"
    if t is None:
        t = cfg["tally"]
        src = "config fallback"
    total = t["bull"] + t["mixed"] + t["bear"]
    wb = t["bull"]  / total * 100
    wm = t["mixed"] / total * 100
    wr = t["bear"]  / total * 100
    new_bar = f'<div class="tbar"><div class="tp bull" style="width:{wb:.1f}%"></div><div class="tp mixed" style="width:{wm:.1f}%"></div><div class="tp bear" style="width:{wr:.1f}%"></div></div>'
    new_lab = f'<div class="tlab"><span class="tb">{t["bull"]} Bull</span><span class="tm">{t["mixed"]} Mixed</span><span class="tr">{t["bear"]} Bear</span></div>'
    html = re.sub(r'<div class="tbar">.*?</div></div>', new_bar, html, count=1)
    html = re.sub(r'<div class="tlab"><span class="tb">\d+ Bull</span><span class="tm">\d+ Mixed</span><span class="tr">\d+ Bear</span></div>', new_lab, html, count=1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    note = ""
    ct = cfg.get("tally")
    if src == "scorecard" and ct and (ct["bull"], ct["mixed"], ct["bear"]) != (t["bull"], t["mixed"], t["bear"]):
        note = f"  (config tally {ct['bull']}/{ct['mixed']}/{ct['bear']} is stale — page is authoritative)"
    return f"OK — {cfg['html_file']}: tally {t['bull']}/{t['mixed']}/{t['bear']} of {total} from {src}{note}"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    for n in all_names():
        print(update_one(n))


if __name__ == "__main__":
    main()
