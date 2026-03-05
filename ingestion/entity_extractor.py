"""Extracts structured entities from normalized text using regex and keyword matching."""

import re
from dataclasses import dataclass, field

# --- Company name patterns ---
COMPANY_PATTERNS = [
    re.compile(r"we are ([A-Z][^,.\n]+)"),
    re.compile(r"this is ([A-Z][^,.\n]+)"),
    re.compile(r"company (?:name )?is ([A-Z][^,.\n]+)"),
    re.compile(r"I(?:'m| am) (?:calling )?from ([A-Z][^,.\n]+)"),
]

# --- Contact name patterns ---
CONTACT_PATTERNS = [
    re.compile(r"my name is ([A-Z][a-z]+ [A-Z][a-z]+)"),
    re.compile(r"I(?:'m| am) ([A-Z][a-z]+ [A-Z][a-z]+)"),
    re.compile(r"speaking with ([A-Z][a-z]+ [A-Z][a-z]+)"),
]

# --- Phone number patterns ---
PHONE_PATTERN = re.compile(r"\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}|\+?1?\d{10,11}")

# --- Email pattern ---
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# --- Service type keywords ---
SERVICE_KEYWORDS: dict[str, str] = {
    "fire protection": "fire_protection",
    "sprinkler": "sprinkler",
    "alarm": "fire_alarm",
    "electrical": "electrical",
    "hvac": "hvac",
    "facility": "facility_maintenance",
}

# --- Emergency keywords ---
EMERGENCY_KEYWORDS = [
    "emergency", "after hours", "urgent", "leak",
    "alarm", "outage", "failure", "triggered",
]

# --- Routing keywords ---
ROUTING_KEYWORDS = [
    "transfer", "route", "send to", "dispatch",
    "forward", "call goes to", "on-call", "escalate",
]

# --- Sentence boundary pattern ---
SENTENCE_SPLIT_PATTERN = re.compile(r"[.!?]+")


@dataclass
class ExtractedEntities:
    company_name: str | None = None
    contact_name: str | None = None
    phone_number: str | None = None
    emails: list[str] = field(default_factory=list)
    service_types: list[str] = field(default_factory=list)
    emergency_examples: list[str] = field(default_factory=list)
    routing_descriptions: list[str] = field(default_factory=list)
    confidence: dict[str, float] = field(default_factory=dict)


def extract_entities(text: str) -> ExtractedEntities:
    """Extract structured entities from normalized text and return an ExtractedEntities instance."""
    entities = ExtractedEntities()

    # Company name
    for pattern in COMPANY_PATTERNS:
        match = pattern.search(text)
        if match:
            entities.company_name = match.group(1).strip()
            entities.confidence["company_name"] = 0.9
            break
    if entities.company_name is None:
        entities.confidence["company_name"] = 0.0

    # Contact name
    for pattern in CONTACT_PATTERNS:
        match = pattern.search(text)
        if match:
            entities.contact_name = match.group(1).strip()
            entities.confidence["contact_name"] = 0.85
            break
    if entities.contact_name is None:
        entities.confidence["contact_name"] = 0.0

    # Phone number
    phone_match = PHONE_PATTERN.search(text)
    if phone_match:
        entities.phone_number = re.sub(r"\D", "", phone_match.group())
        entities.confidence["phone_number"] = 0.95
    else:
        entities.confidence["phone_number"] = 0.0

    # Emails
    entities.emails = EMAIL_PATTERN.findall(text)
    entities.confidence["emails"] = 0.95 if entities.emails else 0.0

    # Service types
    text_lower = text.lower()
    for keyword, service_type in SERVICE_KEYWORDS.items():
        if keyword in text_lower:
            if service_type not in entities.service_types:
                entities.service_types.append(service_type)

    # Split into sentences for emergency and routing extraction
    sentences = [s.strip() for s in SENTENCE_SPLIT_PATTERN.split(text) if s.strip()]

    # Emergency examples
    for sentence in sentences:
        sentence_lower = sentence.lower()
        if any(kw in sentence_lower for kw in EMERGENCY_KEYWORDS):
            entities.emergency_examples.append(sentence)

    # Routing descriptions
    for sentence in sentences:
        sentence_lower = sentence.lower()
        if any(kw in sentence_lower for kw in ROUTING_KEYWORDS):
            entities.routing_descriptions.append(sentence)

    return entities
