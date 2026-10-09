---
name: lit-recon
description: >
  One gated pipeline from "what should this paper be about" to a defensible corpus and topic
  proposal: fix the constraints, retrieve across arXiv / Semantic Scholar / Crossref / OpenAlex with
  every record backed by an API response, measure what the target venue actually accepts and how hard
  its evaluations are, survey the competitors, list unnamed candidates, collision-check every
  sub-claim, score, only then name, align the experiment design to the measured thresholds, take an
  adversarial review. Use for "訂題目", "選題", "文獻檢索", "related work", "第二章", "撞題檢查",
  "撞名", "題名怎麼取", "候選題目", "對手調查", "baseline 要比誰", "錄取門檻", "收論文", "survey",
  "novelty check", "有沒有人做過", "這個題目投得上嗎", "what should my paper be about", "is this
  worth a paper", "scope my thesis chapter", "count how many TDSC/TIFS/S&P papers did X" — also when
  a reviewer refuted a "no prior work" claim, or a draft's citations need checking for existence,
  venue and authors. Not for CVE or advisory dup checks; those are bounty-hunt or zdi-bounty.
---

# Lit Recon

Choosing a topic and defending it is a **search problem with gates**. The gates exist because the
cheap failures all happen early and stay invisible until review, and they come in two shapes:

1. **You missed something.** A reviewer names the paper that already did your thing and the
   contribution claim dies. Keyword search is bad at this — the paper that scooped you probably used
   different words. One proposal's "first / no prior work" claim was refuted by **64 arXiv
   preprints** the search had excluded for not being peer-reviewed.
2. **You cited something that isn't quite real.** Wrong venue, wrong authors, a DOI that resolves to
   a different paper, an arXiv ID that was plausible and wrong. One bad citation costs the reviewer's
   trust for every other claim. An audited batch of model-written citations ran **82% bad**.

A topic that dies at stage 6 cost a week. The same topic dying in review costs the cycle — and a
novelty claim a reviewer has already refuted cannot be resubmitted. So every stage has an exit
condition. Do not carry a candidate past a gate it failed; carry fewer candidates instead.

You can enter at any stage. Stages 1–2 stand alone when all that is wanted is a related-work chapter,
a citation audit or a venue count.

## The one rule that gets broken under pressure

**No title, no method name, no subsystem name until the collision check (stage 6) has cleared.**

Naming a thing makes it feel decided. Once there is a title, every later stage quietly becomes an
argument for keeping it, and the collision check degrades into a formality it was supposed to be a
veto on. When the user pushes for a name before stage 6 — and they will — say *"candidates and
verdicts in progress"* and hand over the numbered candidate list instead. That is not stalling: the
candidate list is the more useful artifact, because it is still falsifiable.

## Three rules that apply at every stage

**Nothing from memory.** Every identifier, author list, venue and number traces to a response you
actually received. Reconstructed ones come out *plausible and wrong*, which is worse than missing.
Look up even the papers and seeds you are sure you know.

**Every number carries its filter and denominator.** Not "median 4 baselines" but "median 4 (IQR
3–6), n=31 defense-system papers read in full". A number whose selection cannot be recomputed from
the attached table reads as invented even when it is right — and *unreproducible* draws the same
reviewer response as *wrong*.

**"Could not find it" is never "does not exist."** Write *"not found as of \<date\> across N
queries"* and keep the queries. Never write "first", "no prior work" or "尚無工作". Losing that claim
costs more than the claim: it demonstrates the search was inadequate, which puts every other number
in question. There is no version of the sentence that is safe because you looked hard — a reviewer
needs one paper.

---

## Pipeline

| # | Stage | Produces | Gate — do not proceed until |
|---|---|---|---|
| 0 | [Fix the constraints](#stage-0--fix-the-constraints) | constraint list | venue, compute, prior work to avoid all settled |
| 1 | [Retrieve](#stages-12--retrieve-merge-re-verify) | per-track corpora | every record has API or official-page evidence |
| 2 | [Merge, dedupe, re-verify](#stages-12--retrieve-merge-re-verify) | master table, refs.bib, funnel | unverified records out of the main table |
| 3 | [Venue acceptance analysis](#stage-3--venue-acceptance-analysis) | accepted-paper table, thresholds | every statistic reproducible from the attached table |
| 4 | [Competitor survey](#stage-4--competitor-survey) | baseline table | every competitor has a re-runnability verdict with reasons |
| 5 | [List candidates](#stage-5--list-candidates) | 4–5 **unnamed** candidates | each states what it would do and its nearest existing work |
| 6 | [Collision check](#stage-6--collision-check) | collision table | every sub-claim individually adjudicated |
| 7 | [Score and choose](#stage-7--score-and-choose) | scoring table | weights and per-cell reasons written down |
| 8 | [Name](#stage-8--name) | title, method name, subsystem names | name-collision search clean |
| 9 | [Align the design](#stage-9--align-the-design-to-the-thresholds) | threshold→design table | every stage-3 threshold has a matching design decision |
| 10 | [Independent review](#stage-10--independent-review) | findings, revision | every BLOCKER resolved, with a record of how |
| 11 | [Deliver and maintain](#stage-11--deliver-and-maintain) | versioned artifacts | collision queries scheduled for weekly re-run |

Per-stage record schemas and output formats: `references/stages.md`. Tool bindings and constrained
runtimes: `references/harness.md`.

---

## Stage 0 — fix the constraints

Check memory first, then ask only what is missing, and ask it **all at once** — these answers change
the structure of everything downstream, so discovering one at stage 7 invalidates stages 3–6.

Minimum list: target venue and deadline · compute and privileges · commercial-API budget · the user's
own published **and in-review** work that must be avoided · writing preferences · the paper template.

Write it to memory immediately. A constraint that lives only in the conversation is a constraint the
next session will violate.

The most expensive omission is **the user's own prior work**. Self-overlap is invisible to every
external search in this pipeline — no API knows what someone has in review — and a reviewer familiar
with the author's record spots it at once. Ask for in-review work explicitly; people do not volunteer
it because it is not public yet.

## Stages 1–2 — retrieve, merge, re-verify

The full method is `references/retrieval.md`: how to split tracks, how to brief a track agent, the
record schema, the four verification gates, screening levels, and the merge.

The compressed version. Split 2–4 tracks by **what a paper does**, not by keyword, each with its own
seeds and a closed facet vocabulary. Every track runs both a keyword sweep *and* citation chasing in
both directions from its seeds — the second is where differently-worded work comes from, and forward
citations of a two-to-three-year-old seed is the highest-yield query in the whole method. The four
gates: **evidence** (nothing from memory, unfound → `verified: false` with a reason), **preprint→venue
upgrade** before citing anything, **frontier** (current-year preprints are in, tagged — their absence
is what refuted that "first" claim), and **venue priority** for reading order.

```bash
python scripts/merge_corpus.py lit/tracks/ -o lit/corpus.json --funnel lit/funnel.md
python scripts/make_bib.py    lit/corpus.json -o lit/refs.bib
python scripts/make_table.py  lit/corpus.json -o lit/corpus.xlsx --xlsx
```

Dedupe must include normalised title: the arXiv and proceedings versions of one paper share no
identifier, so ID-only dedupe double-counts your best-known papers and every downstream number
inherits it. `make_bib.py` bars unverified records unless `--all` — the one boundary where a
plausible-but-wrong citation would reach a submission.

## Stage 3 — venue acceptance analysis

Two numbers decide the rest of the paper: what **kinds** of contribution the venue accepts, and how
hard its **evaluations** are. Guessing either produces a topic that is interesting and unpublishable.

Build the acceptance corpus, annotate contribution type and evaluation shape, compute the thresholds.
Procedure and the reproducibility requirements: `references/venue-thresholds.md`.
`scripts/venue_stats.py` prints each figure with its filter and denominator attached.

Two things make these numbers defensible: the universal rule about filters and denominators above,
and — specific to this stage — **abstract-only reading systematically undercounts baselines**, so
papers you did not read in full are counted separately and never pooled. Pool them and the median
drags down, and you will design an under-powered evaluation against it.

Few precedents in a region means one of two things that look identical in the data: the venue **has
not seen** work there (an opening, confirmed by preprints piling up) or **does not take** it (a wall,
which quality cannot fix). The tell is adjacent — if the venue accepts that contribution *type* on
other targets, it is an opening.

## Stage 4 — competitor survey

Per competitor: what it does, threat model, whether code exists, licence, last commit, and the field
that matters — **whether you can actually run it here, with the reason**. Fields in
`references/stages.md`.

A re-runnability verdict is an inference; label it as one, and say why. "no — needs 4×A100, we have
one GPU" is usable by a future session; "no" is not. A competitor with no public implementation can
only be **cited**, never reproduced, and the experiment design has to say so rather than assuming a
number will materialise three weeks before a deadline. Per candidate, name the 3–5 you must beat and
why you must.

## Stage 5 — list candidates

Candidates come from the intersection of three things you now have: the gaps the retrieval tracks
reported, the regions where the venue has few precedents **but preprints are accumulating**, and the
cases each competitor explicitly does not handle.

Per candidate: *number / one sentence on what it would do / threat model or problem setting / the 3
nearest papers / how it differs from each / data and compute needed.*

Four to five. Fewer means the earlier stages were too narrow; more means stage 6 gets done shallowly
for all of them, which is worse than doing it properly for four. **No names** — not even a working
codename, which becomes the method name by stage 8 through pure inertia.

## Stage 6 — collision check

The highest-stakes stage and the one most often done in a way that cannot fail. Break each
candidate's core claim into 2–4 **sub-claims** and query each with 3–5 differently-worded searches
across five vocabulary axes. Full procedure, verdicts and wording rules:
`references/collision-check.md`.

Why sub-claims: a whole candidate is rarely already done — its *parts* are, in different papers, and
the honest novelty is what is left. "A and C exist, B does not" tells you where to put the
contribution; "the candidate is novel" tells you nothing and will not survive a reviewer.

Four mandatory sources, each catching what the others structurally cannot: **arXiv** (last 90 days
read closely), **OpenAlex** (published and adjacent fields), **web search** (industry blogs, CVEs,
advisories, vendor docs — a disclosure rarely makes your *method* unoriginal but can make the
*problem* no longer new, which is harder to argue with), and **your own master table**. That last one
is where the nearest work usually is: you collected it, screened it as merely `related`, and never
connected it to this candidate. A reviewer handed your own bibliography finds it in minutes.

Also ask whether the mechanism is **isomorphic to an older one in another field** — OS provenance
labelling, taint tracking, capability systems, reference monitors. Keyword search in your own field
will not find those and the citation graph often will not either. If it is, address it head-on and
make *why the old mechanism fails in the new setting* the design rationale; that reframing is usually
stronger than the novelty claim it replaces.

## Stage 7 — score and choose

| Criterion | Reads | Default weight |
|---|---|---|
| Novelty | the stage-6 verdicts, not your impression | 2 |
| Venue-precedent fit | contribution type and evaluation shape vs stage 3 | 1 |
| Competitor re-runnability | share of must-beat baselines runnable here | 1 |
| Feasibility | compute, privileges, data, commercial-API budget | 1 |
| Separation from own prior work | different object, interception point, attacker capability, dataset | 1 |
| Workload | higher score = cheaper | 1 |

Novelty is doubled because it is the only criterion that can zero the paper: a feasible, cheap,
well-scoped topic that is already occupied is worth nothing, while an awkward one that is genuinely
new is still a paper.

Write the reason for every cell. Candidates within 1 point of the winner are **not** rejected — they
are the extension paper or the next one; record them with their scores so the decision need not be
re-derived.

## Stage 8 — name

Title format: `<MethodName>: <what it does>`. Plain verb and object, no metaphor, no packaging. The
method name describes the mechanism; each subsystem name maps to one action (find, label, block,
mutate, attest, log). Avoid words close to the user's own prior subsystems — a reviewer who knows the
record reads it as the same system shipped twice.

```python
web_search(query='"<MethodName>" <field> paper')
```

Check subsystem names against system names in the related work too: two different systems with the
same name in one paper is a correction you make at proof stage, in a hurry.

**The title emphasises what the collision check found unoccupied** — not the most impressive part,
the part that is actually yours. A title describing a sub-claim that stage 6 marked as existing work
will be read as that work.

## Stage 9 — align the design to the thresholds

One row per stage-3 threshold with a matching design decision, so alignment is checkable rather than
asserted: baseline count ≥ the median with baselines enumerated and each marked reproduced or quoted;
systems evaluated ≥ the median at pinned versions; whether you do adaptive or stress testing and how;
overhead metrics **replicating at least one competitor's original workload** (numbers measured on
different workloads are not comparable and a reviewer who knows the baseline paper will say so); the
model and dataset mix; the real-world component; and the confounders you will fix or stratify.

Then draft the four load-bearing passages in the user's template with numbers marked
*[to be measured]*: abstract, third paragraph of the introduction, opening of the methods chapter,
end of the evaluation chapter. All four must use the same problem statement, method name and
subsystem names. Writing them in one sitting is a cheap consistency test — if they cannot be made to
agree, the topic is still vague, and that is far cheaper to learn here than after the experiments.

## Stage 10 — independent review

Delegate to a reviewer agent that has the deliverables and the supporting tables but **not** your
reasoning, and that edits nothing — it files findings at BLOCKER / MAJOR / MINOR with location,
evidence and suggested fix. Full prompt in `references/harness.md`.

Six jobs: verify every arXiv ID, DOI and URL exists and says what you claim; re-run the novelty
search independently with ≥10 differently-worded queries **and** search your master table; check
factual assertions against official sources; name the missing baselines, benchmarks and metrics
against the stage-3 thresholds; assess overlap with the user's own prior work; and flag metaphors,
inflated adjectives and any "first" claim.

Handling findings is where this stage earns its keep. **Recompute every BLOCKER yourself before
accepting or rebutting it** — "the statistics are not reproducible" means actually recomputing them.
If the numbers hold and only a column was missing, add the column and say that is what happened.
Accepting a wrong finding corrupts the proposal; waving away a right one is worse. A refuted novelty
claim is **withdrawn**, not softened, and the title and contribution list change with it. Append a
findings-disposition table to the proposal — that table is what makes the next reader trust the rest.

## Stage 11 — deliver and maintain

Version the artifacts (list in `references/stages.md`), then write the decision to memory **including
what was rejected and why**. The rejections are the valuable half: without them a future session
re-derives a dead direction from scratch, and the reasoning that killed it is written down nowhere
else.

```bash
python scripts/collision_watch.py lit/collision_matrix.json -o lit/new_hits.md
```

Schedule that weekly until the paper is submitted, and watch the authors of the nearest work directly,
not just their keywords. The window between choosing a topic and submitting is exactly when someone
else posts it.

---

## Traps

Source behaviour verified against live API responses; dated entries were checked on the date shown.

| Trap | Detail |
|---|---|
| **Naming before stage 6** | The collision check becomes a formality defending a decision already made |
| **Collision-checking only with new queries** | The nearest work is usually already in your own master table |
| **Formal venues only** | Recent preprints and industry disclosures are what most often refute novelty |
| **Ignoring the out-of-field precedent** | A reviewer from that field sees the isomorphism whether you mention it or not |
| **Losing subagents' deviation statements** | A number from partial coverage must carry that limit **everywhere it appears**, not once in an appendix |
| **Several agents on one scholarly API** | Rate limiting pushes you onto web paraphrases — weak evidence you must re-verify later |
| **Semantic Scholar 429s on a cold call** | Unauthenticated, the *first* request can 429 (2026-10-07). Backoff 2/4/8/16 s, one track owns S2, log every 429 |
| **OpenAlex `search=` is full-text** | `search=agent sandbox` → 27,561 hits; `filter=title_and_abstract.search:…` → 2,313 (2026-10-07). Use the filter |
| **OpenAlex under-covers security proceedings** | A low count there is not evidence about the literature |
| **OpenAlex returns repository deposits** | A top hit for one probe was a Zenodo upload. Check `primary_location.source.type` |
| **arXiv over plain `http://`** | Returned an empty body — no error, no results (2026-10-07). Use `https://` |
| **Crossref `offset` paging** | Unstable at proceedings volumes. Use `cursor`; fetch twice and union for reportable counts |
| **Missing abstracts are the source** | Crossref has none for most IEEE conference and much Elsevier content. Record `null`, backfill from S2, say so |
| **Crossref recall is thin** | A known-good title returned `total-results: 2`. It *confirms* a venue; it does not discover papers |
| **USENIX Security has no DOIs** | And is often outside a sandbox allowlist. Reach it via web search, record `verified_by: web_page` |
| **DBLP is bot-gated** | Don't attempt it. Take `externalIds.DBLP` from S2's `/paper/batch` |
| **"ML venues have no DOIs"** | False — NeurIPS resolves via proceedings.com (`10.52202/…`) |
| **`fetch_article_fulltext` 404** | Usually a new arXiv DOI not yet in Crossref, not a missing paper. Fall back to `arxiv.org/html/<id>v1` |
| **`web_search` batched with other calls** | Silently does not execute, and the silence looks like "no results" |
| **Dedupe by ID alone** | arXiv and proceedings versions share no identifier. Normalise titles |
| **A seed ID from memory** | Poisons every citation-chase hop built on it |
| **Zero results read as a gap** | Usually the vocabulary is wrong. Re-query from a seed's reference list first |

---

## Reference files

| File | Read when |
|---|---|
| `references/retrieval.md` | Stages 1–2: track splitting, the brief template, record schema, the four gates, screening, merge |
| `references/sources.md` | Before the first query — per-API cookbook, syntax, field paths, the verification ladder |
| `references/venues.md` | `venue_short` vocabulary, tiers, alias normalisation, per-year venue counting |
| `references/venue-thresholds.md` | Stage 3: acceptance corpus construction and reproducible statistics |
| `references/collision-check.md` | Stage 6: query matrix, the four sources, verdicts, wording |
| `references/stages.md` | Stages 0, 4, 5, 7–11: record schemas, formats, deliverable list |
| `references/harness.md` | Before delegating or writing requests — Claude Science bindings, Claude Code mapping, stdlib HTTP client, low-memory kernels, credentials, screening budget, pacing |

Cookbook entries were verified on the dates they carry. APIs drift: if a field path there disagrees
with what you receive, trust the response and fix the file. A skill that lies about its own sources is
the exact failure it exists to prevent.

## Checklist

- [ ] Venue, compute, commercial API, prior work (**including in-review**) and writing preferences in memory
- [ ] Every corpus record has evidence; current-year preprints systematically included
- [ ] Merge, dedupe, re-verification done; funnel and to-verify list published
- [ ] Acceptance corpus and thresholds done; statistics reproducible from the attached table
- [ ] Baseline table has re-runnability verdicts and per-candidate must-beat sets
- [ ] Each candidate collision-checked across arXiv (last 90 days), OpenAlex, industry/CVE, own table
- [ ] Scoring table has weights and per-cell reasons
- [ ] Title, method name and subsystem names name-collision checked
- [ ] Experiment design aligned threshold by threshold; four passages agree
- [ ] Every review BLOCKER resolved; disposition table appended
- [ ] Artifacts versioned; collision queries scheduled weekly
