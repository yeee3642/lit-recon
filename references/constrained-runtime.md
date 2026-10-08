# Running in a constrained runtime

Some harnesses give you a shell, a network and plenty of RAM. Others give you one sandboxed kernel,
stdlib only, a credential broker and a hard token budget. The method in `SKILL.md` doesn't change —
but in the second case the failure modes are specific, silent, and expensive, so read this before
writing requests rather than after they break.

Contents: [stdlib HTTP](#stdlib-only-http) · [memory and kernels](#memory-and-kernel-startup) ·
[writing files](#writing-files) · [credential brokers](#credential-brokers) ·
[screening budget](#token-budgeted-screening) · [pacing](#pacing)

---

## Stdlib-only HTTP

`urllib.request`, `json`, `xml.etree.ElementTree`, `time` and `re` are enough for all four sources.
No `requests`, no `httpx`, nothing to install. This is the whole client:

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
    """Build a query string. Always go through this — hand-built ones break on quoted phrases."""
    return urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
```

Two things that bite:

- **Hand-concatenated query strings.** arXiv phrase queries need `abs:"prompt injection"` with the
  quotes percent-encoded; Semantic Scholar's boolean syntax uses `+ - | "…"`. Build with
  `urlencode`, never with f-strings, or you will spend an hour debugging an empty result set that is
  really a malformed URL.
- **Atom, not JSON.** arXiv returns Atom XML. Namespaces are required in every `find`:

  ```python
  NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
  root = get_xml("https://export.arxiv.org/api/query?" + q(
      search_query='abs:"prompt injection"', start=0, max_results=100,
      sortBy="submittedDate", sortOrder="descending"))
  total = root.findtext("{http://a9.com/-/spec/opensearch/1.1/}totalResults")
  for e in root.findall("a:entry", NS):
      arxiv_id = e.findtext("a:id", default="", namespaces=NS).rsplit("/", 1)[-1]  # keep version off
      journal  = e.findtext("arxiv:journal_ref", namespaces=NS)   # free venue upgrade when present
      doi      = e.findtext("arxiv:doi", namespaces=NS)
  ```

  Read `journal_ref` and `doi` on every entry before running a separate published-version search —
  arXiv often already knows where the paper appeared.

---

## Memory and kernel startup

A long-lived analysis kernel can be the wrong tool. On a box with ~1.7 GB free, starting one may
simply never finish — and the usual cause is not memory at all but a **filesystem grant that is too
broad**, so the kernel blocks trying to mount a directory tree it was given access to. The symptom
is a startup timeout, which reads like a resource problem and isn't.

So: do the retrieval in whatever lightweight evaluation tool the harness already has running, keep
state in that one session, and write results to disk as you go rather than holding a 400-record
corpus in memory across a restart you may not get.

Practical consequences:

- **Checkpoint after every source, not at the end.** A run that dies at record 380 and has written
  nothing has cost you the whole budget.
- **Stream, don't accumulate.** Append each record to the file; don't build one giant list and
  serialize once.
- Don't parse every abstract into memory to decide screening. Screen on title first, fetch abstracts
  only for survivors.

---

## Writing files

Always `open(path, "w", encoding="utf-8")`. Paper titles and author names carry diacritics, and on a
Windows host the default encoding is cp950 — `write()` raises `UnicodeEncodeError` partway through and
leaves a truncated, syntactically invalid JSON file. The same applies to reading back:
`open(path, encoding="utf-8")`.

For JSON, `json.dump(..., ensure_ascii=False)` keeps the file readable; `ensure_ascii=True` is safe but
turns every non-ASCII name into escapes you then can't grep.

---

## Credential brokers

Some harnesses hold API keys behind a broker rather than in the environment:

```python
try:
    key = host.credentials.request("openalex")   # name varies by harness
except host.CredentialUnavailable:
    key = None                                   # degrade, don't fail the run
```

Three rules:

- **Never print, log or echo the key**, and never write it into the corpus file or a notes file.
  A 429 response body that echoes your key, captured into a run artifact, is a real leak path.
- **Degrade rather than abort.** A missing OpenAlex key costs you a supplementary source; it should
  not cost you the track. Record the skip in `coverage_limits` so the gap is visible in the report.
- **Mind mutually-exclusive auth.** Some APIs want a key *or* a polite-pool identifier, not both;
  OpenAlex in particular should get `api_key=` and **no** `mailto=` when a key is available. Sending
  both is not harmless — follow whatever the brief specifies for that harness.

---

## Token-budgeted screening

When screening runs through a model with a per-call frame cap and a call-count cap, do the arithmetic
before you start. A typical shape: ~2.0M tokens per call, ~3.8k tokens of fixed system prefix on
every call, ~150 calls total.

The per-call cap is almost never your binding constraint. 25 title+abstract pairs is roughly 9k
tokens — three orders of magnitude under a 2.0M frame. **The call cap is the budget**, and the fixed
prefix means small batches waste it:

| Batch size | Papers screened in 150 calls | Prefix overhead |
|---|---|---|
| 5 | 750 | 570k tokens |
| 25 | 3,750 | 570k tokens |
| 50 | 7,500 | 570k tokens |

Same overhead, 10× the reach. So batch as large as judgment quality allows — and 20–30 is where that
tops out in practice, because a model asked to rate 50 abstracts in one call starts giving the later
ones visibly less attention, which is a silent quality loss you won't see in the output format.

Two more consequences:

- **Rules first is a budget decision, not just a speed one.** Keyword exclusion of the obviously
  out-of-field costs zero calls. Spend model judgment only on the ambiguous middle.
- **Screen on title alone for the first pass** when the candidate set is large, then fetch abstracts
  only for survivors. Titles are ~15 tokens; abstracts are ~350.

---

## Pacing

| Source | Pace |
|---|---|
| arXiv | ≥3 s between calls. It is a courtesy limit that is actually enforced. |
| Semantic Scholar | Backoff 2/4/8/16 s on 429. With no key, expect a 429 on the first call. |
| Crossref | Polite-pool identifier; otherwise unthrottled in practice at this volume. |
| OpenAlex | Generous; batch with `per-page=200` rather than paging in 25s. |

Pacing interacts badly with parallel tracks: three agents each respecting a 3-second arXiv interval
are collectively hitting it every second. Either serialize the shared source behind one track, or
widen the interval proportionally to the number of tracks.
