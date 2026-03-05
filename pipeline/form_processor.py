"""Converts a structured onboarding form dictionary into a partial AgentConfiguration containing only explicitly provided fields."""

from datetime import datetime

from schemas.agent_schema import (
    AgentConfiguration,
    BusinessHours,
    ClientInfo,
    EmergencyDefinition,
    IntegrationConstraint,
    RoutingRule,
    VersionMetadata,
)


def parse_form(form_data: dict) -> AgentConfiguration:
    """Parse a form dictionary into a partial AgentConfiguration with only explicitly provided fields."""
    business_hours = BusinessHours()

    timezone = form_data.get("timezone")
    if timezone and isinstance(timezone, str) and timezone.strip():
        business_hours.timezone = timezone.strip()

    schedule = form_data.get("business_hours")
    if schedule and isinstance(schedule, dict):
        business_hours.schedule = {k: v for k, v in schedule.items() if v}

    emergency_definitions: list[EmergencyDefinition] = []
    raw_emergencies = form_data.get("emergency_types")
    if raw_emergencies and isinstance(raw_emergencies, list):
        for item in raw_emergencies:
            if isinstance(item, dict) and item.get("type") and item.get("description"):
                emergency_definitions.append(
                    EmergencyDefinition(
                        type=item["type"],
                        description=item["description"],
                        priority=item.get("priority", "high"),
                    )
                )

    routing_rules: list[RoutingRule] = []
    raw_routing = form_data.get("routing_rules")
    if raw_routing and isinstance(raw_routing, list):
        for item in raw_routing:
            if isinstance(item, dict) and item.get("condition") and item.get("destination"):
                routing_rules.append(
                    RoutingRule(
                        condition=item["condition"],
                        destination=item["destination"],
                        transfer_timeout_seconds=item.get("transfer_timeout_seconds"),
                    )
                )

    transfer_destinations: list[str] = []
    raw_dests = form_data.get("transfer_destinations")
    if raw_dests and isinstance(raw_dests, list):
        transfer_destinations = [d for d in raw_dests if isinstance(d, str) and d.strip()]

    fallback_logic: str | None = None
    raw_fallback = form_data.get("fallback_logic")
    if raw_fallback and isinstance(raw_fallback, str) and raw_fallback.strip():
        fallback_logic = raw_fallback.strip()

    integration_constraints: list[IntegrationConstraint] = []
    raw_integrations = form_data.get("integrations")
    if raw_integrations and isinstance(raw_integrations, list):
        for item in raw_integrations:
            if isinstance(item, dict) and item.get("system") and item.get("rule"):
                integration_constraints.append(
                    IntegrationConstraint(
                        system=item["system"],
                        rule=item["rule"],
                        restriction=item.get("restriction"),
                    )
                )

    metadata = VersionMetadata(
        version_number="__partial__",
        source="form",
        timestamp=datetime.utcnow().isoformat() + "Z",
    )

    return AgentConfiguration(
        client_id="__form_partial__",
        client_info=ClientInfo(),
        business_hours=business_hours,
        emergency_definitions=emergency_definitions,
        routing_rules=routing_rules,
        transfer_destinations=transfer_destinations,
        integration_constraints=integration_constraints,
        fallback_logic=fallback_logic,
        questions_or_unknowns=[],
        metadata=metadata,
    )
