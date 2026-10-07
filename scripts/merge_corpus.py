#!/usr/bin/env python3
"""Merge per-track literature JSONL into one deduped corpus, with a funnel report.

    python merge_corpus.py lit/tracks/ -o lit/corpus.jsonl --funnel lit/funnel.md

Dedupe is by DOI, arXiv ID *and* normalized title, unioned together. Title matching is the one that
matters: the arXiv version and the proceedings version of the same paper share no identifier at all,
so an ID-only merge silently double-counts exactly the papers everyone knows.

Stdlib only, so it runs anywhere — including over ssh on a box you have no control over.
"""

import argparse
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

# Canonical venue -> substrings seen in the wild (lowercase, matched as substrings).
# Add to this rather than replacing; see references/venues.md.
VENUE_ALIASES = {
    "S&P": ["ieee symposium on security and privacy", "symposium on security and privacy",
            "conf/sp/", "oakland"],
    "CCS": ["conference on computer and communications security", "sigsac", "conf/ccs/"],
    "USENIX Security": ["usenix security", "conf/uss/"],
    "NDSS": ["network and distributed system security", "ndss", "conf/ndss/"],
    "EuroS&P": ["european symposium on security and privacy", "eurosp", "conf/eurosp/"],
    "ACSAC": ["computer security applications conference", "acsac", "conf/acsac/"],
    "RAID": ["research in attacks, intrusions", "conf/raid/"],
    "AsiaCCS": ["asia conference on computer and communications security", "asiaccs",
                "conf/asiaccs/"],
    "TDSC": ["dependable and secure computing", "journals/tdsc/"],
    "TIFS": ["information forensics and security", "journals/tifs/"],
    "TOPS": ["transactions on privacy and security", "tissec", "journals/tops/"],
    "NeurIPS": ["neural information processing systems", "neurips", "nips", "conf/nips/"],
    "ICML": ["international conference on machine learning", "conf/icml/"],
    "ICLR": ["international conference on learning representations", "conf/iclr/"],
    "ACL": ["annual meeting of the association for computational linguistics", "conf/acl/"],
    "EMNLP": ["empirical methods in natural language processing", "conf/emnlp/"],
    "NAACL": ["north american chapter of the association", "conf/naacl/"],
    "ICSE": ["international conference on software engineering", "conf/icse/"],
    "FSE": ["foundations of software engineering", "conf/fse/", "conf/sigsoft/"],
    "ASE": ["automated software engineering", "conf/ase/"],
    "ISSTA": ["software testing and analysis", "conf/issta/"],
    "OSDI": ["operating systems design and implementation", "conf/osdi/"],
    "SOSP": ["symposium on operating systems principles", "conf/sosp/"],
    "EuroSys": ["eurosys", "conf/eurosys/"],
    "USENIX ATC": ["usenix annual technical conference", "conf/usenix/"],
    "NSDI": ["networked systems design and implementation", "conf/nsdi/"],
    "arXiv": ["arxiv", "corr"],
    "Zenodo": ["zenodo"],
}

TIERS = {
    "A1": ["S&P", "CCS", "USENIX Security", "NDSS"],
    "A2": ["EuroS&P", "ACSAC", "RAID", "AsiaCCS"],
    "J": ["TDSC", "TIFS", "TOPS"],
    "B": ["NeurIPS", "ICML", "ICLR", "ACL", "EMNLP", "NAACL",
          "ICSE", "FSE", "ASE", "ISSTA",
          "OSDI", "SOSP", "EuroSys", "USENIX ATC", "NSDI"],
    "P": ["arXiv", "Zenodo"],
}
TIER_OF_VENUE = {v: t for t, vs in TIERS.items() for v in vs}
TIER_RANK = {"A1": 0, "A2": 1, "J": 2, "B": 3, "C": 4, "P": 5, "?": 6}
RELEVANCE_RANK = {"core": 0, "related": 1, "background": 2, "": 3}


def norm_title(t):
    """Lowercase, strip punctuation, collapse whitespace. Stable across index formatting."""
    t = re.sub(r"[^a-z0-9 ]+", " ", (t or "").lower())
    return re.sub(r"\s+", " ", t).strip()


def norm_arxiv(x):
    """2406.13352v3 / arXiv:2406.13352 / abs/2406.13352 -> 2406.13352"""
    m = re.search(r"(\d{4}\.\d{4,5})", str(x or ""))
    return m.group(1) if m else None


def norm_doi(x):
    x = str(x or "").lower().strip()
    x = re.sub(r"^https?://(dx\.)?doi\.org/", "", x)
    x = re.sub(r"^doi:", "", x)
    return x or None


def canon_venue(rec):
    """Return (canonical_venue, tier). Honest '?' when nothing backs the venue."""
    blob = " ".join(str(rec.get(k) or "") for k in
                    ("venue", "venue_raw", "container_title", "journal", "dblp")).lower()
    if blob.strip():
        for canon, needles in VENUE_ALIASES.items():
            if any(n in blob for n in needles):
                return canon, TIER_OF_VENUE.get(canon, "C")
    rtype = (rec.get("type") or "").lower()
    if rtype in ("preprint", "repository"):
        return (rec.get("venue") or "arXiv"), "P"
    if blob.strip():
        return (rec.get("venue") or rec.get("venue_raw")), "C"
    return (rec.get("venue") or None), "?"


def keys_for(rec):
    ks = []
    doi = norm_doi(rec.get("doi") or (rec.get("id", "").startswith("doi:") and rec["id"][4:]))
    if doi:
        ks.append("doi:" + doi)
    ax = norm_arxiv(rec.get("arxiv") or rec.get("id") or "")
    if ax:
        ks.append("arxiv:" + ax)
    nt = norm_title(rec.get("title"))
    if nt:
        ks.append("title:" + nt)
    return ks


class Union:
    def __init__(self):
        self.p = {}

    def find(self, k):
        self.p.setdefault(k, k)
        while self.p[k] != k:
            self.p[k] = self.p[self.p[k]]
            k = self.p[k]
        return k

    def join(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def better(a, b):
    """Which record should be the base of a merged pair? Published beats preprint, then tier."""
    ta, tb = TIER_RANK.get(a["tier"], 9), TIER_RANK.get(b["tier"], 9)
    if ta != tb:
        return a if ta < tb else b
    if bool(a.get("doi")) != bool(b.get("doi")):
        return a if a.get("doi") else b
    return a if len(json.dumps(a, ensure_ascii=False)) >= len(json.dumps(b, ensure_ascii=False)) else b


def merge(records):
    u = Union()
    for i, r in enumerate(records):
        ks = keys_for(r) or ["row:%d" % i]
        u.join(ks[0], "row:%d" % i)
        for k in ks[1:]:
            u.join(ks[0], k)

    groups = defaultdict(list)
    for i, r in enumerate(records):
        groups[u.find("row:%d" % i)].append(r)

    out = []
    for members in groups.values():
        base = members[0]
        for m in members[1:]:
            base = better(base, m)
        base = dict(base)
        base["tracks"] = sorted({t for m in members for t in
                                 ([m["track"]] if isinstance(m.get("track"), str)
                                  else (m.get("tracks") or [])) if t})
        base["relevance"] = min((m.get("relevance", "") for m in members),
                                key=lambda r: RELEVANCE_RANK.get(r, 9))
        ev = [m["evidence"] for m in members if m.get("evidence")]
        if ev:
            base["evidence"] = ev[0] if len(ev) == 1 else ev
        alt = sorted({m.get("id") for m in members if m.get("id") and m.get("id") != base.get("id")})
        if alt:
            base["alt_ids"] = alt
        base["_n_source_rows"] = len(members)
        out.append(base)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tracks_dir")
    ap.add_argument("-o", "--out", default="corpus.jsonl")
    ap.add_argument("--funnel", default="funnel.md")
    args = ap.parse_args()

    files = sorted(pathlib.Path(args.tracks_dir).glob("*.jsonl"))
    if not files:
        sys.exit("no .jsonl files in %s" % args.tracks_dir)

    records, per_track, bad = [], Counter(), []
    for f in files:
        track = f.stem
        for ln, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError as e:
                bad.append("%s:%d unparseable (%s)" % (f.name, ln, e.msg))
                continue
            r.setdefault("track", track)
            v, t = canon_venue(r)
            r["venue"], r["tier"] = v, t
            if not r.get("evidence"):
                r["status"] = "unverified"
                bad.append("%s:%d no evidence block -> unverified: %s"
                           % (f.name, ln, (r.get("title") or "?")[:60]))
            records.append(r)
            per_track[track] += 1

    merged = merge(records)
    merged.sort(key=lambda r: (RELEVANCE_RANK.get(r.get("relevance", ""), 9),
                               TIER_RANK.get(r.get("tier"), 9),
                               -(r.get("year") or 0)))

    kept = [r for r in merged if not str(r.get("status", "")).startswith("excluded")]
    included = [r for r in kept if r.get("status") != "unverified"]
    rel = Counter(r.get("relevance", "?") for r in included)
    pre = sum(1 for r in included if r.get("tier") == "P")
    unver = sum(1 for r in merged if r.get("status") == "unverified")
    cross = sum(1 for r in merged if len(r.get("tracks") or []) > 1)

    pathlib.Path(args.out).write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in merged), encoding="utf-8")

    L = ["# Retrieval funnel", "",
         "| Stage | Count |", "|---|---|",
         "| Retrieved (all tracks, all sources) | %d |" % len(records),
         "| After dedupe | %d |" % len(merged),
         "| After screening | %d |" % len(kept),
         "| **Included** | **%d** |" % len(included),
         "| &nbsp;&nbsp;core / related / background | %d / %d / %d |"
         % (rel["core"], rel["related"], rel["background"]),
         "| &nbsp;&nbsp;peer-reviewed / preprint-only | %d / %d |" % (len(included) - pre, pre),
         "| &nbsp;&nbsp;unverified (flagged, not dropped) | %d |" % unver,
         "", "## Retrieved per track", "", "| Track | Rows |", "|---|---|"]
    L += ["| %s | %d |" % (t, n) for t, n in sorted(per_track.items())]
    L += ["", "Found by more than one track: **%d** (overlap is a health signal — zero means the "
              "tracks were split so narrowly they share no boundary)." % cross,
          "", "## Tier breakdown (included)", "", "| Tier | Count |", "|---|---|"]
    tc = Counter(r.get("tier", "?") for r in included)
    L += ["| %s | %d |" % (t, tc[t]) for t in ("A1", "A2", "J", "B", "C", "P", "?") if tc[t]]

    if bad:
        L += ["", "## Needs attention", ""] + ["- %s" % b for b in bad]

    pathlib.Path(args.funnel).write_text("\n".join(L) + "\n", encoding="utf-8")
    # ASCII only on stdout: Windows consoles default to cp950 here and mangle em-dashes.
    print("%d rows -> %d records | included %d | %s, %s"
          % (len(records), len(merged), len(included), args.out, args.funnel))
    if bad:
        print("%d record(s) need attention - see %s" % (len(bad), args.funnel))


if __name__ == "__main__":
    main()
