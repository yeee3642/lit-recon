# Venues: tiers, aliases, counting

## Tier table

Reading priority, not a quality verdict. It decides what you read closely versus what gets one
sentence, and it is what the merge script writes into `tier`.

| Tier | Venues |
|---|---|
| **A1** — 資安四大 | IEEE S&P (Oakland) · ACM CCS · USENIX Security · NDSS |
| **A2** — second-tier security | EuroS&P · ACSAC · RAID · AsiaCCS |
| **J** — security journals | TDSC · TIFS · TOPS |
| **B** — strong adjacent | ML/NLP: NeurIPS, ICML, ICLR, ACL, EMNLP, NAACL · SE: ICSE, FSE, ASE, ISSTA · Systems: OSDI, SOSP, EuroSys, USENIX ATC, NSDI |
| **C** — other peer-reviewed | Everything else with a real venue, incl. DSN, ESORICS, PETS/PoPETs, SaTML, workshops |
| **P** — preprint only | arXiv, Zenodo, any `repository` source with no published version found |
| **?** — unverified | No API response backs the venue. Stays in the corpus, flagged. |

A1/A2/J/B reflect the stated priority for this project. Tier C exists so that a DSN or PETS paper
doesn't get silently dropped — if you promote one into the chapter, that's a judgment call worth a
line in the notes rather than a quiet reclassification.

A preprint stays **P** until the upgrade check finds a published version. Then it takes the real
venue's tier and keeps the arXiv ID as a secondary identifier.

## Alias normalization

Indexes return the same venue under many strings. Normalize before counting or deduping, or the
funnel lies. Match case-insensitively on substrings:

| Canonical | Seen as |
|---|---|
| `S&P` | IEEE Symposium on Security and Privacy · Proceedings - IEEE Symposium on Security and Privacy · SP · Oakland · `conf/sp/` |
| `CCS` | ACM SIGSAC Conference on Computer and Communications Security · Proceedings of the ... CCS · `conf/ccs/` |
| `USENIX Security` | USENIX Security Symposium · Proceedings of the Nth USENIX Security Symposium · `conf/uss/` |
| `NDSS` | Network and Distributed System Security Symposium · `conf/ndss/` |
| `EuroS&P` | IEEE European Symposium on Security and Privacy · `conf/eurosp/` |
| `ACSAC` | Annual Computer Security Applications Conference · `conf/acsac/` |
| `RAID` | International Symposium on Research in Attacks, Intrusions and Defenses · `conf/raid/` |
| `AsiaCCS` | ACM Asia Conference on Computer and Communications Security · ASIACCS · `conf/asiaccs/` |
| `TDSC` | IEEE Transactions on Dependable and Secure Computing · `journals/tdsc/` |
| `TIFS` | IEEE Transactions on Information Forensics and Security · `journals/tifs/` |
| `TOPS` | ACM Transactions on Privacy and Security · TOPS · TISSEC (pre-2016 name) |
| `NeurIPS` | Advances in Neural Information Processing Systems NN · NIPS · `conf/nips/` |

Two things that bite:

- **`SP` is ambiguous.** It matches both IEEE S&P and signal-processing venues. Match the full
  string, never the bare token.
- **TOPS was TISSEC** until 2016. A pre-2016 count under the new name misses a decade — irrelevant
  for a 2023–2026 window, but not if the window ever widens.

The merge script holds this table in `VENUE_ALIASES`; add rather than replace when a new string
shows up, and the alias file stays the single place the knowledge lives.

## Counting a journal or venue per year

The defensible way to answer "how many TDSC papers 2023–2026 did X". Two steps, both verified live
on 2026-10-07.

**1. Resolve the venue to an OpenAlex source ID** — don't filter on a venue name string, it will
silently miss the records indexed under a variant.

```bash
curl -s "https://api.openalex.org/sources?search=IEEE+Transactions+on+Dependable+and+Secure+Computing&per-page=2&mailto=<addr>"
```

Confirmed IDs (check `issn_l` matches before trusting one):

| Venue | OpenAlex source ID | ISSN-L |
|---|---|---|
| TDSC | `S133795288` | 1545-5971 |
| TIFS | `S61310614` | 1556-6013 |
| TOPS | `S4210174050` | 2471-2566 |

**2. Filter and group.**

```bash
curl -s "https://api.openalex.org/works?filter=primary_location.source.id:S133795288,publication_year:2023-2026,title_and_abstract.search:LLM%20agent&per-page=50&mailto=<addr>"
# → meta.count = 10  (verified 2026-10-07)

curl -s "https://api.openalex.org/works?filter=primary_location.source.id:S133795288,publication_year:2023-2026,title_and_abstract.search:agent&group_by=publication_year&mailto=<addr>"
# → 2026:19  2025:11  2024:6  2023:7  (verified 2026-10-07)
```

Notes that matter for a reportable number:

- `group_by` returns **unordered** buckets. Sort before putting them in a table.
- Sanity-check the denominator. TDSC 2023–2026 total is **1,883**; if a topical filter returns a
  number anywhere near that, the filter isn't doing anything.
- A count is only as good as its query string. Report the exact filter alongside the number —
  "10 TDSC papers" means nothing without `title_and_abstract.search:LLM agent` printed next to it.
- 2026 counts are **partial** — the year isn't over. Say so, or the trend line you draw is an
  artifact.
- USENIX Security can't be counted this way (no DOIs, uneven OpenAlex coverage). Count it from the
  per-year accepted-papers page via web search and mark the method difference in the report.
