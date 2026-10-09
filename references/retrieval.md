# Retrieval: stages 1–2

Building the corpus. This is a **recall problem under an honesty constraint**, and it fails in two
directions — missing the paper that already did your thing, and citing something that isn't quite
real. Everything here pushes recall up and keeps every record traceable to a response that actually
came back.

Contents: [tracks](#split-tracks-by-question-not-by-keyword) · [seeds](#seeds) ·
[brief template](#briefing-a-track) · [record schema](#record-schema) · [the four gates](#the-four-gates) ·
[screening](#screening-rules-first-model-second) · [merge](#stage-2--merge-and-re-verify) ·
[deliverables](#deliverables)

API syntax and per-source traps: `sources.md`. Venue vocabulary: `venues.md`. Running this with
stdlib HTTP, a low-memory kernel or a token budget: `harness.md`.

---

## Split tracks by question, not by keyword

Keyword-split tracks overlap, double-count, and push the real thinking into the dedupe step. Split so
each track owns a different **thing a paper does**, give it its own seeds and its own facet
vocabulary, and each agent can hold one coherent model of its slice. Three to four tracks is usual.

Two tests for a good split: a paper should have one obvious home, and the tracks should still share a
*boundary* — if no paper is ever found by two tracks, the cuts were too narrow and you have a recall
problem dressed as tidiness. `merge_corpus.py` reports the cross-track count for exactly this reason.

A worked split by **defense layer**, which is a generally useful axis when the paper proposes a
mechanism — the thing that enforces, the thing that decides, and the thing that measures:

| Track | Owns | Facets |
|---|---|---|
| `mechanism` | The enforcement layer: how the boundary is implemented, the attack research that breaks it, and the classic systems work that is the chapter's baseline | `kernel-isolation` / `vm-isolation` / `language-runtime` / `syscall-filter` / `network-egress` / `escape-attack` |
| `policy` | The decision layer: what is allowed and who says so — policy languages, reference monitors, capability models, the permission model of the surrounding ecosystem | `policy-language` / `runtime-monitor` / `capability` / `permission-model` / `authorization-flow` |
| `evaluation` | Benchmarks and measurement, **recording how each one builds its execution environment**, plus per-year counts in the target venues | `benchmark` / `attack-corpus` / `metric` / `venue-count` |

The third track does two jobs on purpose: a benchmark paper is interesting once as related work and
once as something you may have to run against, so ask for its *environment construction*, not its
headline number. Its venue counts also feed stage 3.

### Facets

Facets subdivide a track; `relevance` rates a paper against your claim. They are orthogonal — a
`background` paper still gets a facet.

Keep each track's facet set **closed**, 4–6 values, and name them for *mechanisms* rather than topics.
`syscall-filter` and `runtime-monitor` describe something a paper does, so a paper lands in one.
`security`, `llm`, `evaluation` describe what it is about, and everything lands in all of them.

## Seeds

3–8 papers per track that you already trust. Seeds exist to feed citation chasing, which is where
differently-worded work comes from.

**Look the seeds up rather than writing their IDs.** A seed list with a hallucinated arXiv number
poisons every expansion built on it, and the expansion is the part you cannot audit by eye.

---

## Briefing a track

A track agent should never have to ask you a question. It gets one brief and returns a corpus file, a
notes file and a structured report. If it has to guess at the schema, the allowed sources, or what
counts as `core`, you get three tracks that cannot be merged.

About **85% of a brief is identical across tracks.** Write that once; per track you change only the
track name, seeds, facets, task description and scale target.

> Keep filled-in briefs out of version control if they name unpublished work. A brief listing your
> seeds, your facets and your target venue is a readable summary of your next paper.

### Skeleton

**1. Context (shared)** — the paper's topic in one sentence and the target venues; what this round is
for and what happens to the output next ("collection only; the main session merges, annotates and
selects" stops an agent editorialising or stopping early); and **today's date**, because agents reason
badly about "recent" without it.

**2. Runtime constraints (shared)** — state them as hard rules *with the reason attached*, or the
agent optimises around them. Which execution tool to use and which to avoid, memory ceiling, file
encoding, request pacing. Content in `harness.md`.

**3. Sources (shared)** — per source: endpoint, query syntax, auth, and the known failure. Lift from
`sources.md`. State explicitly which sources are **unreachable and must not be attempted** — an agent
that spends twenty minutes fighting a bot-gated site has spent your budget on nothing.

**4. Hard rules (shared)** — the four gates below, each with its reason.

**5. Output contract (shared)** — the record schema field by field, with the enumerated vocabularies
spelled out, then the structured report: counts, the 10–20 most important papers with a one-line
*why* each, observed gaps, coverage limits. Ask for counts that are **recomputable from the corpus
file** — a number you cannot recompute from the artifact is a number you cannot defend.

**6. The track (the only part you rewrite)** — track value; the task in two or three sentences; seeds
*by title* with the instruction to look up their identifiers; the closed facet set; the overlap
targets, each described well enough to judge against (and if a project is known only by a codename
and a subsystem list, say so and require the verdict be marked inferred); and a scale target as a
range — `core+related ≈ 70–130` sets a useful expectation, "find everything" does not.

### What a thin brief costs

| Omission | What you get |
|---|---|
| No schema | Three corpora that can't be merged; a day of reconciliation |
| No `verified` field | A corpus you cannot distinguish from a plausible one |
| No "preprints mandatory" | A clean peer-reviewed corpus and a refuted novelty claim |
| No facets | 120 records in one undifferentiated list |
| No unreachable-source list | Budget burned on a bot-gated site |
| No scale target | Either 15 records or 600 |
| No date | "Recent work" meaning three years ago |

---

## Retrieve: every track does both

- **Keyword sweep** across every available source. Syntax and traps in `sources.md`.
- **Citation chasing from the seeds, both directions** — references (backward) and citations
  (forward). One hop minimum from every seed; two hops from the seeds closest to your contribution.
  Forward citations of a two-to-three-year-old seed is the single highest-yield query in the method
  for finding current work that uses other words.

Log **queries run, what returned nothing, and every API failure**. A dead query is data. A swallowed
429 is a hole in your recall that is indistinguishable from "nothing exists" — the one conclusion in a
paper you cannot afford to get wrong.

## Record schema

One object per record. Nothing goes in a field that did not come back in a response.

| Field | Notes |
|---|---|
| `key` | short cite key, `author+year+word` → `hofmann2025sandbox` |
| `title`, `authors`, `year` | as returned; publisher or arXiv rendering of names |
| `arxiv_id`, `doi` | `null` when there is none — **never** when you just didn't look |
| `venue` | full official venue name; `"arXiv"` if preprint-only |
| `venue_short` | from the closed vocabulary in `venues.md`; anything outside it is `other` |
| `peer_reviewed` | `true`/`false` |
| `abstract` | full text, or `null` if the source has none (common, and not an error) |
| `url` | canonical landing page |
| `track`, `facet` | which track found it, and its sub-topic tag within that track |
| `relevance` | `core` / `related` / `background` |
| `verified_by` | `arxiv_api` / `crossref` / `s2` / `openalex` / `web_page` |
| `verified` | `true`/`false`; `false` must come with a `note` saying what failed |
| `source_queries` | every query string that hit this record |
| `overlap_user_work` | the user's own project it collides with, or `none` |
| `note` | one line: why it's in, or why it isn't verified |

Carry extra fields when a project needs them (`retrieved`, `citation_count`, `threat_model`) —
`merge_corpus.py` passes unknown keys through rather than dropping them.

## The four gates

**Evidence gate.** Every field traces to an API response. Know a fact but have no response for it?
`verified: false`, with the reason in `note`, and it shows up in the funnel. Never reconstruct an
arXiv ID, DOI, author list or venue from memory — they come out *plausible and wrong*, which is the
worst failure mode a citation has. Look up even the papers you are sure you know.

**Preprint→venue upgrade gate.** Every arXiv record gets a published-version check by exact title
before you cite it. arXiv's own `journal_ref` / `doi` fields are a free upgrade when present, so read
them first. Citing the arXiv version of a paper that appeared at your own target venue reads as not
having done the reading.

**Frontier gate.** Current and prior-year preprints are **in**, tagged `peer_reviewed: false`. They
are not prior art the way a reviewed paper is, but they are where a collision surfaces first and what
a reviewer will have read. Excluding them is what got one proposal's "first / no prior work" claim
refuted by **64 of them**. Keep them separable so the prose can treat them differently — never drop
them.

**Venue-priority gate.** Collect broadly; prioritise by tier when deciding what gets read closely
versus what gets a sentence. Tiers in `venues.md`.

## Screening: rules first, model second

Keyword rules do the cheap exclusion (wrong field, wrong window, obvious noise). Only then spend model
judgement on title + abstract:

| Level | Meaning |
|---|---|
| `core` | Directly handles your mechanism — the thing you claim |
| `related` | Adjacent problem; informs framing or shares a technique |
| `background` | Classic/foundational work; the chapter's baseline, not a competitor |

Rules alone over-exclude — different vocabulary is the whole problem. Judgement alone is slow and,
through a token-budgeted model, expensive. Batch 20–30 title+abstract pairs per call; the budget
arithmetic is in `harness.md`.

---

## Stage 2 — merge and re-verify

```bash
python scripts/merge_corpus.py lit/tracks/ -o lit/corpus.json --funnel lit/funnel.md
```

Reads `.json` (a list of records) or `.jsonl`, dedupes on DOI, arXiv ID **and** normalised title,
assigns `venue_short` + tier, and counts the funnel. When one work appears as both preprint and
published paper it keeps the published record and preserves the arXiv ID.

⚠ **Dedupe must include normalised title.** The arXiv version and the proceedings version of one paper
share no identifier at all — ID-only dedupe silently double-counts exactly the papers everyone knows,
and every number downstream inherits the error.

**Re-verify the weak records.** Anything with only second-hand evidence, placeholder author strings,
or `verified: false` gets one more attempt by exact-title search. Accept the match only at
similarity ≥0.9; everything else moves to a to-verify list rather than into the main table.

```python
from difflib import SequenceMatcher
# OpenAlex title search, take the highest-similarity hit, reject below 0.9
```

The gate for leaving this stage: **unverified records are out of the main table** — present in the
corpus, visible in the funnel, excluded from anything that gets cited.

## Deliverables

```bash
python scripts/make_bib.py   lit/corpus.json -o lit/refs.bib
python scripts/make_table.py lit/corpus.json -o lit/corpus.xlsx --xlsx
```

`make_bib.py` bars unverified records unless `--all` — this is the one boundary where a
plausible-but-wrong citation would reach a submission. `make_table.py` emits the annotation columns
(`threat_model`, `mechanism`, `evaluation`, `limitations`) **empty**, because those are judgements
made while reading; the sheet is the worksheet.

The funnel is what makes the method defensible, so lead with it:

```
| Stage                               | Count |
| Retrieved (all tracks, all sources) |   412 |
| After dedupe                        |   287 |
| After screening                     |   154 |
| Included (verified)                 |   131 |
|   core / related / background       | 24 / 61 / 46 |
|   peer-reviewed / preprint-only     | 108 / 23 |
|   unverified (flagged, not dropped) |     3 |
```

And state the limits honestly:

> Rule-based, reproducible retrieval over the arXiv, Semantic Scholar, Crossref and OpenAlex APIs
> with citation chasing from seed papers — **not a PRISMA systematic review**. Work using unusual
> terminology and not reachable through the citation graph from our seeds may be missed. Crossref and
> OpenAlex have no deposited abstract for many IEEE conference and Elsevier papers; those were judged
> from title and venue or backfilled from Semantic Scholar. [List every source that rate-limited, was
> unavailable, or was skipped, and which track it degraded.]

Overstating the method is the same failure as overstating a finding. A stated limitation costs
nothing; a discovered one costs the paper.
