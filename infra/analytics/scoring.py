"""Health scoring — weighted score per target and per run."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..probes.base import ProbeResult, ProbeStatus
from .verdict import (
    Verdict, VerdictThresholds,
    get_verdict, verdict_to_score, DEFAULT_THRESHOLDS,
)


# Default weights — how much each probe contributes to overall score
DEFAULT_WEIGHTS: dict[str, int] = {
    "ping": 30,
    "dns": 20,
    "tcp": 25,
    "http": 25,
}


@dataclass
class MetricScore:
    """Score for a single metric within a probe result."""

    metric_name: str
    value: float | None
    verdict: Verdict
    score: int


@dataclass
class TargetScore:
    """Aggregated health score for a single target."""

    target_id: str
    health_score: int
    overall_verdict: Verdict
    metric_scores: list[MetricScore] = field(default_factory=list)


def _extract_metric(probe_result: ProbeResult) -> tuple[str, float | None]:
    """Extract the primary metric from a probe result for scoring."""
    name = probe_result.probe_name
    if name == "ping":
        return "ping_latency_ms", probe_result.metrics.get("latency_avg_ms")
    elif name == "dns":
        return "dns_latency_ms", probe_result.latency_ms
    elif name == "tcp":
        return "tcp_latency_ms", probe_result.latency_ms
    elif name == "http":
        return "http_latency_ms", probe_result.latency_ms
    return f"{name}_latency_ms", probe_result.latency_ms


def score_target(
    target_id: str,
    probe_results: list[ProbeResult],
    thresholds: dict[str, VerdictThresholds] | None = None,
    weights: dict[str, int] | None = None,
) -> TargetScore:
    """Calculate weighted health score for a target.

    Args:
        target_id: Target identifier.
        probe_results: List of probe results for this target.
        thresholds: Metric thresholds (defaults to DEFAULT_THRESHOLDS).
        weights: Probe weights (defaults to DEFAULT_WEIGHTS).

    Returns:
        TargetScore with overall health score and per-metric breakdown.
    """
    thresholds = thresholds or DEFAULT_THRESHOLDS
    weights = weights or DEFAULT_WEIGHTS

    metric_scores: list[MetricScore] = []
    weighted_total = 0.0
    weight_sum = 0.0

    for pr in probe_results:
        # Failed/error probes get score 0 regardless of metrics
        if pr.status in (ProbeStatus.FAILED, ProbeStatus.ERROR, ProbeStatus.TIMEOUT):
            verdict = Verdict.SEVERE
            score = 0
            metric_name = f"{pr.probe_name}_status"
            value = None
        else:
            metric_name, value = _extract_metric(pr)
            if metric_name in thresholds:
                verdict = get_verdict(value, thresholds[metric_name])
            else:
                verdict = Verdict.GOOD if pr.status == ProbeStatus.OK else Verdict.UNKNOWN
            score = verdict_to_score(verdict)

        # Also check packet loss for ping
        if pr.probe_name == "ping" and pr.status == ProbeStatus.OK:
            loss = pr.metrics.get("packet_loss_pct")
            if loss is not None and "ping_loss_pct" in thresholds:
                loss_verdict = get_verdict(loss, thresholds["ping_loss_pct"])
                loss_score = verdict_to_score(loss_verdict)
                if loss_score < score:
                    score = loss_score
                    verdict = loss_verdict
                metric_scores.append(MetricScore("ping_loss_pct", loss, loss_verdict, loss_score))

        metric_scores.append(MetricScore(metric_name, value, verdict, score))

        weight = weights.get(pr.probe_name, 10)
        weighted_total += score * weight
        weight_sum += weight

    if weight_sum > 0:
        health_score = round(weighted_total / weight_sum)
    else:
        health_score = 0

    overall_verdict = _score_to_verdict(health_score)

    return TargetScore(
        target_id=target_id,
        health_score=health_score,
        overall_verdict=overall_verdict,
        metric_scores=metric_scores,
    )


def _score_to_verdict(score: int) -> Verdict:
    """Convert numeric health score to verdict."""
    if score >= 85:
        return Verdict.GOOD
    if score >= 70:
        return Verdict.FAIR
    if score >= 40:
        return Verdict.POOR
    return Verdict.SEVERE
