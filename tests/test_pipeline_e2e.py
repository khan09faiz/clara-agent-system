"""End-to-end tests for the full Clara pipeline (demo → v1, onboarding → v2)."""

import json
from datetime import datetime
from unittest.mock import patch

import pytest

from schemas.agent_schema import AgentConfiguration
from pipeline.demo_processor import process_demo
from pipeline.onboarding_processor import process_onboarding
from pipeline.form_processor import parse_form
from prompt.prompt_builder import build_prompt
from versioning.version_manager import save_version, load_version
from engine.change_logger import reset_change_log, get_change_log


FIXED_TIMESTAMP = datetime(2026, 1, 15, 12, 0, 0)


def _load_fixture(name: str) -> str:
    with open(f"tests/fixtures/{name}", "r", encoding="utf-8") as f:
        return f.read()


def _load_json_fixture(name: str) -> dict:
    with open(f"tests/fixtures/{name}", "r", encoding="utf-8") as f:
        return json.load(f)


class TestDemoPipeline:

    def setup_method(self) -> None:
        reset_change_log()

    @patch("pipeline.demo_processor.datetime")
    def test_demo_produces_v1(self, mock_dt) -> None:
        """Demo stage processes a transcript and produces a v1 config."""
        mock_dt.utcnow.return_value = FIXED_TIMESTAMP
        transcript = _load_fixture("sample_demo_transcript.txt")
        config = process_demo(client_id="silverline", transcript=transcript)

        assert config.metadata.version_number == "v1"
        assert config.metadata.source == "demo"
        assert config.client_id == "silverline"
        assert config.client_info.company_name is not None
        assert "Silverline" in config.client_info.company_name
        assert config.client_info.contact_name == "Marcus Rivera"

    @patch("pipeline.demo_processor.datetime")
    def test_demo_flags_unknowns(self, mock_dt) -> None:
        """Demo stage flags expected unknowns for fields not provided."""
        mock_dt.utcnow.return_value = FIXED_TIMESTAMP
        transcript = _load_fixture("sample_demo_transcript.txt")
        config = process_demo(client_id="silverline", transcript=transcript)

        unknowns_text = " ".join(config.questions_or_unknowns)
        assert "business_hours.schedule" in unknowns_text
        assert "business_hours.timezone" in unknowns_text
        assert "transfer_destinations" in unknowns_text

    @patch("pipeline.demo_processor.datetime")
    def test_demo_extracts_emergencies(self, mock_dt) -> None:
        """Demo stage extracts emergency definitions from transcript."""
        mock_dt.utcnow.return_value = FIXED_TIMESTAMP
        transcript = _load_fixture("sample_demo_transcript.txt")
        config = process_demo(client_id="silverline", transcript=transcript)

        assert len(config.emergency_definitions) > 0

    def test_demo_requires_input(self) -> None:
        """Demo stage raises ValueError when no transcript or audio provided."""
        with pytest.raises(ValueError, match="Must provide either"):
            process_demo(client_id="test")


class TestOnboardingPipeline:

    def setup_method(self) -> None:
        reset_change_log()

    @patch("pipeline.onboarding_processor.datetime")
    @patch("pipeline.demo_processor.datetime")
    def test_onboarding_produces_v2(self, mock_demo_dt, mock_onboard_dt) -> None:
        """Onboarding stage merges into v1 and produces a v2 config."""
        mock_demo_dt.utcnow.return_value = FIXED_TIMESTAMP
        mock_onboard_dt.utcnow.return_value = FIXED_TIMESTAMP

        demo_transcript = _load_fixture("sample_demo_transcript.txt")
        v1 = process_demo(client_id="silverline", transcript=demo_transcript)

        reset_change_log()

        onboarding_transcript = _load_fixture("sample_onboarding_transcript.txt")
        form_data = _load_json_fixture("sample_form.json")
        v2 = process_onboarding(
            existing_config=v1,
            transcript=onboarding_transcript,
            form_data=form_data,
        )

        assert v2.metadata.version_number == "v2"
        assert v2.metadata.source == "onboarding"
        assert v2.client_id == "silverline"

    @patch("pipeline.onboarding_processor.datetime")
    @patch("pipeline.demo_processor.datetime")
    def test_onboarding_resolves_unknowns(self, mock_demo_dt, mock_onboard_dt) -> None:
        """Onboarding stage resolves unknowns that were flagged during demo."""
        mock_demo_dt.utcnow.return_value = FIXED_TIMESTAMP
        mock_onboard_dt.utcnow.return_value = FIXED_TIMESTAMP

        demo_transcript = _load_fixture("sample_demo_transcript.txt")
        v1 = process_demo(client_id="silverline", transcript=demo_transcript)

        reset_change_log()

        onboarding_transcript = _load_fixture("sample_onboarding_transcript.txt")
        form_data = _load_json_fixture("sample_form.json")
        v2 = process_onboarding(
            existing_config=v1,
            transcript=onboarding_transcript,
            form_data=form_data,
        )

        # Form provides business_hours, timezone, transfer_destinations, routing_rules, fallback_logic
        unknowns_text = " ".join(v2.questions_or_unknowns)
        assert "business_hours.schedule" not in unknowns_text
        assert "business_hours.timezone" not in unknowns_text
        assert "transfer_destinations" not in unknowns_text
        assert "fallback_logic" not in unknowns_text

    @patch("pipeline.onboarding_processor.datetime")
    @patch("pipeline.demo_processor.datetime")
    def test_onboarding_populates_business_hours(self, mock_demo_dt, mock_onboard_dt) -> None:
        """Onboarding stage populates business hours from form data."""
        mock_demo_dt.utcnow.return_value = FIXED_TIMESTAMP
        mock_onboard_dt.utcnow.return_value = FIXED_TIMESTAMP

        v1 = process_demo(client_id="silverline", transcript=_load_fixture("sample_demo_transcript.txt"))
        reset_change_log()

        v2 = process_onboarding(
            existing_config=v1,
            transcript=_load_fixture("sample_onboarding_transcript.txt"),
            form_data=_load_json_fixture("sample_form.json"),
        )

        assert v2.business_hours.timezone == "America/Denver"
        assert "monday" in v2.business_hours.schedule
        assert v2.business_hours.schedule["saturday"] == "closed"

    @patch("pipeline.onboarding_processor.datetime")
    @patch("pipeline.demo_processor.datetime")
    def test_onboarding_logs_changes(self, mock_demo_dt, mock_onboard_dt) -> None:
        """Onboarding stage logs all changes in the change log."""
        mock_demo_dt.utcnow.return_value = FIXED_TIMESTAMP
        mock_onboard_dt.utcnow.return_value = FIXED_TIMESTAMP

        v1 = process_demo(client_id="silverline", transcript=_load_fixture("sample_demo_transcript.txt"))
        reset_change_log()

        v2 = process_onboarding(
            existing_config=v1,
            transcript=_load_fixture("sample_onboarding_transcript.txt"),
            form_data=_load_json_fixture("sample_form.json"),
        )

        change_log = get_change_log()
        assert len(change_log) > 0
        # Should have logged business_hours.timezone among others
        fields_changed = [e.field for e in change_log]
        assert any("business_hours" in f for f in fields_changed)


class TestFullPipelineRoundTrip:

    def setup_method(self) -> None:
        reset_change_log()

    @patch("pipeline.onboarding_processor.datetime")
    @patch("pipeline.demo_processor.datetime")
    def test_v1_v2_save_load_roundtrip(self, mock_demo_dt, mock_onboard_dt, tmp_path) -> None:
        """Full pipeline: demo → save v1 → onboarding → save v2 → load both."""
        mock_demo_dt.utcnow.return_value = FIXED_TIMESTAMP
        mock_onboard_dt.utcnow.return_value = FIXED_TIMESTAMP

        # Demo → v1
        v1 = process_demo(client_id="silverline", transcript=_load_fixture("sample_demo_transcript.txt"))
        save_version(v1, str(tmp_path))

        # Load v1 back
        loaded_v1 = load_version("silverline", "v1", str(tmp_path))
        assert loaded_v1.model_dump() == v1.model_dump()

        reset_change_log()

        # Onboarding → v2
        v2 = process_onboarding(
            existing_config=loaded_v1,
            transcript=_load_fixture("sample_onboarding_transcript.txt"),
            form_data=_load_json_fixture("sample_form.json"),
        )
        save_version(v2, str(tmp_path))

        # Load v2 back
        loaded_v2 = load_version("silverline", "v2", str(tmp_path))
        assert loaded_v2.model_dump() == v2.model_dump()

        # Both versions coexist
        from versioning.version_manager import list_versions
        versions = list_versions("silverline", str(tmp_path))
        assert versions == ["v1", "v2"]

    @patch("pipeline.onboarding_processor.datetime")
    @patch("pipeline.demo_processor.datetime")
    def test_prompt_generation_after_onboarding(self, mock_demo_dt, mock_onboard_dt) -> None:
        """Prompt generated from v2 config contains expected content."""
        mock_demo_dt.utcnow.return_value = FIXED_TIMESTAMP
        mock_onboard_dt.utcnow.return_value = FIXED_TIMESTAMP

        v1 = process_demo(client_id="silverline", transcript=_load_fixture("sample_demo_transcript.txt"))
        reset_change_log()
        v2 = process_onboarding(
            existing_config=v1,
            transcript=_load_fixture("sample_onboarding_transcript.txt"),
            form_data=_load_json_fixture("sample_form.json"),
        )

        prompt = build_prompt(v2)

        # Prompt must contain key content
        assert "Clara" in prompt
        assert "Silverline" in prompt
        assert "Business Hours" in prompt or "business hours" in prompt.lower()
        assert "After Hours" in prompt
        assert "emergency" in prompt.lower()

    @patch("pipeline.demo_processor.datetime")
    def test_pipeline_idempotent_demo(self, mock_dt) -> None:
        """Running demo processing twice with identical input produces identical output."""
        mock_dt.utcnow.return_value = FIXED_TIMESTAMP
        transcript = _load_fixture("sample_demo_transcript.txt")

        reset_change_log()
        v1_first = process_demo(client_id="silverline", transcript=transcript)

        reset_change_log()
        v1_second = process_demo(client_id="silverline", transcript=transcript)

        assert v1_first.model_dump() == v1_second.model_dump()

    @patch("engine.change_logger.datetime")
    @patch("pipeline.form_processor.datetime")
    @patch("pipeline.onboarding_processor.datetime")
    @patch("pipeline.demo_processor.datetime")
    def test_pipeline_idempotent_onboarding(
        self, mock_demo_dt, mock_onboard_dt, mock_form_dt, mock_changelog_dt,
    ) -> None:
        """Running onboarding twice with identical input produces identical output."""
        for m in (mock_demo_dt, mock_onboard_dt, mock_form_dt, mock_changelog_dt):
            m.utcnow.return_value = FIXED_TIMESTAMP

        transcript = _load_fixture("sample_demo_transcript.txt")
        v1 = process_demo(client_id="silverline", transcript=transcript)

        onboarding_transcript = _load_fixture("sample_onboarding_transcript.txt")
        form_data = _load_json_fixture("sample_form.json")

        reset_change_log()
        v2_first = process_onboarding(
            existing_config=v1,
            transcript=onboarding_transcript,
            form_data=form_data,
        )

        reset_change_log()
        v2_second = process_onboarding(
            existing_config=v1,
            transcript=onboarding_transcript,
            form_data=form_data,
        )

        assert v2_first.model_dump() == v2_second.model_dump()
