# Collision check

The stage that decides whether the paper is worth writing. It is also the stage most often performed
in a way that cannot fail, which is the same as not performing it.

## Check sub-claims, not candidates

A whole candidate is rarely already done. Its *parts* usually are, in different papers, and the
honest novelty is whatever is left. So decompose each candidate's core claim into **2–4 sub-claims**
and adjudicate each one separately.

This also produces the right output when the answer is partial — and partial is the normal answer.
"Sub-claims A and C exist in the literature, B does not" tells you exactly where to put the
contribution. "The candidate is novel" tells you nothing and will not survive contact with a
reviewer.

## Query matrix

Per sub-claim, **3–5 differently-worded queries**, deliberately spread across five vocabulary axes.
Searching one axis five times is one query, not five.

| Axis | Example of what it catches |
|---|---|
| Synonyms | the same mechanism under a different academic name |
| Field jargon | the term insiders use that never appears in a title |
| Industry phrasing | vendor and practitioner wording, usually shorter and blunter |
| Informal name | what people call the attack or technique in conversation |
| Concrete nouns | specific file, API, component, config or protocol names |

The last axis is the highest-yield and the most often skipped. A paper that never uses your abstract
framing will still name the component it attacked.

```python
queries = {
  "子主張A-1": 'abs:"<詞>" AND abs:<詞>',
  "子主張A-2": '(abs:<同義詞1> OR abs:<同義詞2>) AND abs:<對象>',
  # … ≥4 s between calls, sort by submission date descending, take the top 25–30
}
```

Keep this dict in a file. It is the input to the weekly re-run at stage 11, and it is the evidence
behind whatever you write about novelty — "N queries as of \<date\>" is only meaningful if the N
queries still exist.

## The four mandatory sources

Each one catches something the others structurally cannot.

1. **arXiv, targeted, with the last 90 days read closely.** Sorted by submission date descending.
   This is where a collision appears first, and a three-month-old preprint is something a reviewer
   has read and you have not.
2. **OpenAlex.** Published venues and journals, including the ones adjacent to your field that you
   do not follow.
3. **Web search — industry blogs, CVEs, advisories, vendor documentation, accepted-paper lists.**
   An industry disclosure rarely makes your *method* unoriginal. It can make the *problem* no longer
   new, which is harder to argue with, because "practitioners already knew" is not answerable by
   pointing at the absence of a paper.
4. **Your own master table.** Search it with a regex over title and abstract:

   ```python
   pat = r"<詞1>|<詞2>|<詞3>"
   hit = df[df.title.str.contains(pat, case=False, na=False)
            | df.abstract.str.contains(pat, case=False, na=False)]
   ```

   **This is where the nearest work usually is.** You collected it, screened it as `related`, and
   never connected it to this candidate. A reviewer handed your own bibliography will find it in
   minutes. Treat skipping this step as the single most likely way the check fails.

## Verdicts

| Situation | Verdict |
|---|---|
| Every sub-claim already done, by papers or products | **Occupied** — drop the candidate |
| Some sub-claims done | **Adjacent** — novelty moves to the untouched sub-claims; the done ones are *not* claimed as new anywhere in the paper |
| Only industry instances, no academic systematisation | **Room** — but the contribution must then be a systematic method, a new finding, or a general defense. Reproducing what practitioners already do is not a paper |
| Nothing found | Record *"not found as of \<date\> across N queries"* |

"Adjacent" is the most common verdict and the most useful. It does not kill the candidate; it tells
you which sentences in the introduction have to go.

## Wording rules

**"We could not find it" is not "it does not exist."** Write what you did:

> Not found as of 2026-10-09 across 17 queries spanning arXiv (last 90 days), OpenAlex, vendor
> advisories and our own 287-record corpus.

Never write **"first"**, **"no prior work"**, or **"尚無工作"**. Those are the cheapest claims in the
paper to attack and the most expensive to lose — and losing one costs the credibility of every other
claim, because it demonstrates the search was inadequate rather than that the result was wrong.

There is no version of this that is safe because you looked hard. A reviewer needs one paper.

## Collision table

```
candidate, sub_claim, closest_work, id_or_url, date_or_venue, overlap, verdict, checked_on
```

`overlap` is prose: what specifically is shared, in one line. `verdict` is from the table above.
`checked_on` is why the table can be re-run rather than redone.

## The out-of-field precedent

Before writing a verdict, ask whether the mechanism is **isomorphic to an older one in another
field** — OS provenance labelling, taint tracking, capability systems, reference monitors, firewall
policy languages, database integrity constraints. Keyword search across your own field will not find
these, and the citation graph often will not either.

If it is isomorphic, that is not fatal and not something to hide. Address it directly in related
work, and make **why the old mechanism fails in the new setting** the design rationale. That reframing
is usually stronger than the novelty claim it replaces. A reviewer from the older field will see the
resemblance whether or not you mention it; the only question is whether you look like you knew.

## Weekly re-run

`scripts/collision_watch.py` takes the saved query matrix, re-runs it, and reports only what is new
since the last run. The window between choosing a topic and submitting is exactly when someone else
posts it, so this runs weekly until the paper is in — and the authors of the nearest work are worth
watching directly, not just their keywords.
