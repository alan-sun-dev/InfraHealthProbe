"""Probe contract — all probes implement this interface."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProbeStatus(str, Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"


@dataclass
class ProbeResult:
    """Canonical result returned by every probe."""

    probe_name: str
    target_id: str
    status: ProbeStatus
    latency_ms: float | None = None
    detail: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    timestamp_utc: str = ""
    error: str | None = None

    def __post_init__(self):
        if not self.timestamp_utc:
            self.timestamp_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class BaseProbe(ABC):
    """Abstract base class for all probes."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for this probe type (e.g. 'ping', 'dns', 'tcp')."""

    @property
    def timeout_ms(self) -> int:
        """Default timeout in milliseconds."""
        return 5000

    @property
    def expected_fields(self) -> list[str]:
        """Metric field names this probe produces."""
        return []

    @abstractmethod
    def probe(self, target: dict) -> ProbeResult:
        """Execute the probe against a target and return a result.

        Args:
            target: Canonical target dict with keys like
                     TargetId, Hostname, FQDN, IPAddress, Ports, Urls, etc.

        Returns:
            ProbeResult with status, latency, and optional metrics.
        """

    def probe_safe(self, target: dict) -> ProbeResult:
        """Execute probe with error handling — never raises."""
        try:
            return self.probe(target)
        except Exception as exc:
            return ProbeResult(
                probe_name=self.name,
                target_id=target.get("TargetId", "unknown"),
                status=ProbeStatus.ERROR,
                error=str(exc),
            )
