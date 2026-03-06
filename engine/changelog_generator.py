"""Generates human-readable Markdown changelog and machine-readable diff JSON from v1 → v2 transitions."""

import json
import os
from datetime import datetime
from typing import Any

from schemas.agent_schema import AgentConfiguration, ChangeLogEntry


def _format_value(val: Any) -> str:
    """Format a value for display in Markdown."""
    if val is None:
        return "`null`"
    if isinstance(val, list):
        if not val:
            return "`[]`"
        if all(isinstance(v, str) for v in val):
            return ", ".join(f"`{v}`" for v in val)
        return f"```json\n{json.dumps(val, indent=2)}\n```"
    if isinstance(val, dict):
        return f"```json\n{json.dumps(val, indent=2)}\n```"
    return f"`{val}`"


def generate_changelog_md(
    v1: AgentConfiguration,
    v2: AgentConfiguration,
    change_log: list[ChangeLogEntry],
) -> str:
    """Generate a human-readable Markdown changelog from v1 → v2."""
    lines: list[str] = []

    lines.append(f"# Changelog: {v1.client_id}")
    lines.append(f"**v1 → v2** | Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")

    # Summary counts
    added = [e for e in change_log if e.reason == "new_entry"]
    changed = [e for e in change_log if e.reason in ("field_update", "onboarding_override")]
    overrides = [e for e in change_log if e.reason == "onboarding_override"]

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **{len(change_log)}** total changes")
    lines.append(f"- **{len(added)}** fields added")
    lines.append(f"- **{len(changed)}** fields changed")
    lines.append(f"- **{len(overrides)}** conflict resolutions (onboarding wins)")
    lines.append("")

    # Conflict resolutions
    if overrides:
        lines.append("## Conflict Resolutions")
        lines.append("")
        for entry in overrides:
            lines.append(f"### `{entry.field}`")
            lines.append(f"- **Previous (v1):** {_format_value(entry.previous_value)}")
            lines.append(f"- **New (v2):** {_format_value(entry.new_value)}")
            lines.append(f"- **Resolution:** Onboarding data takes precedence")
            lines.append("")

    # All changes grouped by category
    lines.append("## All Changes")
    lines.append("")

    # Group by field prefix
    groups: dict[str, list[ChangeLogEntry]] = {}
    for entry in change_log:
        prefix = entry.field.split(".")[0]
        groups.setdefault(prefix, []).append(entry)

    for group_name, entries in groups.items():
        lines.append(f"### {group_name}")
        lines.append("")
        lines.append("| Field | Previous | New | Reason |")
        lines.append("|-------|----------|-----|--------|")
        for entry in entries:
            prev = str(entry.previous_value)[:60] if entry.previous_value is not None else "—"
            new = str(entry.new_value)[:60]
            lines.append(f"| `{entry.field}` | {prev} | {new} | {entry.reason} |")
        lines.append("")

    # Remaining unknowns
    if v2.questions_or_unknowns:
        lines.append("## Remaining Open Questions")
        lines.append("")
        for q in v2.questions_or_unknowns:
            lines.append(f"- {q}")
        lines.append("")
    else:
        lines.append("## Open Questions")
        lines.append("")
        lines.append("All questions resolved. Agent is ready for deployment.")
        lines.append("")

    return "\n".join(lines)


def generate_diff_json(
    v1: AgentConfiguration,
    v2: AgentConfiguration,
    change_log: list[ChangeLogEntry],
) -> dict:
    """Generate a machine-readable diff dictionary."""
    v1_dict = json.loads(v1.model_dump_json())
    v2_dict = json.loads(v2.model_dump_json())

    diff = {
        "client_id": v1.client_id,
        "from_version": v1.metadata.version_number,
        "to_version": v2.metadata.version_number,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "changes": [
            {
                "field": e.field,
                "previous_value": e.previous_value,
                "new_value": e.new_value,
                "source": e.source,
                "reason": e.reason,
                "timestamp": e.timestamp,
            }
            for e in change_log
        ],
        "summary": {
            "total_changes": len(change_log),
            "fields_added": len([e for e in change_log if e.reason == "new_entry"]),
            "fields_changed": len([e for e in change_log if e.reason in ("field_update", "onboarding_override")]),
            "conflicts_resolved": len([e for e in change_log if e.reason == "onboarding_override"]),
            "unknowns_remaining": len(v2.questions_or_unknowns),
        },
    }
    return diff


def save_changelog(
    v1: AgentConfiguration,
    v2: AgentConfiguration,
    change_log: list[ChangeLogEntry],
    output_dir: str,
) -> tuple[str, str]:
    """Save both changelog.md and diff.json. Returns (md_path, json_path)."""
    os.makedirs(output_dir, exist_ok=True)

    md_content = generate_changelog_md(v1, v2, change_log)
    md_path = os.path.join(output_dir, f"{v1.client_id}_changelog.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    diff_content = generate_diff_json(v1, v2, change_log)
    json_path = os.path.join(output_dir, f"{v1.client_id}_diff.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(diff_content, f, indent=2)

    return os.path.abspath(md_path), os.path.abspath(json_path)
