#!/usr/bin/env python3
"""Acceptance-threshold summary from an annotated accepted-papers table.

    python venue_stats.py accepted_papers.csv -o acceptance_patterns.md

Every figure is printed with the filter and the denominator that produced it, because a number whose
selection cannot be recomputed from the attached table reads as invented even when it is right - and
"unreproducible" draws the same reviewer response as "wrong".

Expects the stage-3 annotation columns (see references/venue-thresholds.md). Missing columns are
reported rather than silently treated as empty, since a quietly absent column turns into a quietly
wrong median.

Stdlib only - no pandas, so this runs in a constrained kernel.
"""

import argparse
import csv
import pathlib
import sys
from collections import Counter

NEEDED = ["year", "contribution_type", "in_core_set", "fulltext_read", "n_baselines",
          "n_systems_evaluated", "adaptive_attack", "overhead_measured", "real_world",
          "artifact", "evidence", "defense_layer", "target"]
METHOD_TYPES = {"defense-system", "detection"}
TRUTHY = {"1", "true", "t", "yes", "y"}


def truthy(v):
    return str(v or "").strip().lower() in TRUTHY


def num(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def quantile(xs, q):
    """Linear-interpolation quantile, matching numpy/pandas default so figures agree."""
    if not xs:
        return None
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    pos = (len(s) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def fmt(x):
    if x is None:
        return "n/a"
    return str(int(x)) if float(x).is_integer() else "%.1f" % x


def rate(rows, col, want="yes"):
    """Share of rows whose column equals `want`, ignoring blanks - blanks are 'not annotated',
    which is different from 'no' and must not be counted as a denominator."""
    vals = [str(r.get(col) or "").strip().lower() for r in rows]
    known = [v for v in vals if v]
    if not known:
        return None, 0, 0
    hit = sum(1 for v in known if v == want)
    return hit / len(known), hit, len(known)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("table")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--venue", default=None, help="venue name for the report header")
    args = ap.parse_args()

    with open(args.table, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        sys.exit("%s has no rows" % args.table)

    missing = [c for c in NEEDED if c not in rows[0]]
    all_n = len(rows)
    core = [r for r in rows if truthy(r.get("in_core_set"))]
    method = [r for r in core if (r.get("contribution_type") or "").strip() in METHOD_TYPES]
    read = [r for r in method if truthy(r.get("fulltext_read"))]
    unread = [r for r in method if not truthy(r.get("fulltext_read"))]

    L = ["# Acceptance patterns%s" % ((" - " + args.venue) if args.venue else ""), "",
         "Source table: `%s`, %d rows." % (pathlib.Path(args.table).name, all_n), ""]

    if missing:
        L += ["> ⚠ Missing annotation column(s): `%s`. Figures depending on them are absent, not "
              "zero." % "`, `".join(missing), ""]

    L += ["## Population", "",
          "| Set | Filter | n |", "|---|---|---|",
          "| All rows | - | %d |" % all_n,
          "| Core set | `in_core_set` | %d |" % len(core),
          "| Method papers | core AND `contribution_type` in %s | %d |"
          % (sorted(METHOD_TYPES), len(method)),
          "| …read in full | AND `fulltext_read` | %d |" % len(read),
          "| …abstract/title only | AND NOT `fulltext_read` | %d |" % len(unread), ""]

    # --- thresholds, from full-text papers only -------------------------------------------------
    L += ["## Evaluation thresholds", "",
          "Computed over **method papers read in full** (n=%d). Abstract-only papers are reported "
          "separately below and never pooled: reading only the abstract systematically undercounts "
          "baselines, so pooling drags the median down and you design an under-powered evaluation "
          "against it." % len(read), "",
          "| Threshold | Value | Filter | n |", "|---|---|---|---|"]

    for label, col in (("Baselines compared", "n_baselines"),
                       ("Systems evaluated", "n_systems_evaluated")):
        xs = [v for v in (num(r.get(col)) for r in read) if v is not None]
        L.append("| %s (median, IQR) | %s (%s–%s) | method AND fulltext_read AND `%s` numeric | %d |"
                 % (label, fmt(quantile(xs, .5)), fmt(quantile(xs, .25)),
                    fmt(quantile(xs, .75)), col, len(xs)))

    for label, col in (("Adaptive / stress testing", "adaptive_attack"),
                       ("Overhead measured", "overhead_measured"),
                       ("Real-world component", "real_world"),
                       ("Artifact released", "artifact")):
        r_, hit, den = rate(read, col)
        L.append("| %s | %s | method AND fulltext_read AND `%s` annotated | %d/%d |"
                 % (label, "n/a" if r_ is None else "%.0f%%" % (100 * r_), col, hit, den))
    L.append("")

    if unread:
        xs = [v for v in (num(r.get("n_baselines")) for r in unread) if v is not None]
        if xs:
            L += ["Abstract/title-only method papers, for comparison: baselines median %s "
                  "(n=%d). If this sits well below the full-text median, that gap is the reading "
                  "bias, not a trend." % (fmt(quantile(xs, .5)), len(xs)), ""]

    # --- distributions --------------------------------------------------------------------------
    L += ["## Contribution types (core set, n=%d)" % len(core), "",
          "| Type | n |", "|---|---|"]
    L += ["| %s | %d |" % (t or "(blank)", n)
          for t, n in Counter((r.get("contribution_type") or "").strip() for r in core).most_common()]

    years = Counter((r.get("year") or "").strip() for r in core)
    L += ["", "## Per year (core set)", "", "| Year | n |", "|---|---|"]
    L += ["| %s | %d |" % (y or "(blank)", years[y]) for y in sorted(years)]
    L += ["", "⚠ The most recent year is partial unless its proceedings are closed. Say so, or a "
              "trend line is an artifact of the calendar.", ""]

    # --- thin regions: where candidates come from -----------------------------------------------
    L += ["## Layer × target (core set)", "",
          "Cells with few precedents are where stage-5 candidates come from - **after** you decide "
          "whether the venue has not seen that work yet (an opening, confirmed by preprints piling "
          "up) or does not take it (a wall). The tell: if the venue accepts that contribution type "
          "on *other* targets, it is an opening.", "",
          "| Layer | Target | n |", "|---|---|---|"]
    cells = Counter(((r.get("defense_layer") or "").strip(), (r.get("target") or "").strip())
                    for r in core)
    L += ["| %s | %s | %d |" % (a or "(blank)", b or "(blank)", n)
          for (a, b), n in sorted(cells.items(), key=lambda kv: -kv[1])]

    ev = Counter((r.get("evidence") or "").strip() for r in core)
    L += ["", "## Coverage", "", "| Evidence route | n |", "|---|---|"]
    L += ["| %s | %d |" % (e or "(blank)", ev[e]) for e in sorted(ev)]
    L += ["", "Routes differ in what they can support: `title` rows cannot contribute to any "
              "evaluation threshold. Keep this table attached to every statistic quoted above.", ""]

    report = "\n".join(L) + "\n"
    if args.out:
        pathlib.Path(args.out).write_text(report, encoding="utf-8")
        print("%d rows -> %s" % (all_n, args.out))
    else:
        print(report)
    if missing:
        print("missing column(s): %s" % ", ".join(missing), file=sys.stderr)


if __name__ == "__main__":
    main()
