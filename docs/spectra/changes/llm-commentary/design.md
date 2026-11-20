## Context

Events carry deterministic `analysis.what/why/next` and an `evidence` map (from `prediction-and-events`). The user wants LLM-written commentary on top. The user's working preference is local-first privacy with cloud LLMs limited to public information; F1 timing data is public, so both a cloud model (Gemini) and the lab's self-hosted model server fit. This is Stage 3 work: it must never block the core demo.

The lab server at the user's university exposes an OpenAI-compatible API (`/v1/models`, `/v1/chat/completions`) behind a router that loads models on request. Measured on 2026-11-20: `/v1/models` lists `glm`, `nemotron`, `deepseek`, `minimax`, `step` and their `-long` variants, with no Qwen model; `glm` (served as `glm-5.3-flash`) answered a 3-word prompt in 1.2 s with `finish_reason: stop` and no reasoning text. The first Gemini call (`gemini-4-hydrogen`) on the same day returned HTTP 503 "high demand". The user chose to run AUGUR commentary with the lab `glm` first.

## Goals / Non-Goals

**Goals:**

- One short paragraph of commentary per event, in an analyst's voice, in English or Traditional Chinese.
- No invented numbers or drivers reach the viewer.
- Everything works without an API key or LLM server.
- The same commentary path works with Gemini or with any OpenAI-compatible server (the lab `glm` first).

**Non-Goals:**

- Commentary for the Wrapped cards.
- Streaming or live generation inside an API request.
- Provider-specific SDKs other than google-genai (OpenAI-compatible servers are reached with the Python standard library).
- Sending event outcomes to the LLM (they would leak the future during replay).

## Decisions

### Narrator interface with an offline default

`Narrator` protocol: `name` and `narrate(event) -> str | None`. Built-ins: `none` (always None), `gemini`, and `openai_compat`. The template analysis stays the source of truth; commentary is an optional extra field. Alternative: replace the template text with LLM text. Rejected because tests, bench, and offline users need deterministic text.

### Gemini call through google-genai

`GeminiNarrator` uses the `google-genai` SDK: `genai.Client(api_key=GEMINI_API_KEY).models.generate_content(model=GEMINI_MODEL, contents=prompt, config={"temperature": 0.4, "max_output_tokens": 200})`. `GEMINI_MODEL` defaults to `gemini-flash-latest`, the alias the Gemini API documentation describes for the newest Flash model; set a fixed model id for reproducible output. The prompt contains only the event type, lap, drivers, evidence, and template What/Why/Next, never `outcome` fields, and asks for at most 60 words (English) or 120 characters (Traditional Chinese), conditional and probabilistic in tone, no instructions to teams. On HTTP 429 or 5xx it retries twice with 2 s and 4 s waits; after that the event gets no commentary.

### OpenAI-compatible narrator for self-hosted servers

`OpenAICompatNarrator` (name `openai_compat`) sends the same prompt as one user message to `POST <AUGUR_LLM_BASE_URL>/chat/completions` with `{"model": AUGUR_LLM_MODEL, "temperature": 0.4, "max_tokens": 200}` using `urllib.request` from the standard library, so no new dependency is needed. `AUGUR_LLM_BASE_URL` is required (for example `http://<lab-host>:11400/v1`) and must start with `http://` or `https://`; `AUGUR_LLM_MODEL` defaults to `glm`; `AUGUR_LLM_API_KEY` is optional and, when set, is sent as `Authorization: Bearer <key>`. The text is `choices[0].message.content` with any `<think>...</think>` block removed; `reasoning_content` is ignored. Each request has a 120 s timeout (estimate: the router loads unloaded models on the first request; measure the cold-load time on the lab server and raise it only with evidence). Retries match Gemini: HTTP 429 or 5xx retried twice with 2 s and 4 s waits. Alternative: the `openai` Python SDK. Rejected because one POST does not justify a new dependency.

### Narrator selection

`AUGUR_NARRATOR` (default `gemini`) selects the narrator for both `augur.narrate` (when `--narrator` is omitted) and the API's commentary lookup. The cache key's `llm_model` is the configured model name (`GEMINI_MODEL` or `AUGUR_LLM_MODEL`), not the name the server reports, so the lab router alias `glm` stays stable in the cache.

### Grounding check before storing

After generation, every number in the text (integers, decimals, percentages) must match the event's lap or a value in the evidence or template text (the lap is in the prompt, and the fading-tyres template does not repeat it: on 2026-11-20 all 10 rejections of 116 Abu Dhabi `glm` texts were the event's own lap), comparing percentages with their fractions (62% matches 0.62) and allowing rounding to the shown precision, and every three-letter uppercase driver code must be in the event's `drivers` or evidence. A failing text is discarded and the reason is printed as `rejected <event_id>: <reason>`. Alternative: trust the model. Rejected because invented numbers would undermine the benchmark story.

### Generate in a separate command and cache

`python -m augur.narrate --race <race_id> [--model lightgbm] [--narrator gemini|openai_compat|none]` generates commentary for events that have none cached and stores it in `commentary(event_id, model, narrator, llm_model, lang, prompt_version, text, created_at)`. The API joins it into `/events` as `commentary` (null when absent). A later live service calls the narrator for each new event. Alternative: generate inside `augur.analyze`. Rejected so that analysis stays offline and deterministic.

### Commentary label comes from the response

The dashboard cannot read backend environment variables, so `/events` adds one top-level field, `commentary_model`: the configured LLM model name of the current narrator settings (for example `glm` or `gemini-4-hydrogen`), or null when the narrator is `none` or the narrator settings are invalid. Alternative: make each event's `commentary` an object `{text, llm_model}`. Rejected because it changes the field type the contract already fixed; every served commentary row comes from the same current settings, so one top-level name is enough.

## Implementation Contract

- Command output: `narrated <race_id>: <ok> ok, <rejected> rejected, <failed> failed, <cached> cached`. After 3 network errors in a row with no HTTP status (refused, unreachable, timed out) it prints `stopped after 3 connection errors in a row; <n> events not tried`, counts those events as failed, and exits 0. With the `none` narrator it prints `narrator none; nothing generated` and exits 0.
- Rounding tolerance: a shown number matches a value when they differ by at most half a unit of the shown precision, so 1.25 grounds both "1.2" and "1.3". Without the narrator's required setting it prints `<SETTING> not set; nothing generated` and exits 0: `GEMINI_API_KEY not set; nothing generated` for `gemini`, `AUGUR_LLM_BASE_URL not set; nothing generated` for `openai_compat`.
- `/events` events gain `commentary` (string or null); the response gains top-level `commentary_model` (string or null); no other field changes.
- Dashboard: when the primary event has `commentary`, the card shows it first as a quote labelled `AUGUR commentary · <commentary_model>`, followed by What / Why / Next.
- Acceptance: `pytest backend` with a fake Gemini client and a fake HTTP opener covers prompt content (no outcome fields), grounding pass and fail cases, caching, retries, `<think>` removal, and the missing-setting messages; `npm --prefix frontend run test` covers the quote block. Manual: with the lab server, narrate `2024-24-abu-dhabi-grand-prix` with `--narrator openai_compat` and record the ok/rejected/failed counts.
- Scope in: narrator interface, Gemini narrator, OpenAI-compatible narrator, `AUGUR_NARRATOR` selection, grounding check, cache table, command, API fields, card block, AGENTS.md wording for the narrator rule. Scope out: Wrapped commentary, provider SDKs other than google-genai, live generation.

## Risks / Trade-offs

- [The grounding check rejects good text that rounds differently] → allow rounding to the shown precision; record the rejection rate on the demo race and loosen only with evidence. Measured 2026-11-20: the template texts of all 152 Bahrain and 116 Abu Dhabi events pass the check.
- [`gemini-flash-latest` or the lab router alias `glm` changes the underlying model over time] → `llm_model` is stored with each text; a fixed model id gives reproducible results where the provider offers one.
- [API cost and rate limits] → one call per event, cached; the demo races have 152 (Bahrain) and 116 (Abu Dhabi) events (measured).
- [The lab server is reachable only from the university network or VPN] → `augur.narrate` reports the events as failed and exits 0; cached commentary keeps working offline.
