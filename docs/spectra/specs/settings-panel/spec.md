# settings-panel Specification

## Purpose

Let the viewer change which model AUGUR serves, the commentary language, and the data source from the dashboard without restarting the server, while the commentary narrator, API keys, and LLM server addresses stay on the server.

## Requirements

### Requirement: Settings precedence

The served model, commentary language, and data source SHALL be read through one settings function whose value comes from `data/settings.json` when set there, otherwise from `AUGUR_MODEL` / `AUGUR_COMMENTARY_LANG`, otherwise from the defaults `lightgbm`, `en`, `replay`. A change SHALL apply to the next API request without a restart. The commentary language from this function SHALL be the language `/events` uses to look up cached commentary and the language `augur.narrate` generates in.

#### Scenario: Precedence order

- **WHEN** the model setting is resolved
- **THEN** it follows the cases below

##### Example: model resolution

| data/settings.json model | AUGUR_MODEL | Served model |
| ------------------------ | ----------- | ------------ |
| mymodel | baseline | mymodel |
| (absent) | baseline | baseline |
| (absent) | (unset) | lightgbm |

#### Scenario: Commentary language follows settings

- **WHEN** `data/settings.json` sets `commentary_lang` to `zh-TW` and `AUGUR_COMMENTARY_LANG` is `en`
- **THEN** `/events` serves commentary cached with language `zh-TW`, and `augur.narrate` stores new commentary with language `zh-TW`

---
### Requirement: Settings API

`GET /api/settings` SHALL return `model`, `commentary_lang`, `data_source`, `models` (each with `name`, `author`, `trained`), `commentary_langs` (`en`, `zh-TW`), `data_sources` (`replay` available, `live` not available), and a read-only `commentary` object with `narrator` (the `AUGUR_NARRATOR` value), `llm_model` (the configured LLM model name, or null for `none`), `configured` (whether the narrator's required setting is present), and `missing` (the name of the missing environment variable, or null). `PUT /api/settings` SHALL accept any subset of `model`, `commentary_lang`, and `data_source`, persist it to `data/settings.json`, and return the GET shape. It SHALL reject with 422 an unknown model (`unknown model <name>`), a model without a model file (`model <name> is not trained`), an unsupported language (`unsupported language <lang>`), `data_source` `live` (`live data is not available yet`), and any other field (`unknown field <field>`), including the narrator and any key or server setting. No response SHALL contain an API key, part of one, or the LLM server address.

#### Scenario: Settings validation

- **WHEN** the client sends `PUT /api/settings` bodies
- **THEN** the responses follow the cases below

##### Example: PUT cases

| Body | Status | detail |
| ---- | ------ | ------ |
| `{"model": "baseline"}` (trained) | 200 | — |
| `{"model": "nope"}` | 422 | unknown model nope |
| `{"commentary_lang": "ja"}` | 422 | unsupported language ja |
| `{"data_source": "live"}` | 422 | live data is not available yet |
| `{"gemini_api_key": "abc"}` | 422 | unknown field gemini_api_key |
| `{"narrator": "gemini"}` | 422 | unknown field narrator |

#### Scenario: Secrets never exposed

- **WHEN** `GEMINI_API_KEY`, `AUGUR_LLM_API_KEY`, and `AUGUR_LLM_BASE_URL` are set and the client calls `GET /api/settings`
- **THEN** the response contains none of their values

##### Example: commentary status

| AUGUR_NARRATOR | Set variables | commentary |
| -------------- | ------------- | ---------- |
| `openai_compat` | `AUGUR_LLM_BASE_URL`, `AUGUR_LLM_MODEL=glm` | `{narrator: "openai_compat", llm_model: "glm", configured: true, missing: null}` |
| `openai_compat` | (none) | `{narrator: "openai_compat", llm_model: "glm", configured: false, missing: "AUGUR_LLM_BASE_URL"}` |
| `gemini` | `GEMINI_API_KEY` | `{narrator: "gemini", llm_model: "gemini-flash-latest", configured: true, missing: null}` |
| `none` | (none) | `{narrator: "none", llm_model: null, configured: false, missing: null}` |

---
### Requirement: Settings side sheet

A gear button in the status bar SHALL open a side sheet showing the model list (untrained models disabled and marked "not trained"), the commentary language (English, 繁體中文), the data source (Replay; Live disabled with "Coming later"), and the read-only commentary status: `<narrator> · <llm_model> — Configured`, `<narrator> · <llm_model> — Not configured — set <missing> in .env`, or `Off — AUGUR_NARRATOR is none`. The sheet SHALL NOT contain any input for the narrator, API keys, or the LLM server. Saving SHALL call `PUT /api/settings` and reload the current lap's data; a 422 SHALL be shown as the `detail` text next to the Save button.

#### Scenario: Switch model

- **WHEN** the viewer selects `baseline` and saves at lap 20
- **THEN** the dashboard re-fetches lap 20 and the events and predictions come from `baseline`

#### Scenario: Model not analyzed for this race

- **WHEN** the viewer switches to a trained model that has not analyzed the current race
- **THEN** the intelligence panel shows the existing "Race not analyzed" message for that race

#### Scenario: Commentary status shown read-only

- **WHEN** the settings report `{narrator: "openai_compat", llm_model: "glm", configured: true, missing: null}`
- **THEN** the sheet shows `openai_compat · glm — Configured` and has no input for the narrator, a key, or a server address
