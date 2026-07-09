"""Top-level convenience: run refresh_all from the project root.

Simply forwards to utils/refresh_all.py so you can execute the pipeline via
either `python refresh_all.py` (from project root) or
`python utils/refresh_all.py` (from anywhere). Both are equivalent.
"""
from __future__ import annotations
import os, sys, runpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "utils"))
runpy.run_path(os.path.join(HERE, "utils", "refresh_all.py"), run_name="__main__")
