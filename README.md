# lit-recon

A [Claude Code](https://claude.com/claude-code) skill for building an academic literature corpus
that a reviewer can't take apart.

A literature search is a **recall problem under an honesty constraint**, and it fails in two
directions:

1. **You missed something.** A reviewer names the paper that already did your thing, and the
   contribution claim dies. Keyword search is bad at this, because the paper that scooped you
   probably used different words. One proposal's "first / no prior work" claim was refuted by **64
   arXiv preprints** the search had excluded for not being peer-reviewed.
2. **You cited something that isn't quite real.** Wrong venue, wrong authors, a DOI that resolves to
   a different paper, an arXiv ID that was plausible and wrong. One bad citation costs the
   reviewer's trust for every other claim. An audited batch of model-written citations ran **82% bad**.

So: fan parallel tracks over four APIs, chase citations in both directions from seed papers to catch
the vocabulary you didn't think of, require every field in every record to trace back to a response
you actually received, and report the funnel so the narrowing is visible.

It is deliberately **not** a PRISMA systematic review, and says so in the output it produces.

## Install

```bash
git clone https://github.com/yeee3642/lit-recon.git ~/.claude/skills/lit-recon
```

Or install `dist/lit-recon.skill` through the Claude desktop app, or just copy the folder.

Then invoke it with `/lit-recon`, or just describe the problem ("is this idea taken", "I need the
related work for X", "文獻檢索").

## Harness-agnostic

The method needs four things: HTTP, JSON/XML parsing, somewhere to write a file, and a way to run
tracks. Subagents and a shell are nice; stdlib `urllib` in one sandboxed kernel with 1.7 GB of RAM is
enough, and `references/constrained-runtime.md` covers that case specifically — including a
copy-pasteable stdlib client with the right backoff ladder, the Atom namespace handling arXiv
requires, and the token arithmetic for budgeted LLM screening.

The scripts are stdlib-only Python 3 with no dependencies, so they run over ssh on a box you can't
install onto. `--xlsx` optionally uses openpyxl and degrades to CSV without it.

## What's in it

| File | Contents |
|---|---|
| `SKILL.md` | The method: six stages, four gates, record schema, screening, trap table |
| `references/sources.md` | Per-API cookbook — endpoints, query syntax, field paths, backoff, the verification ladder |
| `references/venues.md` | `venue_short` vocabulary, tiers, alias normalization, verified venue-counting recipe |
| `references/track-brief.md` | Reusable track-brief skeleton + a worked three-track split |
| `references/constrained-runtime.md` | stdlib HTTP, low-memory kernels, credential brokers, screening budget |
| `scripts/merge_corpus.py` | Dedupe across tracks, assign venue + tier, emit the funnel |
| `scripts/make_bib.py` | → `refs.bib`, with unverified records barred by default |
| `scripts/make_table.py` | → CSV/xlsx reading table with the annotation columns left empty |
| `tests/test_pipeline.py` | 39 checks over the whole pipeline |

## The four gates

The part worth stealing.

- **Evidence gate** — every field traces to an API response. Know a fact but have no response for it?
  `verified: false` with the reason, and it shows up in the report. Never reconstruct an arXiv ID,
  DOI, author list or venue from memory; they come out plausible and wrong, which is the worst
  possible failure mode for a citation. `make_bib.py` enforces this at the boundary that matters —
  unverified records cannot reach `refs.bib` without an explicit `--all`.
- **Preprint→venue upgrade gate** — every arXiv record gets a published-version check before you
  cite it. Citing the arXiv version of a paper that appeared at your own target venue reads as not
  having done the reading.
- **Frontier gate** — current-year preprints are **in**, tagged separately. They aren't prior art the
  way a peer-reviewed paper is, but they're where a collision with your idea surfaces first and what
  a reviewer will have read.
- **Venue-priority gate** — collect broadly, prioritize by tier when deciding what gets read closely
  versus what gets a sentence.

## Things that cost a run if you don't know them

Verified against live API responses. Full table in `SKILL.md`.

| Trap | Detail |
|---|---|
| Semantic Scholar without a key | A cold first call returns `429`. Back off 2/4/8/16s, and log every one — a swallowed 429 looks exactly like "nothing exists". Parallel tracks retrying independently turn a soft limit into a wall. |
| OpenAlex `search=` is full-text | `search=agent sandbox` → 27,561 hits; `filter=title_and_abstract.search:agent sandbox` → 2,313. Use the filter. |
| OpenAlex under-covers security proceedings | A low count there is not evidence about the literature. |
| OpenAlex returns repository deposits | A top hit for one probe was a Zenodo upload. Check `primary_location.source.type`. |
| arXiv over plain `http://` | Returns an empty body. No error. Use `https://`. |
| Missing abstracts | Crossref has none for most IEEE conference and much Elsevier content. That's the source, not your query. |
| Crossref recall | A known-good title returned `total-results: 2`. Crossref *confirms* a venue; it doesn't discover papers. |
| USENIX Security | No DOIs at all, and often outside a sandbox allowlist. Reach it via web search. |
| DBLP | Bot-gated. Take `externalIds.DBLP` from Semantic Scholar's `/paper/batch` instead. |
| "ML venues have no DOIs" | False — NeurIPS resolves via proceedings.com (`10.52202/…`). |
| Dedupe by ID | The arXiv and proceedings versions of one paper share no identifier. Normalize titles. |
| Zero results | Usually the vocabulary is wrong, not a gap. A gap claim is the most expensive sentence in a paper. |
| A seed ID from memory | Poisons every citation-chase hop built on it. Search for seeds; never type their IDs. |

## Output

```bash
python scripts/merge_corpus.py lit/tracks/ -o lit/corpus.json --funnel lit/funnel.md
python scripts/make_bib.py   lit/corpus.json -o lit/refs.bib
python scripts/make_table.py lit/corpus.json -o lit/corpus.xlsx --xlsx
```

The funnel is what makes the method defensible:

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

It also reports how many records more than one track found — zero overlap means the tracks were cut
so narrowly they share no boundary, which is a recall problem dressed as tidiness.

## Pairs with

[topic-pick](https://github.com/yeee3642/topic-pick) — the gated pipeline for deciding *what paper to
write*. It calls this skill for its literature stages, then adds venue-threshold measurement,
competitor survey, sub-claim collision checks and an adversarial review. Use lit-recon alone for a
related-work chapter, a citation audit or a venue count; use topic-pick when the question is what the
paper should be.

## License

MIT. See [LICENSE](LICENSE).
