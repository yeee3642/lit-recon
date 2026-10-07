# lit-recon

A [Claude Code](https://claude.com/claude-code) skill for building an academic literature corpus
that a reviewer can't take apart.

A literature search is a **recall problem under an honesty constraint**, and it fails in two
directions:

1. **You missed something.** A reviewer names the paper that already did your thing, and the
   contribution claim dies. Keyword search is bad at this, because the paper that scooped you
   probably used different words.
2. **You cited something that isn't quite real.** Wrong venue, wrong authors, a DOI that resolves to
   a different paper, an arXiv ID that was plausible and wrong. One bad citation costs the
   reviewer's trust for every other claim. An audited batch of model-written citations in this
   project's history ran **82% bad**.

So: fan parallel subagent tracks over four APIs, chase citations in both directions from seed papers
to catch the vocabulary you didn't think of, require every field in every record to trace back to a
response you actually received, and report the funnel so the narrowing is visible.

It is deliberately **not** a PRISMA systematic review, and says so in the output it produces.

## Install

Drop it in your skills directory:

```bash
git clone https://github.com/yeee3642/lit-recon.git ~/.claude/skills/lit-recon
```

Or install `dist/lit-recon.skill` through the Claude desktop app, or just copy the folder. No
dependencies — `merge_corpus.py` is stdlib-only Python 3, so it runs over ssh on a box where you
can't install anything.

Then invoke it with `/lit-recon`, or just describe the problem ("is this idea taken", "I need the
related work for X", "文獻檢索").

## What's in it

| File | Contents |
|---|---|
| `SKILL.md` | The method: five stages, four gates, record schema, screening levels, trap table |
| `references/sources.md` | Per-API cookbook — endpoints, query syntax, field paths, rate limits, what each source is and isn't good for |
| `references/venues.md` | Venue tiers, alias normalization, and a verified recipe for counting a journal per year |
| `scripts/merge_corpus.py` | Dedupe across tracks, assign venue tier, emit the funnel report |

## The four gates

These are the part worth stealing.

- **Evidence gate** — every field traces to an API response. Know a fact but have no response for
  it? The record is `unverified` and says so in the report. Never reconstruct an arXiv ID, DOI,
  author list or venue from memory; they come out plausible and wrong, which is the worst possible
  failure mode for a citation.
- **Preprint→venue upgrade gate** — every arXiv record gets a published-version check before you
  cite it. Citing the arXiv version of a paper that appeared at your own target venue reads as not
  having done the reading.
- **Frontier gate** — current-year preprints are **in**, tagged separately. They aren't prior art
  the way a peer-reviewed paper is, but they're where a collision with your idea surfaces first and
  what a reviewer will have read. A proposal that omits the preprint frontier gets its "no prior
  work exists" claim refuted on exactly that ground.
- **Venue-priority gate** — collect broadly, prioritize by tier when deciding what gets read closely
  versus what gets a sentence.

## Things that cost a run if you don't know them

Verified against live API responses on 2026-10-07. The full table is in `SKILL.md`.

| Trap | Detail |
|---|---|
| Semantic Scholar without a key | A cold first call returns `429`. Parallel tracks each retrying independently turn a soft limit into a wall — and a silent 429 looks exactly like "nothing exists". |
| OpenAlex `search=` is full-text | `search=agent sandbox` → 27,561 hits; `filter=title_and_abstract.search:agent sandbox` → 2,313. Use the filter. |
| OpenAlex returns repository deposits | A top hit for one probe was a Zenodo upload. Check `primary_location.source.type`. |
| arXiv over plain `http://` | Returns an empty body. No error. Use `https://`. |
| Crossref and IEEE conference papers | Frequently no deposited abstract — not an error. Backfill from Semantic Scholar. |
| Crossref recall | A known-good title returned `total-results: 2`. Crossref *confirms* a venue; it doesn't discover papers. |
| USENIX Security | No DOIs at all. Web-search the per-year accepted-papers page. |
| DBLP | Bot-gated. Take `externalIds.DBLP` from Semantic Scholar instead. |
| "ML venues have no DOIs" | False — NeurIPS resolves via proceedings.com (`10.52202/…`). |
| Dedupe by ID | The arXiv version and the proceedings version of one paper share no identifier. Normalize titles or you double-count your best-known papers. |
| Zero results | Usually means the vocabulary is wrong, not that a gap exists. A claimed gap is the most expensive thing in a paper — re-query from a seed's reference list first. |

## Funnel output

`merge_corpus.py` writes the table that makes the method defensible:

```
| Stage                                  | Count |
| Retrieved (all tracks, all sources)    |   412 |
| After dedupe                           |   287 |
| After screening                        |   154 |
| **Included**                           |  **131** |
|   core / related / background          | 24 / 61 / 46 |
|   peer-reviewed / preprint-only        | 108 / 23 |
|   unverified (flagged, not dropped)    |     3 |
```

It also reports how many records more than one track found — zero overlap means the tracks were cut
so narrowly they share no boundary, which is a recall problem, not a tidiness win.

## License

MIT. See [LICENSE](LICENSE).
