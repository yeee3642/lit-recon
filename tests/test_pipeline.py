#!/usr/bin/env python3
"""Smoke test for the merge -> bib -> table pipeline. Self-contained; builds fixtures in a temp dir.

    python tests/test_pipeline.py

Covers what actually goes wrong: one paper arriving as a preprint in one track and a published paper
in another (no shared identifier, title-match only), a DOI-level duplicate, a record with no API
evidence, an explicitly excluded record, a venue nothing in the alias table matches, two records
claiming the same cite key, and a LaTeX special character in a title.
"""

import json
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"

TRACK_A = [
    # Same work as ISOLATION[0] but as a preprint: no shared ID, so only title matching merges them.
    {"key": "alpha2025layered", "title": "A Layered Defence for Untrusted Inputs",
     "authors": ["A Alpha", "B Beta"], "year": 2025,
     "arxiv_id": "2503.18813", "doi": None, "venue": "arXiv", "venue_short": "arXiv",
     "peer_reviewed": False, "abstract": "We present a layered design...", "url": "https://arxiv.org/abs/2503.18813",
     "track": "policy", "facet": "policy-language", "relevance": "core",
     "verified_by": "arxiv_api", "verified": True, "source_queries": ["abs:\"untrusted input\""],
     "overlap_user_work": "none"},
    {"key": "doe2024sandbox", "title": "Sandboxing Everything & Friends",
     "authors": ["Jane Doe"], "year": 2024, "arxiv_id": None, "doi": "10.1109/SP.2024.00001",
     "venue": "2024 IEEE Symposium on Security and Privacy (SP)", "venue_short": "S&P",
     "peer_reviewed": True, "abstract": None, "url": "https://doi.org/10.1109/SP.2024.00001",
     "track": "policy", "facet": "vm-isolation", "relevance": "core",
     "verified_by": "crossref", "verified": True, "source_queries": ["q-sandbox"],
     "overlap_user_work": "none"},
    # No API confirmed this one. Must survive as verified:false, and must not reach refs.bib.
    {"key": "ghost2025unknown", "title": "Some Unverified Thing", "authors": [], "year": 2025,
     "arxiv_id": None, "doi": None, "venue": None, "venue_short": None, "peer_reviewed": False,
     "abstract": None, "url": None, "track": "policy", "facet": "policy-language",
     "relevance": "background", "verified_by": None, "verified": False, "source_queries": ["q-ghost"],
     "overlap_user_work": "none", "note": "title seen in a blog post; no API hit"},
]

TRACK_B = [
    {"key": "alpha2026layered", "title": "A Layered Defence for Untrusted Inputs",
     "authors": ["A Alpha", "B Beta"], "year": 2026, "arxiv_id": None,
     "doi": "10.1109/SP.2026.00042", "venue": "IEEE Symposium on Security and Privacy",
     "venue_short": "S&P", "peer_reviewed": True, "abstract": "We present a layered design...",
     "url": "https://doi.org/10.1109/SP.2026.00042", "track": "mechanism", "facet": "syscall-filter",
     "relevance": "related", "verified_by": "s2", "verified": True,
     "source_queries": ["alpha citations"], "overlap_user_work": "PROJ-A"},
    {"key": "doe2024sandbox", "title": "Sandboxing Everything and Friends (extended)",
     "authors": ["Jane Doe"], "year": 2024, "arxiv_id": None, "doi": "10.1109/SP.2024.00001",
     "venue": "IEEE Symposium on Security and Privacy", "venue_short": "S&P",
     "peer_reviewed": True, "abstract": "An extended treatment.", "url": None,
     "track": "mechanism", "facet": "capability", "relevance": "related",
     "verified_by": "openalex", "verified": True, "source_queries": ["q-sandbox-2"],
     "overlap_user_work": "none"},
    {"key": "chen2026agent", "title": "A Frontier Preprint On Agent Egress", "authors": ["A Chen"],
     "year": 2026, "arxiv_id": "2601.00123", "doi": None, "venue": "arXiv",
     "venue_short": "arXiv", "peer_reviewed": False, "abstract": "Egress control...",
     "url": "https://arxiv.org/abs/2601.00123", "track": "mechanism", "facet": "network-egress",
     "relevance": "core", "verified_by": "arxiv_api", "verified": True,
     "source_queries": ["cat:cs.CR egress"], "overlap_user_work": "none"},
    # Same cite key as the record above - must be disambiguated, not silently overwritten.
    {"key": "chen2026agent", "title": "Runtime Monitors for Tool Calls", "authors": ["B Chen"],
     "year": 2026, "arxiv_id": None, "doi": "10.1109/TDSC.2026.00007",
     "venue": "IEEE Transactions on Dependable and Secure Computing", "venue_short": "TDSC",
     "peer_reviewed": True, "abstract": "A monitor...", "url": None, "track": "mechanism",
     "facet": "runtime-monitor", "relevance": "related", "verified_by": "crossref",
     "verified": True, "source_queries": ["tdsc monitor"], "overlap_user_work": "none"},
    {"key": "old2019offtopic", "title": "Off Topic Paper", "authors": ["C Old"], "year": 2019,
     "arxiv_id": None, "doi": "10.1145/zzz", "venue": "Journal of Nothing", "venue_short": "other",
     "peer_reviewed": True, "abstract": None, "url": None, "track": "mechanism", "facet": "metric",
     "relevance": "background", "verified_by": "openalex", "verified": True,
     "source_queries": ["q-off"], "overlap_user_work": "none",
     "status": "excluded(outside the year window)"},
]

CHECKS = []


def check(name, cond):
    CHECKS.append((name, bool(cond)))


def run(script, *args):
    r = subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("%s failed:\n%s%s" % (script, r.stdout, r.stderr))
    return r


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        tracks = tmp / "tracks"
        tracks.mkdir()
        for stem, rows in (("policy", TRACK_A), ("mechanism", TRACK_B)):
            (tracks / (stem + ".json")).write_text(
                json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

        corpus, funnel = tmp / "corpus.json", tmp / "funnel.md"
        run("merge_corpus.py", tracks, "-o", corpus, "--funnel", funnel)
        recs = json.loads(corpus.read_text(encoding="utf-8"))
        report = funnel.read_text(encoding="utf-8")
        by_tier = {}
        for r in recs:
            by_tier.setdefault(r["tier"], r)

        check("8 input rows collapse to 6 records", len(recs) == 6)

        dup = [r for r in recs if r["title"].startswith("A Layered")]
        check("preprint + published merge on normalized title", len(dup) == 1)
        check("published version wins the merge", dup and dup[0]["peer_reviewed"] is True)
        check("arXiv id is carried onto the published record",
              dup and dup[0]["arxiv_id"] == "2503.18813")
        check("DOI is carried onto the merged record",
              dup and dup[0]["doi"] == "10.1109/SP.2026.00042")
        check("merged record credits both tracks",
              dup and dup[0]["tracks"] == ["mechanism", "policy"])
        check("facets from both tracks are unioned",
              dup and dup[0]["facets"] == ["policy-language", "syscall-filter"])
        check("best relevance across copies wins", dup and dup[0]["relevance"] == "core")
        check("source_queries are unioned for provenance",
              dup and len(dup[0]["source_queries"]) == 2)
        check("verified_by records every source that confirmed it",
              dup and sorted(dup[0]["verified_by"]) == ["arxiv_api", "s2"])
        check("overlap with own work survives the merge",
              dup and dup[0]["overlap_user_work"] == "PROJ-A")

        check("DOI duplicate across tracks merges",
              sum(1 for r in recs if r["title"].startswith("Sandboxing")) == 1)
        check("S&P alias resolves to tier A1", by_tier.get("A1", {}).get("venue_short") == "S&P")
        check("TDSC resolves to tier J", by_tier.get("J", {}).get("venue_short") == "TDSC")
        check("preprint with no published version stays tier P",
              by_tier.get("P", {}).get("venue_short") == "arXiv")
        check("record with no venue evidence lands in tier ?", "?" in by_tier)

        unver = [r for r in recs if not r.get("verified")]
        check("unverified record is kept, not dropped", len(unver) == 1)
        check("unverified record keeps its explanatory note",
              unver and "no API hit" in (unver[0].get("note") or ""))
        check("missing venue evidence is flagged in the report", "no venue evidence" in report)

        check("excluded record drops out of the screened count", "| After screening | 5 |" in report)
        check("included counts only verified, non-excluded records",
              "| **Included (verified)** | **4** |" in report)
        check("relevance breakdown is reported", "| 3 / 1 / 0 |" in report)
        check("preprint split is reported", "peer-reviewed / preprint-only | 3 / 1 |" in report)
        check("cross-track overlap is reported", "more than one track: **2**" in report)
        check("facet histogram is reported", "## Facet (included)" in report)
        check("own-work overlap is surfaced in the report", "PROJ-A" in report)

        # Re-running on merged output must be a no-op; this pipeline gets re-run constantly.
        again = tmp / "t2"
        again.mkdir()
        (again / "merged.json").write_text(corpus.read_text(encoding="utf-8"), encoding="utf-8")
        run("merge_corpus.py", again, "-o", tmp / "c2.json", "--funnel", tmp / "f2.md")
        check("merge is idempotent",
              len(json.loads((tmp / "c2.json").read_text(encoding="utf-8"))) == len(recs))

        bib_path = tmp / "refs.bib"
        run("make_bib.py", corpus, "-o", bib_path)
        bib = bib_path.read_text(encoding="utf-8")
        check("unverified record never reaches refs.bib", "ghost2025unknown" not in bib)
        check("exclusion of unverified records is stated in the file header",
              "unverified record(s) excluded" in bib)
        check("conference paper becomes @inproceedings", "@inproceedings{doe2024sandbox" in bib)
        check("journal paper becomes @article", "@article{" in bib and "TDSC" not in bib.split(
            "@article{")[1].split("journal")[0])
        check("preprint becomes @misc with eprint", "@misc{" in bib and "eprint" in bib)
        check("LaTeX special character is escaped", r"Sandboxing Everything \& Friends" in bib)
        check("title braces protect capitalisation", "title          = {{" in bib)
        check("duplicate cite keys are disambiguated",
              "{chen2026agent," in bib and "{chen2026agenta," in bib)

        run("make_bib.py", corpus, "-o", tmp / "all.bib", "--all")
        allbib = (tmp / "all.bib").read_text(encoding="utf-8")
        check("--all includes unverified records, marked", "ghost2025unknown" in allbib
              and "UNVERIFIED" in allbib)

        csv_path = tmp / "corpus.csv"
        run("make_table.py", corpus, "-o", csv_path)
        head, *body = csv_path.read_text(encoding="utf-8-sig").splitlines()
        check("table header carries the annotation columns",
              all(c in head for c in ("threat_model", "mechanism", "evaluation", "limitations")))
        check("table has one row per record", len(body) == len(recs))
        check("annotation columns come out empty for the reader to fill",
              head.split(",").index("mechanism") >= 0
              and body[0].split(",")[head.split(",").index("mechanism")] == "")

    failed = [n for n, ok in CHECKS if not ok]
    for name, ok in CHECKS:
        print(("  ok   " if ok else "  FAIL ") + name)
    print("\n%d/%d passed" % (len(CHECKS) - len(failed), len(CHECKS)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
