"""Path helpers shared by every utility."""
from __future__ import annotations
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STOCKS_DIR = os.path.join(ROOT, "stocks")

# Ensure stocks/ is importable regardless of cwd
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def html_path(cfg: dict) -> str:
    """Absolute path to a stock's HTML report file."""
    return os.path.join(STOCKS_DIR, cfg["html_file"])
