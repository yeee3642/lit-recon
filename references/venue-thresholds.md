# Venue acceptance analysis

Two numbers decide the shape of the paper: **what kinds of contribution the venue actually accepts**,
and **how hard its evaluations are**. Both are measurable from the last few years of proceedings, and
guessing either one produces a topic that is interesting and unpublishable.

Everything downstream depends on this: stage 5 looks for regions with few precedents, stage 7 scores
fit against it, stage 9 aligns the experiment design to it.

## 1. Build the acceptance corpus

Delegate this to one agent. Route depends on what exists for the venue:

| Source available | Method |
|---|---|
| OpenAlex has the venue as a source | Resolve `/sources?search=<venue>` to a source ID, then pull every year in full via `primary_location.source.id` + `publication_year` |
| Crossref has DOIs | Pull by `container-title`, ISSN, or DOI prefix. **Use `cursor`, not `offset`** — offset paging is unstable at these volumes; fetch twice and union when the count has to be reportable |
| No DOIs | Web-search the official accepted-papers or sessions page and take every title |
| Current year not yet published | Use the official acceptance list — titles and authors only — and mark `evidence=title` |

Record the route per paper. The statistics are stratified on it, and a corpus assembled by three
different routes without that column cannot be defended.

## 2. Screen, then annotate

**Wide screen** on titles, plus abstracts where available, against topic terms → candidate set.

**Inclusion judgement** in batches through the screening model. Any batch that fails to parse gets
re-run paper by paper. Never silently drop a paper because its batch errored — that is how a
systematic bias enters a number you will publish.

**Annotate** each included paper:

```
contribution_type(attack/measurement/defense-system/detection/benchmark/SoK/formal),
target, defense_layer, threat_model, n_systems_evaluated,
models_open, models_commercial, benchmarks, baselines_compared, n_baselines,
metrics, adaptive_attack, overhead_measured, real_world, artifact,
evidence(fulltext/abstract/title), in_core_set, fulltext_read
```

For method, defense and detection papers, read the **evaluation section in full** — baseline counts
and adaptive-attack practice live there and essentially never in the abstract. Retrieval route and
the arXiv-DOI 404 fallback are in `harness.md`.

## 3. Make the statistics reproducible

This is the gate. A number whose selection cannot be recomputed from the attached table reads as
invented even when it is correct — and "unreproducible" and "wrong" get the same reviewer response.

Two columns carry it: `in_core_set` (did this paper pass the topical screen) and `fulltext_read`
(did we read the evaluation section). Every reported statistic filters on them explicitly:

```python
core = acc[acc.in_core_set]
s = core[core.contribution_type.isin(["defense-system", "detection"]) & core.fulltext_read]
nb = pd.to_numeric(s.n_baselines, errors="coerce")
print(len(s), nb.median(), nb.quantile(.25), nb.quantile(.75),
      (s.adaptive_attack == "yes").sum(), (s.overhead_measured == "yes").sum())
```

`scripts/venue_stats.py` computes the standard summary and prints each figure with its filter and
denominator attached, so the report cannot accidentally quote a bare number.

Three rules for reporting:

- **Every proportion ships with its denominator and its filter.** Not "median 4 baselines" but
  "median 4 (IQR 3–6), n=31 defense-system papers read in full".
- **Abstract-only papers are counted separately, never pooled.** Reading only the abstract
  systematically *undercounts* baselines, so pooling drags the median down and you will then design
  an under-powered evaluation against it.
- **The current year is partial.** Say so, or a trend line becomes an artifact of the calendar.

## 4. What this stage outputs

- Papers per year, and the distribution of contribution types.
- Papers per layer and per target — and from that, **the regions with few precedents**. Cross these
  against where preprints are accumulating; that intersection is where stage 5's candidates come from.
- The evaluation profile for method-type papers: baseline count, which benchmarks, what share do
  adaptive or stress testing, what share measure overhead, the open/commercial model mix, the
  dataset list, and what counts as a real-world component here.
- Coverage and gaps: which years are complete, which are titles only, which route produced each.

## Reading the result

Few precedents in a region means one of two things, and they look identical in the data:

- the venue **has not seen** work there yet — an opening, and the piling-up preprints confirm it; or
- the venue **does not take** work of that kind — a wall, and no amount of quality fixes it.

Distinguish them before building a candidate on top. The tell is usually adjacent: if the venue
accepts that *contribution type* elsewhere, on different targets, the region is an opening. If the
contribution type is absent across every target, it is a wall, and the paper belongs somewhere else.

This is also the stage that quietly answers a question nobody asks out loud: **does this topic
publish where you are submitting at all.** If the answer is no, finding that out here costs a day.
