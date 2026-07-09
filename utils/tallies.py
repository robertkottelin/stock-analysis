"""Refresh the scorecard tally bar under Module ∑ to reflect the current
verdict counts (Bull / Mixed / Bear) declared in stocks/config.py."""
from __future__ import annotations
import os, re, sys
from paths import html_path
from analytics import STOCKS, all_names


def update_one(name: str) -> str:
    cfg = STOCKS[name]
    path = html_path(cfg)
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    t = cfg["tally"]
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
    return f"OK — {cfg['html_file']}: tally {t['bull']}/{t['mixed']}/{t['bear']} of {total}"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    for n in all_names():
        print(update_one(n))


if __name__ == "__main__":
    main()
