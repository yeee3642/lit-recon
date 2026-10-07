#!/usr/bin/env python3
"""Smoke test for merge_corpus.py. Self-contained: builds its own fixtures in a temp dir.

    python tests/test_merge.py

Covers the cases that actually go wrong: the same paper arriving as a preprint in one track and a
proceedings paper in another (no shared identifier), a DOI-level duplicate, a record with no
evidence block, an explicitly excluded record, and a venue nothing in the alias table matches.
"""

import json
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
MERGE = HERE.parent / "scripts" / "merge_corpus.py"

TRACK_A = [
    # Same paper as the NeurIPS record below, but as a preprint: no shared ID, title-match only.
    {"id": "arxiv:2406.13352", "title": "AgentDojo: A Dynamic Environment to Evaluate Prompt "
     "Injection Attacks", "year": 2024, "venue_raw": "arXiv", "type": "preprint",
     "relevance": "related", "evidence": {"source": "arxiv", "query": "abs:AgentDojo"}},
    {"id": "doi:10.1109/SP.2024.00001", "title": "Sandboxing Everything", "year": 2024,
     "venue_raw": "2024 IEEE Symposium on Security and Privacy (SP)", "type": "conference",
     "relevance": "core", "evidence": {"source": "crossref", "query": "t"}},
    # No evidence block -> must be forced to unverified, not silently included.
    {"id": "s2:abc", "title": "Some Unverified Thing", "year": 2025, "venue_raw": "",
     "relevance": "background"},
]

TRACK_B = [
    {"id": "doi:10.52202/079017-2636", "title": "AgentDojo: A Dynamic Environment to Evaluate "
     "Prompt Injection Attacks", "year": 2024, "doi": "10.52202/079017-2636",
     "venue_raw": "Advances in Neural Information Processing Systems 37", "type": "conference",
     "relevance": "core", "evidence": {"source": "crossref", "query": "bib=AgentDojo"}},
    {"id": "doi:10.1109/SP.2024.00001", "title": "Sandboxing Everything (extended)", "year": 2024,
     "doi": "10.1109/SP.2024.00001", "venue_raw": "IEEE Symposium on Security and Privacy",
     "type": "conference", "relevance": "related", "evidence": {"source": "openalex", "query": "y"}},
    {"id": "arxiv:2501.99999", "title": "A Frontier Preprint On Agent Egress", "year": 2026,
     "venue_raw": "arXiv", "type": "preprint", "relevance": "core",
     "evidence": {"source": "arxiv", "query": "z"}},
    {"id": "doi:10.1145/zzz", "title": "Off Topic Paper", "year": 2019,
     "venue_raw": "Journal of Nothing", "type": "journal", "relevance": "background",
     "status": "excluded(out of window)", "evidence": {"source": "openalex", "query": "w"}},
]

CHECKS = []


def check(name, cond):
    CHECKS.append((name, bool(cond)))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        tracks = tmp / "tracks"
        tracks.mkdir()
        for stem, rows in (("isolation", TRACK_A), ("evaluation", TRACK_B)):
            (tracks / (stem + ".jsonl")).write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

        out, funnel = tmp / "corpus.jsonl", tmp / "funnel.md"
        r = subprocess.run([sys.executable, str(MERGE), str(tracks), "-o", str(out),
                            "--funnel", str(funnel)], capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit("merge_corpus.py failed:\n" + r.stdout + r.stderr)

        recs = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
        by_tier = {x["tier"]: x for x in recs}
        titles = {x["title"] for x in recs}
        report = funnel.read_text(encoding="utf-8")

        check("7 input rows collapse to 5 records", len(recs) == 5)

        dojo = [x for x in recs if x["title"].startswith("AgentDojo")]
        check("preprint + proceedings merge on normalized title", len(dojo) == 1)
        check("published version wins the merge", dojo and dojo[0]["venue"] == "NeurIPS")
        check("arXiv id survives as an alt_id", dojo and "arxiv:2406.13352" in dojo[0].get("alt_ids", []))
        check("merged record credits both tracks",
              dojo and sorted(dojo[0]["tracks"]) == ["evaluation", "isolation"])
        check("best relevance across merged copies wins", dojo and dojo[0]["relevance"] == "core")

        check("DOI duplicate across tracks merges", sum(
            1 for x in recs if x["title"].startswith("Sandboxing")) == 1)
        check("S&P alias resolves to tier A1", "A1" in by_tier and by_tier["A1"]["venue"] == "S&P")
        check("preprint with no published version stays tier P", "P" in by_tier)
        check("unmatched venue lands in tier C", "C" in by_tier)

        unver = [x for x in recs if x.get("status") == "unverified"]
        check("record with no evidence is forced to unverified", len(unver) == 1)
        check("unverified record is kept, not dropped", "Some Unverified Thing" in titles)
        check("unverified record is flagged in the report", "no evidence block" in report)

        check("excluded record drops out of the screened count", "| After screening | 4 |" in report)
        check("included count excludes both excluded and unverified",
              "| **Included** | **3** |" in report)
        check("cross-track overlap is reported", "more than one track: **2**" in report)

        # Re-running on the merged output must be a no-op; the pipeline gets re-run constantly.
        again = tmp / "t2"
        again.mkdir()
        (again / "merged.jsonl").write_text(out.read_text(encoding="utf-8"), encoding="utf-8")
        r2 = subprocess.run([sys.executable, str(MERGE), str(again), "-o", str(tmp / "c2.jsonl"),
                             "--funnel", str(tmp / "f2.md")], capture_output=True, text=True)
        recs2 = [json.loads(l) for l in (tmp / "c2.jsonl").read_text(encoding="utf-8").splitlines()]
        check("merge is idempotent", r2.returncode == 0 and len(recs2) == len(recs))

    failed = [n for n, ok in CHECKS if not ok]
    for name, ok in CHECKS:
        print(("  ok   " if ok else "  FAIL ") + name)
    print("\n%d/%d passed" % (len(CHECKS) - len(failed), len(CHECKS)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
