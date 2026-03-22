"""Configuration and profile loading."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .analytics.verdict import VerdictThresholds, Direction


@dataclass
class ProbeConfig:
    """Configuration for a single probe type."""

    enabled: bool = True
    timeout_ms: int = 5000
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScheduleConfig:
    """Schedule settings for repeated runs."""

    interval_minutes: int = 5
    retry_on_failure: bool = True
    max_retries: int = 2


@dataclass
class Profile:
    """Loaded and merged profile configuration."""

    name: str = "default"
    probes: dict[str, ProbeConfig] = field(default_factory=dict)
    thresholds: dict[str, VerdictThresholds] = field(default_factory=dict)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)

    def is_probe_enabled(self, probe_name: str) -> bool:
        """Check if a probe is enabled in this profile."""
        if probe_name not in self.probes:
            return True  # enabled by default if not specified
        return self.probes[probe_name].enabled

    def get_probe_timeout(self, probe_name: str) -> int:
        """Get timeout for a probe, falling back to probe's own default."""
        if probe_name in self.probes:
            return self.probes[probe_name].timeout_ms
        return 5000


def load_profile(path: str | Path) -> Profile:
    """Load a profile from a JSON file.

    Args:
        path: Path to profile JSON.

    Returns:
        Populated Profile object.
    """
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    probes = {}
    for name, cfg in raw.get("Probes", {}).items():
        probes[name] = ProbeConfig(
            enabled=cfg.get("enabled", True),
            timeout_ms=cfg.get("timeout_ms", 5000),
            extra={k: v for k, v in cfg.items() if k not in ("enabled", "timeout_ms")},
        )

    thresholds = {}
    for name, cfg in raw.get("Thresholds", {}).items():
        dir_str = cfg.get("direction", "lower_is_better")
        direction = Direction.HIGHER_IS_BETTER if dir_str == "higher_is_better" else Direction.LOWER_IS_BETTER
        thresholds[name] = VerdictThresholds(
            good=cfg["good"],
            fair=cfg["fair"],
            poor=cfg["poor"],
            direction=direction,
        )

    schedule = ScheduleConfig()
    if "Schedule" in raw:
        s = raw["Schedule"]
        schedule = ScheduleConfig(
            interval_minutes=s.get("interval_minutes", 5),
            retry_on_failure=s.get("retry_on_failure", True),
            max_retries=s.get("max_retries", 2),
        )

    return Profile(
        name=raw.get("ProfileName", path.stem),
        probes=probes,
        thresholds=thresholds,
        schedule=schedule,
    )


def merge_cli_overrides(profile: Profile, **overrides) -> Profile:
    """Apply CLI argument overrides on top of a profile copy.

    Returns a new Profile; the original is not mutated.

    Supported overrides:
        interval: int — override schedule interval_minutes
        probes: list[str] — restrict to only these probe names
    """
    merged = copy.deepcopy(profile)

    if "interval" in overrides and overrides["interval"] is not None:
        merged.schedule.interval_minutes = overrides["interval"]

    if "probes" in overrides and overrides["probes"] is not None:
        enabled_set = set(overrides["probes"])
        for name in list(merged.probes.keys()):
            merged.probes[name].enabled = name in enabled_set

    return merged
