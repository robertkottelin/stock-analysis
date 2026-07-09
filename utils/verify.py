"""HTML parse + integrity check for every stock report."""
from __future__ import annotations
import os, sys
from html.parser import HTMLParser
from paths import STOCKS_DIR


class _Checker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.errors = [], []
        self.void = {
            'br','hr','img','input','meta','link','source','area','base','col','embed','wbr','track',
            'circle','rect','line','path','use','stop','ellipse','polygon','polyline',
        }
    def handle_starttag(self, tag, attrs):
        if tag not in self.void:
            self.stack.append((tag, self.getpos()))
    def handle_endtag(self, tag):
        # Void elements have no end tag — ignore any that slip through
        # (HTMLParser dispatches self-closing `<line />` as both start and end).
        if tag in self.void:
            return
        if not self.stack:
            self.errors.append(f'Unmatched </{tag}> at {self.getpos()}')
            return
        while self.stack and self.stack[-1][0] != tag:
            self.stack.pop()
        if self.stack:
            self.stack.pop()
    def handle_startendtag(self, tag, attrs):
        # Explicit self-closing (`<foo />`): treat void as fully void, and
        # treat non-void as a normal open+close pair.
        if tag in self.void:
            return
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)


def check(path: str) -> tuple[bool, dict]:
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    p = _Checker(); p.feed(html)
    stats = {
        'parse_errors': len(p.errors),
        'unclosed': len(p.stack),
        'sections_open':  html.count('<section'),
        'sections_close': html.count('</section>'),
        'script_open':  html.count('<script>'),
        'script_close': html.count('</script>'),
        'mI': '<section class="mod" id="mI">' in html,
        'mJ': '<section class="mod" id="mJ">' in html,
        'audit': '<section class="audit" id="mAudit">' in html,
        'kelly': 'Kelly f*' in html,
        'rdcf':  'Reverse-DCF' in html,
        'stepper_i': '<a href="#mI">' in html,
        'stepper_j': '<a href="#mJ">' in html,
        'stepper_audit': '<a href="#mAudit">' in html,
        'sim': 'function simulate' in html,
    }
    ok = (
        stats['parse_errors'] == 0 and stats['unclosed'] == 0
        and stats['sections_open'] == stats['sections_close']
        and stats['script_open'] == stats['script_close']
        and stats['mI'] and stats['mJ'] and stats['audit']
        and stats['kelly'] and stats['rdcf']
        and stats['stepper_i'] and stats['stepper_j'] and stats['stepper_audit']
        and stats['sim']
    )
    return ok, stats


def main() -> int:
    sys.stdout.reconfigure(encoding='utf-8')
    any_fail = False
    for f in sorted(os.listdir(STOCKS_DIR)):
        if not f.endswith('.html'):
            continue
        path = os.path.join(STOCKS_DIR, f)
        ok, s = check(path)
        any_fail = any_fail or (not ok)
        print(f'{f}')
        print(f'  parse errors={s["parse_errors"]}  unclosed={s["unclosed"]}  '
              f'<section>={s["sections_open"]}/{s["sections_close"]}  '
              f'<script>={s["script_open"]}/{s["script_close"]}')
        print(f'  mI={s["mI"]}  mJ={s["mJ"]}  audit={s["audit"]}  '
              f'Kelly={s["kelly"]}  RDCF={s["rdcf"]}  '
              f'stepper(I/J/Audit)={s["stepper_i"]}/{s["stepper_j"]}/{s["stepper_audit"]}  '
              f'JS engine={s["sim"]}')
        print(f'  overall={"OK" if ok else "FAIL"}')
        print()
    return 1 if any_fail else 0


if __name__ == '__main__':
    sys.exit(main())
