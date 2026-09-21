# Audit

A record of what was wrong with the previous version and what was done about it.
Written after reading every file in the repository and running the pipeline against
live APIs.

Severity is about user or operator impact, not effort to fix.

---

## Security

### 1. Server-side request forgery in the page reader — *high*

`scrape_url` fetched whatever URL a language model handed it, with no validation:

```python
resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
```

The reader agent chooses that URL from search results and scraped page content —
both attacker-influenceable. A page that says "for full text see
`http://169.254.169.254/latest/meta-data/iam/security-credentials/`" would have had
its cloud instance credentials fetched and pasted into the report.

**Fixed** in `argus/tools.py`. `assert_url_is_safe` now rejects non-HTTP schemes,
non-standard ports, `localhost`/`.local` hosts, and any host resolving to a private,
loopback, link-local, reserved, multicast or unspecified address — IPv4 and IPv6.
Redirects are followed manually so every hop is re-validated, responses are capped
at `SCRAPE_MAX_BYTES`, and non-HTML content types are refused. 14 parametrised tests
cover the blocked cases.

### 2. CORS open to every origin — *high*

```python
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
```

on an endpoint that accepts a user's API key. Any website could call the API from a
visitor's browser and spend the server's Groq and Tavily quota.

**Fixed.** Origins come from `ALLOWED_ORIGINS`, methods and headers are restricted,
and the server logs a warning at startup if it is still running wide open.

### 3. No rate limiting — *medium*

A single visitor in a loop could exhaust the daily quota for everyone. **Fixed** with
a per-IP sliding window (`RATE_LIMIT_REQUESTS` per `RATE_LIMIT_WINDOW_SECONDS`)
returning `429` with a `Retry-After` header. It is in-process, which is correct for a
single worker and documented as needing a shared store beyond that.

### 4. No input validation — *medium*

`topic` was an unbounded string passed straight into prompts. **Fixed** with length
bounds and whitespace normalisation in the request model.

### 5. Untrusted web content mixed into prompts as instructions — *medium*

Scraped pages went into the writer prompt unlabelled, so a page containing "ignore
your previous instructions" was indistinguishable from the operator's own prompt.
**Mitigated** in `argus/prompts.py`: retrieved material is fenced in
`<research_material>` tags and every prompt that handles it states the content is
untrusted data, never instructions. This reduces the risk; it does not eliminate it.

### 6. Caller-supplied API keys could populate a shared cache — *medium*

Introduced with caching and closed before it shipped: results from a request that
used a visitor's own key are never cached, so one user's key can never serve another
user's request. Covered by `test_caller_supplied_keys_are_never_cached`.

---

## Correctness

### 7. The progress display was fabricated — *high*

The old frontend made one blocking `POST`, then, after it returned, animated all
five stages with `setTimeout`:

```js
const res = await axios.post(`${API}/research`, ...);   // everything happens here
setDone([0]); setActive(1); setProgress(20);
addLog("Search complete — sources found", "success");
await delay(500);
setDone([0,1]); setActive(2); setProgress(40);
```

Every timestamp, stage transition and log line in that feed was invented on the
client after the work had already finished.

**Fixed.** The pipeline is an async generator that yields events as work happens, the
API streams them as server-sent events, and the UI renders only what it receives.
Stage bars are positioned and sized by the server's own timings.

### 8. Cerebras could never work without a pasted key — *high*

```python
return ChatOpenAI(model="llama3.1-8b", api_key=api_key, base_url="https://api.cerebras.ai/v1")
```

`api_key` was `None` whenever the user did not paste one, so the OpenAI client fell
back to `OPENAI_API_KEY` — a variable this project never sets or documents. The
provider was permanently broken on the default path.

**Fixed.** `get_llm` resolves the caller's key, then that specific provider's
configured key, and raises `MissingCredentialsError` (surfaced as `402` with an
actionable message) rather than constructing a client that cannot authenticate.
Cerebras now uses `langchain-cerebras` instead of the OpenAI compatibility shim.

### 9. Every model in the registry was dead — *high*

Discovered by running the pipeline: it reached the writer stage and failed with

```
The model `llama-3.3-70b-versatile` does not exist or you do not have access to it.
```

Querying the provider confirmed Groq no longer serves any Llama model for tool use.
The registry's entire Groq and Cerebras line-up had been retired upstream.

**Fixed.** The registry now points at `openai/gpt-oss-120b`, `openai/gpt-oss-20b` and
`qwen/qwen3.8-27b`, with the old names kept as aliases so existing clients resolve.
`scripts/check_models.py` probes every entry against its provider and exits non-zero
on a retired model, so this is caught deliberately next time.

### 10. The stream's time budget could not fire — *medium*

Introduced during this work and caught by running it: the deadline was checked only
when an event arrived, so a stage sleeping through a rate-limit backoff emitted
nothing and the run could overrun indefinitely. **Fixed** by enforcing the budget
around the *wait* for each event, and covered by a test that stalls the pipeline.

### 11. An empty stream failed a run that had done all its work — *medium*

Reasoning models sometimes stream only hidden chain-of-thought and no content
chunks, which raised "The model returned an empty report" after search and read had
already succeeded. **Fixed** with one non-streaming retry before giving up.

### 12. Two finished features were never wired in — *medium*

`build_fact_checker_chain` and `build_credibility_chain` were fully written and never
called by anything. **Fixed** — both now run as pipeline stages with their own tabs,
and fact-check verdicts are parsed into structured output.

### 13. The reader agent fought the model for no benefit — *medium*

The old reader was a ReAct agent prompted to call `scrape_url` with a URL the system
already had, including a paragraph arguing with the model about whether URLs existed:

```python
f"Do NOT say you cannot find URLs — they are clearly listed after 'URL:' ..."
```

It read one page per run and could fail if the model declined to call the tool.

**Replaced** with a deterministic parallel fetch of the top `SCRAPE_MAX_PAGES`
sources. Measured on a live run: 3 pages in 2.4s instead of 1 page, no LLM tokens
spent, and no failure mode where the model simply refuses.

### 14. A redirected page lost its link back to its source — *medium*

Found by looking at the finished UI: the header read "3 read in full" while only
one source carried the badge. `fetch_page` returns the URL it *landed* on, and the
client matched pages to search results on that. Any source that redirected — a
`utm` strip, an `http`→`https` upgrade — silently stopped matching.

**Fixed.** A page now carries `source_url`, the URL that was requested, alongside
`url`, where it ended up. The client correlates on the former. Verified on a live
run: three of three pages match, including one that redirected.

### 15. A page with no text counted as read — *medium*

Also found in the UI: a card reading "Read in full — 0 characters". A
client-rendered page returns 200 with an empty shell, so extraction produced
nothing while the fetch counted as a success. The report was not grounded in it,
but the source count said otherwise.

**Fixed.** `fetch_page` raises `EmptyPageError` below `MIN_USEFUL_CHARS`, so such a
page is reported as unread with a reason instead of inflating the count.

### 16. Download filenames could end in a dash — *low*

Caught by a frontend test the moment it was written: `slugify` stripped trailing
dashes *before* truncating, so any topic cut mid-word produced `topic-.md`. Fixed
by trimming after the slice.

### 17. The PDF export drew black boxes instead of characters — *medium*

Caught by exporting a real report rather than the synthetic fixture. ReportLab's
built-in fonts are WinAnsi-encoded, and the writer emits typographic characters
outside cp1252 — one report contained **58 non-breaking hyphens and 32 narrow
no-break spaces**. Each rendered as a tofu box, so "low‑carbon" printed as
"low■carbon" throughout.

**Fixed** with `winansi()`: explicit substitutions for the common offenders, then
an NFKD fold to catch ligatures, then a final pass dropping anything still
unrepresentable. A test asserts the output of hostile input is always cp1252-
encodable, so this cannot regress silently.

The synthetic fixture passed the whole time. Only a real export showed it.

### 18. Frontend and backend model lists had already drifted — *low*

The backend offered `Groq — Llama 3.1 8B`; the UI never listed it. Model identity was
a display string matched with `==`, so a punctuation change would silently fall
through to a default. **Fixed** — models have stable ids, the frontend fetches the
catalogue from `/api/models`, and legacy display strings resolve as aliases.

---

## Reliability

### 19. Parallel review stages exceeded the free tier — *high*

Found by running the pipeline: firing all four review chains at once produced a
`429` on one and a `413` on another, because fact-check alone asked for 8,516 tokens
against an 8,000 token-per-minute cap. Two of seven stages failed on every run.

**Fixed** three ways — `REVIEW_CONCURRENCY` gates in-flight chains, `MAX_RESEARCH_CHARS`
caps any single payload, and rate-limit errors are retried using the delay the
provider itself reports. All seven stages now complete.

### 20. Raw provider errors were shown to users — *medium*

A throttled run surfaced 400 characters of provider JSON. `friendly_error` now
translates the common failures into something actionable.

### 21. Unpinned dependencies — *medium*

`requirements.txt` listed 19 bare package names. A fresh deploy could install a
different major version of LangChain than the one tested. **Fixed** — both
requirements files are pinned.

### 22. No tests, no CI, no container — *medium*

**Fixed.** 105 backend tests and 43 frontend tests, all offline and deterministic;
GitHub Actions running lint, format, tests on two Python versions, the frontend
typecheck, tests and build, and a Docker image smoke test; and a non-root
Dockerfile with a health check.

---

## Housekeeping

- `print(f"DEBUG model_choice: '{model_choice}'")` ran on every request. Replaced with
  structured logging.
- `app.py` — 909 lines of Streamlit duplicating the pipeline, with its own drifting
  copy of the model list — moved to `legacy/streamlit_app.py`. It still runs via the
  compatibility shims.
- The frontend carried `axios`, `react-syntax-highlighter` and `web-vitals` as
  dependencies. None were used; removed.
- The frontend ran on Create React App, which is unmaintained and cannot build
  Tailwind v4. Migrated to Vite + TypeScript; `tsc --noEmit` is now part of the
  build, and the Markdown renderer is code-split out of the landing bundle.
- `tools.py` imported `rich.print`, overriding the builtin in a module with no CLI.
- The report was exportable only as `.txt`. Now Markdown (with critique, fact-check
  and sources) or the full JSON result.

---

## Known limitations

These are deliberate, not oversights:

- **Rate limiting is per-process.** Correct for one worker; multiple instances need a
  shared store such as Redis.
- **The cache is in-memory.** It is cleared on restart, which on a free tier that
  sleeps means most cold visitors get a fresh run.
- **Prompt-injection mitigation is partial.** Fencing and instruction-hardening reduce
  the risk from scraped content but cannot eliminate it.
- **Gemini and Cerebras entries are unverified.** No keys were available to probe them;
  `scripts/check_models.py` will confirm them once keys exist.
- **Credibility scores are model judgement**, not a reputation database. They are
  useful as a prompt for scepticism, not as ground truth.
