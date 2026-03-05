"""Processes onboarding call inputs and form data to produce a v2 AgentConfiguration by updating v1."""

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
from pipeline.form_processor import parse_form
from engine import conflict_detector, merge_engine
from engine.change_logger import log_change, get_change_log


def _slugify(text: str) -> str:
    """Lowercase, replace non-alphanumeric with underscore, collapse and strip underscores, truncate to 50 chars."""
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = re.sub(r"_+", "_", slug)
    slug = slug.strip("_")
    return slug[:50]


def process_onboarding(
    existing_config: AgentConfiguration,
    transcript: str | None = None,
    audio_path: str | None = None,
    form_data: dict | None = None,
    whisper_api_key: str | None = None,
) -> AgentConfiguration:
    """Process onboarding inputs and merge into existing v1 config to produce v2."""
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

    # Step 2: Normalize and extract
    normalized_text = normalize_transcript(raw_text)
    entities = extract_entities(normalized_text)

    # Step 3: Build partial config from transcript entities (no unknowns)
    transcript_partial = AgentConfiguration(
        client_id=existing_config.client_id,
        client_info=ClientInfo(
            company_name=entities.company_name,
            contact_name=entities.contact_name,
            phone=entities.phone_number,
            emails=entities.emails,
        ),
        emergency_definitions=[
            EmergencyDefinition(
                type=_slugify(ex),
                description=ex,
                priority="high",
            )
            for ex in entities.emergency_examples
        ],
        metadata=VersionMetadata(
            version_number="__partial__",
            source="onboarding",
            timestamp=datetime.utcnow().isoformat() + "Z",
        ),
    )

    # Step 4: If form_data provided, parse and merge form on top of transcript partial
    if form_data is not None:
        form_partial = parse_form(form_data)
        # Form data is more authoritative — merge form on top of transcript partial
        combined_updates = merge_engine.merge(
            existing=transcript_partial,
            updates=form_partial,
            source="form",
        )
        # Restore correct client_id and metadata
        combined_updates.client_id = existing_config.client_id
    else:
        combined_updates = transcript_partial

    # Step 5: Detect conflicts between existing config and combined updates
    conflicts = conflict_detector.detect(
        existing=existing_config,
        incoming=combined_updates,
    )
    conflict_log_entries = []
    for conflict in conflicts:
        entry = log_change(
            field=conflict.field,
            previous_value=conflict.existing_value,
            new_value=conflict.incoming_value,
            source="onboarding",
            reason="onboarding_override",
        )
        conflict_log_entries.append(entry)

    # Step 6: Merge into existing config
    merged_config = merge_engine.merge(
        existing=existing_config,
        updates=combined_updates,
        source="onboarding",
    )

    # Step 7: Remove resolved unknowns
    remaining_unknowns: list[str] = []
    for unknown_entry in merged_config.questions_or_unknowns:
        # Extract the field name before the colon
        field_name = unknown_entry.split(":")[0].strip()
        resolved = False

        # Check if the referenced field now has a value
        if field_name == "business_hours.schedule" and merged_config.business_hours.schedule:
            resolved = True
        elif field_name == "business_hours.timezone" and merged_config.business_hours.timezone:
            resolved = True
        elif field_name == "transfer_destinations" and merged_config.transfer_destinations:
            resolved = True
        elif field_name == "routing_rules" and merged_config.routing_rules:
            resolved = True
        elif field_name == "fallback_logic" and merged_config.fallback_logic:
            resolved = True
        elif field_name == "client_info.company_name" and merged_config.client_info.company_name:
            resolved = True
        elif field_name == "client_info.contact_name" and merged_config.client_info.contact_name:
            resolved = True
        elif field_name == "client_info.phone" and merged_config.client_info.phone:
            resolved = True
        elif field_name == "client_info.emails" and merged_config.client_info.emails:
            resolved = True
        elif field_name == "emergency_definitions" and merged_config.emergency_definitions:
            resolved = True

        if not resolved:
            remaining_unknowns.append(unknown_entry)

    merged_config.questions_or_unknowns = remaining_unknowns

    # Step 8: Append conflict log entries to metadata change_log
    all_change_entries = get_change_log()
    merged_config.metadata.change_log = list(all_change_entries)

    # Step 9: Set v2 metadata
    merged_config.metadata.version_number = "v2"
    merged_config.metadata.source = "onboarding"
    merged_config.metadata.timestamp = datetime.utcnow().isoformat() + "Z"

    # Step 10: Return
    return merged_config
