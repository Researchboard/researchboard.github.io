#!/usr/bin/env python3
"""
Posts the daily "Today in Research" summary to social media, right after the
website has been published. Each platform is skipped quietly if its keys are
not set, and a failure on one platform never stops the website update.

Repository secrets (Settings -> Secrets and variables -> Actions):

  Facebook Page
    FB_PAGE_ID            the Page's numeric ID
    FB_PAGE_TOKEN         a Page access token with pages_manage_posts

  LinkedIn
    LINKEDIN_TOKEN        access token with w_member_social (personal profile)
                          or w_organization_social (company page)
    LINKEDIN_AUTHOR       urn:li:person:XXXX or urn:li:organization:12345
                          (optional for a personal profile - found automatically
                          if the token also has the "openid" scope)
    LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET / LINKEDIN_REFRESH_TOKEN
                          optional: if your app has refresh tokens, a fresh
                          access token is fetched on every run

Repository variables (optional): SITE_URL, FB_GRAPH_VERSION, LINKEDIN_VERSION.
Set SOCIAL_DRY_RUN=1 to print the posts without sending them.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LOG = DATA / "social_log.json"
SITE = os.environ.get("SITE_URL", "").strip().rstrip("/") or "https://researchboard.github.io"
FB_VERSION = os.environ.get("FB_GRAPH_VERSION", "").strip() or "v23.0"
LI_VERSION = os.environ.get("LINKEDIN_VERSION", "").strip() or "202608"
DRY = os.environ.get("SOCIAL_DRY_RUN", "") not in ("", "0", "false")


def env(name: str) -> str:
    return os.environ.get(name, "").strip()


def request(method: str, url: str, data=None, headers=None, raw: bytes | None = None):
    headers = dict(headers or {})
    body = raw
    if data is not None and raw is None:
        if headers.get("Content-Type") == "application/json":
            body = json.dumps(data).encode()
        else:
            body = urllib.parse.urlencode(data).encode()
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            text = r.read().decode("utf-8", "replace")
            return r.status, dict(r.headers), (json.loads(text) if text.strip().startswith(("{", "[")) else text)
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"HTTP {e.code}: {text}") from None


# --------------------------------------------------------------------------- the message

def compose() -> dict | None:
    hist = json.loads((DATA / "history.json").read_text(encoding="utf-8"))
    latest = json.loads((DATA / "latest.json").read_text(encoding="utf-8"))
    day = latest.get("latest_day")
    rec = hist.get("days", {}).get(day)
    if not rec:
        return None
    names = latest.get("country_names", {})
    d = dt.date.fromisoformat(day)
    f = lambda n: "—" if n is None else f"{n:,}"  # noqa: E731
    top = list((rec.get("countries") or {}).items())[:3]
    medals = ["🥇", "🥈", "🥉"]
    lines = [
        f"📊 Today in Research — {d:%B} {d.day}, {d.year}",
        "",
        f"📄 {f(rec.get('papers'))} new papers from {f(rec.get('countries_active'))} countries",
        f"🧬 {f(rec.get('pubmed_added'))} records added to PubMed",
        f"🔗 {f(rec.get('citations_made'))} new citations made",
        f"🏛️ {f(rec.get('institutions_active'))} active institutions",
    ]
    if top:
        lines += ["", "Top countries:"] + [f"{medals[i]} {names.get(c, c)} — {n:,}" for i, (c, n) in enumerate(top)]
    inst = (rec.get("institutions") or [])[:1]
    if inst:
        lines += ["", f"Most active institution: {inst[0]['name']} ({inst[0]['count']:,} papers)"]
    url = f"{SITE}/blog/daily-{day}.html"
    lines += ["", f"Full daily report 👉 {url}", "", "#Research #Science #OpenScience #Bibliometrics #PubMed #ResearchBoard"]
    card = ROOT / "posts" / "images" / "cards" / f"daily-{day}.png"
    return {"day": day, "text": "\n".join(lines), "url": url,
            "title": f"Today in Research — {d:%B} {d.day}, {d.year}",
            "card_path": card if card.exists() else None,
            "card_url": f"{SITE}/blog/images/cards/daily-{day}.png" if card.exists() else None}


# --------------------------------------------------------------------------- Facebook

def post_facebook(msg: dict) -> str:
    page, token = env("FB_PAGE_ID"), env("FB_PAGE_TOKEN")
    if not (page and token):
        return "skipped (no FB_PAGE_ID / FB_PAGE_TOKEN)"
    base = f"https://graph.facebook.com/{FB_VERSION}/{page}"
    if DRY:
        return "dry run"
    if msg["card_url"]:
        # photo post: the image card plus the text (the link is in the text)
        _, _, res = request("POST", f"{base}/photos", {"url": msg["card_url"], "caption": msg["text"], "access_token": token})
    else:
        _, _, res = request("POST", f"{base}/feed", {"message": msg["text"], "link": msg["url"], "access_token": token})
    return f"posted (id {res.get('post_id') or res.get('id')})"


# --------------------------------------------------------------------------- LinkedIn

def linkedin_token() -> str:
    rt, cid, secret = env("LINKEDIN_REFRESH_TOKEN"), env("LINKEDIN_CLIENT_ID"), env("LINKEDIN_CLIENT_SECRET")
    if rt and cid and secret:
        _, _, res = request("POST", "https://www.linkedin.com/oauth/v2/accessToken",
                            {"grant_type": "refresh_token", "refresh_token": rt, "client_id": cid, "client_secret": secret})
        return res["access_token"]
    return env("LINKEDIN_TOKEN")


def post_linkedin(msg: dict) -> str:
    token = linkedin_token()
    if not token:
        return "skipped (no LINKEDIN_TOKEN)"
    author = env("LINKEDIN_AUTHOR")
    if not author:
        _, _, me = request("GET", "https://api.linkedin.com/v2/userinfo", headers={"Authorization": f"Bearer {token}"})
        author = f"urn:li:person:{me['sub']}"
    if DRY:
        return f"dry run as {author}"
    h = {"Authorization": f"Bearer {token}", "LinkedIn-Version": LI_VERSION,
         "X-Restli-Protocol-Version": "2.0.0", "Content-Type": "application/json"}
    content = None
    if msg["card_path"]:
        _, _, init = request("POST", "https://api.linkedin.com/rest/images?action=initializeUpload",
                             {"initializeUploadRequest": {"owner": author}}, headers=h)
        v = init["value"]
        request("PUT", v["uploadUrl"], raw=msg["card_path"].read_bytes(),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "image/png"})
        content = {"media": {"id": v["image"], "altText": msg["title"]}}
    body = {"author": author, "commentary": linkedin_escape(msg["text"]), "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
            "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False}
    if content:
        body["content"] = content
    _, headers, _ = request("POST", "https://api.linkedin.com/rest/posts", body, headers=h)
    return f"posted (id {headers.get('x-restli-id') or headers.get('X-RestLi-Id') or 'ok'})"


def linkedin_escape(text: str) -> str:
    """LinkedIn's commentary field treats these characters as markup."""
    for ch in "\\|{}@[]()<>#*_~":
        text = text.replace(ch, "\\" + ch)
    # turn escaped hashtags back into real, clickable LinkedIn hashtags
    return re.sub(r"\\#(\w+)", lambda m: "{hashtag|\\#|" + m.group(1) + "}", text)


# --------------------------------------------------------------------------- main

def main() -> int:
    msg = compose()
    if not msg:
        print("Nothing to post (no complete day).")
        return 0
    log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {}
    print("----- message -----\n" + msg["text"] + "\n-------------------")
    changed = False
    for name, fn in (("facebook", post_facebook), ("linkedin", post_linkedin)):
        done = log.get(name, [])
        if msg["day"] in done:
            print(f"{name}: already posted for {msg['day']}")
            continue
        try:
            result = fn(msg)
        except Exception as e:  # noqa: BLE001 - one platform must not block the other
            result = f"FAILED: {e}"
        print(f"{name}: {result}")
        if result.startswith("posted"):
            log[name] = (done + [msg["day"]])[-60:]
            changed = True
    if changed and not DRY:
        LOG.write_text(json.dumps(log, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
