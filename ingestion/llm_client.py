"""LLM client abstraction for enhanced entity extraction.

Supports three backends:
  - rule_based: No LLM, uses pure regex extraction (default, zero-cost)
  - groq: Groq free tier API (Llama 3)
  - ollama: Local Ollama instance (zero-cost, requires local install)

The LLM is used to *enhance* entity extraction, not replace it.
Rule-based extraction always runs first; the LLM fills gaps.
Falls back to rule_based silently if the configured LLM fails.
"""

import json
import os
import re
from dataclasses import dataclass

LLM_BACKEND = os.environ.get("LLM_BACKEND", "rule_based")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")

EXTRACTION_PROMPT = """Extract the following fields from this call transcript as JSON.
Return ONLY valid JSON with these keys (use null for missing fields):
{
  "company_name": "string or null",
  "contact_name": "string or null",
  "phone_number": "string or null",
  "emails": ["list of strings"],
  "service_types": ["list of strings like fire_protection, sprinkler, hvac, electrical"],
  "emergency_examples": ["list of emergency scenario descriptions"],
  "routing_descriptions": ["list of routing/transfer descriptions"],
  "business_hours_timezone": "string or null",
  "business_hours_schedule": {"day": "hours"} or null,
  "fallback_logic": "string or null"
}

Transcript:
{text}

JSON:"""


@dataclass
class LLMExtractionResult:
    """Structured result from LLM-enhanced extraction."""
    company_name: str | None = None
    contact_name: str | None = None
    phone_number: str | None = None
    emails: list[str] | None = None
    service_types: list[str] | None = None
    emergency_examples: list[str] | None = None
    routing_descriptions: list[str] | None = None
    business_hours_timezone: str | None = None
    business_hours_schedule: dict[str, str] | None = None
    fallback_logic: str | None = None
    backend_used: str = "rule_based"


def get_backend() -> str:
    """Return the currently configured LLM backend name."""
    return os.environ.get("LLM_BACKEND", "rule_based")


def _call_groq(text: str) -> str | None:
    """Call Groq API and return raw response text."""
    try:
        import groq
        client = groq.Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": EXTRACTION_PROMPT.format(text=text[:4000])}],
            temperature=0,
            max_tokens=1500,
        )
        return response.choices[0].message.content
    except Exception:
        return None


def _call_ollama(text: str) -> str | None:
    """Call local Ollama instance and return raw response text."""
    try:
        import urllib.request
        payload = json.dumps({
            "model": OLLAMA_MODEL,
            "prompt": EXTRACTION_PROMPT.format(text=text[:4000]),
            "stream": False,
            "options": {"temperature": 0},
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body.get("response", "")
    except Exception:
        return None


def _parse_llm_json(raw: str) -> dict | None:
    """Extract and parse JSON from LLM response text."""
    if not raw:
        return None
    # Try to find JSON block in response
    json_match = re.search(r"\{[\s\S]*\}", raw)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            return None
    return None


def llm_extract(text: str) -> LLMExtractionResult:
    """Run LLM-enhanced extraction. Returns LLMExtractionResult with extracted fields.

    Falls back to empty result if LLM is unavailable or fails.
    """
    backend = get_backend()

    if backend == "rule_based":
        return LLMExtractionResult(backend_used="rule_based")

    raw_response: str | None = None
    if backend == "groq" and GROQ_API_KEY:
        raw_response = _call_groq(text)
    elif backend == "ollama":
        raw_response = _call_ollama(text)

    if raw_response is None:
        return LLMExtractionResult(backend_used="rule_based")

    parsed = _parse_llm_json(raw_response)
    if parsed is None:
        return LLMExtractionResult(backend_used="rule_based")

    return LLMExtractionResult(
        company_name=parsed.get("company_name"),
        contact_name=parsed.get("contact_name"),
        phone_number=parsed.get("phone_number"),
        emails=parsed.get("emails"),
        service_types=parsed.get("service_types"),
        emergency_examples=parsed.get("emergency_examples"),
        routing_descriptions=parsed.get("routing_descriptions"),
        business_hours_timezone=parsed.get("business_hours_timezone"),
        business_hours_schedule=parsed.get("business_hours_schedule"),
        fallback_logic=parsed.get("fallback_logic"),
        backend_used=backend,
    )


def merge_llm_into_entities(
    entities: "ExtractedEntities",  # noqa: F821
    llm_result: LLMExtractionResult,
) -> "ExtractedEntities":  # noqa: F821
    """Fill gaps in regex-extracted entities with LLM results. LLM only fills None/empty fields."""
    if llm_result.backend_used == "rule_based":
        return entities

    if entities.company_name is None and llm_result.company_name:
        entities.company_name = llm_result.company_name
        entities.confidence["company_name"] = 0.75

    if entities.contact_name is None and llm_result.contact_name:
        entities.contact_name = llm_result.contact_name
        entities.confidence["contact_name"] = 0.7

    if entities.phone_number is None and llm_result.phone_number:
        cleaned = re.sub(r"\D", "", llm_result.phone_number)
        if len(cleaned) >= 10:
            entities.phone_number = cleaned
            entities.confidence["phone_number"] = 0.7

    if not entities.emails and llm_result.emails:
        entities.emails = llm_result.emails
        entities.confidence["emails"] = 0.7

    if not entities.service_types and llm_result.service_types:
        entities.service_types = llm_result.service_types

    if not entities.emergency_examples and llm_result.emergency_examples:
        entities.emergency_examples = llm_result.emergency_examples

    if not entities.routing_descriptions and llm_result.routing_descriptions:
        entities.routing_descriptions = llm_result.routing_descriptions

    return entities
