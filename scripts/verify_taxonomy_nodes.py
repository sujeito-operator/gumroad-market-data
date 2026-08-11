#!/usr/bin/env python3
"""Which of the crawled taxonomy nodes does Gumroad's discover endpoint actually KNOW?

WHY THIS EXISTS
---------------
`collect_taxonomy.py` walks `data/gumroad-taxonomy.txt` -- the category tree read out of
the category picker on a product's EDIT page -- and fetches each node as

    https://gumroad.com/discover?taxonomy=<slug>

That endpoint does not 404 on a slug it does not recognise. **It silently serves the
default discover feed.** Measured 2026-08-11:

    ?taxonomy=fiction-books/children-s-books   -> 36 permalinks
    ?taxonomy=3d/3d-assets/3ds-max             -> the SAME 36, same order
    ?taxonomy=zzz-not-a-real-category-xyz      -> the SAME 36, same order
    ?taxonomy=design/graphics/assets-and-templates -> a different 36  (a real node)

So a node the endpoint does not know was recorded as a category holding 44 listings of
other people's products. "Fiction Books > Children's Books" was published with a median
of $32.05 computed from a NinjaTrader indicator, a peptide book and a sales-funnel course.

The collector's own comment shows how it was missed: the path form `/3d/3d-assets/3ds-max`
404s while `?taxonomy=` "returns 48 cards", and the 48 cards were read as evidence the
node was real. They are evidence of nothing -- a garbage slug returns 48 cards too.

THE TEST
--------
Fetch a CONTROL slug that cannot exist. Anything whose permalink set matches the control
is the default feed wearing a category's name. The feed rotates, so the control is
re-fetched periodically and a node is compared against every control seen so far.

    python3 scripts/verify_taxonomy_nodes.py --selftest
    python3 scripts/verify_taxonomy_nodes.py --out data/node-verification.json

Plain HTTP, no browser: the permalinks are in the delivered HTML.
"""

import argparse, json, re, sys, time, urllib.parse, urllib.request

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36")
PERM = re.compile(r"https://([a-z0-9][a-z0-9\-]*)\.gumroad\.com/l/([A-Za-z0-9_\-]+)")

# Slugs that cannot be categories. Several, because one of them one day becoming a real
# category would silently turn this instrument into a rubber stamp.
CONTROLS = [
    "zzz-not-a-real-category-xyz",
    "qqq-operator-control-slug-2",
    "no-such-taxonomy-please-ignore",
]

# A node is the default feed if this much of it is the control. Not 1.0: the feed is
# ranked and a slow page can drop or gain a card between two fetches.
MATCH = 0.80


def permalinks(html):
    """The distinct product permalinks a discover page delivered, in first-seen order."""
    out, seen = [], set()
    for host, key in PERM.findall(html):
        u = f"https://{host}.gumroad.com/l/{key}"
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def fetch(slug, timeout=45):
    url = "https://gumroad.com/discover?taxonomy=" + urllib.parse.quote(slug, safe="")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf8", "replace")


def overlap(a, b):
    """Share of `a` that also appears in `b`. Empty `a` overlaps nothing -- it is not a
    match for the control, it is a separate outcome, and 1.0 here would call it one."""
    a, b = set(a), set(b)
    if not a:
        return 0.0
    return len(a & b) / len(a)


def classify(node_perms, controls, match=MATCH):
    """`controls` is a list of permalink lists. A node is DEFAULT_FEED if it matches any
    of them -- the feed rotates, so the control drawn nearest in time is the one that
    will match, and requiring all of them would let rotation clear a bad node."""
    if not node_perms:
        return "empty", 0.0
    best = max((overlap(node_perms, c) for c in controls), default=0.0)
    return ("default_feed" if best >= match else "real"), best


def slugify(node):
    """Same rule as collect_taxonomy.slugify -- imported by value, not by reference, so
    a change there does not silently change what this instrument verified."""
    parts = []
    for p in node.split(">"):
        p = p.strip().lower()
        p = p.replace("&", "and")
        p = re.sub(r"[^a-z0-9]+", "-", p).strip("-")
        parts.append(p)
    return "/".join(parts)


def selftest():
    ok = True
    def chk(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        print(("  PASS  " if cond else "  FAIL  ") + name)

    h = ('<a href="https://foo.gumroad.com/l/abc">x</a> junk '
         '<a href="https://bar.gumroad.com/l/Zed_9">y</a> '
         '<a href="https://foo.gumroad.com/l/abc">dup</a>')
    p = permalinks(h)
    chk("permalinks: extracts both", p == ["https://foo.gumroad.com/l/abc",
                                           "https://bar.gumroad.com/l/Zed_9"])
    chk("permalinks: de-dupes, keeps order", len(p) == 2 and p[0].endswith("abc"))
    chk("permalinks: ignores a non-permalink gumroad URL",
        permalinks('<a href="https://gumroad.com/discover?x=1">z</a>') == [])

    A = [f"u{i}" for i in range(10)]
    chk("overlap: identical is 1.0", overlap(A, A) == 1.0)
    chk("overlap: disjoint is 0.0", overlap(A, ["q"]) == 0.0)
    chk("overlap: 8 of 10", abs(overlap(A, A[:8]) - 0.8) < 1e-9)
    chk("overlap: empty left is 0.0, NOT 1.0", overlap([], A) == 0.0)

    chk("classify: exact control is default_feed", classify(A, [A])[0] == "default_feed")
    chk("classify: 8/10 of control is default_feed", classify(A, [A[:8] + ["x", "y"]])[0]
        == "default_feed")
    chk("classify: 7/10 is real", classify(A, [A[:7] + list("xyz")])[0] == "real")
    chk("classify: no rows is empty, not default_feed", classify([], [A])[0] == "empty")
    chk("classify: matches ANY control, not all",
        classify(A, [["q"], A])[0] == "default_feed")

    chk("slugify: 3ds max", slugify("3D > 3D Assets > 3ds Max") == "3d/3d-assets/3ds-max")
    chk("slugify: ampersand becomes and",
        slugify("Drawing & Painting") == "drawing-and-painting")
    chk("slugify: apostrophe drops",
        slugify("Fiction Books > Children's Books") == "fiction-books/children-s-books")

    chk("controls are distinct", len(set(CONTROLS)) == len(CONTROLS))
    chk("MATCH is a share, not a count", 0.5 < MATCH < 1.0)
    print("SELFTEST", "OK" if ok else "FAILED")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--taxonomy", default="data/gumroad-taxonomy.txt")
    ap.add_argument("--crawled", default="data/raw-taxonomy.jsonl",
                    help="verify only nodes this crawl recorded rows for")
    ap.add_argument("--out", default="data/node-verification.json")
    ap.add_argument("--delay", type=float, default=1.2)
    ap.add_argument("--recontrol", type=int, default=25,
                    help="re-fetch a control every N nodes; the feed rotates")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    if a.selftest:
        return selftest()

    crawled = [json.loads(l) for l in open(a.crawled)]
    nodes = [r["node"] for r in crawled if r.get("ok") and r.get("rows")]
    if a.limit:
        nodes = nodes[:a.limit]
    print(f"{len(nodes)} nodes with rows to verify", flush=True)

    controls, out = [], []
    ci = 0
    for i, node in enumerate(nodes):
        if i % a.recontrol == 0:
            try:
                c = permalinks(fetch(CONTROLS[ci % len(CONTROLS)]))
                ci += 1
                if c:
                    controls.append(c)
                    print(f"  [control {len(controls)}] {len(c)} permalinks", flush=True)
            except Exception as e:
                print(f"  [control] ERR {e}", flush=True)
            time.sleep(a.delay)

        slug = slugify(node)
        rec = {"node": node, "slug": slug}
        try:
            perms = permalinks(fetch(slug))
            rec["n"], (rec["verdict"], rec["control_overlap"]) = (
                len(perms), classify(perms, controls))
        except Exception as e:
            rec["verdict"], rec["error"] = "error", str(e)
        out.append(rec)
        print(f"  {i+1:>3}/{len(nodes)}  {rec.get('verdict','?'):<13} "
              f"{rec.get('control_overlap', 0):.2f}  {node}", flush=True)
        time.sleep(a.delay)

    tally = {}
    for r in out:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
    doc = {"checked": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "controls": [len(c) for c in controls], "match_threshold": MATCH,
           "tally": tally, "nodes": out}
    open(a.out, "w").write(json.dumps(doc, indent=1))
    print("\ntally:", tally)
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
