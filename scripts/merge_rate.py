#!/usr/bin/env python3
"""Decide whether a list repo is worth a submission BEFORE spending one on it.

The rule this encodes (next.md, OPERATIONAL FACTS): check the repo that actually
accepts the submission, its merge rate over the last N closed PRs, whether it is
archived, and what its default branch is. A prior session closed the apd-core
channel by checking the *parent* repo instead of the data repo that takes entries.

Usage:
    python3 scripts/merge_rate.py owner/repo [owner/repo ...] [--n 15] [--why]

--why also prints the closing comment on each *rejected* PR, which is how #667
was written to pass: both of that repo's recent rejections were rejected solely
for not completing the PR template.

Needs GITHUB_CLASSIC_PAT in the environment (the fine-grained GITHUB_PAT is
scoped to our own repos and 403s on other people's).
"""
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"


def get(path):
    req = urllib.request.Request(
        API + path,
        headers={
            "Authorization": "token " + os.environ["GITHUB_CLASSIC_PAT"],
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"_error": f"HTTP {e.code}"}


def verdict(repo, n=15, why=False):
    meta = get(f"/repos/{repo}")
    if "_error" in meta:
        print(f"{repo}: {meta['_error']} — cannot assess, do not submit blind")
        return
    flags = []
    if meta.get("archived"):
        flags.append("ARCHIVED")
    if meta.get("disabled"):
        flags.append("DISABLED")
    if not meta.get("has_issues"):
        flags.append("issues-off")
    prs = get(
        f"/repos/{repo}/pulls?state=closed&per_page={n}&sort=updated&direction=desc"
    )
    if isinstance(prs, dict):
        print(f"{repo}: {prs.get('_error', 'no PR data')}")
        return
    merged = [p for p in prs if p.get("merged_at")]
    print(
        f"\n{repo} — {meta['stargazers_count']} stars, default branch "
        f"{meta['default_branch']}, pushed {meta['pushed_at'][:10]}"
        + (" [" + ", ".join(flags) + "]" if flags else "")
    )
    print(f"  merges {len(merged)}/{len(prs)} of its last {len(prs)} closed PRs")
    for p in prs:
        mark = "M" if p.get("merged_at") else "-"
        print(f"   {mark} {p['closed_at'][:10]} #{p['number']} {p['title'][:64]}")
    if why:
        for p in prs:
            if p.get("merged_at"):
                continue
            cs = get(f"/repos/{repo}/issues/{p['number']}/comments")
            if isinstance(cs, list) and cs:
                last = cs[-1]
                body = " ".join(last["body"].split())[:160]
                print(f"   rejected #{p['number']}: {last['user']['login']}: {body}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n = 15
    if "--n" in sys.argv:
        n = int(sys.argv[sys.argv.index("--n") + 1])
        args = [a for a in args if a != str(n)]
    why = "--why" in sys.argv
    if not args:
        print(__doc__)
        sys.exit(1)
    for repo in args:
        verdict(repo, n=n, why=why)


if __name__ == "__main__":
    main()
