"""Tests for prompt generation functionality."""

import pytest

from schemas.agent_schema import (
    AgentConfiguration,
    BusinessHours,
    ClientInfo,
    EmergencyDefinition,
    RoutingRule,
    VersionMetadata,
)
from prompt.prompt_builder import build_prompt


def _make_metadata(version: str = "v1", source: str = "test") -> VersionMetadata:
    return VersionMetadata(
        version_number=version,
        source=source,
        timestamp="2026-01-01T00:00:00Z",
    )


def _make_config(**kwargs) -> AgentConfiguration:
    defaults = {
        "client_id": "test_client",
        "metadata": _make_metadata(),
    }
    defaults.update(kwargs)
    return AgentConfiguration(**defaults)


class TestPromptGeneration:

    def test_prompt_contains_company_name(self) -> None:
        """Prompt contains the company name when set."""
        config = _make_config(
            client_info=ClientInfo(company_name="Acme Fire Protection"),
        )
        prompt = build_prompt(config)
        assert "Acme Fire Protection" in prompt

    def test_prompt_contains_all_emergency_types(self) -> None:
        """Prompt contains all emergency type values."""
        config = _make_config(
            emergency_definitions=[
                EmergencyDefinition(type="sprinkler_leak", description="Leak", priority="high"),
                EmergencyDefinition(type="fire_alarm_trigger", description="Alarm", priority="high"),
            ],
        )
        prompt = build_prompt(config)
        assert "sprinkler_leak" in prompt
        assert "fire_alarm_trigger" in prompt

    def test_prompt_fallback_for_missing_company_name(self) -> None:
        """Prompt uses 'your company' when company_name is None."""
        config = _make_config(
            client_info=ClientInfo(company_name=None),
        )
        prompt = build_prompt(config)
        assert "your company" in prompt

    def test_prompt_no_hours_message_when_schedule_empty(self) -> None:
        """Prompt shows not-configured message when schedule is empty."""
        config = _make_config(
            business_hours=BusinessHours(schedule={}),
        )
        prompt = build_prompt(config)
        assert "Business hours have not been configured." in prompt

    def test_prompt_unknowns_section_present(self) -> None:
        """Prompt contains operator review section when unknowns are present."""
        config = _make_config(
            questions_or_unknowns=["business_hours.timezone: not provided during demo"],
        )
        prompt = build_prompt(config)
        assert "OPERATOR REVIEW REQUIRED" in prompt

    def test_prompt_no_unknowns_section_when_empty(self) -> None:
        """Prompt does not contain operator review section when no unknowns."""
        config = _make_config(
            questions_or_unknowns=[],
        )
        prompt = build_prompt(config)
        assert "OPERATOR REVIEW REQUIRED" not in prompt

    def test_prompt_is_deterministic(self) -> None:
        """Calling build_prompt twice on the same config produces identical output."""
        config = _make_config(
            client_info=ClientInfo(company_name="Acme"),
            business_hours=BusinessHours(
                timezone="America/Denver",
                schedule={"monday": "8am-5pm"},
            ),
            emergency_definitions=[
                EmergencyDefinition(type="sprinkler_leak", description="Leak", priority="high"),
            ],
            routing_rules=[
                RoutingRule(condition="after hours emergency", destination="555-0001", transfer_timeout_seconds=60),
            ],
            fallback_logic="Take a message.",
            questions_or_unknowns=["test: something"],
        )
        prompt1 = build_prompt(config)
        prompt2 = build_prompt(config)
        assert prompt1 == prompt2
