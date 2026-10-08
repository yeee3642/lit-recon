---
name: lit-recon
description: >
  Build a verifiable academic literature corpus for a related-work chapter, novelty check, survey
  or venue-fit count: fan parallel tracks over the arXiv, Semantic Scholar, Crossref and OpenAlex
  APIs, back every record with a returned API response, and emit a corpus plus refs.bib, a
  spreadsheet and a retrieved→deduped→screened→included funnel.
  Use whenever the user is writing or defending an academic paper and needs to know what already
  exists: "related work", "第二章", "文獻檢索", "survey the literature", "有沒有人做過", "撞題了嗎",
  "novelty check", "prior art for my paper", "收論文", "選題", "count how many TDSC/TIFS/S&P papers
  did X", "is this idea taken". Also when a reviewer refuted a "no prior work exists" claim, when a
  draft's citations need checking for existence / venue / authors, when preprints need upgrading to
  their published venue, or when writing a brief for a literature-retrieval subagent. NOT for CVE or
  advisory duplicate checks on a vulnerability — that belongs to bounty-hunt or zdi-bounty.
---

# Lit Recon

A literature search is a **recall problem under an honesty constraint**, and it fails in two
directions:

1. **You missed something.** A reviewer names the paper that already did your thing, and the
   contribution claim dies. Five research directions have died this way in one project — every one
   found *after* the effort was spent, none of them by keyword search. One proposal's "first / no
   prior work" claim was refuted by **64 arXiv preprints** the search had excluded for not being
   peer-reviewed.
2. **You cited something that isn't quite real.** Wrong venue, wrong authors, a DOI that resolves to
   a different paper, an arXiv ID that was plausible and wrong. One bad citation costs the
   reviewer's trust for every other claim. An audited batch of model-written citations ran **82% bad**.

Everything here pushes recall up and keeps every record traceable to a response that actually came
back. Nothing in this skill is written from memory, and neither is anything you produce with it.

## Harness-agnostic by design

The method needs four things: HTTP GET/POST, JSON/XML parsing, somewhere to write a file, and a way
to run tracks. Everything else varies. If you have subagents, run tracks in parallel; if you have one
constrained kernel, run them in sequence. If you only have stdlib `urllib` and 1.7 GB of RAM, that is
enough — see `references/constrained-runtime.md` before writing a single request in that situation,
because the failure modes there are specific and silent.

---

## Workflow

| Stage | What happens | Where |
|---|---|---|
| **1. Frame** | Discriminating question, track split, seed sets | below |
| **2. Brief** | One self-contained brief per track | `references/track-brief.md` |
| **3. Retrieve** | Keyword sweep + citation chasing, per track | `references/sources.md` |
| **4. Merge** | Dedupe across tracks, assign tier, funnel | `scripts/merge_corpus.py` |
| **5. Position** | Read core papers against your own contribution | below |
| **6. Deliver** | refs.bib, spreadsheet, gap report, honest limits | `scripts/make_bib.py`, `scripts/make_table.py` |

```
<project>/lit/
├── frame.md              # question, tracks, seeds, run date
├── briefs/<track>.md     # what each track agent was told
├── tracks/<track>.json   # list of records (schema below)
├── tracks/<track>.md      # queries run, dead ends, every API failure
├── corpus.json           # merged, deduped
├── funnel.md             # the counts
├── refs.bib              # LaTeX-ready
└── corpus.csv / .xlsx    # the reading table
```

---

## 1. Frame

### Write the discriminating question before the first query

The expensive mistake is searching your **ecosystem name** instead of your **experimental
relationship**. "LLM agent security" returns thousands of papers and still misses the one that
already ran your experiment under different words.

Write down: the observation held fixed, the component you intervene on, the security outcome you
measure independently, and the result that would end the investigation. Then search for *that
relationship*. Every one of those five dead directions was killed by a paper that shared the
experiment but not the vocabulary — which is also why §3 insists on citation chasing.

### Split tracks by question, not by keyword

Keyword-split tracks overlap, double-count, and push the real thinking into the dedupe step. Split so
each track owns a different **thing a paper does**, give it its own seeds and its own facet
vocabulary, and each agent can hold one coherent model of its slice. Three to four tracks is usual.

Two tests for a good split: a paper should have one obvious home, and the tracks should still share a
*boundary* — if no paper is ever found by two tracks, the cuts were too narrow and you have a recall
problem dressed as tidiness.

A worked three-track split (defense layer / artifact type) is in `references/track-brief.md`. Use it
as a shape, not a template to fill — the right axis depends on the paper.

### Seeds

3–8 papers per track that you already trust. Seeds exist to feed citation chasing, which is where
differently-worded work comes from. **Look the seeds up rather than writing their IDs** — a seed list
with a hallucinated arXiv number poisons every expansion built on it.

---

## 2. Brief each track

A track agent needs to be able to work without asking you anything. The brief carries the paper's
topic and target venues, the runtime constraints, which sources are allowed and their quirks, the
record schema, the gates, the track's own seeds and facets, the overlap targets, and the scale
target.

Most of that is identical across tracks. `references/track-brief.md` holds the reusable skeleton and
the one worked example; write the per-track 10% and paste the rest.

---

## 3. Retrieve

### Each track does both

- **Keyword sweep** across every available source. Query syntax, field paths, rate limits and the
  per-source traps are in `references/sources.md` — read it before the first request.
- **Citation chasing from the seeds, both directions** — references (backward) and citations
  (forward). One hop minimum from every seed; two hops from the seeds closest to your contribution.
  Forward citations of a 2023–2024 seed is the single highest-yield query in the method for finding
  current work that uses other words.

Log **queries run, what returned nothing, and every API failure**. A dead query is data. A swallowed
429 is a hole in your recall that is indistinguishable from "nothing exists" — which is the one
conclusion in a paper you cannot afford to get wrong.

### Record schema

One object per record. Nothing goes in a field that did not come back in a response.

| Field | Notes |
|---|---|
| `key` | short cite key, `author+year+word` → `hofmann2025sandbox` |
| `title`, `authors`, `year` | as returned; publisher or arXiv rendering of names |
| `arxiv_id`, `doi` | `null` when there is none — **never** when you just didn't look |
| `venue` | full official venue name; `"arXiv"` if preprint-only |
| `venue_short` | from the fixed vocabulary in `references/venues.md`; anything outside it is `other` |
| `peer_reviewed` | `true`/`false` |
| `abstract` | full text, or `null` if the source has none (common and not an error) |
| `url` | canonical landing page |
| `track`, `facet` | which track found it, and its sub-topic tag within that track |
| `relevance` | `core` / `related` / `background` — see below |
| `verified_by` | `arxiv_api` / `crossref` / `s2` / `openalex` / `web_page` |
| `verified` | `true`/`false`; `false` must come with a `note` saying what failed |
| `source_queries` | every query string that hit this record |
| `overlap_user_work` | name of the user's own project it collides with, or `none` |
| `note` | one line: why it's in, or why it isn't verified |

Carry extra fields if a project needs them (`retrieved`, `citation_count`, `threat_model`) — the merge
script passes unknown keys through untouched rather than dropping them.

### The four gates

These are the skill. A track that skips them produces a corpus that looks finished and isn't.

**Evidence gate.** Every field traces to an API response. Know a fact but have no response for it?
`verified: false`, with the reason in `note`, and it shows up in the report. Never reconstruct an
arXiv ID, DOI, author list or venue from memory — they come out *plausible and wrong*, which is the
worst failure mode a citation has. Look up even the papers you are sure you know.

**Preprint→venue upgrade gate.** Every arXiv record gets a published-version check by exact title
before you cite it. arXiv's own `journal_ref` / `doi` fields are a free upgrade when present, so read
them first. Citing the arXiv version of a paper that appeared at your own target venue reads as not
having done the reading.

**Frontier gate.** Current and prior-year preprints are **in**, tagged `peer_reviewed: false`. They
are not prior art the way a reviewed paper is, but they are where a collision surfaces first and what
a reviewer will have read. Excluding them is what got that "first / no prior work" claim refuted by 64
of them. Keep them separable so the prose can treat them differently — never drop them.

**Venue-priority gate.** Collect broadly; prioritize by tier when deciding what gets read closely
versus what gets a sentence. Tiers in `references/venues.md`.

### Screening: rules first, model second

Keyword rules do the cheap exclusion (wrong field, wrong window, obvious noise). Only then spend model
judgment on title + abstract:

| Level | Meaning |
|---|---|
| `core` | Directly handles your mechanism — the thing you claim |
| `related` | Adjacent problem; informs framing or shares a technique |
| `background` | Classic/foundational work; the chapter's baseline, not a competitor |

Rules alone over-exclude (different vocabulary is the whole problem), judgment alone is slow and, when
it runs through a token-budgeted model, expensive. If you are batching screening through an LLM, batch
20–30 title+abstract pairs per call and keep a hard cap on call count; budget arithmetic in
`references/constrained-runtime.md`.

---

## 4. Merge

```bash
python scripts/merge_corpus.py lit/tracks/ -o lit/corpus.json --funnel lit/funnel.md
```

Reads `.json` (list of records) or `.jsonl`, dedupes on DOI, arXiv ID **and** normalized title,
assigns `venue_short` + tier from the alias table, and counts the funnel. When one work appears as
both preprint and published paper it keeps the published record and preserves the arXiv ID.

⚠ Dedupe must include normalized title. The arXiv version and the proceedings version of one paper
share no identifier at all — ID-only dedupe silently double-counts exactly the papers everyone knows,
and every number downstream inherits the error.

---

## 5. Position

For every `core` paper, set `overlap_user_work` against the user's own contributions:

| Value | Meaning | Consequence |
|---|---|---|
| `none` | Same area, different mechanism | One sentence in related work |
| *project name* | Overlapping mechanism | A paragraph saying precisely where you diverge |

And escalate immediately, in prose, not buried in a JSON field, when a paper **runs your
discriminating experiment**. That is a collision: either the contribution changes or you need a
defensible reason the paper is wrong. Finding it now costs a day; finding it in review costs the cycle.

When the user's own project is known only by a codename and a subsystem list, say that the overlap
call is **inferred from the name** and mark it low-confidence. A confident overlap verdict built on a
guess about your own unpublished work is worse than no verdict.

---

## 6. Deliver

```bash
python scripts/make_bib.py   lit/corpus.json -o lit/refs.bib
python scripts/make_table.py lit/corpus.json -o lit/corpus.csv     # --xlsx if openpyxl is present
```

Lead the report with the funnel — it is what makes the method defensible and shows where the
narrowing happened:

```
| Stage                               | Count |
| Retrieved (all tracks, all sources) |   412 |
| After dedupe                        |   287 |
| After screening                     |   154 |
| Included                            |   131 |
|   core / related / background       | 24 / 61 / 46 |
|   peer-reviewed / preprint-only     | 108 / 23 |
|   unverified (flagged, not dropped) |     3 |
```

Then the corpus by track and relevance, the per-sub-problem "strongest current method", the residual
gaps (each with the key of the nearest existing work, so a gap claim is checkable), and this:

> This is a rule-based, reproducible retrieval over the arXiv, Semantic Scholar, Crossref and
> OpenAlex APIs with citation chasing from seed papers — **not a PRISMA systematic review**. Work
> using unusual terminology and not reachable through the citation graph from our seeds may be
> missed. Crossref and OpenAlex have no deposited abstract for many IEEE conference and Elsevier
> papers; those were judged from title and venue or backfilled from Semantic Scholar. [List every
> source that rate-limited, was unavailable, or was skipped, and which track it degraded.]

Overstating the method is the same failure as overstating a finding. A stated limitation costs
nothing; a discovered one costs the paper.

---

## Traps

Verified against live API responses; dated entries were checked on the date shown.

| Trap | Detail |
|---|---|
| **Semantic Scholar 429s on a cold call** | Unauthenticated, the shared pool is saturated — the *first* request can 429 (2026-10-07). Exponential backoff 2/4/8/16s, give **one** track ownership of S2 or serialize it, and log every 429. Parallel tracks retrying independently turn a soft limit into a wall. |
| **OpenAlex `search=` is full-text** | `search=agent sandbox` → 27,561 hits; `filter=title_and_abstract.search:agent sandbox` → 2,313 (2026-10-07). 12× noise. Use the filter. |
| **OpenAlex returns repository deposits** | A top hit for one probe was a Zenodo upload, not a paper. Check `primary_location.source.type == "repository"`. |
| **OpenAlex under-covers security proceedings** | Treat it as a supplement for top-tier security venues, never the primary index. |
| **arXiv over plain `http://`** | Returned an empty body — no error, no results (2026-10-07). Use `https://`. |
| **Missing abstracts are the source, not your bug** | Crossref routinely has none for IEEE conference and Elsevier papers. Record `null` and backfill from S2; don't re-query hoping it appears. |
| **Crossref recall is thin** | A known-good title returned `total-results: 2`. Crossref *confirms* a venue; it does not discover papers. |
| **USENIX Security has no DOIs** | And usenix.org is often outside a sandbox's allowlist. Reach the paper page through web search and record `verified_by: web_page`. |
| **DBLP is bot-gated** | Don't attempt programmatic access. Take `externalIds.DBLP` from Semantic Scholar's `/paper/batch` instead. |
| **"ML venues have no DOIs"** | False — NeurIPS resolves via proceedings.com (`10.52202/…`). Don't skip Crossref for ML work. |
| **Dedupe by ID alone** | arXiv and proceedings versions share no identifier. Normalize titles. |
| **Zero results ≠ a gap** | It usually means the vocabulary is wrong. Re-query from a seed's reference list before claiming a gap — a gap claim is the most expensive sentence in the paper. |
| **A seed ID from memory** | Poisons every citation-chase hop built on it. Search for seeds; never type their IDs. |

---

## Reference files

- `references/sources.md` — per-API cookbook: endpoints, query syntax, field paths, backoff, what each
  source is and isn't good for. Read before the first query.
- `references/venues.md` — `venue_short` vocabulary, tiers, alias normalization, and a verified recipe
  for counting a venue per year.
- `references/track-brief.md` — the reusable track-brief skeleton plus one worked example. Read when
  splitting tracks or writing a brief.
- `references/constrained-runtime.md` — running this with stdlib-only HTTP, a low-memory kernel, a
  credential broker, or a token-budgeted screening model. Read **before** writing requests in that
  kind of harness, not after it breaks.

The cookbook entries were verified against live responses on the dates they carry. APIs drift: if a
field path there disagrees with what you receive, trust the response and fix the file. A skill that
lies about its own sources is the exact failure it exists to prevent.
