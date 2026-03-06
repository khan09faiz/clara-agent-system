"""Tests for entity extraction and chat log parsing."""

import pytest

from ingestion.entity_extractor import extract_entities, ExtractedEntities
from ingestion.chat_log_parser import parse_chat_log


class TestExtractEntities:

    def test_extract_company_name_we_are(self) -> None:
        """Extracts company name from 'we are <Name>' pattern."""
        text = "we are Silverline Fire Protection, a fire protection contractor."
        entities = extract_entities(text)
        assert entities.company_name == "Silverline Fire Protection"
        assert entities.confidence["company_name"] > 0

    def test_extract_company_name_this_is(self) -> None:
        """Extracts company name from 'this is <Name>' pattern."""
        text = "this is Acme Services calling about our account."
        entities = extract_entities(text)
        assert entities.company_name == "Acme Services calling about our account"

    def test_extract_company_name_missing(self) -> None:
        """Returns None and zero confidence when no company name is found."""
        text = "hello, just calling to check on something"
        entities = extract_entities(text)
        assert entities.company_name is None
        assert entities.confidence["company_name"] == 0.0

    def test_extract_contact_name(self) -> None:
        """Extracts contact name from 'my name is <First Last>' pattern."""
        text = "Hi, my name is Marcus Rivera and I need help."
        entities = extract_entities(text)
        assert entities.contact_name == "Marcus Rivera"
        assert entities.confidence["contact_name"] > 0

    def test_extract_contact_name_im_pattern(self) -> None:
        """Extracts contact name from 'I'm <First Last>' pattern."""
        text = "I'm John Smith and I need to report an issue."
        entities = extract_entities(text)
        assert entities.contact_name == "John Smith"

    def test_extract_contact_name_missing(self) -> None:
        """Returns None when no contact name is found."""
        text = "just checking in about the account."
        entities = extract_entities(text)
        assert entities.contact_name is None
        assert entities.confidence["contact_name"] == 0.0

    def test_extract_phone_number(self) -> None:
        """Extracts a US phone number from text."""
        text = "You can reach us at 303-555-0172 anytime."
        entities = extract_entities(text)
        assert entities.phone_number == "3035550172"
        assert entities.confidence["phone_number"] > 0

    def test_extract_phone_number_parenthesized(self) -> None:
        """Extracts phone number in (xxx) xxx-xxxx format."""
        text = "Call us at (403) 870-8494 for emergencies."
        entities = extract_entities(text)
        assert entities.phone_number == "4038708494"

    def test_extract_phone_number_missing(self) -> None:
        """Returns None when no phone number is found."""
        text = "No contact details provided."
        entities = extract_entities(text)
        assert entities.phone_number is None
        assert entities.confidence["phone_number"] == 0.0

    def test_extract_emails(self) -> None:
        """Extracts email addresses from text."""
        text = "Send details to marcus@silverlinefire.com and info@example.com please."
        entities = extract_entities(text)
        assert "marcus@silverlinefire.com" in entities.emails
        assert "info@example.com" in entities.emails
        assert entities.confidence["emails"] > 0

    def test_extract_emails_missing(self) -> None:
        """Returns empty list when no emails are found."""
        text = "No email addresses here."
        entities = extract_entities(text)
        assert entities.emails == []
        assert entities.confidence["emails"] == 0.0

    def test_extract_service_types(self) -> None:
        """Extracts service type keywords from text."""
        text = "We handle fire protection and sprinkler system installs."
        entities = extract_entities(text)
        assert "fire_protection" in entities.service_types
        assert "sprinkler" in entities.service_types

    def test_extract_service_types_hvac(self) -> None:
        """Extracts HVAC service type."""
        text = "We specialize in HVAC maintenance and repairs."
        entities = extract_entities(text)
        assert "hvac" in entities.service_types

    def test_extract_emergency_examples(self) -> None:
        """Extracts sentences containing emergency keywords."""
        text = (
            "We get sprinkler leak calls all the time. "
            "When an alarm is triggered we need immediate response. "
            "Regular inspections are routine."
        )
        entities = extract_entities(text)
        assert len(entities.emergency_examples) >= 2
        emergency_text = " ".join(entities.emergency_examples).lower()
        assert "leak" in emergency_text
        assert "alarm" in emergency_text or "triggered" in emergency_text

    def test_extract_routing_descriptions(self) -> None:
        """Extracts sentences containing routing keywords."""
        text = (
            "For emergencies, transfer the call to dispatch immediately. "
            "Routine calls can wait until morning."
        )
        entities = extract_entities(text)
        assert len(entities.routing_descriptions) >= 1
        routing_text = " ".join(entities.routing_descriptions).lower()
        assert "transfer" in routing_text or "dispatch" in routing_text

    def test_extract_from_sample_demo_transcript(self) -> None:
        """Extracts expected entities from the sample demo transcript fixture."""
        with open("tests/fixtures/sample_demo_transcript.txt", "r", encoding="utf-8") as f:
            text = f.read()
        entities = extract_entities(text)
        assert entities.company_name is not None
        assert "Silverline" in entities.company_name
        assert entities.contact_name == "Marcus Rivera"
        assert entities.phone_number is not None
        assert entities.emails
        assert "marcus@silverlinefire.com" in entities.emails
        assert len(entities.service_types) > 0
        assert len(entities.emergency_examples) > 0


class TestParseChatLog:

    def test_parse_labeled_fields(self) -> None:
        """Parses explicitly labeled Company/Contact/Phone/Email fields."""
        text = (
            "Company: Acme Corp\n"
            "Contact: Jane Doe\n"
            "Phone: 555-123-4567\n"
            "Emails: jane@acme.com, support@acme.com\n"
        )
        entities = parse_chat_log(text)
        assert entities.company_name == "Acme Corp"
        assert entities.contact_name == "Jane Doe"
        assert entities.phone_number == "5551234567"
        assert "jane@acme.com" in entities.emails
        assert "support@acme.com" in entities.emails

    def test_parse_sample_chat_log_fixture(self) -> None:
        """Parses the sample chat log fixture file correctly."""
        with open("tests/fixtures/sample_chat_log.txt", "r", encoding="utf-8") as f:
            text = f.read()
        entities = parse_chat_log(text)
        assert entities.company_name == "G&M Pressure Washing"
        assert entities.contact_name == "Shelley Manley"
        assert entities.phone_number == "4038708494"
        assert "gm_pressurewash@yahoo.ca" in entities.emails

    def test_parse_chat_log_fallback_to_extraction(self) -> None:
        """Falls back to regex extraction when labels are absent."""
        text = "Hi, my name is John Smith. I'm calling from Delta Services. Call us at 555-000-1234."
        entities = parse_chat_log(text)
        # Should fall back to extract_entities
        assert entities.company_name is not None
        assert entities.contact_name == "John Smith"
        assert entities.phone_number is not None

    def test_parse_chat_log_partial_labels(self) -> None:
        """Uses labels where present, falls back for missing ones."""
        text = (
            "Company: PartialCo\n"
            "my name is Alice Brown. Call 555-999-0000.\n"
        )
        entities = parse_chat_log(text)
        assert entities.company_name == "PartialCo"  # from label
        assert entities.contact_name == "Alice Brown"  # from fallback
        assert entities.phone_number is not None  # from fallback

    def test_confidence_high_for_labeled_fields(self) -> None:
        """Labeled fields get 0.95 confidence."""
        text = "Company: TestCo\nContact: Bob Jones\n"
        entities = parse_chat_log(text)
        assert entities.confidence.get("company_name") == 0.95
        assert entities.confidence.get("contact_name") == 0.95
