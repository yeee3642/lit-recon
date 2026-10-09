# Harness: tool bindings and constrained runtimes

The pipeline needs four things: HTTP, JSON/XML parsing, somewhere to write a file, and a way to run
tracks. Everything else varies by harness. This file holds the bindings for Claude Science, the
mapping to Claude Code, and the parts that only matter when the runtime is tight — which is where the
failures are silent and expensive.

Contents: [two planes](#two-planes) · [stage 0](#stage-0--constraints) ·
[delegation](#delegating-tracks) · [stdlib HTTP client](#stdlib-only-http-client) ·
[API templates](#api-query-templates) · [full text](#full-text-extraction) ·
[memory, files, credentials](#memory-files-and-credentials) · [screening budget](#screening-budget) ·
[pacing](#pacing) · [artifacts](#artifacts-and-versioning) · [reviewer](#stage-10--reviewer-agent) ·
[Claude Code](#running-this-outside-claude-science)

---

## Two planes

Mixing these up is the first thing that goes wrong.

- **`repl`** is the control plane. Delegation (`host.delegate`, `host.collect`), credentials
  (`host.credentials`), background findings (`host.findings`). Keep it light.
- **`python`** is the analysis kernel. Merging, dedupe, statistics, spreadsheet writing. A `python`
  cell that needs a secret must declare it, e.g. `credentials=["OpenAlex"]`, then read
  `os.environ["OPENALEX_API_KEY"]`.

Other tools: `web_search`, `fetch_article_fulltext`, `save_artifacts`, `ask_user`, `search_memory`,
`write_memory`, `request_network_access`.

⚠ **`web_search` must be issued on its own.** Batched in the same turn as other tool calls it simply
does not execute, and the silence looks like "no results" rather than "never ran".

---

## Stage 0 — constraints

```python
search_memory(query="<topic> 論文 題目 投稿 場地 限制")
```

Then ask everything that changes downstream structure, in one go — a constraint discovered at stage 7
invalidates stages 3 through 6:

```python
ask_user(header="投稿目標", question="投稿出口是哪一類？",
         options=[{"label":"領域頂會"}, {"label":"領域頂刊"}, {"label":"相鄰領域頂會"}])
ask_user(header="實驗條件", question="實驗可用什麼環境？",
         options=[{"label":"有 root／GPU"}, {"label":"只有無 root 環境"}, {"label":"可租雲端"}])
ask_user(header="範圍", question="要涵蓋哪些面向？", multi_select=True, options=[...])
```

Persist immediately:

```python
write_memory(entity="project:<pid>", append=[
    {"text": "投稿目標為 <場地>；實驗條件 <…>；需避開舊作 <…>", "evidence": "stated"}])
```

`evidence` separates `stated` (the user said so) from `observed` (you verified it). Later sessions
need the difference: a stated constraint can be renegotiated, an observed one cannot.

---

## Delegating tracks

Dispatch all tracks together, and keep **no more than 2–3 agents on the same scholarly API** — they
share an egress IP, and the rate limiting that follows pushes agents onto web paraphrases, i.e. weak
evidence you will have to re-verify later.

```python
import json
M = host.artifact_marker     # save_artifacts first, then embed the marker in the task text

common = f"""
背景：<主題>，目標 <場地>，今天 <日期>。只做文獻蒐集。
規則：
1. 每筆都要有 API 回傳或官方頁面證據；不得從記憶寫 ID、作者、場地；查不到標 verified=false。
2. 必須系統性納入近兩年的預印本。
3. arXiv 每次請求間隔 ≥5 秒，遇 429 等 60 秒；Semantic Scholar 只用 /paper/batch 查場地。
4. OpenAlex 每個請求帶 api_key（repl 內 key = host.credentials.request("openalex")），不送 mailto。
5. 不使用遠端運算；寫檔用 encoding='utf-8'。
6. host.llm 每個 frame 上限 2.0M token，相關性篩選要批次（一次 20–30 篇）。
輸出：JSON list（欄位見 retrieval.md 的 record schema），save_artifacts 後回報 version_id。
"""

schema = {"type": "object", "properties": {
    "corpus_version_id": {"type": "string"},
    "n_records": {"type": "integer"}, "n_verified": {"type": "integer"},
    "queries_used": {"type": "array", "items": {"type": "string"}},
    "key_papers": {"type": "array", "items": {"type": "object"}},
    "observed_gaps": {"type": "array", "items": {"type": "string"}},
    "coverage_limits": {"type": "array", "items": {"type": "string"}}},
    "required": ["corpus_version_id", "n_records", "n_verified",
                 "queries_used", "observed_gaps", "coverage_limits"]}

reqs = [{"task": common + "本軌：<子問題 A>……", "name": "軌道A", "output_schema": schema},
        {"task": common + "本軌：<子問題 B>……", "name": "軌道B", "output_schema": schema},
        {"task": common + "本軌：<子問題 C>……", "name": "軌道C", "output_schema": schema}]

desc = host.delegate(reqs, wait=False)
fids = [d["frame_id"] for d in desc]
json.dump(fids, open("handoff/fids.json", "w"))
```

Collect, and **read every deviation statement line by line**:

```python
res = host.collect(fids, timeout=1800)      # still-running frames return status=running; call again
for r in res:
    print(r["name"], r["status"], r.get("deviations"))
    print(r["structured_output"]["corpus_version_id"])
```

A deviation is not a footnote. Any number produced under partial coverage, rate limiting or a
substitute source is **provisional**, and that limit travels with the number everywhere it appears —
not once in an appendix.

The brief skeleton itself is in `retrieval.md`; don't restate the record schema in the task text,
point at it.

---

## Stdlib-only HTTP client

`urllib.request`, `json`, `xml.etree.ElementTree`, `time` and `re` are enough for all four sources.
No `requests`, no `httpx`, nothing to install.

```python
import json, time, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

UA = "lit-recon/1.0 (academic literature retrieval)"

def _open(req, timeout=30):
    """GET/POST with exponential backoff on 429 and 5xx. Returns bytes."""
    delay = 2
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            # 429 is the normal state of an unauthenticated Semantic Scholar, not an anomaly.
            if e.code in (429, 500, 502, 503, 504) and attempt < 4:
                time.sleep(delay); delay *= 2            # 2, 4, 8, 16
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < 4:
                time.sleep(delay); delay *= 2
                continue
            raise
    raise RuntimeError("unreachable")

def get_json(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    return json.loads(_open(req))

def get_xml(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return ET.fromstring(_open(req))

def post_json(url, payload, headers=None):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"User-Agent": UA, "Content-Type": "application/json", **(headers or {})})
    return json.loads(_open(req))

def q(**params):
    """Build a query string. Always go through this - hand-built ones break on quoted phrases."""
    return urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
```

Two things bite:

- **Hand-concatenated query strings.** arXiv phrase queries need `abs:"prompt injection"` with the
  quotes percent-encoded; Semantic Scholar's boolean syntax uses `+ - | "…"`. Build with
  `urlencode`, never with f-strings, or you will spend an hour debugging an empty result set that is
  really a malformed URL.
- **Atom, not JSON.** arXiv returns Atom XML and namespaces are required in every lookup:

  ```python
  NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
  root = get_xml("https://export.arxiv.org/api/query?" + q(
      search_query='abs:"prompt injection"', start=0, max_results=100,
      sortBy="submittedDate", sortOrder="descending"))
  total = root.findtext("{http://a9.com/-/spec/opensearch/1.1/}totalResults")
  for e in root.findall("a:entry", NS):
      arxiv_id = e.findtext("a:id", default="", namespaces=NS).rsplit("/", 1)[-1]  # strip vN
      journal  = e.findtext("arxiv:journal_ref", namespaces=NS)   # free venue upgrade when present
      doi      = e.findtext("arxiv:doi", namespaces=NS)
  ```

  Read `journal_ref` and `doi` on every entry before running a separate published-version search.
  Both are frequently `None` even for published work, so their absence proves nothing.

---

## API query templates

arXiv, by submission date, newest first:

```
https://export.arxiv.org/api/query?search_query=<q>&start=0&max_results=100&sortBy=submittedDate&sortOrder=descending
https://export.arxiv.org/api/query?id_list=2504.11703,2606.25189          # verify IDs, don't trust a list
```

OpenAlex — `api_key` on every request, **never** `mailto` when a key is in use:

```
https://api.openalex.org/works?search=<詞>&filter=from_publication_date:2024-01-01&per_page=200&cursor=*&api_key=<key>
https://api.openalex.org/sources?search=<場地名>&api_key=<key>                                    # resolve the venue first
https://api.openalex.org/works?filter=primary_location.source.id:<Sxxxx>,publication_year:2026&per_page=200&cursor=*&api_key=<key>
```

Crossref:

```
https://api.crossref.org/works?filter=issn:<ISSN>,from-pub-date:2023-01-01&rows=1000&cursor=*       # a journal
https://api.crossref.org/works?filter=prefix:<DOI 前綴>,from-pub-date:2024-01-01&rows=1000&cursor=*  # by publisher prefix
https://api.crossref.org/works/<DOI>                                                                 # verify one
```

⚠ **Crossref `offset` paging is unstable at these volumes.** Use `cursor`. For a corpus you will
report counts from, fetch twice and take the union — a single pass can silently drop pages.

Semantic Scholar, **venue lookup only** in a constrained run, POST, back off 60 s on 403/429:

```
POST https://api.semanticscholar.org/graph/v1/paper/batch?fields=venue,publicationVenue,externalIds
body: {"ids": ["ARXIV:2504.11703", "DOI:10.1145/3808103"]}
```

Full per-source cookbook, including the bulk search and citation-chasing endpoints: `sources.md`.

Venues with no API, industry documents, advisories:

```python
web_search(query="<場地> <年> accepted papers")     # on its own, see the warning above
```

Blocked domain:

```python
request_network_access(domain="api.github.com")
```

---

## Full-text extraction

Method and defense papers need the **evaluation section**, not the abstract — baseline counts and
adaptive-attack practice live there, and abstract-only reading undercounts both.

```python
fetch_article_fulltext(doi="10.48550/arXiv.<id>")
```

⚠ A 404 here usually means a **new arXiv DOI not yet registered with Crossref**, not a missing paper.
Fall back to `https://arxiv.org/html/<id>v1`, cut out the evaluation section programmatically, and
hand that slice to the screening model. Record which route produced each annotation
(`evidence=fulltext|abstract|title`) — stage 3's statistics are stratified on it.

---

## Memory, files and credentials

### Kernels and memory

A long-lived analysis kernel can be the wrong tool. On a box with ~1.7 GB free, starting one may
never finish — and the usual cause is not memory but a **filesystem grant that is too broad**, so the
kernel blocks mounting a tree it was given access to. The symptom is a startup timeout, which reads
like a resource problem and isn't.

So do retrieval in whatever lightweight evaluation tool is already running, keep state in that one
session, and **write results to disk as you go**:

- **Checkpoint after every source, not at the end.** A run that dies at record 380 having written
  nothing has cost the whole budget.
- **Stream, don't accumulate.** Append each record; don't build one giant list and serialise once.
- Screen on title first; fetch abstracts only for survivors.

### Writing files

Always `open(path, "w", encoding="utf-8")`, and the same on read. Titles and author names carry
diacritics, and where the host default is cp950 `write()` raises `UnicodeEncodeError` partway through
and leaves a truncated, invalid JSON file. For JSON use `ensure_ascii=False` so the file stays
greppable.

### Credential brokers

```python
try:
    key = host.credentials.request("openalex")
except host.CredentialUnavailable:
    key = None                                   # degrade, don't fail the run
```

- **Never print, log or echo the key**, and never write it into a corpus or notes file. A 429 body
  that echoes your key, captured into a run artifact, is a real leak path.
- **Degrade rather than abort.** A missing OpenAlex key costs a supplementary source, not the track.
  Record the skip in `coverage_limits` so the gap is visible in the report.
- **Mind mutually-exclusive auth.** OpenAlex should get `api_key=` and **no** `mailto=` when a key is
  available.

---

## Screening budget

When screening runs through a model with a per-call frame cap and a call-count cap, do the arithmetic
first. A typical shape: ~2.0M tokens per call, ~3.8k tokens of fixed system prefix per call, ~150
calls.

The per-call cap is almost never binding. 25 title+abstract pairs is roughly 9k tokens — three orders
of magnitude under 2.0M. **The call cap is the budget**, and the fixed prefix means small batches
waste it:

| Batch size | Papers screened in 150 calls | Prefix overhead |
|---|---|---|
| 5 | 750 | 570k tokens |
| 25 | 3,750 | 570k tokens |
| 50 | 7,500 | 570k tokens |

Same overhead, 10× the reach. Batch as large as judgement quality allows — 20–30 is where that tops
out, because a model asked to rate 50 abstracts in one call gives the later ones visibly less
attention, a silent quality loss the output format will not show you.

Two consequences: **rules-first is a budget decision**, not just a speed one; and any batch that
fails to parse gets re-run paper by paper, never silently dropped — that is how a systematic bias
enters a number you will publish.

---

## Pacing

| Source | Pace |
|---|---|
| arXiv | ≥3 s documented; use **≥5 s** with parallel tracks, and 60 s after a 429 |
| Semantic Scholar | Backoff 2/4/8/16 s. With no key, expect a 429 on the *first* call |
| Crossref | Polite-pool identifier; otherwise unthrottled at this volume |
| OpenAlex | Generous; batch with `per-page=200` rather than paging in 25s |

Pacing interacts badly with parallel tracks: three agents each respecting a 3-second arXiv interval
are collectively hitting it every second. Serialise the shared source behind one track, or widen the
interval proportionally.

---

## Artifacts and versioning

```python
save_artifacts(files=["literature_master.xlsx", "refs.bib", "final_corpus.json"],
               language="python", checkpoints=["final_corpus.json"])
```

Revisions go back to the **same** artifact as a new version, so the history survives:

```python
save_artifacts(files=["topic_proposal.md"], language="python",
               version_of={"topic_proposal.md": "<artifact_id>"})
```

Background review findings:

```python
host.findings()                                            # inspect
host.findings.mark_addressed(ids, note="<what changed>")   # only once genuinely fixed
```

---

## Stage 10 — reviewer agent

The reviewer gets the deliverables and the supporting tables, **not** your reasoning, and edits
nothing:

```python
task = f"""你是 <場地> 審稿人，獨立審查選題書與文獻回顧，不修改原檔，只交意見。
受審：{M('<選題書 VID>')}、{M('<文獻回顧 VID>')}、{M('<撞題表 VID>')}、{M('<對手表 VID>')}
參考：{M('<錄取論文表 VID>')}、{M('<文獻總表 VID>')}
請做：
1. 逐一核實所有 arXiv ID、DOI、URL 存在且描述相符；列出不符者。
2. 用 ≥10 組不同用詞獨立檢索新穎性，並在附的文獻總表內搜尋；列出最接近 5 篇與重疊程度。
3. 查核事實陳述（廠商行為、版本、CVE）是否有官方來源。
4. 依階段 3 的評估門檻指出缺少的對手、benchmark、指標。
5. 與使用者舊作 <舊作名> 的重複風險。
6. 寫作檢查：比喻、形容詞、「首個／尚無」宣稱。
輸出 review_findings.md，每條含嚴重度 BLOCKER/MAJOR/MINOR、位置、問題、證據、建議修正。"""

schema = {"type": "object", "properties": {
    "review_md_version_id": {"type": "string"},
    "novelty_verdict": {"type": "string"},
    "closest_works": {"type": "array", "items": {"type": "object"}},
    "citation_problems": {"type": "array", "items": {"type": "object"}},
    "findings": {"type": "array", "items": {"type": "object", "properties": {
        "severity": {"type": "string", "enum": ["BLOCKER", "MAJOR", "MINOR"]},
        "location": {"type": "string"}, "issue": {"type": "string"},
        "evidence": {"type": "string"}, "fix": {"type": "string"}},
        "required": ["severity", "issue", "fix"]}}},
    "required": ["review_md_version_id", "novelty_verdict", "closest_works", "findings"]}

d = host.delegate({"task": task, "name": "獨立審查", "output_schema": schema}, wait=False)
```

Giving it the master table matters: the reviewer's most useful finding is usually a paper **you had
already collected** and never connected to the candidate.

---

## Running this outside Claude Science

The method does not depend on the harness; the bindings do. Under Claude Code:

| Claude Science | Claude Code |
|---|---|
| `host.delegate(reqs, wait=False)` | `Agent` / `Task` tool, one call per track, backgrounded |
| `host.collect(fids, timeout=…)` | task-completion notifications; `SendMessage` to continue an agent |
| `output_schema` on a delegation | state the schema in the prompt and validate the returned file yourself — there is no enforcement |
| `deviations` on a result | ask for it explicitly in the prompt; it will not appear otherwise |
| `host.credentials.request(name)` | environment variable, or ask the user; never echo the value |
| `ask_user(header=…, options=[…])` | `AskUserQuestion` |
| `search_memory` / `write_memory` | the memory directory — one fact per file plus the index |
| `save_artifacts(version_of=…)` | git commits in the project repo |
| `fetch_article_fulltext(doi=…)` | `WebFetch` on the DOI or the arXiv HTML URL |
| `web_search` | `WebSearch` |
| `host.llm` batch screening | a subagent, or inline judgement; no frame cap to budget against |
| `python` kernel with `credentials=[…]` | `Bash` with the secret already in the environment |
| `host.findings` | the review agent's returned report |
| `request_network_access(domain=…)` | the permission prompt; a denial is the user's answer, do not retry |

Two things genuinely disappear outside Claude Science and must be replaced by hand: **schema
enforcement** on delegated output, and the **deviation statement**. Both are load-bearing — the first
is what makes the tracks mergeable, the second is what keeps a provisional number from being reported
as final. Ask for both in the prompt and check for them on return.
