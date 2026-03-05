"""Processes demo call inputs into a v1 AgentConfiguration with unknowns explicitly flagged."""

import re
from datetime import datetime

from schemas.agent_schema import (
    AgentConfiguration,
    BusinessHours,
    ClientInfo,
    EmergencyDefinition,
    VersionMetadata,
)
from ingestion.audio_transcriber import transcribe_audio
from ingestion.transcript_parser import normalize_transcript
from ingestion.entity_extractor import extract_entities


def _slugify(text: str) -> str:
    """Lowercase, replace non-alphanumeric with underscore, collapse and strip underscores, truncate to 50 chars."""
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = re.sub(r"_+", "_", slug)
    slug = slug.strip("_")
    return slug[:50]


def process_demo(
    client_id: str,
    transcript: str | None = None,
    audio_path: str | None = None,
    whisper_api_key: str | None = None,
) -> AgentConfiguration:
    """Process demo call input and return a v1 AgentConfiguration with unknowns flagged."""
    # Validation
    if transcript is None and audio_path is None:
        raise ValueError("Must provide either transcript or audio_path")
    if audio_path is not None and whisper_api_key is None:
        raise ValueError("whisper_api_key required when audio_path is provided")

    # Step 1: Get raw text
    if audio_path is not None:
        raw_text = transcribe_audio(audio_path, whisper_api_key)  # type: ignore[arg-type]
    else:
        raw_text = transcript  # type: ignore[assignment]

    # Step 2: Normalize
    normalized_text = normalize_transcript(raw_text)

    # Step 3: Extract entities
    entities = extract_entities(normalized_text)

    # Step 4: Map entities to config
    questions_or_unknowns: list[str] = []

    client_info = ClientInfo(
        company_name=entities.company_name,
        contact_name=entities.contact_name,
        phone=entities.phone_number,
        emails=entities.emails,
    )

    # Emergency definitions
    emergency_definitions: list[EmergencyDefinition] = []
    if entities.emergency_examples:
        for example in entities.emergency_examples:
            emergency_definitions.append(
                EmergencyDefinition(
                    type=_slugify(example),
                    description=example,
                    priority="high",
                )
            )
        questions_or_unknowns.append(
            "emergency_definitions: priority and type need confirmation"
        )

    # Routing descriptions -> unknowns only
    for desc in entities.routing_descriptions:
        truncated = desc[:60]
        questions_or_unknowns.append(
            f"routing_rule: '{truncated}' needs destination confirmed"
        )

    # Step 5: Add standard unknowns for fields not provided during demo
    if client_info.company_name is None:
        questions_or_unknowns.append("client_info.company_name: not provided during demo")
    if client_info.contact_name is None:
        questions_or_unknowns.append("client_info.contact_name: not provided during demo")
    if client_info.phone is None:
        questions_or_unknowns.append("client_info.phone: not provided during demo")
    if not client_info.emails:
        questions_or_unknowns.append("client_info.emails: not provided during demo")

    # Always add these unknowns after demo
    questions_or_unknowns.append("business_hours.schedule: not provided during demo")
    questions_or_unknowns.append("business_hours.timezone: not provided during demo")
    questions_or_unknowns.append("transfer_destinations: not provided during demo")
    questions_or_unknowns.append("routing_rules: not confirmed during demo")
    questions_or_unknowns.append("fallback_logic: not provided during demo")

    # Step 6: Build metadata
    metadata = VersionMetadata(
        version_number="v1",
        source="demo",
        timestamp=datetime.utcnow().isoformat() + "Z",
    )

    # Step 7: Return config
    return AgentConfiguration(
        client_id=client_id,
        client_info=client_info,
        business_hours=BusinessHours(),
        emergency_definitions=emergency_definitions,
        routing_rules=[],
        transfer_destinations=[],
        integration_constraints=[],
        fallback_logic=None,
        questions_or_unknowns=questions_or_unknowns,
        metadata=metadata,
    )
