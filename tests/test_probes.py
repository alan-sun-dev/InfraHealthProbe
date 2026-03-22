"""Tests for probe registry and probe contracts."""

import pytest

from infra.probes import PROBE_REGISTRY, get_probe, list_probes
from infra.probes.base import BaseProbe, ProbeResult, ProbeStatus


class TestProbeRegistry:
    def test_all_probes_registered(self):
        expected = {"ping", "dns", "tcp", "http", "wifi"}
        assert set(PROBE_REGISTRY.keys()) == expected

    def test_get_probe_returns_instance(self):
        probe = get_probe("ping")
        assert isinstance(probe, BaseProbe)
        assert probe.name == "ping"

    def test_get_unknown_probe_raises(self):
        with pytest.raises(KeyError, match="Unknown probe"):
            get_probe("nonexistent")

    def test_list_probes(self):
        names = list_probes()
        assert "ping" in names
        assert "dns" in names
        assert "tcp" in names
        assert "http" in names

    def test_all_probes_implement_contract(self):
        for name, cls in PROBE_REGISTRY.items():
            probe = cls()
            assert isinstance(probe.name, str)
            assert len(probe.name) > 0
            assert isinstance(probe.timeout_ms, int)
            assert isinstance(probe.expected_fields, list)


class TestProbeResult:
    def test_default_timestamp(self):
        r = ProbeResult(probe_name="test", target_id="T1", status=ProbeStatus.OK)
        assert r.timestamp_utc  # auto-populated

    def test_error_result(self):
        r = ProbeResult(
            probe_name="test",
            target_id="T1",
            status=ProbeStatus.ERROR,
            error="connection refused",
        )
        assert r.error == "connection refused"
        assert r.latency_ms is None


class TestProbeSafe:
    def test_probe_safe_catches_exception(self):
        """probe_safe() should never raise, even if probe() throws."""

        class BrokenProbe(BaseProbe):
            @property
            def name(self):
                return "broken"

            def probe(self, target):
                raise RuntimeError("kaboom")

        p = BrokenProbe()
        result = p.probe_safe({"TargetId": "T1"})
        assert result.status == ProbeStatus.ERROR
        assert "kaboom" in result.error
