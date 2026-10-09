# Stage detail: record schemas and output formats

Companion to `SKILL.md`. Retrieval (stages 1–2) belongs to `lit-recon`; the collision check and the
acceptance analysis have their own files. What is here is the rest: the exact fields and formats, so
two sessions a month apart produce artifacts that line up.

Contents: [stage 0](#stage-0--constraint-list) · [stage 4](#stage-4--competitor-table) ·
[stage 5](#stage-5--candidate-format) · [stage 7](#stage-7--scoring-table) ·
[stage 8](#stage-8--naming) · [stage 9](#stage-9--threshold-to-design-table) ·
[stage 10](#stage-10--handling-findings) · [stage 11](#stage-11--deliverables)

---

## Stage 0 — constraint list

```
target_venue          # the actual venue, not "a top conference"
venue_deadline        # absolute date; relative dates rot
compute               # root? GPU? rentable cloud? what you actually have today
commercial_api_budget # yes/no and roughly how much - this kills or enables whole evaluation designs
own_prior_work        # published AND in review. the entries that must be avoided
writing_preferences   # register, language, things the user does not want to see
paper_template        # the structure the four passages at stage 9 must fit
```

`own_prior_work` is the field that gets skipped and costs the most. Self-overlap is invisible to every
external search in this pipeline — no API knows what the user has in review — and a reviewer familiar
with the author's record spots it immediately. Ask for in-review work explicitly; people do not
volunteer it because it is not public yet.

---

## Stage 4 — competitor table

```
name, kind(academic/industry/substrate), ref, venue_year, layer,
what_it_does, threat_model,
code_url, license, last_commit, stars, repro_scripts, needs_paid_api,
runnable_here(yes/partial/no + reason),
published_results(numbers + the section or table they came from),
their_baselines, relevant_to(candidate numbers)
```

Repository facts:

```
GET https://api.github.com/repos/<owner>/<repo>
→ stargazers_count, license.spdx_id, pushed_at
```

Blocked domain → `request_network_access(domain="api.github.com")`.

Three rules:

- **`runnable_here` is an inference. Say so in the cell.** "no — requires 4×A100, we have one GPU" is
  usable by a future session; "no" is not.
- **A competitor with no public implementation can only be cited.** Record `published_results` with
  the section or table number, and make the experiment design state that this baseline is quoted
  rather than reproduced. Quietly assuming a number will materialise is how an evaluation plan
  becomes undeliverable three weeks before a deadline.
- **Per candidate, name the 3–5 you must beat, and why you must.** A long undifferentiated list means
  nobody chose.

`their_baselines` is worth the effort: it tells you what this venue's reviewers already consider the
obligatory comparison set, which is often broader than what you would have picked.

---

## Stage 5 — candidate format

Candidates come from the intersection of: the gaps the retrieval tracks reported, the regions where
the venue has few precedents but preprints are accumulating, and the cases each competitor does not
handle.

One block per candidate, same shape every time:

```
C<n>
  does:        one sentence on what the work would do
  setting:     threat model, or the problem setting if it is not a security paper
  nearest:     3 papers, with keys from the master table
  differs:     how it differs from each of those three, one line each
  needs:       data, compute, access, commercial API
```

**No names.** Not a title, not a method name, not a working codename — a codename becomes the method
name by stage 8 through pure inertia. See the rule at the top of `SKILL.md`.

Four to five candidates. Fewer means the earlier stages were too narrow; more means stage 6 will be
done shallowly for all of them, which is worse than doing it properly for four.

---

## Stage 7 — scoring table

| Criterion | What it reads | Default weight |
|---|---|---|
| Novelty | the stage-6 verdicts, not your impression | 2 |
| Venue-precedent fit | contribution type and evaluation shape against stage 3 | 1 |
| Competitor re-runnability | share of must-beat baselines actually runnable here | 1 |
| Feasibility | compute, privileges, data, commercial-API budget | 1 |
| Separation from own prior work | different object, interception point, attacker capability, or dataset | 1 |
| Workload | higher score = cheaper | 1 |

Every cell gets a one-line reason. A scoring table without reasons is a number you cannot defend to
the user, to a reviewer, or to yourself in three weeks.

Novelty is weighted double because it is the only criterion that can zero out the paper: a feasible,
well-scoped, cheap topic that is already occupied is worth nothing, while an awkward one that is
genuinely new is still a paper.

**Candidates within 1 point of the winner are not rejected** — they are the extension paper or the
next one. Record them as such, with their scores, so the decision does not have to be re-derived.

---

## Stage 8 — naming

- Title: `<MethodName>: <what it does>`. Plain verb and object, no metaphor.
- Method name: describes the mechanism.
- Subsystem names: one action each — find, label, block, mutate, attest, log.
- Avoid words close to the user's own prior subsystems; a reviewer who knows the record reads it as
  the same system shipped twice.

Checks:

```python
web_search(query='"<MethodName>" <field> paper')
```

Also check each subsystem name against system names appearing in the related work. Two different
systems with the same name in one paper is a correction you make at proof stage, in a hurry.

**The title emphasises what the collision check found unoccupied** — not the most impressive part,
the part that is actually yours. If the title describes a sub-claim that stage 6 marked as existing
work, the paper will be read as that work.

---

## Stage 9 — threshold-to-design table

One row per stage-3 threshold, so the alignment is checkable rather than asserted:

| Threshold (measured at stage 3) | This paper's design |
|---|---|
| Median baselines = N | ≥N competitors, enumerated B1…Bk, each marked reproduced or quoted |
| Median systems evaluated = M | ≥M systems at pinned versions |
| Adaptive/stress testing in X% of papers | whether we do it, and the construction |
| Overhead measured in Y% | which metrics, replicating at least one competitor's original workload |
| Model / dataset mix | open + commercial, dataset list |
| Real-world component | measurement, disclosure, or deployment |
| Known confounders | fixed or stratified — name them |

Replicating a competitor's **original workload** for the overhead comparison matters more than it
looks: overhead numbers measured on different workloads are not comparable, and a reviewer who knows
the baseline paper will say so.

### The four load-bearing passages

Draft these together, in the user's template, with numbers marked `[to be measured]`:

1. abstract
2. third paragraph of the introduction (the contribution paragraph)
3. opening of the methods chapter
4. end of the evaluation chapter

All four must use the **same problem statement, method name and subsystem names**. Writing them in
one sitting is a cheap consistency test: if they cannot be made to agree, the topic is still vague,
and that is much cheaper to discover here than after the experiments are run.

---

## Stage 10 — handling findings

Each finding: severity `BLOCKER`/`MAJOR`/`MINOR`, location, issue, evidence, suggested fix.

- **Recompute every BLOCKER before accepting or rebutting it.** "Statistics not reproducible" means
  actually recomputing them. If the numbers hold and only a selection column was missing, add the
  column and record that this is what happened. Accepting a wrong finding corrupts the proposal;
  waving away a right one is worse.
- **A refuted novelty claim is withdrawn**, and the title and contribution list change with it. Not
  softened — withdrawn.
- Append a disposition table to the end of the proposal:

  ```
  | finding | severity | disposition |
  ```

  That table is what makes the next reader trust the rest of the document.

Revisions go back to the same artifact as a new version (`version_of=`), so the history survives.

---

## Stage 11 — deliverables

| File | Contents |
|---|---|
| `topic_proposal.md` | verdict, thresholds, candidates and collision verdicts, scoring, the title, threat model, research questions, method, difference table, separation from own prior work, experiment design, the four passages, risks, findings disposition |
| `lit_review_report.md` | method and funnel, acceptance patterns, taxonomy and the strongest current method per sub-problem, residual gaps, coverage limits |
| `literature_master.xlsx`, `refs.bib` | the corpus and bibliography (produced by `lit-recon`) |
| `accepted_papers.csv`, `acceptance_patterns.md` | the acceptance corpus and its analysis |
| `baselines.xlsx`, `collision_check.csv` | competitor table and collision table |

Then write the decision to memory — **including what was rejected and why**:

```python
write_memory(entity="project:<pid>", append=[
    {"text": "選定題目 <題名>；新穎性放在 <…>；已放棄 <…> 因 <…>", "evidence": "observed"}])
```

The rejections are the valuable half. Without them a future session re-derives a dead direction from
scratch, which is exactly the failure this whole pipeline exists to prevent — and it is the one
failure mode that recurs, because the reasoning that killed a direction is never written down
anywhere else.

Schedule the collision queries weekly (`scripts/collision_watch.py`) until the paper is submitted.
