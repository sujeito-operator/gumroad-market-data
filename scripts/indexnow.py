#!/usr/bin/env python3
"""Submit every URL in sitemap.xml to IndexNow.

IndexNow is the only search-submission route this operation has that needs no account —
Google Search Console and Bing Webmaster Tools are both gated signups, which has been the
wall all week. It feeds Bing, Yandex and Seznam. Re-run after ANY content change; three
sessions have done this by hand and one of them forgot.

    python3 scripts/indexnow.py

The key file must stay served at docs/<key>.txt or submissions are rejected.
"""
import json, pathlib, re, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOST = "sujeito-operator.github.io"
KEY = "836c912b4f4eefa4d1f3c35538e2e588087078e1aaf2f4353771b6b04dae8da2"
KEY_LOCATION = f"https://{HOST}/gumroad-market-data/{KEY}.txt"


def main():
    sitemap = (ROOT / "docs" / "sitemap.xml").read_text()
    urls = re.findall(r"<loc>(.*?)</loc>", sitemap)
    if not urls:
        raise SystemExit("no <loc> entries in sitemap.xml")
    payload = json.dumps({"host": HOST, "key": KEY, "keyLocation": KEY_LOCATION,
                          "urlList": urls}).encode()
    req = urllib.request.Request(
        "https://api.indexnow.org/indexnow", data=payload,
        headers={"Content-Type": "application/json; charset=utf-8",
                 "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                               "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"})
    with urllib.request.urlopen(req, timeout=45) as r:
        # 200 and 202 both mean accepted; anything else is a real failure.
        print(f"submitted {len(urls)} urls -> HTTP {r.status}")


if __name__ == "__main__":
    main()
