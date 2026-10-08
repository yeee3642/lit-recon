# Writing a track brief

A track agent should never have to ask you a question. It gets one brief and produces a corpus file,
a notes file and a structured report. If it has to guess at the schema, the allowed sources, or what
counts as `core`, you get three tracks that can't be merged.

About 85% of a brief is identical across tracks. Write that once; per track you only change the
**track name, seeds, facets, task description and scale target**.

> Keep the brief out of the repo if it names unpublished work. A brief that lists your seeds, your
> facets and your target venue is a readable summary of your next paper. Fill the private parts from
> a local file and keep only the skeleton under version control.

---

## Skeleton

### 1. Context (shared)

- The paper's topic in one sentence, and the target venues.
- What this round is for, and what happens to the output next — "collection only; the main session
  merges, annotates and selects the topic" tells the agent not to editorialize or stop early.
- Today's date. Agents reason badly about "recent" without it.

### 2. Runtime constraints (shared)

State these as hard rules with the reason attached, because an agent that doesn't know *why* will
optimize around them. Anything learned the hard way in a previous run belongs here — see
`constrained-runtime.md`. Typical content: which execution tool to use and which to avoid, memory
ceiling, file-writing encoding, request pacing.

### 3. Sources (shared)

Per source: the endpoint, the query syntax, the auth story, and the known failure. Lift from
`sources.md`. State explicitly which sources are **not** reachable and must not be attempted — an
agent that spends twenty minutes fighting a bot-gated site has spent your budget on nothing.

### 4. Hard rules (shared)

- No fabrication. Every record needs API-returned evidence. Unfound → `verified: false` with a reason,
  never a guess.
- Never write an identifier from memory — search for it.
- Preprints from the current and prior year are mandatory, tagged. Give the reason: a prior proposal's
  "first / no prior work" claim was refuted by 64 preprints it had excluded.
- Screening budget: rules first; batch 20–30 title+abstract pairs per model call; cap the call count.

### 5. Output contract (shared)

The record schema, field by field, with the enumerated vocabularies spelled out (`venue_short`,
`relevance`, `verified_by`, `facet`). Then the structured report: counts, the 10–20 most important
papers with a one-line *why* each, observed gaps, coverage limits.

Ask for counts that are **checkable against the corpus file** — `n_records`, `n_core`, `n_verified`,
`n_preprints`. A number that can't be recomputed from the artifact is a number you can't defend.

### 6. The track (per track — the only part you rewrite)

- `track` value.
- The task in two or three sentences: what class of work this track owns.
- **Seeds**, with the instruction to *look up* their identifiers rather than trust the list's
  spelling. Name them by title, not by ID.
- **Facets** — the sub-topic vocabulary for this track, enumerated. Facets are what make a 120-record
  corpus navigable, and they only work if every track agent uses the same closed set within its track.
- **Overlap targets** — the user's own projects this track might collide with, each with enough
  description to judge overlap. If a project is known only by a codename and a subsystem list, say so
  and require the agent to mark the verdict as inferred.
- Scale target, as a range. `core+related ≈ 70–130` sets a useful expectation; "find everything" does
  not.

---

## Facets

Facets subdivide a track; relevance rates a paper against your claim. They are orthogonal — a
`background` paper still gets a facet.

Keep each track's facet set closed, 4–6 values, and name them for *mechanisms* rather than topics, so
a paper lands in one. `ifc-taint`, `plan-execute-separation`, `capability`, `runtime-monitor` each
describe something a paper *does*. `security`, `llm`, `evaluation` describe what it is about, and
everything lands in all of them.

---

## Worked example

Neutral topic, to show the shape. Three tracks split by **defense layer**, which is a generally
useful axis when the paper proposes a mechanism: the thing that enforces, the thing that decides, and
the thing that measures.

| Track | Owns | Facets |
|---|---|---|
| `mechanism` | The enforcement layer: how the boundary is actually implemented, plus the attack research that breaks it, plus the classic systems work that is the chapter's baseline | `kernel-isolation` / `vm-isolation` / `language-runtime` / `syscall-filter` / `network-egress` / `escape-attack` |
| `policy` | The decision layer: what is allowed, who says so, how it is specified and enforced at runtime — policy languages, reference monitors, capability models, permission models of the surrounding ecosystem | `policy-language` / `runtime-monitor` / `capability` / `permission-model` / `authorization-flow` |
| `evaluation` | Benchmarks and measurement, **recording how each one builds its execution environment**, plus per-year counts in the target venues | `benchmark` / `attack-corpus` / `metric` / `venue-count` |

The third track is doing two jobs on purpose. A benchmark paper is interesting twice — once as related
work, once as something you may have to run against — so the brief asks for its *environment
construction*, not just its headline number. And the venue counts answer a question the other tracks
can't: does this topic actually publish where you are submitting.

The split also passes both tests from `SKILL.md`: a paper proposing a seccomp profile has one obvious
home, and a paper proposing a policy language *enforced by* a sandbox will be found by two tracks —
which is the shared boundary you want.

---

## What a thin brief costs

| Omission | What you get |
|---|---|
| No schema | Three corpora that can't be merged; a day of reconciliation |
| No `verified` field | A corpus you cannot distinguish from a plausible one |
| No "preprints mandatory" | A clean peer-reviewed corpus and a refuted novelty claim |
| No facets | 120 records in one undifferentiated list |
| No unreachable-source list | Budget burned on a bot-gated site |
| No scale target | Either 15 records or 600 |
| No date | "Recent work" meaning 2023 |
