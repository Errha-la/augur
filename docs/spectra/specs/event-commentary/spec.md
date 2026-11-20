# event-commentary Specification

## Purpose

Add optional commentator-style text to race events with an LLM, while guaranteeing that every number and driver it mentions comes from AUGUR's own evidence, and keeping AUGUR fully usable without an API key or LLM server.

## Requirements

### Requirement: Narrator interface

The system SHALL define a `Narrator` protocol with `name` and `narrate(event)` returning text or None, with built-in narrators `none`, `gemini`, and `openai_compat`. The `gemini` narrator SHALL call the model named by `GEMINI_MODEL` (default `gemini-flash-latest`) through the google-genai SDK with temperature 0.4 and at most 200 output tokens, in the language set by `AUGUR_COMMENTARY_LANG` (`en` default, or `zh-TW`). The prompt SHALL contain the event type, lap, drivers, evidence, and template analysis, and SHALL NOT contain `outcome`, `outcome_lap`, or `outcome_text`.

#### Scenario: Prompt excludes outcomes

- **WHEN** the narrator builds a prompt for an event whose outcome is "hit"
- **THEN** the prompt contains the evidence values and no outcome field or value

---
### Requirement: OpenAI-compatible narrator

The `openai_compat` narrator SHALL send the same prompt as one user message to `POST <AUGUR_LLM_BASE_URL>/chat/completions` with the model named by `AUGUR_LLM_MODEL` (default `glm`), temperature 0.4, and at most 200 tokens, adding `Authorization: Bearer <AUGUR_LLM_API_KEY>` only when that variable is set. `AUGUR_LLM_BASE_URL` MUST start with `http://` or `https://`. The narrator SHALL return `choices[0].message.content` with any `<think>...</think>` block removed, SHALL retry twice on HTTP 429 or 5xx with 2 s and 4 s waits, and SHALL return None after the last failure or when the content is empty.

#### Scenario: Thinking block removed

- **WHEN** the server returns content `<think>check the gap</think>NOR is 1.8 s behind PIA.`
- **THEN** the narrator returns `NOR is 1.8 s behind PIA.`

#### Scenario: Invalid base URL

- **WHEN** `AUGUR_LLM_BASE_URL` is `file:///etc/passwd`
- **THEN** creating the narrator fails with an error naming `AUGUR_LLM_BASE_URL`

---
### Requirement: Narrator selection

`AUGUR_NARRATOR` (default `gemini`) SHALL select the narrator used by `augur.narrate` when `--narrator` is omitted and the narrator settings the API uses to look up cached commentary. The cached `llm_model` SHALL be the configured model name (`GEMINI_MODEL` or `AUGUR_LLM_MODEL`).

#### Scenario: Lab server selected by environment

- **WHEN** `AUGUR_NARRATOR=openai_compat` and `AUGUR_LLM_MODEL=glm` are set and the command runs without `--narrator`
- **THEN** the stored rows have narrator `openai_compat` and llm_model `glm`

---
### Requirement: Grounded commentary only

Generated text SHALL be stored only when every number in it matches the event's lap or a value in the event's evidence or template text (a percentage matches its fraction, rounding to the shown precision allowed) and every three-letter uppercase driver code appears in the event's drivers or evidence. Otherwise the text SHALL be discarded and `rejected <event_id>: <reason>` printed.

#### Scenario: Grounding cases

- **WHEN** generated texts are checked against evidence `{gap_s: 1.84, win_probability: 0.62, tyre_age: 14}` and drivers NOR, PIA
- **THEN** the results follow the table below

##### Example: check results

| Text fragment | Result | Reason |
| ------------- | ------ | ------ |
| "NOR is 1.8 s behind PIA" | accepted | 1.8 rounds 1.84 |
| "a 62% chance" | accepted | matches 0.62 |
| "PIA's tyres are 14 laps old" | accepted | matches tyre_age |
| "about 3 seconds" | rejected | 3 not in evidence |
| "HAM could join the fight" | rejected | HAM not in drivers |

#### Scenario: Event lap grounds the text

- **WHEN** the text "On lap 48 ZHO's tyres are fading" is checked for an event on lap 48 whose evidence and template text do not contain 48
- **THEN** the text is accepted

---
### Requirement: Narrate command and cache

`python -m augur.narrate --race <race_id> [--model <name>] [--narrator gemini|openai_compat|none]` SHALL generate commentary only for events without a cached text for the same model, narrator, LLM model, language, and prompt version, SHALL store results in the `commentary` table, and SHALL print `narrated <race_id>: <ok> ok, <rejected> rejected, <failed> failed, <cached> cached`. When the selected narrator's required setting is missing it SHALL print `<SETTING> not set; nothing generated` (`GEMINI_API_KEY` for `gemini`, `AUGUR_LLM_BASE_URL` for `openai_compat`) and exit with code 0.

#### Scenario: Second run uses the cache

- **WHEN** the command runs twice for the same race and settings
- **THEN** the second run makes no LLM calls and reports every event as cached

##### Example: cached counts

- **GIVEN** a race with 5 analyzed events and a narrator that returns grounded text
- **WHEN** the command runs twice with the same settings
- **THEN** the first run prints `narrated <race_id>: 5 ok, 0 rejected, 0 failed, 0 cached` and the second prints `narrated <race_id>: 0 ok, 0 rejected, 0 failed, 5 cached`

#### Scenario: No key

- **WHEN** the narrator is `gemini` and `GEMINI_API_KEY` is unset
- **THEN** the command prints `GEMINI_API_KEY not set; nothing generated` and exits with code 0

#### Scenario: No server

- **WHEN** the narrator is `openai_compat` and `AUGUR_LLM_BASE_URL` is unset
- **THEN** the command prints `AUGUR_LLM_BASE_URL not set; nothing generated` and exits with code 0

---
### Requirement: Serve and show commentary

Each event in `/events` SHALL include `commentary`, the cached text for the served model and current narrator settings, or null. The `/events` response SHALL include a top-level `commentary_model`: the configured LLM model name of the current narrator settings, or null when the narrator is `none` or its settings are invalid. When the primary event card's event has commentary, the dashboard SHALL show it first as a quote labelled `AUGUR commentary · <commentary_model>`, followed by What, Why, and Next.

#### Scenario: Event without commentary

- **WHEN** an event has no cached commentary
- **THEN** `commentary` is null and the card shows only What, Why, and Next

#### Scenario: Label from the response

- **WHEN** `/events` returns `commentary_model` `glm` and the primary event has commentary
- **THEN** the card's quote label reads `AUGUR commentary · glm`
