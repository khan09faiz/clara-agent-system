"""Deterministically merges an incoming AgentConfiguration update into an existing configuration, logging all changes."""

from schemas.agent_schema import (
    AgentConfiguration,
    BusinessHours,
    ClientInfo,
    VersionMetadata,
)
from engine.change_logger import log_change


def merge(
    existing: AgentConfiguration,
    updates: AgentConfiguration,
    source: str,
    explicit_override: bool = False,
) -> AgentConfiguration:
    """Merge updates into existing config and return a new AgentConfiguration instance."""
    # Start with a deep copy of existing
    merged = existing.model_copy(deep=True)

    # --- Scalar: client_info fields ---
    for attr in ("company_name", "contact_name", "phone"):
        inc_val = getattr(updates.client_info, attr)
        ex_val = getattr(merged.client_info, attr)
        if inc_val is not None and inc_val != ex_val:
            log_change(
                field=f"client_info.{attr}",
                previous_value=ex_val,
                new_value=inc_val,
                source=source,
                reason="field_update",
            )
            setattr(merged.client_info, attr, inc_val)

    # client_info.emails: deduplicate and append
    if updates.client_info.emails:
        existing_emails = set(merged.client_info.emails)
        new_emails = [e for e in updates.client_info.emails if e not in existing_emails]
        if new_emails:
            log_change(
                field="client_info.emails",
                previous_value=merged.client_info.emails,
                new_value=merged.client_info.emails + new_emails,
                source=source,
                reason="field_update",
            )
            merged.client_info.emails = merged.client_info.emails + new_emails

    # --- Business hours timezone (scalar) ---
    if (
        updates.business_hours.timezone is not None
        and updates.business_hours.timezone != merged.business_hours.timezone
    ):
        log_change(
            field="business_hours.timezone",
            previous_value=merged.business_hours.timezone,
            new_value=updates.business_hours.timezone,
            source=source,
            reason="field_update",
        )
        merged.business_hours.timezone = updates.business_hours.timezone

    # --- Business hours schedule (dict merge) ---
    if updates.business_hours.schedule:
        for day, hours in updates.business_hours.schedule.items():
            ex_hours = merged.business_hours.schedule.get(day)
            if ex_hours != hours:
                log_change(
                    field=f"business_hours.schedule.{day}",
                    previous_value=ex_hours,
                    new_value=hours,
                    source=source,
                    reason="field_update",
                )
                merged.business_hours.schedule[day] = hours

    # --- Emergency definitions ---
    if explicit_override and updates.emergency_definitions:
        log_change(
            field="emergency_definitions",
            previous_value=[e.model_dump() for e in merged.emergency_definitions],
            new_value=[e.model_dump() for e in updates.emergency_definitions],
            source=source,
            reason="explicit_override",
        )
        merged.emergency_definitions = list(updates.emergency_definitions)
    else:
        existing_types = {e.type: i for i, e in enumerate(merged.emergency_definitions)}
        for inc_e in updates.emergency_definitions:
            if inc_e.type in existing_types:
                idx = existing_types[inc_e.type]
                ex_e = merged.emergency_definitions[idx]
                if ex_e.description != inc_e.description or ex_e.priority != inc_e.priority:
                    log_change(
                        field=f"emergency_definitions.{inc_e.type}",
                        previous_value=ex_e.model_dump(),
                        new_value=inc_e.model_dump(),
                        source=source,
                        reason="onboarding_override",
                    )
                    merged.emergency_definitions[idx] = inc_e.model_copy()
            else:
                log_change(
                    field=f"emergency_definitions.{inc_e.type}",
                    previous_value=None,
                    new_value=inc_e.model_dump(),
                    source=source,
                    reason="new_entry",
                )
                merged.emergency_definitions.append(inc_e.model_copy())

    # --- Routing rules ---
    if explicit_override and updates.routing_rules:
        log_change(
            field="routing_rules",
            previous_value=[r.model_dump() for r in merged.routing_rules],
            new_value=[r.model_dump() for r in updates.routing_rules],
            source=source,
            reason="explicit_override",
        )
        merged.routing_rules = list(updates.routing_rules)
    else:
        existing_conditions = {r.condition: i for i, r in enumerate(merged.routing_rules)}
        for inc_r in updates.routing_rules:
            if inc_r.condition in existing_conditions:
                idx = existing_conditions[inc_r.condition]
                ex_r = merged.routing_rules[idx]
                if (
                    ex_r.destination != inc_r.destination
                    or ex_r.transfer_timeout_seconds != inc_r.transfer_timeout_seconds
                ):
                    log_change(
                        field=f"routing_rules.{inc_r.condition}",
                        previous_value=ex_r.model_dump(),
                        new_value=inc_r.model_dump(),
                        source=source,
                        reason="onboarding_override",
                    )
                    merged.routing_rules[idx] = inc_r.model_copy()
            else:
                log_change(
                    field=f"routing_rules.{inc_r.condition}",
                    previous_value=None,
                    new_value=inc_r.model_dump(),
                    source=source,
                    reason="new_entry",
                )
                merged.routing_rules.append(inc_r.model_copy())

    # --- Integration constraints ---
    if explicit_override and updates.integration_constraints:
        log_change(
            field="integration_constraints",
            previous_value=[c.model_dump() for c in merged.integration_constraints],
            new_value=[c.model_dump() for c in updates.integration_constraints],
            source=source,
            reason="explicit_override",
        )
        merged.integration_constraints = list(updates.integration_constraints)
    else:
        existing_systems = {c.system: i for i, c in enumerate(merged.integration_constraints)}
        for inc_c in updates.integration_constraints:
            if inc_c.system in existing_systems:
                idx = existing_systems[inc_c.system]
                ex_c = merged.integration_constraints[idx]
                if ex_c.rule != inc_c.rule or ex_c.restriction != inc_c.restriction:
                    log_change(
                        field=f"integration_constraints.{inc_c.system}",
                        previous_value=ex_c.model_dump(),
                        new_value=inc_c.model_dump(),
                        source=source,
                        reason="onboarding_override",
                    )
                    merged.integration_constraints[idx] = inc_c.model_copy()
            else:
                log_change(
                    field=f"integration_constraints.{inc_c.system}",
                    previous_value=None,
                    new_value=inc_c.model_dump(),
                    source=source,
                    reason="new_entry",
                )
                merged.integration_constraints.append(inc_c.model_copy())

    # --- Transfer destinations (deduplicate) ---
    if explicit_override and updates.transfer_destinations:
        log_change(
            field="transfer_destinations",
            previous_value=merged.transfer_destinations,
            new_value=updates.transfer_destinations,
            source=source,
            reason="explicit_override",
        )
        merged.transfer_destinations = list(updates.transfer_destinations)
    else:
        existing_dests = set(merged.transfer_destinations)
        for dest in updates.transfer_destinations:
            if dest not in existing_dests:
                log_change(
                    field="transfer_destinations",
                    previous_value=merged.transfer_destinations.copy(),
                    new_value=merged.transfer_destinations + [dest],
                    source=source,
                    reason="new_entry",
                )
                merged.transfer_destinations.append(dest)
                existing_dests.add(dest)

    # --- Fallback logic (scalar) ---
    if updates.fallback_logic is not None and updates.fallback_logic != merged.fallback_logic:
        log_change(
            field="fallback_logic",
            previous_value=merged.fallback_logic,
            new_value=updates.fallback_logic,
            source=source,
            reason="field_update",
        )
        merged.fallback_logic = updates.fallback_logic

    return merged
