"""
CLI entrypoint: python -m post_scraper <url>
Prints the scraped result as JSON (or error).
"""
from __future__ import annotations

import json
import sys

from .scraper import scrape_post


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m post_scraper <url>", file=sys.stderr)
        sys.exit(1)
    url = sys.argv[1].strip()
    result = scrape_post(url)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
