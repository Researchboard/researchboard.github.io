#!/usr/bin/env python3
"""Monthly check that every scholarship's official link still works. Writes data/link_check.json; problems are printed in the run log."""
from __future__ import annotations

import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "link_check.json"


def check(url: str) -> int:
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method, headers={"User-Agent": "Mozilla/5.0 (ResearchBoard link check)"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.status
        except urllib.error.HTTPError as e:
            if method == "GET" or e.code not in (403, 405, 400):
                return e.code
        except Exception:  # noqa: BLE001
            if method == "GET":
                return 0
    return 0


def main() -> None:
    try:
        last = json.loads(OUT.read_text(encoding="utf-8"))
        if (dt.date.today() - dt.date.fromisoformat(last["checked"])).days < 28 and "--force" not in sys.argv:
            print("links checked less than 4 weeks ago, skipping")
            return
    except Exception:  # noqa: BLE001
        pass
    items = json.loads((ROOT / "assets" / "scholarships.json").read_text(encoding="utf-8"))["items"]
    results = []
    for s in items:
        for url in [s["url"]] + ([s["local"]["url"]] if s.get("local") else []):
            code = check(url)
            results.append({"id": s["id"], "url": url, "status": code})
            if not (200 <= code < 400) and code not in (403,):   # some official sites block automated checks with 403
                print(f"BROKEN? {s['name']}: {url} -> {code}")
    OUT.write_text(json.dumps({"checked": dt.date.today().isoformat(), "results": results}, indent=1), encoding="utf-8")
    print(f"checked {len(results)} links")


if __name__ == "__main__":
    main()
