"""Parses chat log exports that contain labeled contact info such as Company, Contact, Phone, and Emails."""

import re

from ingestion.entity_extractor import ExtractedEntities, extract_entities

COMPANY_LABEL = re.compile(r"Company:\s*(.+)", re.IGNORECASE)
CONTACT_LABEL = re.compile(r"Contact:\s*(.+)", re.IGNORECASE)
PHONE_LABEL = re.compile(r"Phone:\s*(.+)", re.IGNORECASE)
EMAIL_LABEL = re.compile(r"Emails?:\s*(.+)", re.IGNORECASE)


def parse_chat_log(raw_text: str) -> ExtractedEntities:
    """Parse labeled contact info from a chat log, falling back to entity extraction."""
    entities = ExtractedEntities()

    # Attempt explicit label parsing
    company_match = COMPANY_LABEL.search(raw_text)
    if company_match:
        entities.company_name = company_match.group(1).strip()
        entities.confidence["company_name"] = 0.95

    contact_match = CONTACT_LABEL.search(raw_text)
    if contact_match:
        entities.contact_name = contact_match.group(1).strip()
        entities.confidence["contact_name"] = 0.95

    phone_match = PHONE_LABEL.search(raw_text)
    if phone_match:
        entities.phone_number = re.sub(r"\D", "", phone_match.group(1).strip())
        entities.confidence["phone_number"] = 0.95

    email_match = EMAIL_LABEL.search(raw_text)
    if email_match:
        entities.emails = [e.strip() for e in email_match.group(1).split(",") if e.strip()]
        entities.confidence["emails"] = 0.95

    # Fall back to extract_entities for any fields not found by label parsing
    fallback = extract_entities(raw_text)

    if entities.company_name is None and fallback.company_name is not None:
        entities.company_name = fallback.company_name
        entities.confidence["company_name"] = fallback.confidence.get("company_name", 0.0)

    if entities.contact_name is None and fallback.contact_name is not None:
        entities.contact_name = fallback.contact_name
        entities.confidence["contact_name"] = fallback.confidence.get("contact_name", 0.0)

    if entities.phone_number is None and fallback.phone_number is not None:
        entities.phone_number = fallback.phone_number
        entities.confidence["phone_number"] = fallback.confidence.get("phone_number", 0.0)

    if not entities.emails and fallback.emails:
        entities.emails = fallback.emails
        entities.confidence["emails"] = fallback.confidence.get("emails", 0.0)

    # Always pull through non-contact fields from fallback
    entities.service_types = fallback.service_types
    entities.emergency_examples = fallback.emergency_examples
    entities.routing_descriptions = fallback.routing_descriptions

    return entities
