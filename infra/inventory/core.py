"""Inventory core — normalize, validate, deduplicate, merge."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Target:
    """Canonical target object — all providers normalize to this."""

    target_id: str
    type: str = ""
    location: str = ""
    function: str = ""
    hostname: str = ""
    fqdn: str = ""
    ip_address: str = ""
    os: str = ""
    urls: list[str] = field(default_factory=list)
    ports: list[int] = field(default_factory=list)
    probe_profile: str = "default"
    enabled: bool = True
    priority: str = "Normal"
    owner_group: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "TargetId": self.target_id,
            "Type": self.type,
            "Location": self.location,
            "Function": self.function,
            "Hostname": self.hostname,
            "FQDN": self.fqdn,
            "IPAddress": self.ip_address,
            "OS": self.os,
            "Urls": self.urls,
            "Ports": self.ports,
            "ProbeProfile": self.probe_profile,
            "Enabled": self.enabled,
            "Priority": self.priority,
            "OwnerGroup": self.owner_group,
            "Notes": self.notes,
        }


def validate_target(target: Target) -> list[str]:
    """Validate a target and return list of error messages (empty = valid)."""
    errors = []
    if not target.target_id:
        errors.append("TargetId is required")
    if not target.fqdn and not target.ip_address:
        errors.append("At least one of FQDN or IPAddress is required")
    if not target.probe_profile:
        errors.append("ProbeProfile is required")
    for port in target.ports:
        if not isinstance(port, int) or port < 1 or port > 65535:
            errors.append(f"Invalid port: {port}")
    return errors


def normalize_target(raw: dict) -> Target:
    """Convert a raw dict (from any provider) into a canonical Target."""
    ports = raw.get("Ports", [])
    if isinstance(ports, str):
        ports = [int(p.strip()) for p in ports.split(";") if p.strip().isdigit()]

    urls = raw.get("Urls", [])
    if isinstance(urls, str):
        urls = [u.strip() for u in urls.split(";") if u.strip()]

    enabled = raw.get("Enabled", True)
    if isinstance(enabled, str):
        enabled = enabled.lower() in ("true", "yes", "1")

    return Target(
        target_id=str(raw.get("TargetId", raw.get("Title", ""))).strip(),
        type=str(raw.get("Type", "")).strip(),
        location=str(raw.get("Location", "")).strip(),
        function=str(raw.get("Function", "")).strip(),
        hostname=str(raw.get("Hostname", "")).strip(),
        fqdn=str(raw.get("FQDN", "")).strip(),
        ip_address=str(raw.get("IPAddress", "")).strip(),
        os=str(raw.get("OS", "")).strip(),
        urls=urls,
        ports=ports,
        probe_profile=str(raw.get("ProbeProfile", "default")).strip(),
        enabled=enabled,
        priority=str(raw.get("Priority", "Normal")).strip(),
        owner_group=str(raw.get("OwnerGroup", "")).strip(),
        notes=str(raw.get("Notes", "")).strip(),
    )


def deduplicate_targets(targets: list[Target]) -> list[Target]:
    """Remove duplicate targets by TargetId, keeping the last occurrence."""
    seen: dict[str, Target] = {}
    for t in targets:
        seen[t.target_id] = t
    return list(seen.values())


def merge_inventories(primary: list[Target], overrides: list[Target]) -> list[Target]:
    """Merge primary inventory with local overrides.

    Override targets with matching TargetId replace primary entries.
    Override-only targets are appended.
    """
    merged: dict[str, Target] = {t.target_id: t for t in primary}
    for override in overrides:
        merged[override.target_id] = override
    return list(merged.values())


def filter_targets(
    targets: list[Target],
    *,
    location: str | None = None,
    function: str | None = None,
    enabled_only: bool = True,
) -> list[Target]:
    """Filter targets by criteria."""
    result = targets
    if enabled_only:
        result = [t for t in result if t.enabled]
    if location:
        result = [t for t in result if location.lower() in t.location.lower()]
    if function:
        result = [t for t in result if function.lower() in t.function.lower()]
    return result
