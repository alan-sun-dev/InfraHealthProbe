"""Tests for analytics: scoring, hints, summary."""

import pytest

from infra.probes.base import ProbeResult, ProbeStatus
from infra.analytics.verdict import Verdict, get_verdict, VerdictThresholds, Direction
from infra.analytics.scoring import score_target, TargetScore, _score_to_verdict
from infra.analytics.hints import get_hints, Hint
from infra.analytics.summary import generate_summary
from infra.runner import RunResult, TargetResult
from infra.inventory.core import Target


# -- Scoring tests --

class TestScoring:
    def test_all_ok_high_score(self):
        results = [
            ProbeResult(probe_name="ping", target_id="T1", status=ProbeStatus.OK,
                        latency_ms=3.0, metrics={"latency_avg_ms": 3.0, "packet_loss_pct": 0.0}),
            ProbeResult(probe_name="dns", target_id="T1", status=ProbeStatus.OK, latency_ms=50.0),
            ProbeResult(probe_name="tcp", target_id="T1", status=ProbeStatus.OK, latency_ms=40.0),
            ProbeResult(probe_name="http", target_id="T1", status=ProbeStatus.OK, latency_ms=200.0),
        ]
        ts = score_target("T1", results)
        assert ts.health_score >= 85
        assert ts.overall_verdict == Verdict.GOOD

    def test_all_failed_zero_score(self):
        results = [
            ProbeResult(probe_name="ping", target_id="T1", status=ProbeStatus.FAILED),
            ProbeResult(probe_name="dns", target_id="T1", status=ProbeStatus.TIMEOUT),
        ]
        ts = score_target("T1", results)
        assert ts.health_score == 0
        assert ts.overall_verdict == Verdict.SEVERE

    def test_mixed_results(self):
        results = [
            ProbeResult(probe_name="ping", target_id="T1", status=ProbeStatus.OK,
                        latency_ms=3.0, metrics={"latency_avg_ms": 3.0, "packet_loss_pct": 0.0}),
            ProbeResult(probe_name="tcp", target_id="T1", status=ProbeStatus.FAILED),
        ]
        ts = score_target("T1", results)
        assert 0 < ts.health_score < 85

    def test_packet_loss_lowers_score(self):
        good = [
            ProbeResult(probe_name="ping", target_id="T1", status=ProbeStatus.OK,
                        latency_ms=3.0, metrics={"latency_avg_ms": 3.0, "packet_loss_pct": 0.0}),
        ]
        lossy = [
            ProbeResult(probe_name="ping", target_id="T1", status=ProbeStatus.OK,
                        latency_ms=3.0, metrics={"latency_avg_ms": 3.0, "packet_loss_pct": 5.0}),
        ]
        good_score = score_target("T1", good).health_score
        lossy_score = score_target("T1", lossy).health_score
        assert lossy_score < good_score

    def test_empty_results(self):
        ts = score_target("T1", [])
        assert ts.health_score == 0
        assert ts.overall_verdict == Verdict.SEVERE


class TestScoreToVerdict:
    def test_thresholds(self):
        assert _score_to_verdict(100) == Verdict.GOOD
        assert _score_to_verdict(85) == Verdict.GOOD
        assert _score_to_verdict(84) == Verdict.FAIR
        assert _score_to_verdict(70) == Verdict.FAIR
        assert _score_to_verdict(69) == Verdict.POOR
        assert _score_to_verdict(40) == Verdict.POOR
        assert _score_to_verdict(39) == Verdict.SEVERE
        assert _score_to_verdict(0) == Verdict.SEVERE


# -- Hints tests --

class TestHints:
    def test_all_failed_host_down(self):
        results = [
            ProbeResult(probe_name="ping", target_id="T1", status=ProbeStatus.FAILED),
            ProbeResult(probe_name="dns", target_id="T1", status=ProbeStatus.FAILED),
        ]
        hints = get_hints("T1", results)
        assert len(hints) == 1
        assert "down" in hints[0].cause.lower() or "unreachable" in hints[0].cause.lower()
        assert hints[0].confidence == "high"

    def test_icmp_blocked(self):
        results = [
            ProbeResult(probe_name="ping", target_id="T1", status=ProbeStatus.FAILED),
            ProbeResult(probe_name="dns", target_id="T1", status=ProbeStatus.OK, latency_ms=50.0),
        ]
        hints = get_hints("T1", results)
        causes = [h.cause for h in hints]
        assert any("ICMP" in c for c in causes)

    def test_dns_failure(self):
        results = [
            ProbeResult(probe_name="ping", target_id="T1", status=ProbeStatus.OK, latency_ms=5.0),
            ProbeResult(probe_name="dns", target_id="T1", status=ProbeStatus.FAILED),
        ]
        hints = get_hints("T1", results)
        causes = [h.cause for h in hints]
        assert any("DNS" in c for c in causes)

    def test_app_layer_issue(self):
        results = [
            ProbeResult(probe_name="tcp", target_id="T1", status=ProbeStatus.OK, latency_ms=20.0),
            ProbeResult(probe_name="http", target_id="T1", status=ProbeStatus.FAILED,
                        metrics={"urls": [{"url": "http://x.com", "reachable": False, "error": "500"}]}),
        ]
        hints = get_hints("T1", results)
        causes = [h.cause for h in hints]
        assert any("application" in c.lower() or "web service" in c.lower() for c in causes)

    def test_tcp_port_closed(self):
        results = [
            ProbeResult(probe_name="tcp", target_id="T1", status=ProbeStatus.FAILED,
                        metrics={"ports": [{"port": 443, "open": False, "error": "refused"}]}),
        ]
        hints = get_hints("T1", results)
        causes = [h.cause for h in hints]
        assert any("port" in c.lower() for c in causes)

    def test_no_hints_when_all_ok(self):
        results = [
            ProbeResult(probe_name="ping", target_id="T1", status=ProbeStatus.OK,
                        latency_ms=3.0, metrics={"latency_avg_ms": 3.0, "packet_loss_pct": 0.0}),
            ProbeResult(probe_name="dns", target_id="T1", status=ProbeStatus.OK, latency_ms=50.0),
            ProbeResult(probe_name="tcp", target_id="T1", status=ProbeStatus.OK, latency_ms=40.0),
            ProbeResult(probe_name="http", target_id="T1", status=ProbeStatus.OK, latency_ms=200.0),
        ]
        hints = get_hints("T1", results)
        assert len(hints) == 0


# -- Summary tests --

class TestSummary:
    def _make_run_result(self):
        return RunResult(
            run_id="TEST-001",
            profile_name="test",
            start_time_utc="2026-03-23T10:00:00Z",
            end_time_utc="2026-03-23T10:00:05Z",
            elapsed_ms=5000.0,
            target_results=[
                TargetResult(
                    target=Target(target_id="T1", fqdn="good.com", location="Taiwan",
                                  function="Cache", probe_profile="default"),
                    probe_results=[
                        ProbeResult(probe_name="ping", target_id="T1", status=ProbeStatus.OK,
                                    latency_ms=3.0, metrics={"latency_avg_ms": 3.0, "packet_loss_pct": 0.0}),
                    ],
                ),
                TargetResult(
                    target=Target(target_id="T2", fqdn="bad.com", location="Singapore",
                                  function="EDI", probe_profile="default"),
                    probe_results=[
                        ProbeResult(probe_name="ping", target_id="T2", status=ProbeStatus.FAILED),
                        ProbeResult(probe_name="dns", target_id="T2", status=ProbeStatus.FAILED),
                    ],
                ),
            ],
        )

    def test_summary_contains_sections(self):
        text = generate_summary(self._make_run_result())
        assert "EXECUTIVE SUMMARY" in text
        assert "TECHNICAL DETAIL" in text
        assert "TEST-001" in text

    def test_summary_contains_target_ids(self):
        text = generate_summary(self._make_run_result())
        assert "T1" in text
        assert "T2" in text

    def test_summary_shows_problem_targets(self):
        text = generate_summary(self._make_run_result())
        assert "needing attention" in text.lower() or "SEVERE" in text

    def test_summary_shows_hints_for_failures(self):
        text = generate_summary(self._make_run_result())
        # T2 has all probes failed → should show "down" hint
        assert "down" in text.lower() or "unreachable" in text.lower()
