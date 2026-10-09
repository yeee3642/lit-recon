#!/usr/bin/env python3
"""Smoke test for venue_stats.py and collision_watch.py. Self-contained fixtures in a temp dir.

    python tests/test_scripts.py
    python tests/test_scripts.py --no-network     # skip the live arXiv portion

The venue_stats checks are offline and strict - they pin the exact medians, IQRs and denominators,
because the whole point of that script is that its numbers are recomputable. The collision_watch
check needs arXiv and is reported as SKIP, not FAIL, when the network is unavailable.
"""

import argparse
import csv
import json
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"

COLS = ["key", "year", "contribution_type", "in_core_set", "fulltext_read", "n_baselines",
        "n_systems_evaluated", "adaptive_attack", "overhead_measured", "real_world",
        "artifact", "evidence", "defense_layer", "target"]

ROWS = [
    # core, method, read in full  -> these three drive every threshold
    ["p1", "2025", "defense-system", "1", "1", "4", "3", "yes", "yes", "no", "yes",
     "fulltext", "kernel", "A"],
    ["p2", "2025", "defense-system", "1", "1", "6", "5", "no", "yes", "yes", "no",
     "fulltext", "kernel", "A"],
    ["p3", "2025", "detection", "1", "1", "2", "1", "yes", "no", "no", "yes",
     "fulltext", "runtime", "B"],
    # core, method, NOT read in full -> must be reported separately, never pooled
    ["p4", "2026", "defense-system", "1", "0", "1", "1", "no", "no", "no", "no",
     "abstract", "runtime", "B"],
    # core, not a method paper
    ["p5", "2024", "attack", "1", "0", "", "", "", "", "", "", "title", "", "C"],
    # not in the core set at all
    ["p6", "2024", "benchmark", "0", "0", "9", "9", "yes", "yes", "yes", "yes",
     "fulltext", "kernel", "A"],
    # core, method, read, but several annotations blank -> blanks are "not annotated", and must
    # leave the denominator rather than counting as "no"
    ["p7", "2026", "defense-system", "1", "1", "", "", "", "yes", "", "",
     "fulltext", "kernel", "A"],
]

CHECKS = []


def check(name, cond, note=""):
    CHECKS.append((name, "ok" if cond else "FAIL", note))


def skip(name, note):
    CHECKS.append((name, "skip", note))


def run(script, *args, expect_ok=True):
    r = subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)],
                       capture_output=True, text=True)
    if expect_ok and r.returncode != 0:
        sys.exit("%s failed:\n%s%s" % (script, r.stdout, r.stderr))
    return r


def test_venue_stats(tmp):
    table = tmp / "accepted.csv"
    with open(table, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(COLS)
        w.writerows(ROWS)

    out = tmp / "patterns.md"
    run("venue_stats.py", table, "-o", out, "--venue", "TESTCONF")
    md = out.read_text(encoding="utf-8")

    check("header names the venue", "Acceptance patterns - TESTCONF" in md)
    check("all-rows denominator", "| All rows | - | 7 |" in md)
    check("core-set denominator", "| Core set | `in_core_set` | 6 |" in md)
    check("method-paper denominator",
          "'defense-system', 'detection'] | 5 |" in md.replace('"', "'"))
    check("full-text subset counted", "| …read in full | AND `fulltext_read` | 4 |" in md)
    check("abstract-only subset counted separately",
          "| …abstract/title only | AND NOT `fulltext_read` | 1 |" in md)

    # baselines over the three full-text method papers with a numeric value: [2,4,6]
    check("baseline median and IQR computed over full-text papers only",
          "| Baselines compared (median, IQR) | 4 (3–5) |" in md)
    check("baseline figure carries its own denominator",
          "`n_baselines` numeric | 3 |" in md)
    # systems evaluated: [3,5,1] -> median 3, IQR 2-4
    check("systems-evaluated median and IQR", "| Systems evaluated (median, IQR) | 3 (2–4) |" in md)

    # adaptive_attack over full-text method papers: yes,no,yes,(blank) -> 2/3
    check("blank annotations leave the denominator", "| 2/3 |" in md and "Adaptive" in md)
    # overhead_measured: yes,yes,no,yes -> 3/4 = 75%
    check("rate with a full denominator", "| Overhead measured | 75% | " in md
          and "| 3/4 |" in md)

    check("abstract-only baselines reported for comparison, not pooled",
          "Abstract/title-only method papers" in md and "median 1" in md)
    check("reading-bias warning is stated", "that gap is the reading bias" in md)
    check("partial-year warning is stated", "most recent year is partial" in md)
    check("layer x target table present for finding thin regions", "## Layer × target" in md)
    check("opening-versus-wall distinction is spelled out", "it is an opening" in md)
    check("coverage-route table present", "| Evidence route | n |" in md)
    check("title-only rows excluded from thresholds in writing",
          "`title` rows cannot contribute to any evaluation threshold" in md)

    # a missing annotation column must be reported, not silently treated as empty
    thin = tmp / "thin.csv"
    keep = [c for c in COLS if c != "artifact"]
    with open(thin, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(keep)
        w.writerow([ROWS[0][COLS.index(c)] for c in keep])
    r = run("venue_stats.py", thin, "-o", tmp / "thin.md")
    thin_md = (tmp / "thin.md").read_text(encoding="utf-8")
    check("missing column is reported, not assumed empty",
          "Missing annotation column(s): `artifact`" in thin_md
          and "absent, not zero" in thin_md)
    check("missing column also goes to stderr", "artifact" in r.stderr)


def test_collision_watch(tmp, network):
    matrix = tmp / "matrix.json"
    matrix.write_text(json.dumps({
        "project": "testproj",
        "matrix": [{"candidate": "C1", "sub_claim": "A-1",
                    "arxiv": 'abs:"prompt injection" AND abs:agent'}]}, ensure_ascii=False),
        encoding="utf-8")

    if not network:
        skip("collision_watch baseline run", "network disabled")
        skip("collision_watch reports only new hits", "network disabled")
        skip("collision_watch wording support line", "network disabled")
        return

    out1 = tmp / "r1.md"
    r = run("collision_watch.py", matrix, "-o", out1, "--limit", "10", expect_ok=False)
    if r.returncode != 0:
        skip("collision_watch baseline run", "arXiv unreachable: %s" % r.stderr.strip()[-120:])
        skip("collision_watch reports only new hits", "arXiv unreachable")
        skip("collision_watch wording support line", "arXiv unreachable")
        return

    md1 = out1.read_text(encoding="utf-8")
    state_path = matrix.with_suffix(".state.json")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    ids = state.get("C1/A-1", [])
    check("collision_watch baseline run", "**Baseline run.**" in md1 and len(ids) > 0,
          "%d ids recorded" % len(ids))
    check("collision_watch wording support line",
          "It does not support" in md1 and '"first"' in md1)

    # forget one id; the next run must surface exactly that one as new
    dropped = ids[0]
    state["C1/A-1"] = ids[1:]
    state_path.write_text(json.dumps(state), encoding="utf-8")
    out2 = tmp / "r2.md"
    run("collision_watch.py", matrix, "-o", out2, "--limit", "10")
    md2 = out2.read_text(encoding="utf-8")
    check("collision_watch reports only new hits",
          "New since last run: **1**" in md2 and dropped in md2
          and "**Baseline run.**" not in md2, dropped)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-network", action="store_true")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        test_venue_stats(tmp)
        test_collision_watch(tmp, network=not args.no_network)

    failed = [n for n, s, _ in CHECKS if s == "FAIL"]
    skipped = [n for n, s, _ in CHECKS if s == "skip"]
    for name, status, note in CHECKS:
        tag = {"ok": "  ok   ", "FAIL": "  FAIL ", "skip": "  skip "}[status]
        print(tag + name + (("  (%s)" % note) if note else ""))
    print("\n%d passed, %d failed, %d skipped"
          % (len(CHECKS) - len(failed) - len(skipped), len(failed), len(skipped)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
