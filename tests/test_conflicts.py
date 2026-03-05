"""Tests for conflict detection functionality."""

import pytest

from schemas.agent_schema import (
    AgentConfiguration,
    BusinessHours,
    ClientInfo,
    EmergencyDefinition,
    RoutingRule,
    VersionMetadata,
)
from engine.conflict_detector import detect
from engine.merge_engine import merge
from engine.change_logger import get_change_log, reset_change_log, log_change


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


class TestConflicts:

    def setup_method(self) -> None:
        reset_change_log()

    def test_conflict_emergency_priority_change(self) -> None:
        """Detects a conflict when emergency priority changes for the same type."""
        v1 = _make_config(
            emergency_definitions=[
                EmergencyDefinition(type="sprinkler_leak", description="Leak", priority="medium"),
            ],
        )
        incoming = _make_config(
            emergency_definitions=[
                EmergencyDefinition(type="sprinkler_leak", description="Leak", priority="high"),
            ],
        )
        conflicts = detect(existing=v1, incoming=incoming)

        assert len(conflicts) == 1
        assert "emergency_definitions" in conflicts[0].field
        assert conflicts[0].existing_value["priority"] == "medium"
        assert conflicts[0].incoming_value["priority"] == "high"

    def test_conflict_routing_destination_change(self) -> None:
        """Detects a conflict when routing destination changes for the same condition."""
        v1 = _make_config(
            routing_rules=[
                RoutingRule(condition="after hours emergency", destination="555-0001"),
            ],
        )
        incoming = _make_config(
            routing_rules=[
                RoutingRule(condition="after hours emergency", destination="555-0002"),
            ],
        )
        conflicts = detect(existing=v1, incoming=incoming)

        assert len(conflicts) == 1
        assert "routing_rules" in conflicts[0].field

    def test_no_conflict_identical_configs(self) -> None:
        """No conflicts detected when configs are identical."""
        config = _make_config(
            business_hours=BusinessHours(timezone="America/Denver"),
            emergency_definitions=[
                EmergencyDefinition(type="sprinkler_leak", description="Leak", priority="high"),
            ],
            routing_rules=[
                RoutingRule(condition="after hours emergency", destination="555-0001"),
            ],
            fallback_logic="Take a message",
        )
        conflicts = detect(existing=config, incoming=config)

        assert conflicts == []

    def test_conflict_timezone_mismatch(self) -> None:
        """Detects a conflict when timezone differs between configs."""
        v1 = _make_config(
            business_hours=BusinessHours(timezone="America/Chicago"),
        )
        incoming = _make_config(
            business_hours=BusinessHours(timezone="America/Denver"),
        )
        conflicts = detect(existing=v1, incoming=incoming)

        assert len(conflicts) == 1
        assert conflicts[0].field == "business_hours.timezone"

    def test_conflict_resolution_incoming_wins(self) -> None:
        """After merging with a conflict, the merged config uses the incoming value."""
        v1 = _make_config(
            emergency_definitions=[
                EmergencyDefinition(type="sprinkler_leak", description="Leak", priority="medium"),
            ],
        )
        incoming = _make_config(
            emergency_definitions=[
                EmergencyDefinition(type="sprinkler_leak", description="Leak", priority="high"),
            ],
        )

        # Detect conflict and log it
        conflicts = detect(existing=v1, incoming=incoming)
        for conflict in conflicts:
            log_change(
                field=conflict.field,
                previous_value=conflict.existing_value,
                new_value=conflict.incoming_value,
                source="onboarding",
                reason="onboarding_override",
            )

        # Merge
        merged = merge(existing=v1, updates=incoming, source="onboarding")

        # Assert incoming wins
        sprinkler = next(e for e in merged.emergency_definitions if e.type == "sprinkler_leak")
        assert sprinkler.priority == "high"

        # Assert change log has the override entry
        log = get_change_log()
        override_entries = [e for e in log if e.reason == "onboarding_override"]
        assert len(override_entries) >= 1
