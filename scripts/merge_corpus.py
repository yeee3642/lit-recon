#!/usr/bin/env python3
"""Merge per-track literature records into one deduped corpus, with a funnel report.

    python merge_corpus.py lit/tracks/ -o lit/corpus.json --funnel lit/funnel.md

Reads every *.json (a list of records) and *.jsonl (one record per line) in the directory. Record
schema is documented in SKILL.md; unknown fields are passed through untouched, so a project can
carry extra columns without patching this script.

Dedupe is by DOI, arXiv ID *and* normalized title, unioned. Title matching is the one that matters:
the arXiv version and the proceedings version of the same paper share no identifier at all, so an
ID-only merge silently double-counts exactly the papers everyone knows.

Stdlib only, so it runs anywhere - including over ssh on a box you cannot install onto.
"""

import argparse
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

# venue_short -> substrings seen in the wild (lowercase, matched as substrings).
# Add rather than replace; see references/venues.md.
VENUE_ALIASES = {
    "S&P": ["ieee symposium on security and privacy", "symposium on security and privacy",
            "conf/sp/", "oakland"],
    "CCS": ["conference on computer and communications security", "sigsac", "conf/ccs/"],
    "USENIX Security": ["usenix security", "conf/uss/"],
    "NDSS": ["network and distributed system security", "conf/ndss/"],
    "EuroS&P": ["european symposium on security and privacy", "eurosp", "conf/eurosp/"],
    "ACSAC": ["computer security applications conference", "acsac", "conf/acsac/"],
    "RAID": ["research in attacks, intrusions", "conf/raid/"],
    "AsiaCCS": ["asia conference on computer and communications security", "asiaccs",
                "conf/asiaccs/"],
    "TDSC": ["dependable and secure computing", "journals/tdsc/"],
    "TIFS": ["information forensics and security", "journals/tifs/"],
    "TOPS": ["transactions on privacy and security", "tissec", "journals/tops/"],
    "NeurIPS": ["neural information processing systems", "neurips", "conf/nips/"],
    "ICLR": ["learning representations", "conf/iclr/"],
    "ICML": ["international conference on machine learning", "conf/icml/"],
    "ACL": ["association for computational linguistics", "conf/acl/"],
    "EMNLP": ["empirical methods in natural language processing", "conf/emnlp/"],
    "ICSE": ["international conference on software engineering", "conf/icse/"],
    "FSE": ["foundations of software engineering", "conf/fse/", "conf/sigsoft/"],
    "ASE": ["automated software engineering", "conf/ase/"],
    "OSDI": ["operating systems design and implementation", "conf/osdi/"],
    "SOSP": ["operating systems principles", "conf/sosp/"],
    "EuroSys": ["eurosys", "conf/eurosys/"],
    "ATC": ["usenix annual technical conference", "conf/usenix/"],
    "arXiv": ["arxiv", "corr", "zenodo"],
    "tech-report": ["technical report", "tech report", "white paper", "whitepaper"],
}

TIERS = {
    "A1": ["S&P", "CCS", "USENIX Security", "NDSS"],
    "A2": ["EuroS&P", "ACSAC", "RAID", "AsiaCCS"],
    "J": ["TDSC", "TIFS", "TOPS"],
    "B": ["NeurIPS", "ICLR", "ICML", "ACL", "EMNLP", "ICSE", "FSE", "ASE",
          "OSDI", "SOSP", "EuroSys", "ATC"],
    "C": ["other", "tech-report"],
    "P": ["arXiv"],
}
TIER_OF = {v: t for t, vs in TIERS.items() for v in vs}
VOCAB = set(TIER_OF)
TIER_RANK = {"A1": 0, "A2": 1, "J": 2, "B": 3, "C": 4, "P": 5, "?": 6}
RELEVANCE_RANK = {"core": 0, "related": 1, "background": 2, "": 3, None: 3}


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
    return re.sub(r"^doi:", "", x) or None


def as_list(x):
    if x is None:
        return []
    return list(x) if isinstance(x, (list, tuple, set)) else [x]


def classify(rec):
    """Return (venue_short, tier). Trusts an in-vocabulary venue_short; otherwise infers."""
    vs = rec.get("venue_short")
    if vs in VOCAB:
        return vs, TIER_OF[vs]

    blob = " ".join(str(rec.get(k) or "") for k in
                    ("venue_short", "venue", "venue_raw", "container_title", "journal", "dblp")).lower()
    if blob.strip():
        for canon, needles in VENUE_ALIASES.items():
            if any(n in blob for n in needles):
                return canon, TIER_OF[canon]

    # "not peer reviewed" only implies arXiv when something actually points there. Inferring a
    # venue from the absence of evidence is the manufactured-citation failure this skill exists
    # to prevent, so a record with no venue signal at all stays visibly unknown.
    preprintish = norm_arxiv(rec.get("arxiv_id") or rec.get("id") or "") or \
        (rec.get("type") or "").lower() in ("preprint", "repository")
    if preprintish:
        return "arXiv", "P"
    if blob.strip():
        return "other", "C"
    return None, "?"


def keys_for(rec):
    ks = []
    doi = norm_doi(rec.get("doi"))
    if doi:
        ks.append("doi:" + doi)
    ax = norm_arxiv(rec.get("arxiv_id") or rec.get("arxiv") or rec.get("id") or "")
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
    """Base record for a merged pair: published beats preprint, then tier, then DOI, then detail."""
    pa, pb = a.get("peer_reviewed") is True, b.get("peer_reviewed") is True
    if pa != pb:
        return a if pa else b
    ta, tb = TIER_RANK.get(a["tier"], 9), TIER_RANK.get(b["tier"], 9)
    if ta != tb:
        return a if ta < tb else b
    if bool(norm_doi(a.get("doi"))) != bool(norm_doi(b.get("doi"))):
        return a if norm_doi(a.get("doi")) else b
    return a if len(json.dumps(a, ensure_ascii=False)) >= len(
        json.dumps(b, ensure_ascii=False)) else b


def merge(records):
    u = Union()
    for i, r in enumerate(records):
        row = "row:%d" % i
        ks = keys_for(r) or [row]
        u.join(ks[0], row)
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

        base["tracks"] = sorted({t for m in members
                                 for t in as_list(m.get("track")) + as_list(m.get("tracks")) if t})
        base["facets"] = sorted({f for m in members
                                 for f in as_list(m.get("facet")) + as_list(m.get("facets")) if f})
        base["relevance"] = min((m.get("relevance") for m in members),
                                key=lambda r: RELEVANCE_RANK.get(r, 9))
        base["source_queries"] = sorted({q for m in members
                                         for q in as_list(m.get("source_queries")) if q})
        base["verified_by"] = sorted({v for m in members
                                      for v in as_list(m.get("verified_by")) if v})
        # A record is verified if ANY track verified it; preserve each track's note either way.
        base["verified"] = any(m.get("verified") is True for m in members)
        notes = [m["note"] for m in members if m.get("note")]
        if notes:
            base["note"] = " | ".join(dict.fromkeys(notes))
        ow = sorted({m["overlap_user_work"] for m in members
                     if m.get("overlap_user_work") and m["overlap_user_work"] != "none"})
        base["overlap_user_work"] = ow[0] if len(ow) == 1 else (ow or "none")

        # Fill identifiers from whichever copy had them.
        for field, norm in (("doi", norm_doi), ("arxiv_id", norm_arxiv)):
            if not base.get(field):
                for m in members:
                    got = norm(m.get(field) or m.get("arxiv") or m.get("id") or "") if \
                        field == "arxiv_id" else norm(m.get(field))
                    if got:
                        base[field] = got
                        break
        base.setdefault("doi", None)
        base.setdefault("arxiv_id", None)

        base["_n_source_rows"] = len(members)
        out.append(base)
    return out


def load(path):
    """A .json file holds a list of records; a .jsonl holds one per line."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        rows, bad = [], []
        for ln, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                bad.append("%s:%d unparseable (%s)" % (path.name, ln, e.msg))
        return rows, bad
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return [], ["%s unparseable (%s)" % (path.name, e.msg)]
    if isinstance(data, dict):
        data = data.get("records") or data.get("corpus") or []
    if not isinstance(data, list):
        return [], ["%s is not a list of records" % path.name]
    return data, []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tracks_dir")
    ap.add_argument("-o", "--out", default="corpus.json")
    ap.add_argument("--funnel", default="funnel.md")
    args = ap.parse_args()

    d = pathlib.Path(args.tracks_dir)
    files = sorted(list(d.glob("*.json")) + list(d.glob("*.jsonl")))
    if not files:
        sys.exit("no .json/.jsonl files in %s" % args.tracks_dir)

    records, per_track, bad = [], Counter(), []
    for f in files:
        rows, errs = load(f)
        bad += errs
        for i, r in enumerate(rows, 1):
            if not isinstance(r, dict):
                bad.append("%s[%d] is not an object" % (f.name, i))
                continue
            r.setdefault("track", f.stem)
            r["venue_short"], r["tier"] = classify(r)
            where = "%s[%d] %s" % (f.name, i, (r.get("title") or "?")[:50])
            if r.get("verified") is not True:
                r["verified"] = False
                if not r.get("note"):
                    bad.append("unverified with no note: " + where)
            if r.get("peer_reviewed") is None:
                bad.append("peer_reviewed missing: " + where)
            if r["tier"] == "?":
                bad.append("no venue evidence: " + where)
            records.append(r)
            per_track[r["track"] if isinstance(r.get("track"), str) else f.stem] += 1

    merged = merge(records)
    merged.sort(key=lambda r: (RELEVANCE_RANK.get(r.get("relevance"), 9),
                               TIER_RANK.get(r.get("tier"), 9),
                               -(r.get("year") or 0)))

    kept = [r for r in merged if not str(r.get("status", "")).startswith("excluded")]
    incl = [r for r in kept if r.get("verified")]
    rel = Counter(r.get("relevance") or "?" for r in incl)
    pre = sum(1 for r in incl if r.get("peer_reviewed") is not True)
    unver = sum(1 for r in merged if not r.get("verified"))
    cross = sum(1 for r in merged if len(r.get("tracks") or []) > 1)
    ovl = Counter(r["overlap_user_work"] for r in incl
                  if isinstance(r.get("overlap_user_work"), str)
                  and r["overlap_user_work"] != "none")

    pathlib.Path(args.out).write_text(
        json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")

    L = ["# Retrieval funnel", "",
         "| Stage | Count |", "|---|---|",
         "| Retrieved (all tracks, all sources) | %d |" % len(records),
         "| After dedupe | %d |" % len(merged),
         "| After screening | %d |" % len(kept),
         "| **Included (verified)** | **%d** |" % len(incl),
         "| &nbsp;&nbsp;core / related / background | %d / %d / %d |"
         % (rel["core"], rel["related"], rel["background"]),
         "| &nbsp;&nbsp;peer-reviewed / preprint-only | %d / %d |" % (len(incl) - pre, pre),
         "| &nbsp;&nbsp;unverified (flagged, not dropped) | %d |" % unver,
         "", "## Retrieved per track", "", "| Track | Rows |", "|---|---|"]
    L += ["| %s | %d |" % (t, n) for t, n in sorted(per_track.items())]
    L += ["", "Found by more than one track: **%d**. Zero overlap means the tracks were cut so "
              "narrowly they share no boundary - a recall problem, not a tidiness win." % cross,
          "", "## Tier (included)", "", "| Tier | Count |", "|---|---|"]
    tc = Counter(r.get("tier") for r in incl)
    L += ["| %s | %d |" % (t, tc[t]) for t in ("A1", "A2", "J", "B", "C", "P", "?") if tc[t]]

    fc = Counter(f for r in incl for f in (r.get("facets") or []))
    if fc:
        L += ["", "## Facet (included)", "", "| Facet | Count |", "|---|---|"]
        L += ["| %s | %d |" % (f, n) for f, n in fc.most_common()]

    if ovl:
        L += ["", "## Overlap with own work (included)", "", "| Project | Count |", "|---|---|"]
        L += ["| %s | %d |" % (p, n) for p, n in ovl.most_common()]

    if bad:
        L += ["", "## Needs attention (%d)" % len(bad), ""] + ["- %s" % b for b in bad]

    pathlib.Path(args.funnel).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("%d rows -> %d records | included %d | %s, %s"
          % (len(records), len(merged), len(incl), args.out, args.funnel))
    if bad:
        print("%d record(s) need attention - see %s" % (len(bad), args.funnel))


if __name__ == "__main__":
    main()
