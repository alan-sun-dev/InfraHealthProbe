"""Verdict and scoring logic for probe results."""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass


class Verdict(str, Enum):
    GOOD = "GOOD"
    FAIR = "FAIR"
    POOR = "POOR"
    SEVERE = "SEVERE"
    UNKNOWN = "UNKNOWN"


class Direction(str, Enum):
    LOWER_IS_BETTER = "lower_is_better"
    HIGHER_IS_BETTER = "higher_is_better"


@dataclass
class VerdictThresholds:
    """Thresholds for a single metric."""
    good: float
    fair: float
    poor: float
    direction: Direction = Direction.LOWER_IS_BETTER


def get_verdict(value: float | None, thresholds: VerdictThresholds) -> Verdict:
    """Evaluate a single metric value against thresholds."""
    if value is None:
        return Verdict.UNKNOWN

    if thresholds.direction == Direction.LOWER_IS_BETTER:
        if value <= thresholds.good:
            return Verdict.GOOD
        if value <= thresholds.fair:
            return Verdict.FAIR
        if value <= thresholds.poor:
            return Verdict.POOR
        return Verdict.SEVERE
    else:
        if value >= thresholds.good:
            return Verdict.GOOD
        if value >= thresholds.fair:
            return Verdict.FAIR
        if value >= thresholds.poor:
            return Verdict.POOR
        return Verdict.SEVERE


def verdict_to_score(verdict: Verdict) -> int:
    """Convert verdict to numeric score (0-100)."""
    return {
        Verdict.GOOD: 100,
        Verdict.FAIR: 75,
        Verdict.POOR: 40,
        Verdict.SEVERE: 0,
        Verdict.UNKNOWN: 50,
    }[verdict]


# Default thresholds for common probe metrics
DEFAULT_THRESHOLDS: dict[str, VerdictThresholds] = {
    "ping_latency_ms": VerdictThresholds(good=5, fair=15, poor=30),
    "ping_loss_pct": VerdictThresholds(good=0, fair=1, poor=3),
    "dns_latency_ms": VerdictThresholds(good=150, fair=300, poor=500),
    "tcp_latency_ms": VerdictThresholds(good=150, fair=300, poor=500),
    "http_latency_ms": VerdictThresholds(good=300, fair=700, poor=1000),
}
