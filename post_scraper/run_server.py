#!/usr/bin/env python3
"""
Run the Post Scraper test server. Keeps the project self-contained.

Run from inside the post_scraper folder:
    python run_server.py

Or from the folder that contains post_scraper:
    python post_scraper/run_server.py

Then open http://localhost:8765
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the parent of post_scraper is on path so "post_scraper" package is found
_here = Path(__file__).resolve().parent
_root = _here.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from post_scraper.server import main

if __name__ == "__main__":
    main()
