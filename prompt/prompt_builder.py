"""Generates the Retell system prompt string for Clara from a completed AgentConfiguration."""

from schemas.agent_schema import AgentConfiguration


def build_prompt(config: AgentConfiguration) -> str:
    """Build the complete Clara system prompt from an AgentConfiguration and return it as a string."""
    sections: list[str] = []

    company_name = config.client_info.company_name or "your company"

    # --- Section 1: Identity ---
    sections.append(
        f"You are Clara, an AI receptionist for {company_name}.\n"
        "You answer inbound calls professionally and route callers to the right destination."
    )

    # --- Section 2: Business Hours ---
    if config.business_hours.schedule:
        tz = config.business_hours.timezone or "timezone not set"
        lines = [f"Business Hours ({tz}):"]
        day_order = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for day in day_order:
            if day in config.business_hours.schedule:
                lines.append(f"  {day.capitalize()}: {config.business_hours.schedule[day]}")
        sections.append("\n".join(lines))
    else:
        sections.append(
            "Business hours have not been configured.\n"
            "Treat all calls as after-hours until this is resolved."
        )

    # --- Section 3: Emergency Types ---
    if config.emergency_definitions:
        lines = ["Emergency Types:"]
        for ed in config.emergency_definitions:
            lines.append(f"  - {ed.type} ({ed.priority}): {ed.description}")
        sections.append("\n".join(lines))
    else:
        sections.append(
            "No emergency types have been defined.\n"
            "Escalate any caller reporting an urgent issue to a live person immediately."
        )

    # --- Section 4: Business Hours Call Flow ---
    # Find emergency transfer timeout
    timeout_str = "60"
    timeout_note = " (default — confirm with client)"
    for rule in config.routing_rules:
        if "emergency" in rule.condition.lower() and rule.transfer_timeout_seconds is not None:
            timeout_str = str(rule.transfer_timeout_seconds)
            timeout_note = ""
            break

    sections.append(
        f"During Business Hours — follow these steps in order:\n"
        f'1. Greet: "Thank you for calling {company_name}, this is Clara. How can I help you?"\n'
        f"2. Ask for the caller's name.\n"
        f"3. Ask for a callback phone number.\n"
        f"4. Determine if the request is an emergency or a general service request.\n"
        f"5. If emergency: attempt transfer to the appropriate destination.\n"
        f'   If transfer fails after {timeout_str}s{timeout_note}: say "I was unable to reach the team directly.\n'
        f'   I have your information and someone will follow up with you shortly."\n'
        f"6. If non-emergency: confirm the request and advise follow-up during business hours.\n"
        f'7. Ask: "Is there anything else I can help you with today?"\n'
        f"8. Close the call professionally."
    )

    # --- Section 5: After Hours Call Flow ---
    sections.append(
        "After Hours — follow these steps in order:\n"
        "1. Greet the caller and identify yourself as Clara.\n"
        '2. Ask: "What is the reason for your call?"\n'
        '3. Ask: "Is this an emergency situation?"\n'
        "4. If emergency:\n"
        "   a. Collect caller's full name.\n"
        "   b. Collect callback phone number.\n"
        "   c. Collect address or location of the issue.\n"
        "   d. Attempt emergency transfer.\n"
        '   e. If transfer fails: "I was unable to reach the on-call team.\n'
        '      I have your details and someone will contact you as soon as possible."\n'
        "5. If not emergency:\n"
        "   a. Collect details of the request.\n"
        '   b. Confirm: "Our team will follow up with you during business hours."\n'
        "6. Close the call."
    )

    # --- Section 6: Routing Rules ---
    if config.routing_rules:
        lines = ["Routing Rules:"]
        for rule in config.routing_rules:
            line = f"  - When {rule.condition}: transfer to {rule.destination}."
            if rule.transfer_timeout_seconds is not None:
                line += f" Timeout: {rule.transfer_timeout_seconds}s."
            lines.append(line)
        sections.append("\n".join(lines))
    else:
        sections.append("No routing rules configured.")

    # --- Section 7: Fallback Logic ---
    if config.fallback_logic is not None:
        sections.append(f"Fallback:\n{config.fallback_logic}")
    else:
        sections.append(
            "Fallback:\n"
            "If transfer fails, take the caller's name and phone number and confirm someone will\n"
            "follow up as soon as possible."
        )

    # --- Section 8: Integration Constraints ---
    if config.integration_constraints:
        lines = ["Integration Rules:"]
        for ic in config.integration_constraints:
            line = f"  - {ic.system}: {ic.rule}"
            if ic.restriction:
                line += f". {ic.restriction}"
            lines.append(line)
        sections.append("\n".join(lines))

    # --- Section 9: Operator Notes ---
    if config.questions_or_unknowns:
        lines = [
            "--- OPERATOR REVIEW REQUIRED ---",
            "The following items were not resolved during onboarding.",
            "Do not deploy this prompt until all items below are confirmed:",
            "",
        ]
        for unknown in config.questions_or_unknowns:
            lines.append(f"  - {unknown}")
        lines.append("")
        lines.append("--- END OPERATOR NOTES ---")
        sections.append("\n".join(lines))

    return "\n\n".join(sections)
