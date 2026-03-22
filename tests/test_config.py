"""Tests for configuration and profile loading."""

import json

import pytest

from infra.config import load_profile, merge_cli_overrides, Profile, ProbeConfig


class TestLoadProfile:
    def test_load_default_profile(self, tmp_path):
        data = {
            "ProfileName": "test-profile",
            "Probes": {
                "ping": {"enabled": True, "timeout_ms": 3000, "count": 4},
                "dns": {"enabled": True, "timeout_ms": 5000},
                "ssh": {"enabled": False},
            },
            "Thresholds": {
                "ping_latency_ms": {"good": 5, "fair": 15, "poor": 30},
            },
            "Schedule": {
                "interval_minutes": 10,
                "retry_on_failure": False,
                "max_retries": 1,
            },
        }
        path = tmp_path / "profile.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        profile = load_profile(path)
        assert profile.name == "test-profile"
        assert profile.is_probe_enabled("ping") is True
        assert profile.is_probe_enabled("ssh") is False
        assert profile.is_probe_enabled("unknown") is True  # default enabled
        assert profile.get_probe_timeout("ping") == 3000
        assert profile.get_probe_timeout("dns") == 5000
        assert profile.schedule.interval_minutes == 10
        assert profile.schedule.retry_on_failure is False

    def test_load_minimal_profile(self, tmp_path):
        data = {"ProfileName": "minimal"}
        path = tmp_path / "minimal.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        profile = load_profile(path)
        assert profile.name == "minimal"
        assert profile.probes == {}
        assert profile.schedule.interval_minutes == 5  # default

    def test_probe_extra_fields_preserved(self, tmp_path):
        data = {
            "Probes": {"ping": {"enabled": True, "timeout_ms": 3000, "count": 8}},
        }
        path = tmp_path / "extra.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        profile = load_profile(path)
        assert profile.probes["ping"].extra["count"] == 8


class TestMergeCliOverrides:
    def test_override_interval(self):
        profile = Profile(name="test")
        merged = merge_cli_overrides(profile, interval=15)
        assert merged.schedule.interval_minutes == 15

    def test_override_probes(self):
        profile = Profile(
            name="test",
            probes={
                "ping": ProbeConfig(enabled=True),
                "dns": ProbeConfig(enabled=True),
                "tcp": ProbeConfig(enabled=True),
            },
        )
        merged = merge_cli_overrides(profile, probes=["ping", "dns"])
        assert merged.is_probe_enabled("ping") is True
        assert merged.is_probe_enabled("dns") is True
        assert merged.is_probe_enabled("tcp") is False

    def test_no_overrides(self):
        profile = Profile(name="test")
        merged = merge_cli_overrides(profile)
        assert merged.name == "test"  # unchanged
