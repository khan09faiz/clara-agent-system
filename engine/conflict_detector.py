"""Detects contradictions between an existing config and an incoming update before merge is applied."""

from dataclasses import dataclass
from typing import Any

from schemas.agent_schema import AgentConfiguration


@dataclass
class Conflict:
    field: str
    existing_value: Any
    incoming_value: Any
    resolution: str = "incoming_wins"
    reason: str = "onboarding_override"


def detect(
    existing: AgentConfiguration,
    incoming: AgentConfiguration,
) -> list[Conflict]:
    """Return a list of Conflict instances where existing and incoming configs disagree."""
    conflicts: list[Conflict] = []

    # Emergency definitions: same type, different description or priority
    existing_emergencies = {e.type: e for e in existing.emergency_definitions}
    for inc_e in incoming.emergency_definitions:
        if inc_e.type in existing_emergencies:
            ex_e = existing_emergencies[inc_e.type]
            if ex_e.description != inc_e.description or ex_e.priority != inc_e.priority:
                conflicts.append(
                    Conflict(
                        field="emergency_definitions",
                        existing_value=ex_e.model_dump(),
                        incoming_value=inc_e.model_dump(),
                    )
                )

    # Routing rules: same condition, different destination or transfer_timeout_seconds
    existing_routes = {r.condition: r for r in existing.routing_rules}
    for inc_r in incoming.routing_rules:
        if inc_r.condition in existing_routes:
            ex_r = existing_routes[inc_r.condition]
            if (
                ex_r.destination != inc_r.destination
                or ex_r.transfer_timeout_seconds != inc_r.transfer_timeout_seconds
            ):
                conflicts.append(
                    Conflict(
                        field="routing_rules",
                        existing_value=ex_r.model_dump(),
                        incoming_value=inc_r.model_dump(),
                    )
                )

    # Business hours timezone
    if (
        existing.business_hours.timezone is not None
        and incoming.business_hours.timezone is not None
        and existing.business_hours.timezone != incoming.business_hours.timezone
    ):
        conflicts.append(
            Conflict(
                field="business_hours.timezone",
                existing_value=existing.business_hours.timezone,
                incoming_value=incoming.business_hours.timezone,
            )
        )

    # Fallback logic
    if (
        existing.fallback_logic is not None
        and incoming.fallback_logic is not None
        and existing.fallback_logic != incoming.fallback_logic
    ):
        conflicts.append(
            Conflict(
                field="fallback_logic",
                existing_value=existing.fallback_logic,
                incoming_value=incoming.fallback_logic,
            )
        )

    return conflicts
