# Source cookbook

Endpoints and field paths below were exercised against live responses on **2026-10-07** from this
machine. APIs drift. If a response disagrees with this file, the response wins — fix the file.

Contents: [arXiv](#arxiv) · [Semantic Scholar](#semantic-scholar) · [Crossref](#crossref) ·
[OpenAlex](#openalex) · [USENIX / DBLP](#venues-without-a-usable-api) · [Which source for which job](#which-source-for-which-job)

---

## Which source for which job

| Need | Use | Why |
|---|---|---|
| Recent preprints, frontier check | arXiv | Fastest to appear, no key, date-sortable |
| Citation chasing (both directions) | Semantic Scholar | Only one of the four with usable `references` / `citations` |
| Confirm a venue you already suspect | Crossref | Authoritative `container-title`; poor at discovery |
| Broad topical sweep, concept filters | OpenAlex | Biggest index, no key, rich filters |
| Venue of a USENIX paper | Web search | No DOI exists |
| Confirm a DBLP venue key | Semantic Scholar `externalIds.DBLP` | DBLP itself is bot-gated |

Run at least two sources per track. Single-source recall is not defensible, and the overlap between
them is itself a signal — a paper only one index knows about usually means a venue problem worth
checking.

---

## arXiv

```
https://export.arxiv.org/api/query?search_query=<q>&start=0&max_results=100
```

⚠ **https only.** Plain `http://export.arxiv.org/...` returned an empty body — no error, no results.

Atom XML, not JSON.

| Part | Syntax |
|---|---|
| Field prefixes | `ti:` title, `abs:` abstract, `au:` author, `cat:` category, `all:` everything |
| Phrase | `abs:"prompt injection"` — quote it, URL-encode the quotes |
| Boolean | `+AND+`, `+OR+`, `+ANDNOT+` |
| Category | `cat:cs.CR` (security), `cat:cs.AI`, `cat:cs.SE` |
| Sort | `&sortBy=submittedDate&sortOrder=descending` — essential for the frontier gate |
| Paging | `start` + `max_results`; 2000 max per call, ~1 call / 3s |

Total count lives in `<opensearch:totalResults>` — read it before paging, it tells you whether the
query is too broad to be worth walking.

Verified: `abs:"prompt injection"` → **1022** results; newest submission dated 2026-10-06.

Fields to pull per `<entry>`: `id` (the abs URL — the arXiv ID is its tail, keep the version
suffix off the record `id`), `title`, `author/name`, `published`, `updated`, `summary`,
`arxiv:primary_category`, and `arxiv:journal_ref` / `arxiv:doi` **when present — that is a free
published-version upgrade**, so check it before running the upgrade search separately.

---

## Semantic Scholar

```
https://api.semanticscholar.org/graph/v1/paper/search?query=<q>&limit=20&fields=<csv>
https://api.semanticscholar.org/graph/v1/paper/<id>/references?fields=<csv>&limit=100
https://api.semanticscholar.org/graph/v1/paper/<id>/citations?fields=<csv>&limit=100
```

⚠ **Unauthenticated calls 429 immediately.** A cold first call on this machine returned
`{"message": "Too Many Requests...", "code": "429"}`. No `S2_API_KEY` is set in the environment or
any shell rc file. Consequences for a fan-out run:

- Give **one** track ownership of S2, or serialize S2 across tracks. Parallel tracks each retrying
  independently turn a soft limit into a hard wall.
- Exponential backoff, and **log every 429 to the track notes** — an undocumented 429 is a hole in
  your recall that looks exactly like "nothing exists".
- With a key, send it as `x-api-key: <key>` and the limit becomes workable.

`<id>` accepts `arXiv:2406.13352`, `DOI:10.1145/…`, `CorpusId:…`, or the S2 `paperId`.

Useful `fields`: `title,abstract,year,venue,publicationVenue,externalIds,authors,citationCount,
openAccessPdf,publicationTypes`. `externalIds` is where `DOI`, `ArXiv`, `DBLP` and `CorpusId` live —
this is how you confirm a DBLP venue key without touching DBLP.

**This is the only source that does citation chasing.** `/references` is backward (what the seed
cites), `/citations` is forward (who cites the seed). Forward from a 2023–2024 seed is the highest-
yield single query in the whole method for finding 2025–2026 work that uses different vocabulary.

---

## Crossref

```
https://api.crossref.org/works?query.bibliographic=<title>&rows=5&select=DOI,title,container-title,author,issued,type
```

No key. Put a real address in `mailto=` for the polite pool.

Verified: `query.bibliographic=AgentDojo` → `total-results: 2`, and the hit carried
`container-title: ["Advances in Neural Information Processing Systems 37"]`, DOI `10.52202/079017-2636`.

Two lessons in that one response:

- **Recall is thin.** Two results for a well-known paper. Crossref confirms; it does not discover.
- **ML proceedings do have DOIs** (NeurIPS via proceedings.com, `10.52202/…`). Don't skip Crossref
  for ML venues on the assumption they're DOI-less.

⚠ IEEE conference papers frequently have **no deposited abstract**. `select=abstract` comes back
empty and that is not an error. Judge from title + venue, or backfill from S2 / OpenAlex, and say
which in the limitations paragraph.

Field paths: `message.items[].DOI`, `.title[0]`, `.container-title[0]`, `.author[].given/.family`,
`.issued.date-parts[0][0]` (year), `.type` (`proceedings-article` vs `journal-article` — this is
your cleanest conference/journal discriminator).

---

## OpenAlex

```
https://api.openalex.org/works?filter=title_and_abstract.search:<q>&per-page=50&mailto=<addr>
```

No key. `mailto` buys the polite pool.

⚠ **Use the filter, not bare `search=`.** `search=` runs full text:

| Query | Results |
|---|---|
| `search=agent sandbox` | 27,561 |
| `filter=title_and_abstract.search:agent sandbox` | 2,313 |

A 12× noise difference. The full-text index will hand you every paper that says your phrase once in
a footnote.

Filters worth combining: `publication_year:2023-2026`, `type:article`,
`primary_location.source.type:conference|journal|repository`, `cited_by_count:>10`,
`primary_location.source.id:<openalex source id>` (pin to one venue — this is how you count a
journal, see `venues.md`).

⚠ **Repository deposits come back as results.** A top hit for one probe was a Zenodo upload titled
like a paper. Check `primary_location.source.type == "repository"` and treat those as preprints, not
peer-reviewed work. The response also exposes `host_organization_name`, which makes the junk obvious.

Field paths: `results[].id`, `.doi`, `.title`, `.publication_year`, `.type`,
`.primary_location.source.display_name` (venue), `.primary_location.source.type`,
`.authorships[].author.display_name`, `.cited_by_count`, `.abstract_inverted_index` (invert it to
reconstruct the abstract), `.referenced_works`. `meta.count` is the total before paging; the
response also reports `meta.cost_usd`.

---

## Venues without a usable API

**USENIX Security** — no DOIs at all, and usenix.org may be outside the sandbox's reachable set.
Use web search against the per-year accepted-papers page (`USENIX Security 2025 accepted papers
<topic>`), and record `"evidence": {"source": "web", "url": "...", "retrieved": "..."}` so the
record still carries provenance even though no API returned it.

**DBLP** — bot verification blocks programmatic access. Don't fight it. Take `externalIds.DBLP`
from Semantic Scholar; the key itself (`conf/uss/...`, `journals/tdsc/...`) identifies the venue
unambiguously, which is usually all you needed DBLP for.

**NDSS / IEEE S&P / CCS** — all have DOIs; Crossref and OpenAlex both resolve them. Prefer
OpenAlex's `primary_location.source.id` for counting, Crossref's `container-title` for citing.
