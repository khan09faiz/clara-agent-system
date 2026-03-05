"""Tests for merge engine functionality."""

import pytest

from schemas.agent_schema import (
    AgentConfiguration,
    BusinessHours,
    ClientInfo,
    EmergencyDefinition,
    RoutingRule,
    VersionMetadata,
)
from engine.merge_engine import merge
from engine.change_logger import get_change_log, reset_change_log


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


class TestMerging:

    def setup_method(self) -> None:
        reset_change_log()

    def test_merge_no_changes_when_updates_all_none(self) -> None:
        """Merge with all-None update fields produces no changes."""
        v1 = _make_config(
            client_info=ClientInfo(
                company_name="Acme",
                contact_name="John",
                phone="5550001",
                emails=["a@b.com"],
            ),
            business_hours=BusinessHours(timezone="America/Denver", schedule={"monday": "8am-5pm"}),
            fallback_logic="Take a message",
        )
        updates = _make_config()
        result = merge(v1, updates, source="test")

        assert result.client_info.company_name == "Acme"
        assert result.client_info.contact_name == "John"
        assert result.client_info.phone == "5550001"
        assert result.business_hours.timezone == "America/Denver"
        assert result.fallback_logic == "Take a message"
        assert get_change_log() == []

    def test_merge_updates_scalar_field(self) -> None:
        """Merge updates a scalar field and logs the change."""
        v1 = _make_config(
            business_hours=BusinessHours(timezone=None),
        )
        updates = _make_config(
            business_hours=BusinessHours(timezone="America/Denver"),
        )
        result = merge(v1, updates, source="onboarding")

        assert result.business_hours.timezone == "America/Denver"
        log = get_change_log()
        assert len(log) == 1
        assert log[0].field == "business_hours.timezone"
        assert log[0].previous_value is None
        assert log[0].new_value == "America/Denver"

    def test_merge_appends_new_emergency_type(self) -> None:
        """Merge appends a new emergency type without duplicating existing ones."""
        v1 = _make_config(
            emergency_definitions=[
                EmergencyDefinition(type="sprinkler_leak", description="Leak", priority="high"),
            ],
        )
        updates = _make_config(
            emergency_definitions=[
                EmergencyDefinition(type="fire_alarm_trigger", description="Alarm", priority="high"),
            ],
        )
        result = merge(v1, updates, source="onboarding")

        types = [e.type for e in result.emergency_definitions]
        assert "sprinkler_leak" in types
        assert "fire_alarm_trigger" in types
        assert len(types) == 2

    def test_merge_does_not_duplicate_existing(self) -> None:
        """Merge with identical emergency definition produces no duplicate and no log entry."""
        defn = EmergencyDefinition(type="sprinkler_leak", description="Leak", priority="high")
        v1 = _make_config(emergency_definitions=[defn])
        updates = _make_config(emergency_definitions=[defn.model_copy()])
        result = merge(v1, updates, source="onboarding")

        assert len(result.emergency_definitions) == 1
        assert get_change_log() == []

    def test_merge_idempotent(self) -> None:
        """Calling merge twice with identical inputs produces equal results and no extra log entries."""
        v1 = _make_config(
            business_hours=BusinessHours(timezone=None),
        )
        updates = _make_config(
            business_hours=BusinessHours(timezone="America/Denver"),
        )

        result1 = merge(v1, updates, source="onboarding")
        log_count_1 = len(get_change_log())

        reset_change_log()
        result2 = merge(v1, updates, source="onboarding")
        log_count_2 = len(get_change_log())

        assert result1.model_dump() == result2.model_dump()
        assert log_count_1 == log_count_2
