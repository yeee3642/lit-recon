# lit-recon

A [Claude Code](https://claude.com/claude-code) skill that takes a paper from *"what should this be
about"* to a defensible corpus and topic proposal, as a **gated pipeline** rather than a brainstorm.

Twelve stages, each with an exit condition. The gates exist because the cheap failures all happen
early and stay invisible until review, and they come in two shapes:

1. **You missed something.** A reviewer names the paper that already did your thing and the
   contribution claim dies. Keyword search is bad at this — the paper that scooped you probably used
   different words. One proposal's "first / no prior work" claim was refuted by **64 arXiv preprints**
   the search had excluded for not being peer-reviewed.
2. **You cited something that isn't quite real.** Wrong venue, wrong authors, a DOI that resolves to a
   different paper, an arXiv ID that was plausible and wrong. One bad citation costs the reviewer's
   trust for every other claim. An audited batch of model-written citations ran **82% bad**.

A topic that dies at the collision check cost a week. The same topic dying in review costs the cycle
— and a novelty claim a reviewer has already refuted cannot be resubmitted.

You can enter at any stage. Stages 1–2 stand alone when all you want is a related-work chapter, a
citation audit or a venue count.

## The one rule that gets broken under pressure

**No title, no method name, no subsystem name until the collision check has cleared.**

Naming a thing makes it feel decided. Once there is a title, every later stage quietly becomes an
argument for keeping it, and the collision check degrades into a formality it was supposed to be a
veto on. When someone pushes for a name early — and they will — hand over the numbered candidate list
instead. It is the more useful artifact, because it is still falsifiable.

## Install

```bash
git clone https://github.com/yeee3642/lit-recon.git ~/.claude/skills/lit-recon
```

Or install `dist/lit-recon.skill` through the Claude desktop app. Then `/lit-recon`, or just describe
the problem ("訂題目", "文獻檢索", "is this worth a paper", "what should my paper be about").

## Pipeline

| # | Stage | Gate — do not proceed until |
|---|---|---|
| 0 | Fix the constraints | venue, compute, prior work to avoid all settled |
| 1 | Retrieve | every record has API or official-page evidence |
| 2 | Merge, dedupe, re-verify | unverified records out of the main table |
| 3 | Venue acceptance analysis | every statistic reproducible from the attached table |
| 4 | Competitor survey | every competitor has a re-runnability verdict with reasons |
| 5 | List candidates | each states what it would do and its nearest existing work |
| 6 | Collision check | every sub-claim individually adjudicated |
| 7 | Score and choose | weights and per-cell reasons written down |
| 8 | Name | name-collision search clean |
| 9 | Align the design to the thresholds | every stage-3 threshold has a matching design decision |
| 10 | Independent review | every BLOCKER resolved, with a record of how |
| 11 | Deliver and maintain | collision queries scheduled for weekly re-run |

## Harness-agnostic

The method needs four things: HTTP, JSON/XML parsing, somewhere to write a file, and a way to run
tracks. Subagents and a shell are nice; stdlib `urllib` in one sandboxed kernel with 1.7 GB of RAM is
enough. `references/harness.md` covers that case specifically — a copy-pasteable stdlib client with
the right backoff ladder, the Atom namespace handling arXiv requires, low-memory kernel behaviour,
credential brokers, the token arithmetic for budgeted screening, and a mapping between Claude Science
bindings and Claude Code equivalents.

Scripts are stdlib-only Python 3 — no pandas, no requests — so they run in a constrained kernel or
over ssh on a box you cannot install onto. `--xlsx` optionally uses openpyxl and degrades to CSV.

## What's in it

| File | Contents |
|---|---|
| `SKILL.md` | The pipeline, the gates, the three rules that apply everywhere, the trap table |
| `references/retrieval.md` | Stages 1–2: track splitting, brief template, record schema, the four verification gates, screening, merge |
| `references/sources.md` | Per-API cookbook — endpoints, syntax, field paths, backoff, the verification ladder |
| `references/venues.md` | `venue_short` vocabulary, tiers, alias normalisation, per-year venue counting |
| `references/venue-thresholds.md` | Stage 3: acceptance corpus and reproducible statistics |
| `references/collision-check.md` | Stage 6: query matrix, the four mandatory sources, verdict and wording rules |
| `references/stages.md` | Stages 0, 4, 5, 7–11: record schemas, formats, deliverables |
| `references/harness.md` | Tool bindings, constrained runtimes, screening budget, pacing |
| `scripts/merge_corpus.py` | Dedupe across tracks, assign venue + tier, emit the funnel |
| `scripts/make_bib.py` | → `refs.bib`, with unverified records barred by default |
| `scripts/make_table.py` | → CSV/xlsx reading table, annotation columns left empty |
| `scripts/venue_stats.py` | Threshold summary with every figure's filter and denominator attached |
| `scripts/collision_watch.py` | Re-run a saved query matrix, report only what is new |
| `tests/` | 62 checks; the network portion skips cleanly when offline |

## Ideas worth stealing even if you don't use the skill

**Nothing from memory.** Every identifier, author list and venue traces to a response you actually
received. Reconstructed ones come out *plausible and wrong*, which is worse than missing — so look up
even the papers you are certain you know. `make_bib.py` enforces this where it matters: unverified
records cannot reach `refs.bib` without an explicit `--all`.

**Collision-check sub-claims, not candidates.** A whole candidate is rarely already done; its parts
are, in different papers, and the honest novelty is what's left. "Sub-claims A and C exist, B does
not" tells you where to put the contribution. "The candidate is novel" tells you nothing and will not
survive a reviewer.

**Search your own bibliography.** The nearest work is usually already in the corpus you built — you
collected it, screened it as merely *related*, and never connected it to the candidate. Of the four
mandatory collision sources, this is the one people skip and the one that most often catches the
collision.

**Every number carries its filter and denominator.** Not "median 4 baselines" but "median 4 (IQR 3–6),
n=31 defense-system papers read in full". A number whose selection cannot be recomputed from the
attached table reads as invented even when it is right — and *unreproducible* draws the same reviewer
response as *wrong*. `venue_stats.py` makes it awkward to quote a bare number.

**Split tracks so they still share a boundary.** If no paper is ever found by two tracks, the cuts
were too narrow — that is a recall problem dressed as tidiness. `merge_corpus.py` reports the
cross-track count for exactly this reason.

## Wording that costs you the paper

Never write **"first"** or **"no prior work exists"**. Write what you actually did:

> Not found as of 2026-10-09 across 17 queries spanning arXiv (last 90 days), OpenAlex, vendor
> advisories and our own 287-record corpus.

Losing that claim costs more than the claim: it demonstrates the search was inadequate, which puts
every other number in the paper in question. There is no version of the sentence that is safe because
you looked hard — a reviewer needs one paper.

## License

MIT. See [LICENSE](LICENSE).
