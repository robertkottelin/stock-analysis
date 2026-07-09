"""Build a SINGLE stock end-to-end (inject Modules I & J → tallies → finalize →
audit → verify), without touching the other reports.

The root ``refresh_all.py`` runs every stock in the registry; that is the right
default for a weekly refresh, but it fails if any registered stock has no HTML
report yet. This helper lets you (re)build one name in isolation:

    python utils/build_one.py tesla
    python utils/build_one.py spacex --skip-verify

Same builders, same idempotence — just scoped to one ticker.
"""
from __future__ import annotations
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import inject, tallies, finalize, audit, verify           # noqa: E402
from analytics import STOCKS                                # noqa: E402
from paths import html_path                                 # noqa: E402


def build(name: str, skip_verify: bool = False) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if name not in STOCKS:
        print(f"Unknown target: {name}. Known: {list(STOCKS)}")
        return 1
    print("=" * 74)
    print(f"  Building '{name}' ({STOCKS[name]['ticker']}) — I&J · tallies · finalize · audit")
    print("=" * 74)
    print(inject.inject(name))
    print(tallies.update_one(name))
    print(finalize.patch(name))
    print(audit.patch(name))
    if not skip_verify:
        ok, stats = verify.check(html_path(STOCKS[name]))
        print(f"verify: {'OK' if ok else 'FAIL'}  {stats}")
        return 0 if ok else 1
    return 0


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    skip = "--skip-verify" in sys.argv
    if not args:
        print("usage: python utils/build_one.py <name> [--skip-verify]")
        return 2
    return build(args[0], skip_verify=skip)


if __name__ == "__main__":
    sys.exit(main())
