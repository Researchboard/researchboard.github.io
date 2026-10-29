#!/usr/bin/env python3
"""
Tell Bing (and the other IndexNow search engines: Yandex, Seznam, Naver) which pages exist or changed,
so new pages appear in their search — and in AI assistants that use Bing, such as ChatGPT search — quickly.

The key below is public by design: search engines check it against https://researchboard.net/<key>.txt.
Run after the site is deployed:  python scripts/indexnow.py _site/sitemap.xml
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request

KEY = "7dffbc8bd87d1f8af82c6bac42afc83a"
HOST = "researchboard.net"


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "_site/sitemap.xml"
    try:
        xml = open(path, encoding="utf-8").read()
    except FileNotFoundError:
        print("no sitemap, nothing to submit")
        return
    urls = [u for u in re.findall(r"<loc>(.*?)</loc>", xml) if HOST in u][:10000]
    if not urls:
        print("sitemap has no URLs")
        return
    body = json.dumps({"host": HOST, "key": KEY, "keyLocation": f"https://{HOST}/{KEY}.txt", "urlList": urls}).encode()
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"IndexNow: submitted {len(urls)} URLs, HTTP {r.status}")
    except Exception as e:  # noqa: BLE001 - never fail the workflow over this
        print("IndexNow submit failed:", e)


if __name__ == "__main__":
    main()
