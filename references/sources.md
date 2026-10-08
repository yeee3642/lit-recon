# Source cookbook

Endpoints and field paths below were exercised against live responses on **2026-10-07/08**. APIs
drift. If a response disagrees with this file, the response wins — fix the file.

Contents: [which source for which job](#which-source-for-which-job) · [arXiv](#arxiv) ·
[Semantic Scholar](#semantic-scholar) · [Crossref](#crossref) · [OpenAlex](#openalex) ·
[no usable API](#venues-without-a-usable-api) · [verification ladder](#the-verification-ladder)

For stdlib-only clients, backoff and Atom parsing, see `constrained-runtime.md`.

---

## Which source for which job

| Need | Use | Why |
|---|---|---|
| Recent preprints, frontier check | arXiv | Fastest to appear, no key, date-sortable |
| Confirm an arXiv ID is real | arXiv `id_list=` | Authoritative and cheap; do this instead of trusting a list |
| Citation chasing, both directions | Semantic Scholar | The only one of the four with usable `references` / `citations` |
| Large keyword sweeps with boolean syntax | Semantic Scholar `/search/bulk` | Boolean operators, `year=`, `venue=`, 1000/page |
| Confirm a venue you already suspect | Crossref | Authoritative `container-title`; poor at discovery |
| DBLP venue key | Semantic Scholar `/paper/batch` | DBLP itself is bot-gated |
| Broad topical sweep, concept filters, venue counts | OpenAlex | Biggest index, rich filters |
| A USENIX paper's page | Web search | No DOI exists |

Run at least two sources per track. Single-source recall is not defensible, and the disagreement
between them is itself signal — a paper only one index knows about usually has a venue problem worth
checking.

---

## arXiv

```
https://export.arxiv.org/api/query?search_query=<q>&start=0&max_results=100
https://export.arxiv.org/api/query?id_list=2406.13352,2501.00001
```

⚠ **https only.** Plain `http://export.arxiv.org/...` returned an empty body — no error, no results.

Atom XML. Namespaces are mandatory in every lookup; see `constrained-runtime.md` for a working parser.

| Part | Syntax |
|---|---|
| Field prefixes | `ti:` title, `abs:` abstract, `au:` author, `cat:` category, `all:` everything |
| Phrase | `abs:"prompt injection"` — quote it, percent-encode the quotes |
| Boolean | `+AND+`, `+OR+`, `+ANDNOT+` |
| Category | `cat:cs.CR` security, `cat:cs.AI`, `cat:cs.SE`, `cat:cs.OS` |
| Sort | `&sortBy=submittedDate&sortOrder=descending` — required for the frontier gate |
| Paging | `start` + `max_results`; 2000 max per call, ≥3 s between calls |
| **ID check** | `id_list=<csv>` returns only those entries. A bad ID yields no entry — that is your verification. |

Count lives in `<opensearch:totalResults>`; read it before paging to see whether the query is worth
walking. Verified: `abs:"prompt injection"` → **1,025** (2026-10-08), newest submission that day.

Per `<entry>` pull: `id` (the abs URL; the ID is its tail — strip the `vN` suffix for the record),
`title`, `author/name`, `published`, `updated`, `summary`, `arxiv:primary_category`, and
**`arxiv:journal_ref` + `arxiv:doi`**. Those last two are a free published-version upgrade when
present, so read them before running a separate upgrade search. Both are frequently `None` even for
published work, so their absence proves nothing.

---

## Semantic Scholar

```
https://api.semanticscholar.org/graph/v1/paper/search/bulk?query=<q>&fields=<csv>
https://api.semanticscholar.org/graph/v1/paper/search?query=<q>&limit=20&fields=<csv>
https://api.semanticscholar.org/graph/v1/paper/<id>/references?fields=<csv>&limit=100
https://api.semanticscholar.org/graph/v1/paper/<id>/citations?fields=<csv>&limit=100
POST https://api.semanticscholar.org/graph/v1/paper/batch   body {"ids": [...]}
```

⚠ **Unauthenticated calls 429 immediately.** A cold first call returned
`{"message": "Too Many Requests...", "code": "429"}` (2026-10-07). Consequences:

- Exponential backoff **2 / 4 / 8 / 16 s**, and **log every 429** to the track notes. A swallowed 429
  is a recall hole that looks exactly like "nothing exists".
- Give **one** track ownership of S2, or serialize across tracks. Parallel agents retrying
  independently turn a soft limit into a wall.
- With a key, send `x-api-key: <key>` and the limit becomes workable.

**`/search/bulk` is the one to use for sweeps.** It takes boolean syntax and returns up to 1000 per
page with a continuation `token`:

| Operator | Meaning |
|---|---|
| `+` | AND · `agent+sandbox` |
| `\|` | OR · `sandbox\|isolation` |
| `-` | NOT · `agent-reinforcement` |
| `"…"` | phrase · `"information flow control"` |
| `*` | prefix · `capab*` |
| `~N` | fuzzy phrase within N words |

Plus filters `year=2023-2026`, `venue=<csv>`, `fieldsOfStudy=`, `openAccessPdf`. Note `/search/bulk`
has no relevance ranking — it is a filter, not a search engine, so pair a tight boolean with
`year=` rather than hoping the top of the list is the good part.

Useful `fields`: `title,abstract,year,venue,publicationVenue,externalIds,authors,citationCount,
publicationTypes,openAccessPdf`. `externalIds` carries `DOI`, `ArXiv`, `DBLP`, `CorpusId` — this is
how you get a DBLP venue key without touching DBLP.

`<id>` accepts `arXiv:2406.13352`, `DOI:10.1145/…`, `CorpusId:…`, or the S2 `paperId`.

**This is the only source that chases citations.** `/references` is backward (what the seed cites),
`/citations` is forward (who cites the seed). Forward from a 2023–2024 seed is the highest-yield
single query in the whole method for finding current work under different vocabulary.

`/paper/batch` (POST) resolves up to 500 IDs in one call — the cheapest way to verify a seed list and
backfill venues in bulk.

---

## Crossref

```
https://api.crossref.org/works?query.bibliographic=<title>&rows=5&select=DOI,title,container-title,author,issued,type
https://api.crossref.org/works/<doi>
```

No key. Put a real address in `mailto=` for the polite pool.

Verified: `query.bibliographic=AgentDojo` → `total-results: 2`, hit carried
`container-title: ["Advances in Neural Information Processing Systems 37"]`, DOI `10.52202/079017-2636`.

Two lessons in one response:

- **Recall is thin.** Two results for a well-known paper. Crossref *confirms*; it does not discover.
- **ML proceedings do have DOIs** (NeurIPS via proceedings.com). Don't skip Crossref for ML venues.

⚠ **No deposited abstract** for most IEEE conference papers and much Elsevier content. `select=abstract`
comes back empty and that is the source, not your query. Record `abstract: null`, backfill from S2,
and say so in `coverage_limits`.

Field paths: `message.items[].DOI`, `.title[0]`, `.container-title[0]`, `.author[].given/.family`,
`.issued.date-parts[0][0]` (year), `.type` — `proceedings-article` vs `journal-article` is your
cleanest conference/journal discriminator. For a single DOI, the same fields sit under `message`
directly.

---

## OpenAlex

```
https://api.openalex.org/works?filter=title_and_abstract.search:<q>&per-page=200
https://api.openalex.org/sources?search=<venue name>
```

Auth depends on the harness. Either a polite-pool `mailto=<addr>`, **or** `api_key=<key>` — some
setups require the key and forbid sending `mailto` alongside it. Follow the brief; see
`constrained-runtime.md` for fetching a key from a broker without leaking it. No key available →
skip OpenAlex and record the skip; it is a supplement, not a pillar.

⚠ **Use the filter, not bare `search=`.** `search=` runs full text:

| Query | Results |
|---|---|
| `search=agent sandbox` | 27,561 |
| `filter=title_and_abstract.search:agent sandbox` | 2,313 |

A 12× noise difference (2026-10-07). The full-text index hands you every paper that says your phrase
once in a footnote.

⚠ **Security proceedings are under-covered.** OpenAlex's indexing of top-tier security conference
proceedings is incomplete, so a zero or a low count there is not evidence about the literature. Use
it for breadth and for journal counting; confirm conference venues through Crossref or S2.

⚠ **Repository deposits come back as results.** A top hit for one probe was a Zenodo upload titled
like a paper. Check `primary_location.source.type == "repository"` and treat those as preprints.

Filters worth combining: `publication_year:2023-2026`, `type:article`,
`primary_location.source.type:conference|journal|repository`, `cited_by_count:>10`,
`primary_location.source.id:<source id>` (pin to one venue — see `venues.md`), `has_doi:true`.
`group_by=publication_year` gives per-year counts in one call.

Field paths: `results[].id`, `.doi`, `.title`, `.publication_year`, `.type`,
`.primary_location.source.display_name`, `.primary_location.source.type`,
`.authorships[].author.display_name`, `.cited_by_count`, `.referenced_works`,
`.abstract_inverted_index` (invert it to reconstruct the abstract). `meta.count` is the pre-paging
total.

---

## Venues without a usable API

**USENIX Security** — no DOIs at all, and usenix.org is commonly outside a sandbox allowlist. Reach
the paper page through web search (`USENIX Security 2025 accepted papers <topic>`), and record
`verified_by: "web_page"` with the URL so the record still carries provenance.

**DBLP** — bot verification blocks programmatic access. **Do not attempt it.** Take `externalIds.DBLP`
from Semantic Scholar; the key itself (`conf/uss/…`, `journals/tdsc/…`) identifies the venue
unambiguously, which is what you wanted DBLP for.

**NDSS / IEEE S&P / CCS** — all have DOIs; Crossref and OpenAlex both resolve them. Prefer OpenAlex
`primary_location.source.id` for counting, Crossref `container-title` for citing.

---

## The verification ladder

Climb until something authoritative answers, then stop and record which rung answered in
`verified_by`.

1. **arXiv `id_list=`** — proves an arXiv ID exists and gives the canonical title.
2. **Crossref `/works/{doi}`** — proves a DOI exists and gives the official venue.
3. **S2 `/paper/batch`** — resolves a mixed list of IDs, fills venue and DBLP key.
4. **OpenAlex** — breadth and counts; weakest on security proceedings.
5. **Web page** — for venues with no API. Record the URL.

Nothing answered → `verified: false` plus a `note` saying which rungs you tried. That record stays in
the corpus, flagged. Dropping it hides the uncertainty; guessing manufactures it.
