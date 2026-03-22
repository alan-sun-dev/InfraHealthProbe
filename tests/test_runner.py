"""Tests for probe runner."""

import pytest

from infra.config import Profile, ProbeConfig
from infra.inventory.core import Target
from infra.runner import (
    TargetResult,
    RunResult,
    _resolve_probes_for_target,
    run_probes_for_target,
    run_all,
)
from infra.probes.base import ProbeResult, ProbeStatus


class TestResolveProbes:
    def test_target_with_all_fields(self):
        target = Target(
            target_id="T1", fqdn="x.com", ip_address="1.2.3.4",
            ports=[80], urls=["http://x.com"], probe_profile="default",
        )
        profile = Profile(name="default")
        probes = _resolve_probes_for_target(target, profile)
        assert "ping" in probes
        assert "dns" in probes
        assert "tcp" in probes
        assert "http" in probes

    def test_target_ip_only(self):
        target = Target(target_id="T2", ip_address="1.2.3.4", probe_profile="default")
        profile = Profile(name="default")
        probes = _resolve_probes_for_target(target, profile)
        assert "ping" in probes
        assert "dns" not in probes  # no FQDN
        assert "tcp" not in probes  # no ports
        assert "http" not in probes  # no URLs

    def test_profile_disables_probe(self):
        target = Target(
            target_id="T3", fqdn="x.com", ports=[80],
            urls=["http://x.com"], probe_profile="default",
        )
        profile = Profile(
            name="restricted",
            probes={"tcp": ProbeConfig(enabled=False), "http": ProbeConfig(enabled=False)},
        )
        probes = _resolve_probes_for_target(target, profile)
        assert "ping" in probes
        assert "dns" in probes
        assert "tcp" not in probes
        assert "http" not in probes

    def test_target_no_address(self):
        target = Target(target_id="T4", probe_profile="default")
        profile = Profile(name="default")
        probes = _resolve_probes_for_target(target, profile)
        assert probes == []


class TestTargetResult:
    def test_worst_status_ok(self):
        tr = TargetResult(
            target=Target(target_id="T1", fqdn="x.com", probe_profile="d"),
            probe_results=[
                ProbeResult(probe_name="ping", target_id="T1", status=ProbeStatus.OK),
                ProbeResult(probe_name="dns", target_id="T1", status=ProbeStatus.OK),
            ],
        )
        assert tr.worst_status == ProbeStatus.OK
        assert tr.ok_count == 2
        assert tr.fail_count == 0

    def test_worst_status_failed(self):
        tr = TargetResult(
            target=Target(target_id="T1", fqdn="x.com", probe_profile="d"),
            probe_results=[
                ProbeResult(probe_name="ping", target_id="T1", status=ProbeStatus.OK),
                ProbeResult(probe_name="tcp", target_id="T1", status=ProbeStatus.FAILED),
            ],
        )
        assert tr.worst_status == ProbeStatus.FAILED
        assert tr.ok_count == 1
        assert tr.fail_count == 1

    def test_empty_results(self):
        tr = TargetResult(
            target=Target(target_id="T1", fqdn="x.com", probe_profile="d"),
        )
        assert tr.worst_status == ProbeStatus.SKIPPED


class TestRunResult:
    def test_counts(self):
        rr = RunResult(
            run_id="test",
            target_results=[
                TargetResult(
                    target=Target(target_id="T1", fqdn="a.com", probe_profile="d"),
                    probe_results=[
                        ProbeResult(probe_name="ping", target_id="T1", status=ProbeStatus.OK),
                    ],
                ),
                TargetResult(
                    target=Target(target_id="T2", fqdn="b.com", probe_profile="d"),
                    probe_results=[
                        ProbeResult(probe_name="ping", target_id="T2", status=ProbeStatus.OK),
                        ProbeResult(probe_name="dns", target_id="T2", status=ProbeStatus.OK),
                    ],
                ),
            ],
        )
        assert rr.target_count == 2
        assert rr.total_probes == 3
