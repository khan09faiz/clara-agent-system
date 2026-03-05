"""CLI entry point for the Clara Agent System pipeline."""

import argparse
import importlib.util
import json
import os
import sys

from engine.change_logger import reset_change_log, get_change_log
from pipeline.demo_processor import process_demo
from pipeline.onboarding_processor import process_onboarding
from prompt.prompt_builder import build_prompt
from versioning.version_manager import save_version, load_version
from ingestion.chat_log_parser import parse_chat_log

# Import pipeline_logger via importlib to avoid shadowing stdlib logging
_spec = importlib.util.spec_from_file_location(
    "pipeline_logger",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "logging", "pipeline_logger.py"),
)
_pipeline_logger_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pipeline_logger_mod)  # type: ignore[union-attr]
get_logger = _pipeline_logger_mod.get_logger
log_event = _pipeline_logger_mod.log_event


def main() -> None:
    """Parse CLI arguments and run the appropriate pipeline stage."""
    parser = argparse.ArgumentParser(description="Clara Agent System Pipeline")
    parser.add_argument("--stage", required=True, choices=["demo", "onboarding"])
    parser.add_argument("--client_id", required=True)
    parser.add_argument("--transcript", default=None, help="Path to .txt transcript file")
    parser.add_argument("--audio", default=None, help="Path to audio/video file")
    parser.add_argument("--chat_log", default=None, help="Path to chat log .txt file")
    parser.add_argument("--form", default=None, help="Path to JSON form file")
    parser.add_argument("--whisper_key", default=None, help="OpenAI API key for Whisper")
    parser.add_argument("--output_dir", default="./output")
    parser.add_argument("--versions_dir", default="./versions")
    args = parser.parse_args()

    # First call: reset change log
    reset_change_log()

    logger = get_logger(args.client_id)

    if args.stage == "demo":
        _run_demo(args, logger)
    elif args.stage == "onboarding":
        _run_onboarding(args, logger)


def _run_demo(args: argparse.Namespace, logger: object) -> None:
    """Execute the demo pipeline stage."""
    log_event(logger, "pipeline_start", args.client_id, stage="demo", input_type=_input_type(args))

    # Load transcript text
    transcript_text: str | None = None
    chat_prefix = ""

    # Step 3: If chat_log provided, parse and prepend contact info
    if args.chat_log:
        with open(args.chat_log, "r", encoding="utf-8") as f:
            chat_raw = f.read()
        chat_entities = parse_chat_log(chat_raw)
        log_event(logger, "chat_log_parsed", args.client_id,
                  fields_found=_entity_fields(chat_entities))
        # Build text block from extracted entities
        parts = []
        if chat_entities.company_name:
            parts.append(f"Company name is {chat_entities.company_name}")
        if chat_entities.contact_name:
            parts.append(f"my name is {chat_entities.contact_name}")
        if chat_entities.phone_number:
            parts.append(f"phone is {chat_entities.phone_number}")
        if chat_entities.emails:
            parts.append(f"emails: {', '.join(chat_entities.emails)}")
        if parts:
            chat_prefix = ". ".join(parts) + ". "

    # Step 4: Load transcript or transcribe audio
    if args.transcript:
        with open(args.transcript, "r", encoding="utf-8") as f:
            transcript_text = chat_prefix + f.read()
    elif args.audio:
        transcript_text = None  # Will be transcribed in process_demo
    elif chat_prefix:
        transcript_text = chat_prefix

    # Step 5: Process demo
    if args.audio:
        config = process_demo(
            client_id=args.client_id,
            audio_path=args.audio,
            whisper_api_key=args.whisper_key,
        )
    else:
        config = process_demo(
            client_id=args.client_id,
            transcript=transcript_text,
        )

    # Step 6: Save version
    file_path = save_version(config, args.versions_dir)
    log_event(logger, "version_saved", args.client_id, version="v1", file_path=file_path)

    # Step 7: Build prompt
    prompt = build_prompt(config)
    log_event(logger, "prompt_generated", args.client_id, character_count=len(prompt))

    # Step 8: Write output JSON
    os.makedirs(args.output_dir, exist_ok=True)
    output = {
        "client_id": args.client_id,
        "agent_versions": {
            "v1": json.loads(config.model_dump_json()),
        },
        "change_log": [e.model_dump() for e in get_change_log()],
        "questions_or_unknowns": config.questions_or_unknowns,
        "generated_agent_prompt": prompt,
    }
    output_path = os.path.join(args.output_dir, f"{args.client_id}_output.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    # Step 9: Log complete
    log_event(
        logger, "pipeline_complete", args.client_id,
        version="v1", unknowns_remaining=len(config.questions_or_unknowns),
    )


def _run_onboarding(args: argparse.Namespace, logger: object) -> None:
    """Execute the onboarding pipeline stage."""
    log_event(logger, "pipeline_start", args.client_id, stage="onboarding", input_type=_input_type(args))

    # Step 3: Load existing v1 config
    v1_config = load_version(args.client_id, "v1", args.versions_dir)

    # Step 4: Load transcript text
    transcript_text: str | None = None
    if args.transcript:
        with open(args.transcript, "r", encoding="utf-8") as f:
            transcript_text = f.read()

    # Step 5: Load form data
    form_data: dict | None = None
    if args.form:
        with open(args.form, "r", encoding="utf-8") as f:
            form_data = json.load(f)

    # Step 6: Process onboarding
    if args.audio:
        v2_config = process_onboarding(
            existing_config=v1_config,
            audio_path=args.audio,
            form_data=form_data,
            whisper_api_key=args.whisper_key,
        )
    else:
        v2_config = process_onboarding(
            existing_config=v1_config,
            transcript=transcript_text,
            form_data=form_data,
        )

    # Step 7: Save v2 version
    file_path = save_version(v2_config, args.versions_dir)
    log_event(logger, "version_saved", args.client_id, version="v2", file_path=file_path)

    # Step 8: Build prompt
    prompt = build_prompt(v2_config)
    log_event(logger, "prompt_generated", args.client_id, character_count=len(prompt))

    # Step 9: Load v1 again for output
    v1_for_output = load_version(args.client_id, "v1", args.versions_dir)

    # Step 10: Write output JSON
    os.makedirs(args.output_dir, exist_ok=True)
    output = {
        "client_id": args.client_id,
        "agent_versions": {
            "v1": json.loads(v1_for_output.model_dump_json()),
            "v2": json.loads(v2_config.model_dump_json()),
        },
        "change_log": [e.model_dump() for e in get_change_log()],
        "questions_or_unknowns": v2_config.questions_or_unknowns,
        "generated_agent_prompt": prompt,
    }
    output_path = os.path.join(args.output_dir, f"{args.client_id}_output.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    # Step 11: Log complete
    log_event(
        logger, "pipeline_complete", args.client_id,
        version="v2", unknowns_remaining=len(v2_config.questions_or_unknowns),
    )


def _input_type(args: argparse.Namespace) -> str:
    """Determine the input type string from CLI args."""
    if args.audio:
        return "audio"
    if args.transcript:
        return "transcript"
    if getattr(args, "chat_log", None):
        return "chat_log"
    return "unknown"


def _entity_fields(entities: object) -> list[str]:
    """Return a list of field names that have non-empty values on an ExtractedEntities."""
    fields: list[str] = []
    for attr in ("company_name", "contact_name", "phone_number"):
        if getattr(entities, attr, None) is not None:
            fields.append(attr)
    for attr in ("emails", "service_types", "emergency_examples", "routing_descriptions"):
        if getattr(entities, attr, None):
            fields.append(attr)
    return fields


if __name__ == "__main__":
    main()
