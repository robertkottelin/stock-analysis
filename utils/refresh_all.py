"""One-command orchestrator: runs every builder in order and verifies.

Usage (from anywhere — script is self-locating):
    python utils/refresh_all.py                 # or
    python refresh_all.py                       # from the project root

Options:
    --clear-cache      wipe cache/ before starting (force fresh Yahoo fetch)
    --skip-verify      skip the final HTML parse check
"""
from __future__ import annotations
import os, sys, subprocess, shutil, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY   = sys.executable

STEPS = [
    ("inject.py",    ["all"], "Re-rendering Modules I & J with fresh Yahoo v8 data"),
    ("tallies.py",   [],       "Syncing scorecard tally bars"),
    ("finalize.py",  [],       "Stamping build timestamp + refreshing footer notes"),
    ("audit.py",     [],       "Regenerating § Audit data-sources appendix"),
]


def _banner(text: str) -> None:
    print()
    print("=" * 74)
    print(f"  {text}")
    print("=" * 74)


def _run(script: str, args: list[str], label: str) -> int:
    _banner(label)
    cmd = [PY, os.path.join(HERE, script)] + args
    r = subprocess.run(cmd, cwd=HERE, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    return r.returncode


def main() -> int:
    argv = sys.argv[1:]
    skip_verify = "--skip-verify" in argv
    clear_cache = "--clear-cache" in argv

    if clear_cache:
        cache = os.path.join(ROOT, "cache")
        if os.path.isdir(cache):
            # Windows / OneDrive can hold file handles; delete file-by-file
            # so a locked JSON doesn't break the whole run.
            removed, kept = 0, 0
            for fname in os.listdir(cache):
                fp = os.path.join(cache, fname)
                try:
                    if os.path.isfile(fp):
                        os.remove(fp); removed += 1
                except OSError:
                    kept += 1
            print(f"cache cleared: {removed} removed, {kept} kept (locked)")
        else:
            os.makedirs(cache, exist_ok=True)

    started = datetime.datetime.now()
    print(f"refresh_all started at {started.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"project root: {ROOT}")
    print(f"python: {PY}")

    for script, args, label in STEPS:
        rc = _run(script, args, label)
        if rc != 0:
            print(f"\n[!] {script} exited with code {rc}. Stopping.")
            return rc

    if not skip_verify:
        rc = _run("verify.py", [], "Verifying HTML parse + JS engines intact")
        if rc != 0:
            print(f"\n[!] verify.py exited with code {rc}.")
            return rc

    finished = datetime.datetime.now()
    _banner(f"refresh_all completed in {(finished - started).total_seconds():.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
