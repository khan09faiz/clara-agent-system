"""Pydantic v2 schema definitions for Clara agent configuration and versioning."""

from pydantic import BaseModel
from typing import Any


class ChangeLogEntry(BaseModel):
    field: str
    previous_value: Any
    new_value: Any
    source: str  # "demo" | "onboarding" | "form" | "chat_log"
    timestamp: str  # ISO 8601
    reason: str


class VersionMetadata(BaseModel):
    version_number: str  # "v1" | "v2"
    timestamp: str  # ISO 8601
    source: str  # primary source that created this version
    change_log: list[ChangeLogEntry] = []


class ClientInfo(BaseModel):
    company_name: str | None = None
    contact_name: str | None = None
    phone: str | None = None
    emails: list[str] = []


class BusinessHours(BaseModel):
    timezone: str | None = None
    schedule: dict[str, str] = {}
    # keys are lowercase day names e.g. "monday"
    # values are strings e.g. "8am-5pm" or "closed"


class EmergencyDefinition(BaseModel):
    type: str  # snake_case e.g. "sprinkler_leak"
    description: str  # human-readable description
    priority: str  # "high" | "medium" | "low"


class RoutingRule(BaseModel):
    condition: str  # plain language e.g. "after hours emergency"
    destination: str  # phone number or label e.g. "dispatch"
    transfer_timeout_seconds: int | None = None


class IntegrationConstraint(BaseModel):
    system: str  # e.g. "ServiceTrade", "ServiceTitan"
    rule: str  # what Clara must do or avoid
    restriction: str | None = None  # hard constraint if any


class AgentConfiguration(BaseModel):
    client_id: str
    client_info: ClientInfo = ClientInfo()
    business_hours: BusinessHours = BusinessHours()
    emergency_definitions: list[EmergencyDefinition] = []
    routing_rules: list[RoutingRule] = []
    transfer_destinations: list[str] = []
    integration_constraints: list[IntegrationConstraint] = []
    fallback_logic: str | None = None
    questions_or_unknowns: list[str] = []
    metadata: VersionMetadata
