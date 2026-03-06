"""Tests for version manager functionality."""

import json
import pytest

from schemas.agent_schema import (
    AgentConfiguration,
    BusinessHours,
    ClientInfo,
    EmergencyDefinition,
    VersionMetadata,
)
from versioning.version_manager import save_version, load_version, list_versions


def _make_metadata(version: str = "v1", source: str = "test") -> VersionMetadata:
    return VersionMetadata(
        version_number=version,
        source=source,
        timestamp="2026-01-01T00:00:00Z",
    )


def _make_config(version: str = "v1", **kwargs) -> AgentConfiguration:
    defaults = {
        "client_id": "test_client",
        "metadata": _make_metadata(version=version),
    }
    defaults.update(kwargs)
    return AgentConfiguration(**defaults)


class TestVersioning:

    def test_save_and_load_roundtrip(self, tmp_path) -> None:
        """Saving and loading a config produces an identical object."""
        config = _make_config(
            client_info=ClientInfo(
                company_name="Acme Fire Protection",
                contact_name="John Doe",
                phone="5550001234",
                emails=["john@acme.com"],
            ),
            business_hours=BusinessHours(
                timezone="America/Denver",
                schedule={"monday": "8am-5pm", "tuesday": "8am-5pm"},
            ),
            emergency_definitions=[
                EmergencyDefinition(type="sprinkler_leak", description="Active leak", priority="high"),
            ],
            fallback_logic="Take a message and confirm callback.",
            questions_or_unknowns=["routing_rules: not confirmed"],
        )
        save_version(config, str(tmp_path))
        loaded = load_version("test_client", "v1", str(tmp_path))
        assert loaded.model_dump() == config.model_dump()

    def test_save_creates_directory(self, tmp_path) -> None:
        """save_version creates the output directory if it does not exist."""
        nested = tmp_path / "deep" / "nested"
        config = _make_config()
        path = save_version(config, str(nested))
        assert nested.exists()
        assert (nested / "test_client_v1.json").exists()

    def test_load_missing_version_raises(self, tmp_path) -> None:
        """Loading a version that does not exist raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_version("nonexistent_client", "v1", str(tmp_path))

    def test_list_versions_ordering(self, tmp_path) -> None:
        """list_versions returns sorted version strings."""
        save_version(_make_config(version="v1"), str(tmp_path))
        save_version(_make_config(version="v2"), str(tmp_path))

        versions = list_versions("test_client", str(tmp_path))
        assert versions == ["v1", "v2"]

    def test_list_versions_empty_directory(self, tmp_path) -> None:
        """list_versions returns empty list for a directory with no matching files."""
        versions = list_versions("test_client", str(tmp_path))
        assert versions == []

    def test_list_versions_nonexistent_directory(self) -> None:
        """list_versions returns empty list when directory does not exist."""
        versions = list_versions("test_client", "/nonexistent/path")
        assert versions == []

    def test_save_produces_valid_json(self, tmp_path) -> None:
        """Saved file is valid JSON that can be parsed independently."""
        config = _make_config(
            client_info=ClientInfo(company_name="Test Corp"),
        )
        save_version(config, str(tmp_path))
        file_path = tmp_path / "test_client_v1.json"
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["client_id"] == "test_client"
        assert data["client_info"]["company_name"] == "Test Corp"
        assert data["metadata"]["version_number"] == "v1"

    def test_multiple_versions_coexist(self, tmp_path) -> None:
        """v1 and v2 files coexist and load independently."""
        v1 = _make_config(
            version="v1",
            client_info=ClientInfo(company_name="Demo Corp"),
        )
        v2 = _make_config(
            version="v2",
            client_info=ClientInfo(company_name="Onboarded Corp"),
        )
        save_version(v1, str(tmp_path))
        save_version(v2, str(tmp_path))

        loaded_v1 = load_version("test_client", "v1", str(tmp_path))
        loaded_v2 = load_version("test_client", "v2", str(tmp_path))

        assert loaded_v1.client_info.company_name == "Demo Corp"
        assert loaded_v2.client_info.company_name == "Onboarded Corp"
