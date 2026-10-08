# Venues: vocabulary, tiers, counting

## The `venue_short` vocabulary

A **closed set**. Every record takes exactly one value; anything not listed is `other`. A closed
vocabulary is what makes the corpus groupable and countable — the moment two tracks write `SP` and
`IEEE S&P` for the same venue, every count downstream is wrong.

```
S&P  CCS  USENIX Security  NDSS
EuroS&P  ACSAC  RAID  AsiaCCS
TDSC  TIFS  TOPS
NeurIPS  ICLR  ICML  ACL  EMNLP
ICSE  FSE  ASE
OSDI  SOSP  EuroSys  ATC
arXiv  tech-report  other
```

`venue` stays the **full official name** as the API returned it; `venue_short` is this tag. Keep both
— the full string is your evidence, the tag is your index.

Adjust the set to the paper's field before briefing tracks, and give every track the same one. If
your field needs DSN, PETS, ESORICS, ISSTA or NAACL as first-class tags, add them *to the brief* and
to `VENUE_ALIASES` in `merge_corpus.py` rather than letting agents improvise.

## Tiers

Reading priority, not a quality verdict: it decides what gets read closely versus what gets a
sentence. `merge_corpus.py` derives `tier` from `venue_short`.

| Tier | Venues |
|---|---|
| **A1** | S&P · CCS · USENIX Security · NDSS |
| **A2** | EuroS&P · ACSAC · RAID · AsiaCCS |
| **J** | TDSC · TIFS · TOPS |
| **B** | NeurIPS · ICLR · ICML · ACL · EMNLP · ICSE · FSE · ASE · OSDI · SOSP · EuroSys · ATC |
| **C** | `other`, `tech-report` |
| **P** | `arXiv` — preprint with no published version found |
| **?** | No API response backs the venue. Stays in the corpus, flagged. |

Two notes that matter more than the ordering:

- **A preprint stays `P` until the upgrade check runs.** Then it takes the real venue's tier and keeps
  its arXiv ID as a secondary identifier.
- **`tech-report` is tier C but can be a primary source.** A vendor's sandbox design document or an
  incident report is often the only account of what production systems actually do, and no amount of
  peer-reviewed work substitutes for it. Low reading priority, high citation value — don't let the
  tier talk you out of it.

## Alias normalization

Indexes return one venue under many strings. Normalize before counting or deduping, or the funnel
lies. Match case-insensitively on substrings:

| `venue_short` | Seen as |
|---|---|
| `S&P` | IEEE Symposium on Security and Privacy · Proceedings - IEEE Symposium on Security and Privacy · Oakland · `conf/sp/` |
| `CCS` | ACM SIGSAC Conference on Computer and Communications Security · `conf/ccs/` |
| `USENIX Security` | USENIX Security Symposium · Proceedings of the Nth USENIX Security Symposium · `conf/uss/` |
| `NDSS` | Network and Distributed System Security Symposium · `conf/ndss/` |
| `EuroS&P` | IEEE European Symposium on Security and Privacy · `conf/eurosp/` |
| `ACSAC` | Annual Computer Security Applications Conference · `conf/acsac/` |
| `RAID` | International Symposium on Research in Attacks, Intrusions and Defenses · `conf/raid/` |
| `AsiaCCS` | ACM Asia Conference on Computer and Communications Security · ASIACCS · `conf/asiaccs/` |
| `TDSC` | IEEE Transactions on Dependable and Secure Computing · `journals/tdsc/` |
| `TIFS` | IEEE Transactions on Information Forensics and Security · `journals/tifs/` |
| `TOPS` | ACM Transactions on Privacy and Security · TISSEC (pre-2016 name) · `journals/tops/` |
| `NeurIPS` | Advances in Neural Information Processing Systems NN · NIPS · `conf/nips/` |
| `ICLR` / `ICML` | International Conference on Learning Representations / Machine Learning |
| `ACL` / `EMNLP` | Annual Meeting of the Association for Computational Linguistics / Empirical Methods in NLP |
| `ICSE` / `FSE` / `ASE` | International Conference on Software Engineering / Foundations of Software Engineering / Automated Software Engineering |
| `OSDI` / `SOSP` / `EuroSys` / `ATC` | …Operating Systems Design and Implementation / Symposium on Operating Systems Principles / EuroSys / USENIX Annual Technical Conference |
| `arXiv` | arXiv · CoRR · Zenodo and other `repository` sources |

Three that bite:

- **Bare `SP` is ambiguous** — it matches signal-processing venues too. Match the full string, never
  the token.
- **`TOPS` was `TISSEC`** until 2016. Irrelevant inside a 2023–2026 window; not if the window widens.
- **`ATC` vs `ACL`** are three characters apart and both appear as bare acronyms. Match on the
  expanded name.

Add to the table rather than replacing, so the knowledge keeps living in one place.

## Counting a venue per year

The defensible way to answer "how many TDSC papers 2023–2026 did X". Both steps verified 2026-10-07.

**1. Resolve the venue to an OpenAlex source ID.** Never filter on a venue-name string — it silently
misses records indexed under a variant.

```bash
curl -s "https://api.openalex.org/sources?search=IEEE+Transactions+on+Dependable+and+Secure+Computing&per-page=2"
```

Confirmed (check `issn_l` before trusting one):

| Venue | OpenAlex source ID | ISSN-L |
|---|---|---|
| TDSC | `S133795288` | 1545-5971 |
| TIFS | `S61310614` | 1556-6013 |
| TOPS | `S4210174050` | 2471-2566 |

**2. Filter and group.**

```bash
# topical count within one journal
.../works?filter=primary_location.source.id:S133795288,publication_year:2023-2026,title_and_abstract.search:LLM%20agent
# → meta.count = 10

# per-year distribution
.../works?filter=primary_location.source.id:S133795288,publication_year:2023-2026,title_and_abstract.search:agent&group_by=publication_year
# → 2026:19  2025:11  2024:6  2023:7
```

What makes the number reportable:

- **`group_by` returns unordered buckets.** Sort before tabulating.
- **Sanity-check the denominator.** TDSC 2023–2026 total is **1,883**. If a topical filter lands near
  that, the filter isn't filtering.
- **Print the filter next to the number.** "10 TDSC papers" means nothing without
  `title_and_abstract.search:LLM agent` beside it.
- **The current year is partial.** Say so, or the trend you draw is an artifact of the calendar.
- **USENIX Security can't be counted this way** (no DOIs, uneven OpenAlex coverage) and **conference
  counts from OpenAlex are unreliable in general** for security venues. Count those from the per-year
  accepted-papers pages via web search, and mark the method difference in `coverage_limits` — mixing
  an API count and a hand count in one table without saying so is the kind of thing a reviewer finds.
