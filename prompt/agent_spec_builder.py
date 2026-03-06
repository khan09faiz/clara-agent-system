"""Generates a Retell-compatible agent_spec.json from an AgentConfiguration."""

import json
from schemas.agent_schema import AgentConfiguration
from prompt.prompt_builder import build_prompt


def build_agent_spec(config: AgentConfiguration) -> dict:
    """Build a complete Retell agent specification dictionary from an AgentConfiguration."""
    company_name = config.client_info.company_name or "Service Company"
    version = config.metadata.version_number

    # Transfer numbers from routing rules and transfer_destinations
    transfer_numbers = {}
    for rule in config.routing_rules:
        transfer_numbers[rule.condition] = {
            "phone_number": rule.destination,
            "timeout_seconds": rule.transfer_timeout_seconds or 60,
        }
    for dest in config.transfer_destinations:
        if dest not in [v["phone_number"] for v in transfer_numbers.values()]:
            transfer_numbers[f"direct_transfer_{dest}"] = {
                "phone_number": dest,
                "timeout_seconds": 60,
            }

    # Build call transfer protocol
    bh_transfer = None
    emergency_transfer = None
    for rule in config.routing_rules:
        entry = {
            "condition": rule.condition,
            "destination": rule.destination,
            "timeout_seconds": rule.transfer_timeout_seconds or 60,
        }
        if "emergency" in rule.condition.lower():
            emergency_transfer = entry
        else:
            bh_transfer = entry

    call_transfer_protocol = {
        "business_hours": bh_transfer or {
            "condition": "general inquiry during business hours",
            "destination": config.transfer_destinations[0] if config.transfer_destinations else "main_office",
            "timeout_seconds": 60,
        },
        "emergency": emergency_transfer or {
            "condition": "emergency at any time",
            "destination": config.transfer_destinations[0] if config.transfer_destinations else "dispatch",
            "timeout_seconds": 60,
        },
    }

    # Fallback protocol
    fallback_protocol = {
        "action": config.fallback_logic or "Take caller's name and phone number. Confirm someone will follow up as soon as possible.",
        "collect": ["caller_name", "callback_number", "issue_description"],
        "promise": "Someone will follow up within 30 minutes.",
    }

    # Tool invocation placeholders
    tool_invocations = [
        {
            "name": "transfer_call",
            "description": "Transfer the current call to a destination phone number",
            "parameters": {
                "destination": {"type": "string", "description": "Phone number or SIP URI to transfer to"},
                "timeout_seconds": {"type": "integer", "description": "Seconds to wait before fallback"},
            },
        },
        {
            "name": "log_message",
            "description": "Log a message or note about the current call",
            "parameters": {
                "caller_name": {"type": "string"},
                "callback_number": {"type": "string"},
                "issue_type": {"type": "string", "enum": ["emergency", "non_emergency", "general"]},
                "details": {"type": "string"},
            },
        },
        {
            "name": "check_business_hours",
            "description": "Check if current time is within business hours",
            "parameters": {},
            "returns": {"type": "boolean"},
        },
    ]

    # Key variables
    key_variables = {
        "company_name": company_name,
        "timezone": config.business_hours.timezone,
        "business_hours": config.business_hours.schedule or {},
        "transfer_numbers": transfer_numbers,
    }

    # Integration constraints summary
    integration_notes = []
    for ic in config.integration_constraints:
        note = f"{ic.system}: {ic.rule}"
        if ic.restriction:
            note += f" ({ic.restriction})"
        integration_notes.append(note)

    spec = {
        "agent_name": f"Clara - {company_name}",
        "version": version,
        "voice_style": {
            "provider": "retell",
            "voice_id": "eleven_monolingual_v1",
            "tone": "professional, warm, calm",
            "language": "en-US",
        },
        "system_prompt": build_prompt(config),
        "key_variables": key_variables,
        "tool_invocation_placeholders": tool_invocations,
        "call_transfer_protocol": call_transfer_protocol,
        "fallback_protocol": fallback_protocol,
        "integration_constraints": integration_notes,
        "questions_or_unknowns": config.questions_or_unknowns,
        "retell_import_instructions": [
            "1. Log in to https://app.retell.ai/",
            "2. Go to Agents → Create New Agent",
            f"3. Set Agent Name to 'Clara - {company_name}'",
            "4. Select a voice from the Voice Library (recommended: professional female)",
            "5. Paste the 'system_prompt' field into the System Prompt text area",
            "6. Under Tools, add 'transfer_call' with the parameters from call_transfer_protocol",
            "7. Configure the transfer phone numbers from key_variables.transfer_numbers",
            "8. Save and test with a sample inbound call",
        ],
    }

    return spec


def save_agent_spec(config: AgentConfiguration, output_dir: str) -> str:
    """Build and save the agent spec JSON file. Returns the file path."""
    import os
    spec = build_agent_spec(config)
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{config.client_id}_{config.metadata.version_number}_agent_spec.json"
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2)
    return os.path.abspath(filepath)
