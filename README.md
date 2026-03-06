# Clara Agent System

A deterministic pipeline that converts messy onboarding information (demo call transcripts, onboarding calls, chat logs, structured forms, and audio/video recordings) into a structured, versioned AI voice agent configuration for **Clara** — a Retell-based AI receptionist.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Directory Structure](#directory-structure)
4. [Module Reference](#module-reference)
5. [Configuration Schema](#configuration-schema)
6. [Pipeline Workflow](#pipeline-workflow)
7. [Versioning Strategy](#versioning-strategy)
8. [Merge Engine](#merge-engine)
9. [Conflict Detection](#conflict-detection)
10. [Change Logging](#change-logging)
11. [Questions & Unknowns](#questions--unknowns)
12. [Prompt Generation](#prompt-generation)
13. [CLI Usage](#cli-usage)
14. [Testing](#testing)
15. [Requirements](#requirements)

---

## Overview

Clara is an AI receptionist for service companies (e.g., fire protection, HVAC, electrical). She answers inbound phone calls, determines if the caller has an emergency or a general request, routes or transfers the call, and takes messages when transfers fail.

The **Clara Agent System** automates the process of configuring Clara for a new client. Instead of manually writing a prompt and configuration, operators run a two-stage pipeline:

1. **Demo stage** — Ingests a demo call transcript (or audio) and produces a v1 configuration with extracted entities and flagged unknowns.
2. **Onboarding stage** — Ingests an onboarding call transcript and/or structured form, merges the new data into the existing v1 config, resolves unknowns, and produces a v2 configuration with a deployable Retell system prompt.

The system never hallucinates missing values. Any field that cannot be confidently extracted is added to a `questions_or_unknowns` list for human review.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                          CLI (main.py)                           │
│  Parses arguments, orchestrates pipeline stages, writes output   │
└──────────────┬───────────────────────────────────┬───────────────┘
               │                                   │
       ┌───────▼────────┐                 ┌────────▼───────┐
       │  Demo Pipeline  │                │ Onboard Pipeline│
       │ (demo_processor)│                │(onboarding_proc)│
       └───────┬────────┘                 └────────┬───────┘
               │                                   │
    ┌──────────▼──────────────────────────────────▼──────────┐
    │                   Ingestion Layer                        │
    │  transcript_parser │ entity_extractor │ chat_log_parser  │
    │  audio_transcriber │ form_processor                      │
    └──────────┬──────────────────────────────────┬──────────┘
               │                                   │
    ┌──────────▼──────────┐             ┌──────────▼──────────┐
    │   Schema Layer       │             │    Engine Layer      │
    │  AgentConfiguration  │◄────────────│  merge_engine        │
    │  VersionMetadata     │             │  conflict_detector   │
    │  ChangeLogEntry      │             │  change_logger       │
    └──────────┬──────────┘             └──────────────────────┘
               │
    ┌──────────▼──────────┐
    │   Output Layer       │
    │  prompt_builder      │
    │  version_manager     │
    │  pipeline_logger     │
    └─────────────────────┘
```

**Data flows top-down.** Raw inputs enter the ingestion layer, get normalized and extracted into structured entities, then populate an `AgentConfiguration` Pydantic model. The engine layer handles merging, conflict detection, and change logging. The output layer serializes versions, generates prompts, and logs events.

---

## Directory Structure

```
clara-agent-system/
├── main.py                          # CLI entry point
├── requirements.txt                 # Python dependencies
├── README.md                        # This file
│
├── ingestion/                       # Input parsing and extraction
│   ├── __init__.py
│   ├── audio_transcriber.py         # Whisper API integration
│   ├── chat_log_parser.py           # Labeled chat log parsing
│   ├── entity_extractor.py          # Regex-based entity extraction
│   └── transcript_parser.py         # Transcript normalization
│
├── pipeline/                        # Stage-specific processing
│   ├── __init__.py
│   ├── demo_processor.py            # Demo → v1 config
│   ├── form_processor.py            # JSON form → partial config
│   └── onboarding_processor.py      # Onboarding → v2 config
│
├── engine/                          # Merge and conflict logic
│   ├── __init__.py
│   ├── change_logger.py             # Change log accumulator
│   ├── conflict_detector.py         # Conflict detection
│   └── merge_engine.py              # Deterministic merge
│
├── schemas/                         # Pydantic data models
│   ├── __init__.py
│   └── agent_schema.py              # AgentConfiguration and sub-models
│
├── prompt/                          # Retell prompt generation
│   ├── __init__.py
│   └── prompt_builder.py            # Builds Clara system prompt
│
├── versioning/                      # Version persistence
│   ├── __init__.py
│   └── version_manager.py           # Save/load/list JSON versions
│
├── logging/                         # Structured logging
│   └── pipeline_logger.py           # JSON-line logger
│
└── tests/                           # Test suite
    ├── __init__.py
    ├── test_conflicts.py            # Conflict detection tests
    ├── test_entity_extraction.py    # Entity extraction & chat log tests
    ├── test_merging.py              # Merge engine tests
    ├── test_pipeline_e2e.py         # End-to-end pipeline tests
    ├── test_prompt_generation.py    # Prompt builder tests
    ├── test_versioning.py           # Version manager tests
    └── fixtures/
        ├── __init__.py
        ├── sample_chat_log.txt      # Sample chat log input
        ├── sample_demo_transcript.txt       # Sample demo call transcript
        ├── sample_form.json                 # Sample onboarding form
        └── sample_onboarding_transcript.txt # Sample onboarding call transcript
```

---

## Module Reference

### Ingestion Layer

| Module | Purpose |
|--------|---------|
| `ingestion/transcript_parser.py` | Removes filler words ("um", "uh", "like", "you know") and collapses whitespace from raw transcript text. |
| `ingestion/entity_extractor.py` | Uses regex patterns and keyword matching to extract structured entities: company name, contact name, phone number, emails, service types, emergency examples, and routing descriptions. Includes confidence scores per field. |
| `ingestion/chat_log_parser.py` | Parses chat logs with explicit labels (`Company:`, `Contact:`, `Phone:`, `Emails:`). Falls back to `entity_extractor` for any fields not found by label. |
| `ingestion/audio_transcriber.py` | Transcribes audio/video files (`.m4a`, `.mp3`, `.mp4`, `.wav`) to text via the OpenAI Whisper API. |

### Pipeline Layer

| Module | Purpose |
|--------|---------|
| `pipeline/demo_processor.py` | Orchestrates the demo stage: normalize transcript → extract entities → build v1 `AgentConfiguration` → flag all unknowns. |
| `pipeline/onboarding_processor.py` | Orchestrates the onboarding stage: normalize transcript → extract entities → parse form → detect conflicts → merge into v1 → resolve unknowns → produce v2. |
| `pipeline/form_processor.py` | Converts a structured JSON form dictionary into a partial `AgentConfiguration`. Handles business hours, emergency types, routing rules, transfer destinations, fallback logic, and integration constraints. |

### Engine Layer

| Module | Purpose |
|--------|---------|
| `engine/merge_engine.py` | Deterministically merges an incoming config update into an existing config. Updates only changed fields, preserves unrelated fields, and logs every change. Supports `explicit_override` mode for full-replacement of list fields. |
| `engine/conflict_detector.py` | Compares existing and incoming configs and returns a list of `Conflict` objects where values disagree (emergency definitions, routing rules, timezone, fallback logic). |
| `engine/change_logger.py` | Module-level accumulator for `ChangeLogEntry` records. Includes an idempotency check to prevent duplicate entries. Provides `log_change()`, `get_change_log()`, and `reset_change_log()`. |

### Schema Layer

| Module | Purpose |
|--------|---------|
| `schemas/agent_schema.py` | Pydantic v2 models: `AgentConfiguration`, `ClientInfo`, `BusinessHours`, `EmergencyDefinition`, `RoutingRule`, `IntegrationConstraint`, `VersionMetadata`, `ChangeLogEntry`. |

### Output Layer

| Module | Purpose |
|--------|---------|
| `prompt/prompt_builder.py` | Generates the Retell-compatible system prompt from a completed `AgentConfiguration`. Includes business hours flow, after hours flow, routing rules, fallback logic, integration constraints, and operator review notes. |
| `versioning/version_manager.py` | Serializes configs to versioned JSON files (`{client_id}_{version}.json`), loads them back, and lists all versions for a client. |
| `logging/pipeline_logger.py` | Structured JSON-line logger. Each log entry is a single-line JSON object with timestamp, level, event type, and arbitrary key-value data. |

---

## Configuration Schema

The central data model is `AgentConfiguration` (Pydantic v2):

```
AgentConfiguration
├── client_id: str
├── client_info: ClientInfo
│   ├── company_name: str | None
│   ├── contact_name: str | None
│   ├── phone: str | None
│   └── emails: list[str]
├── business_hours: BusinessHours
│   ├── timezone: str | None
│   └── schedule: dict[str, str]        # e.g. {"monday": "8am-5pm"}
├── emergency_definitions: list[EmergencyDefinition]
│   ├── type: str                       # e.g. "sprinkler_leak"
│   ├── description: str
│   └── priority: str                   # "high" | "medium" | "low"
├── routing_rules: list[RoutingRule]
│   ├── condition: str                  # e.g. "after hours emergency"
│   ├── destination: str                # phone number or label
│   └── transfer_timeout_seconds: int | None
├── transfer_destinations: list[str]
├── integration_constraints: list[IntegrationConstraint]
│   ├── system: str                     # e.g. "ServiceTrade"
│   ├── rule: str
│   └── restriction: str | None
├── fallback_logic: str | None
├── questions_or_unknowns: list[str]
└── metadata: VersionMetadata
    ├── version_number: str             # "v1" | "v2"
    ├── timestamp: str                  # ISO 8601
    ├── source: str                     # "demo" | "onboarding" | "form"
    └── change_log: list[ChangeLogEntry]
        ├── field: str
        ├── previous_value: Any
        ├── new_value: Any
        ├── source: str
        ├── timestamp: str
        └── reason: str
```

---

## Pipeline Workflow

### Stage 1: Demo → v1

```
Input: demo transcript (or audio + Whisper key, or chat log)
                    │
                    ▼
        ┌─────────────────────┐
        │ Normalize transcript │  Remove filler words, collapse whitespace
        └──────────┬──────────┘
                   ▼
        ┌─────────────────────┐
        │  Extract entities    │  Regex-based extraction of company, contact,
        │                      │  phone, emails, services, emergencies, routing
        └──────────┬──────────┘
                   ▼
        ┌─────────────────────┐
        │  Build v1 config     │  Map entities to AgentConfiguration fields
        │  + flag unknowns     │  Missing fields → questions_or_unknowns
        └──────────┬──────────┘
                   ▼
        ┌─────────────────────┐
        │  Save v1 version     │  Write {client_id}_v1.json
        └──────────┬──────────┘
                   ▼
        ┌─────────────────────┐
        │  Generate prompt     │  Build Retell system prompt (with unknowns)
        └──────────┬──────────┘
                   ▼
             Output JSON
```

After the demo stage, the v1 config will typically have:
- Extracted client info (company name, contact, phone, emails)
- Emergency definitions inferred from transcript
- Many fields flagged as unknowns (business hours, routing, fallback, etc.)

### Stage 2: Onboarding → v2

```
Input: onboarding transcript + optional form JSON + existing v1 config
                    │
                    ▼
        ┌─────────────────────┐
        │ Normalize transcript │
        │ + Extract entities   │
        └──────────┬──────────┘
                   ▼
        ┌─────────────────────┐
        │  Parse form data     │  Convert JSON form to partial config
        │  (if provided)       │  (business hours, routing rules, etc.)
        └──────────┬──────────┘
                   ▼
        ┌─────────────────────┐
        │  Merge form + trans  │  Form data is more authoritative;
        │  into combined update│  merged on top of transcript data
        └──────────┬──────────┘
                   ▼
        ┌─────────────────────┐
        │  Detect conflicts    │  Compare v1 vs combined update
        │  between v1 and v2   │  Log conflicts as onboarding_override
        └──────────┬──────────┘
                   ▼
        ┌─────────────────────┐
        │  Merge into v1       │  Deterministic merge: update changed fields,
        │                      │  preserve unchanged fields, log all changes
        └──────────┬──────────┘
                   ▼
        ┌─────────────────────┐
        │  Resolve unknowns    │  Remove questions_or_unknowns entries
        │                      │  for fields that now have values
        └──────────┬──────────┘
                   ▼
        ┌─────────────────────┐
        │  Save v2 version     │  Write {client_id}_v2.json
        └──────────┬──────────┘
                   ▼
        ┌─────────────────────┐
        │  Generate prompt     │  Build Retell system prompt (deployment-ready)
        └──────────┬──────────┘
                   ▼
             Output JSON
```

---

## Versioning Strategy

Each pipeline stage produces a versioned configuration:

| Version | Source | Contains |
|---------|--------|----------|
| **v1** | Demo call | Extracted entities + many unknowns flagged |
| **v2** | Onboarding call + form | Merged config with unknowns resolved |

Versions are persisted as individual JSON files:
```
versions/
├── silverline_v1.json
└── silverline_v2.json
```

Each version includes `VersionMetadata` with:
- `version_number` — "v1" or "v2"
- `timestamp` — ISO 8601 timestamp of when the version was created
- `source` — the primary data source ("demo", "onboarding", "form")
- `change_log` — list of all `ChangeLogEntry` records from that pipeline run

The version manager supports:
- `save_version(config, output_dir)` — Serialize to JSON
- `load_version(client_id, version, input_dir)` — Deserialize from JSON
- `list_versions(client_id, directory)` — List all version strings for a client

---

## Merge Engine

The merge engine (`engine/merge_engine.py`) performs deterministic, field-level merging:

**Merge Rules:**

| Field Type | Strategy |
|------------|----------|
| Scalar fields (company_name, timezone, fallback_logic) | Update if incoming value is non-None and differs from existing |
| Emails | Deduplicate and append new entries |
| Business hours schedule | Dict merge — add/update per-day entries |
| Emergency definitions | Match by `type` field — update existing or append new |
| Routing rules | Match by `condition` field — update existing or append new |
| Integration constraints | Match by `system` field — update existing or append new |
| Transfer destinations | Deduplicate and append new entries |

**Key properties:**
- **Preserves unrelated fields** — Starts from a deep copy of the existing config
- **Logs every change** — Every field modification creates a `ChangeLogEntry`
- **Idempotent** — Merging the same update twice produces the same result
- **Supports explicit override** — `explicit_override=True` replaces entire list fields instead of merging

---

## Conflict Detection

The conflict detector (`engine/conflict_detector.py`) identifies contradictions between configurations:

| Conflict Type | Detection Condition |
|---------------|-------------------|
| Emergency definition | Same `type`, different `description` or `priority` |
| Routing rule | Same `condition`, different `destination` or `transfer_timeout_seconds` |
| Timezone | Both configs have non-None timezone values that differ |
| Fallback logic | Both configs have non-None fallback values that differ |

Conflicts are resolved with an **incoming-wins** strategy: the onboarding data takes precedence over demo data. All conflicts are logged with `reason: "onboarding_override"`.

---

## Change Logging

Every configuration modification is recorded as a `ChangeLogEntry`:

```json
{
  "field": "business_hours.timezone",
  "previous_value": null,
  "new_value": "America/Denver",
  "source": "onboarding",
  "timestamp": "2026-01-15T12:00:00Z",
  "reason": "field_update"
}
```

**Reasons:**
| Reason | Meaning |
|--------|---------|
| `field_update` | A scalar or container field was updated with a new value |
| `new_entry` | A new item was appended to a list field |
| `onboarding_override` | A conflict was resolved in favor of the incoming data |
| `explicit_override` | An entire list field was replaced via explicit override mode |

The change logger includes an **idempotency check**: if a log entry with the same field, previous value, new value, and source already exists, it returns the existing entry rather than creating a duplicate.

---

## Questions & Unknowns

The system tracks missing information in the `questions_or_unknowns` field:

- **During demo (v1):** Every required field that was not extracted from the transcript is added as an unknown. Examples:
  - `"business_hours.schedule: not provided during demo"`
  - `"client_info.phone: not provided during demo"`
  - `"transfer_destinations: not provided during demo"`

- **During onboarding (v2):** Each unknown is checked against the merged config. If the referenced field now has a value, the unknown is removed. Only genuinely unresolved items remain.

The system **never invents values** for missing fields. Unknown fields remain `None` or `[]` in the configuration, and the generated prompt includes an `OPERATOR REVIEW REQUIRED` section listing all unresolved items.

---

## Prompt Generation

The prompt builder (`prompt/prompt_builder.py`) generates a complete Retell-compatible system prompt from an `AgentConfiguration`. The prompt includes the following sections:

### 1. Identity
Clara introduces herself as an AI receptionist for the configured company.

### 2. Business Hours
Displays the full weekly schedule with timezone, or a fallback message if not configured.

### 3. Emergency Types
Lists all defined emergency types with priority levels, or a fallback escalation rule.

### 4. Business Hours Call Flow
Step-by-step instructions for handling calls during business hours:
1. Greet the caller and ask how to help
2. Ask for the caller's name
3. Ask for a callback phone number
4. Determine if emergency or general request
5. If emergency: attempt transfer; fallback if transfer fails
6. If non-emergency: confirm and advise follow-up
7. Ask "Is there anything else I can help you with today?"
8. Close the call professionally

### 5. After Hours Call Flow
Step-by-step instructions for handling calls after hours:
1. Greet the caller and identify as Clara
2. Ask the reason for the call
3. Ask if this is an emergency
4. If emergency: collect name, phone, address → attempt transfer → fallback if fails
5. If non-emergency: collect details → confirm follow-up during business hours
6. Close the call

### 6. Routing Rules
Lists all configured routing rules with conditions, destinations, and timeouts.

### 7. Fallback Logic
What to do when transfers fail (configured or default behavior).

### 8. Integration Constraints
System-specific rules (e.g., "Do not create sprinkler jobs in ServiceTrade").

### 9. Operator Review Notes
If any `questions_or_unknowns` remain, the prompt includes a clearly marked section warning operators not to deploy until all items are resolved.

---

## CLI Usage

### Demo Stage

Process a demo call transcript:

```bash
python main.py --stage demo --client_id silverline \
    --transcript tests/fixtures/sample_demo_transcript.txt
```

Process a demo with a chat log prepended:

```bash
python main.py --stage demo --client_id silverline \
    --transcript tests/fixtures/sample_demo_transcript.txt \
    --chat_log tests/fixtures/sample_chat_log.txt
```

Process audio directly (requires OpenAI API key):

```bash
python main.py --stage demo --client_id silverline \
    --audio recording.mp3 --whisper_key sk-...
```

### Onboarding Stage

Process an onboarding call with a form:

```bash
python main.py --stage onboarding --client_id silverline \
    --transcript tests/fixtures/sample_onboarding_transcript.txt \
    --form tests/fixtures/sample_form.json
```

### Optional Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--output_dir` | Directory for output JSON files | `./output` |
| `--versions_dir` | Directory for version JSON files | `./versions` |
| `--whisper_key` | OpenAI API key for Whisper transcription | None |

### Output

Each pipeline run produces a JSON file at `{output_dir}/{client_id}_output.json` containing:

```json
{
  "client_id": "silverline",
  "agent_versions": {
    "v1": { "..." },
    "v2": { "..." }
  },
  "change_log": [ "..." ],
  "questions_or_unknowns": [ "..." ],
  "generated_agent_prompt": "You are Clara, an AI receptionist for ..."
}
```

---

## Testing

The test suite covers all system components. Run with:

```bash
python -m pytest tests/ -v
```

### Test Files

| File | Tests | Coverage |
|------|-------|----------|
| `tests/test_conflicts.py` | 5 | Conflict detection: emergency priority changes, routing destination changes, timezone mismatches, identical config no-conflict, conflict resolution with incoming-wins |
| `tests/test_merging.py` | 5 | Merge engine: no changes with None updates, scalar field updates, append new emergency types, no duplication of identical entries, idempotent merge |
| `tests/test_prompt_generation.py` | 7 | Prompt builder: company name inclusion, emergency types, fallback company name, empty schedule message, unknowns section presence/absence, deterministic output |
| `tests/test_entity_extraction.py` | 21 | Entity extractor: all 7 entity types, sample fixture extraction, chat log labeled parsing, chat log fallback, partial labels, confidence scores |
| `tests/test_versioning.py` | 8 | Version manager: save/load round-trip, directory creation, missing version error, version listing/ordering, JSON validity, multi-version coexistence |
| `tests/test_pipeline_e2e.py` | 12 | End-to-end: demo → v1, unknowns flagging, emergency extraction, input validation, onboarding → v2, unknowns resolution, business hours population, change logging, full round-trip save/load, prompt generation, idempotent demo, idempotent onboarding |

**Total: 58 tests**

---

## Requirements

```
pydantic>=2.0       # Schema definitions and validation
openai>=1.0         # Whisper API for audio transcription
pytest>=7.0         # Test framework
```

Install:

```bash
pip install -r requirements.txt
```

**Python version:** 3.10+

---

## Design Principles

1. **Deterministic** — Same input always produces the same output. No randomness, no LLM calls for configuration extraction.
2. **Idempotent** — Running the pipeline twice with identical input produces identical results.
3. **Never hallucinate** — Missing fields are flagged as unknowns, never invented.
4. **Auditable** — Every change is logged with field, previous value, new value, source, timestamp, and reason.
5. **Incremental** — Versioned configs build on each other. v2 merges into v1, preserving what was already known.
6. **Human-in-the-loop** — The system generates operator review notes when unknowns remain, preventing premature deployment.
