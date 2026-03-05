"""Saves and loads versioned AgentConfiguration files as JSON."""

import os
from pathlib import Path

from schemas.agent_schema import AgentConfiguration


def save_version(config: AgentConfiguration, output_dir: str) -> str:
    """Serialize an AgentConfiguration to a versioned JSON file and return the absolute path."""
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{config.client_id}_{config.metadata.version_number}.json"
    file_path = os.path.join(output_dir, filename)
    json_str = config.model_dump_json(indent=2)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(json_str)
    return os.path.abspath(file_path)


def load_version(client_id: str, version: str, input_dir: str) -> AgentConfiguration:
    """Deserialize an AgentConfiguration from a versioned JSON file."""
    filename = f"{client_id}_{version}.json"
    file_path = os.path.join(input_dir, filename)
    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"No version {version} found for client {client_id} in {input_dir}"
        )
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
    return AgentConfiguration.model_validate_json(text)


def list_versions(client_id: str, directory: str) -> list[str]:
    """Return a sorted list of version strings found for a client, e.g. ['v1', 'v2']."""
    versions: list[str] = []
    if not os.path.isdir(directory):
        return versions
    prefix = f"{client_id}_"
    for entry in os.listdir(directory):
        if entry.startswith(prefix) and entry.endswith(".json"):
            version = entry[len(prefix):-len(".json")]
            versions.append(version)
    return sorted(versions)
