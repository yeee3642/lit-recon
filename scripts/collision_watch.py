#!/usr/bin/env python3
"""Re-run a saved collision query matrix and report only what is new since last time.

    python collision_watch.py matrix.json                      # first run: records the baseline
    python collision_watch.py matrix.json -o new_hits.md       # later runs: diffs against state

The window between choosing a topic and submitting is exactly when someone else posts the same idea,
so this is meant to run weekly until the paper is in. It only works if it is cheap, which means it
has to report *new* hits rather than re-presenting the same 200 papers every week.

matrix.json:

    {
      "project": "<name>",
      "matrix": [
        {"candidate": "C1", "sub_claim": "A-1",
         "arxiv": "abs:\\"untrusted input\\" AND abs:provenance",
         "openalex": "provenance label agent"},
        {"candidate": "C1", "sub_claim": "A-2", "arxiv": "..."}
      ]
    }

State lives next to the matrix as <matrix>.state.json. Delete it to re-baseline.

Stdlib only. OpenAlex queries are skipped unless OPENALEX_API_KEY is set - a missing key degrades
coverage, it does not fail the run, but the report says so.
"""

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = "lit-recon/1.0 (collision watch)"
NS = {"a": "http://www.w3.org/2005/Atom"}
ARXIV_PACE = 5.0      # deliberately above the documented 3 s: parallel agents share an egress IP
BACKOFF_429 = 60.0


def fetch(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                print("  429, waiting %ds" % BACKOFF_429, file=sys.stderr)
                time.sleep(BACKOFF_429)
                continue
            if e.code in (500, 502, 503, 504) and attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            raise
    raise RuntimeError("unreachable")


def arxiv(query, limit=30):
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(
        {"search_query": query, "start": 0, "max_results": limit,
         "sortBy": "submittedDate", "sortOrder": "descending"},
        quote_via=urllib.parse.quote)
    root = ET.fromstring(fetch(url))
    out = []
    for e in root.findall("a:entry", NS):
        aid = (e.findtext("a:id", default="", namespaces=NS) or "").rsplit("/", 1)[-1]
        out.append({"id": "arxiv:" + aid.split("v")[0],
                    "title": " ".join((e.findtext("a:title", default="",
                                                   namespaces=NS) or "").split()),
                    "date": (e.findtext("a:published", default="", namespaces=NS) or "")[:10],
                    "url": "https://arxiv.org/abs/" + aid})
    time.sleep(ARXIV_PACE)
    return out


def openalex(query, key, limit=30):
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(
        {"filter": "title_and_abstract.search:" + query, "per-page": limit,
         "sort": "publication_date:desc", "api_key": key}, quote_via=urllib.parse.quote)
    data = json.loads(fetch(url))
    out = []
    for w in data.get("results", []):
        src = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
        out.append({"id": (w.get("doi") or w.get("id") or "").replace("https://doi.org/", "doi:"),
                    "title": w.get("title") or "",
                    "date": w.get("publication_date") or str(w.get("publication_year") or ""),
                    "url": w.get("doi") or w.get("id") or "",
                    "venue": src})
    time.sleep(1.0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("matrix")
    ap.add_argument("-o", "--out", default=None, help="markdown report (default: stdout only)")
    ap.add_argument("--limit", type=int, default=30)
    args = ap.parse_args()

    mpath = pathlib.Path(args.matrix)
    spec = json.loads(mpath.read_text(encoding="utf-8"))
    rows = spec.get("matrix") or []
    if not rows:
        sys.exit("matrix.json has no 'matrix' entries")

    spath = mpath.with_suffix(".state.json")
    state = json.loads(spath.read_text(encoding="utf-8")) if spath.exists() else {}
    baseline = not state
    key = os.environ.get("OPENALEX_API_KEY")
    today = dt.date.today().isoformat()

    new_by_row, errors, n_queries = [], [], 0
    for row in rows:
        cand, sub = row.get("candidate", "?"), row.get("sub_claim", "?")
        tag = "%s/%s" % (cand, sub)
        seen = set(state.get(tag, []))
        hits, sources = [], []

        for source, runner in (("arxiv", lambda q: arxiv(q, args.limit)),
                               ("openalex", lambda q: openalex(q, key, args.limit))):
            q = row.get(source)
            if not q:
                continue
            if source == "openalex" and not key:
                errors.append("%s: OpenAlex skipped (no OPENALEX_API_KEY)" % tag)
                continue
            n_queries += 1
            sources.append(source)
            print("[%s] %s: %s" % (tag, source, q[:70]), file=sys.stderr)
            try:
                hits += runner(q)
            except Exception as e:                      # a dead query is data, not a crash
                errors.append("%s %s failed: %s: %s" % (tag, source, type(e).__name__, e))

        fresh = [h for h in hits if h["id"] not in seen]
        state[tag] = sorted(seen | {h["id"] for h in hits})
        if fresh:
            new_by_row.append((cand, sub, sources, fresh))

    spath.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")

    total_new = sum(len(f) for _, _, _, f in new_by_row)
    L = ["# Collision watch - %s" % spec.get("project", mpath.stem), "",
         "Run %s - %d queries over %d sub-claims." % (today, n_queries, len(rows))]
    if baseline:
        L += ["", "**Baseline run.** Everything below is simply what the matrix returns today; "
                  "nothing here is new. Later runs diff against this."]
    L += ["", "New since last run: **%d**" % total_new, ""]

    for cand, sub, sources, fresh in new_by_row:
        L += ["## %s / %s  (%s)" % (cand, sub, ", ".join(sources) or "-"), ""]
        for h in sorted(fresh, key=lambda x: x["date"], reverse=True):
            venue = (" | %s" % h["venue"]) if h.get("venue") else ""
            L.append("- `%s` %s%s  \n  %s  \n  %s" % (h["date"], h["id"], venue,
                                                      h["title"][:150], h["url"]))
        L.append("")

    if not new_by_row and not baseline:
        L += ["Nothing new. This is the expected weekly result - it is evidence the claim still "
              "holds as of today, not a reason to stop checking.", ""]
    if errors:
        L += ["## Degraded coverage", "",
              "These limits belong in the report wherever a novelty count appears:", ""]
        L += ["- %s" % e for e in errors]
        L.append("")
    L += ["---", "",
          "Wording: this supports *\"not found as of %s across %d queries\"*. It does not support "
          "\"first\" or \"no prior work\"." % (today, n_queries)]

    report = "\n".join(L) + "\n"
    if args.out:
        pathlib.Path(args.out).write_text(report, encoding="utf-8")
        print("%d new hit(s) -> %s" % (total_new, args.out))
    else:
        print(report)
    if errors:
        print("%d coverage problem(s) - see the report" % len(errors), file=sys.stderr)


if __name__ == "__main__":
    main()
