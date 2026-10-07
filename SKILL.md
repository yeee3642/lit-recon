---
name: lit-recon
description: >
  Build a verifiable academic literature corpus for a paper's related-work chapter, a novelty /
  collision check, or a survey — fanning parallel subagent tracks over the arXiv, Semantic Scholar,
  Crossref and OpenAlex APIs, backing every record with a returned API response, and reporting a
  retrieved → deduped → screened → included funnel. Use whenever the user is writing or defending
  an academic paper and needs to know what already exists: "related work", "第二章", "文獻檢索",
  "survey the literature", "有沒有人做過", "撞題了嗎", "novelty check", "prior art for my paper",
  "收論文", "count how many TDSC/TIFS/S&P papers did X", "is this idea taken". Also when a reviewer
  pushed back on a "no prior work exists" claim, when a draft's citations need checking for
  existence / venue / authors, or when preprints need upgrading to their published venue. NOT for
  CVE or advisory duplicate checks on a vulnerability finding — that is prior art in the bounty
  sense and belongs to bounty-hunt, zdi-bounty or kernel-patchdiff.
---

# Lit Recon

A literature search is a **recall problem under an honesty constraint**. Two ways it kills a paper:

1. **You missed something.** A reviewer names the paper that already did your thing, and the
   contribution claim dies. Five research directions have died this way in one project — every one
   found *after* the effort was spent, none of them by keyword search.
2. **You cited something that isn't quite real.** Wrong venue, wrong authors, a DOI that resolves to
   a different paper, an arXiv number from memory. One bad citation costs you the reviewer's trust
   for every other claim. An audited batch of model-written citations ran **82% bad**.

Everything below exists to push recall up and keep every record traceable to a response you actually
received. Nothing here is written from memory, and neither is anything you produce.

---

## Workflow

| Stage | What happens |
|---|---|
| **1. Frame** | Write the discriminating question, pick the tracks, build seed sets |
| **2. Fan out** | One subagent per track, each writing its own JSONL |
| **3. Merge** | `scripts/merge_corpus.py` — dedupe across tracks, assign tier, emit funnel |
| **4. Position** | Read core papers against your own contribution, fill `overlap` |
| **5. Report** | Funnel table + corpus + honest limitations paragraph |

Workspace:

```
<project>/lit/
├── frame.md            # the question, the tracks, the seeds, the date
├── tracks/
│   ├── <track>.jsonl   # one record per line, written by that track's agent
│   └── <track>.md      # that agent's notes: queries run, dead ends, API failures
├── corpus.jsonl        # merged, deduped (merge_corpus.py writes this)
├── funnel.md           # the counts (merge_corpus.py writes this)
└── related-work.md     # the prose you actually ship
```

---

## 1. Frame

### Write the discriminating question first

The expensive mistake is searching for your **ecosystem name** instead of your **experimental
relationship**. "LLM agent security" returns thousands of papers and still misses the one that
already ran your experiment under different words.

Before any query, write down: the observation held fixed, the component you intervene on, the
security outcome you measure independently, and the result that would end your investigation. Then
search for *that relationship*. This single reframe is what every one of those five dead directions
was missing — each was killed by a paper that shared the experiment but not the vocabulary.

### Split tracks by question, not by keyword

Keyword-split tracks overlap, double-count, and leave the dedupe step doing the real thinking.
Split so each track owns a different **thing a paper does**, give it its own seeds, and let each
agent hold one coherent mental model. Three to four tracks is the usual sweet spot.

A split that worked, for an agent-security paper:

| Track | Owns |
|---|---|
| **Execution isolation** | Containers, gVisor, Firecracker, WASM, seccomp, Landlock, eBPF, egress control; sandbox-escape and exfiltration attack research; industry sandbox design docs and vuln reports; classic sandbox systems as the chapter's baseline |
| **Permission control** | System-layer defenses constraining tool calls (CaMeL, Progent, IsolateGPT, FIDES…), policy languages, runtime monitors, MCP permission models — each flagged for overlap with your own design |
| **Evaluation & venues** | Agent-security benchmarks (AgentDojo, ASB, RedCode, CVE-Bench…), recording **how each builds its execution environment**; plus per-year counts in the target journals and top venues |

Note what the third track is really for: a benchmark paper is interesting to you twice — once as
related work, once as the thing you may have to run against. Record its environment construction,
not just its headline number.

### Seeds

Each track needs 3–8 seed papers you already trust. Seeds exist to feed the citation-chasing step
(§2), which is where the papers using *different vocabulary* come from. Keyword search alone will
not find them — this is the single biggest recall gain available.

---

## 2. Fan out

One subagent per track. Give each the track table row, its seeds, the record schema, the gates, and
`references/sources.md`. Each writes `tracks/<track>.jsonl` plus a notes file recording **queries
run, what returned nothing, and every API failure** — a dead query is data; an undocumented API
429 is a silent hole in your recall.

### Each track does both

- **Keyword search** across all four APIs. Query shapes and quirks: `references/sources.md`.
- **Citation chasing** from the seeds, **both directions** — references (backward) and citations
  (forward), via Semantic Scholar. This is the step that catches terminology you did not think of.
  One hop from each seed is the minimum; two hops on the seeds closest to your contribution.

### Record schema

One JSON object per line. Nothing enters a record that did not come back in a response.

```json
{
  "id": "arxiv:2406.13352",
  "title": "AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses",
  "authors": ["Edoardo Debenedetti", "..."],
  "year": 2024,
  "venue_raw": "Advances in Neural Information Processing Systems 37",
  "venue": "NeurIPS",
  "type": "conference",
  "track": "evaluation",
  "relevance": "core",
  "why": "benchmark; builds a sandboxed tool-call environment per task — record how",
  "overlap": "adjacent",
  "status": "included",
  "evidence": {
    "source": "crossref",
    "query": "query.bibliographic=AgentDojo",
    "field": "container-title",
    "retrieved": "2026-10-07"
  }
}
```

`id` is whichever is most stable: `doi:…` > `arxiv:…` > `s2:<paperId>`. `venue` normalization and
`tier` assignment: `references/venues.md` (the merge script assigns `tier` for you).

### The four gates

These are the whole point of the skill. A track agent that skips them produces a corpus that looks
finished and isn't.

**Evidence gate.** Every field traces to an API response. If you know a fact but no response
returned it, the record is `"status": "unverified"` and says so in the final report. Never
reconstruct an arXiv ID, a DOI, an author list or a venue from memory — they come out plausible and
wrong, which is the worst possible failure mode for a citation.

**Preprint→venue upgrade gate.** Every arXiv record gets a published-version check before you cite
it: search Semantic Scholar / Crossref / OpenAlex by exact title. If it was accepted somewhere, the
venue becomes the real one and `type` stops being `preprint`. Citing the arXiv version of a paper
that appeared at your own target venue reads as not having done the reading.

**Frontier gate.** 2025–2026 preprints are **in**, tagged `"type": "preprint"`. They do not count
as prior art the way a peer-reviewed paper does, but they are exactly where a collision with your
idea will surface first, and they are what a reviewer will have read. A previous proposal on this
project omitted the preprint frontier and had its "no prior work exists" claim refuted on exactly
that ground. Keep them separable in the corpus so the prose can treat them differently — never
exclude them.

**Venue-priority gate.** Collect broadly, prioritize by tier when you decide what gets read closely
and what gets a sentence. Tier table in `references/venues.md`; top-tier security first, then
EuroS&P / ACSAC / RAID / AsiaCCS, then ML / NLP / SE / systems venues.

### Screening: rules first, judgment second

Keyword rules do the cheap exclusion (wrong field, wrong decade, obvious noise). Then read **title
and abstract** and assign:

| Level | Meaning |
|---|---|
| `core` | Directly handles your mechanism — agent isolation, over-privilege, the thing you claim |
| `related` | Adjacent problem; informs framing or shares a technique |
| `background` | Classic systems security; the chapter's baseline, not a competitor |

Rules alone over-exclude (different vocabulary) and judgment alone is slow; the two-pass order is
what keeps both recall and throughput.

---

## 3. Merge

```bash
python scripts/merge_corpus.py lit/tracks/ -o lit/corpus.jsonl --funnel lit/funnel.md
```

It dedupes on DOI, arXiv ID and normalized title; when the same work appears as both a preprint and
a published paper it keeps the **published** record and notes the arXiv ID. It assigns `tier` from
the venue aliases, counts the funnel, and flags records missing an `evidence` block.

⚠ Dedupe must be by normalized title, not by ID. The arXiv version and the proceedings version of
one paper share no identifier at all — ID-only dedupe silently double-counts your best-known papers
and inflates every number in the funnel.

---

## 4. Position

For every `core` paper, fill `overlap` against your own contribution:

| Value | Meaning | What it does to your draft |
|---|---|---|
| `none` | Same area, different mechanism | One sentence in related work |
| `adjacent` | Overlapping mechanism, different threat model or layer | A paragraph saying precisely where you diverge |
| `collides` | Runs your discriminating experiment | Stop. Either your contribution changes or you need a reason this paper is wrong |

A `collides` is worth more than a hundred `none`s and should be escalated to the user immediately,
not buried in a corpus file. Finding it now costs a day; finding it in a review costs the cycle.

---

## 5. Report

Lead with the funnel — it is what makes the method defensible and shows exactly where the narrowing
happened:

```markdown
| Stage | Count |
|---|---|
| Retrieved (all tracks, all sources) | N |
| After dedupe | N |
| After screening | N |
| Included | N |
|   core / related / background | n / n / n |
|   peer-reviewed / preprint-only | n / n |
|   unverified (flagged, not dropped) | n |
```

Then the corpus grouped by track and relevance, then this, honestly:

> This is a rule-based, reproducible retrieval over the arXiv, Semantic Scholar, Crossref and
> OpenAlex APIs with citation chasing from seed papers — not a PRISMA systematic review. Work using
> unusual terminology and not reachable through the citation graph from our seeds may be missed.
> Crossref frequently has no deposited abstract for IEEE conference papers; those were judged from
> title and venue or backfilled from Semantic Scholar. [Record any API that rate-limited or failed,
> and which track it degraded.]

Overstating the method is the same failure as overstating a finding. A stated limitation costs
nothing; a discovered one costs the paper.

---

## Traps

Verified live on 2026-10-07 unless marked otherwise.

| Trap | Detail |
|---|---|
| **S2 without a key = instant 429** | The unauthenticated pool is saturated — a cold first call returns `429` right away. No key is set on this machine. Three parallel tracks hammering it is worse than one. Give **one** track ownership of S2 calls, or serialize with backoff; request a key if this becomes routine. |
| **OpenAlex `search=` is full-text** | `search=agent sandbox` → 27,561 hits. `filter=title_and_abstract.search:agent sandbox` → 2,313. Use the filter; the bare `search` buries you in papers that mention the phrase once. |
| **OpenAlex surfaces Zenodo deposits** | Top hit for one query was a Zenodo upload, not a paper. Check `primary_location.source.type` — `repository` means preprint/deposit, not peer review. |
| **arXiv over plain http returns empty** | `http://export.arxiv.org/api/query` gave an empty body; `https://` works. Silent failure, not an error. |
| **Crossref has no abstracts for IEEE conf papers** | Judge from title + venue, or backfill the abstract from Semantic Scholar / OpenAlex. Say so in the limitations. |
| **USENIX Security has no DOIs** | And usenix.org may not be reachable from the sandbox. Use web search against the per-year accepted-papers page. |
| **DBLP is bot-gated** | Programmatic access fails. Take `externalIds.DBLP` from Semantic Scholar instead to confirm a venue. |
| **ML venues do have DOIs now** | NeurIPS resolves through proceedings.com (`10.52202/…`). Don't assume "no DOI" and skip Crossref for ML work. |
| **Crossref bibliographic recall is thin** | A known-good title returned `total-results: 2`. Crossref is for *confirming* a venue you suspect, not for discovering papers. |
| **Zero results ≠ nothing exists** | It usually means the vocabulary is wrong. Re-query from a seed's reference list before concluding a gap — a claimed gap is the most expensive thing in the paper. |

---

## Reference files

- `references/sources.md` — per-API cookbook: endpoints, query syntax, the fields to read, rate
  limits, what each source is and is not good for. Read before writing the first query.
- `references/venues.md` — venue tier table, alias normalization, and how to produce a defensible
  per-year count for a journal.

The cookbook was verified against live responses on the date in its header. APIs drift: if a field
path there disagrees with what you actually receive, trust the response and fix the file — a skill
that lies about its own sources is the exact failure it exists to prevent.
