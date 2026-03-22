"""Tests for inventory core and providers."""

import json
import tempfile
from pathlib import Path

import pytest

from platform.inventory.core import (
    Target,
    normalize_target,
    validate_target,
    deduplicate_targets,
    merge_inventories,
    filter_targets,
)
from platform.inventory.local_json import load_json_inventory


class TestNormalizeTarget:
    def test_basic_normalization(self):
        raw = {
            "TargetId": "TEST-001",
            "FQDN": "test.example.com",
            "IPAddress": "10.0.0.1",
            "Ports": [80, 443],
            "ProbeProfile": "default",
        }
        target = normalize_target(raw)
        assert target.target_id == "TEST-001"
        assert target.fqdn == "test.example.com"
        assert target.ports == [80, 443]
        assert target.enabled is True

    def test_semicolon_ports(self):
        raw = {"TargetId": "TEST-002", "FQDN": "x.com", "Ports": "80;443;22", "ProbeProfile": "default"}
        target = normalize_target(raw)
        assert target.ports == [80, 443, 22]

    def test_semicolon_urls(self):
        raw = {"TargetId": "TEST-003", "FQDN": "x.com", "Urls": "http://a;http://b", "ProbeProfile": "default"}
        target = normalize_target(raw)
        assert target.urls == ["http://a", "http://b"]

    def test_enabled_string_conversion(self):
        for truthy in ("true", "True", "yes", "1"):
            raw = {"TargetId": "T", "FQDN": "x.com", "Enabled": truthy, "ProbeProfile": "default"}
            assert normalize_target(raw).enabled is True

        for falsy in ("false", "no", "0", ""):
            raw = {"TargetId": "T", "FQDN": "x.com", "Enabled": falsy, "ProbeProfile": "default"}
            assert normalize_target(raw).enabled is False


class TestValidateTarget:
    def test_valid_target(self):
        target = Target(target_id="T1", fqdn="x.com", probe_profile="default")
        assert validate_target(target) == []

    def test_missing_target_id(self):
        target = Target(target_id="", fqdn="x.com", probe_profile="default")
        errors = validate_target(target)
        assert any("TargetId" in e for e in errors)

    def test_missing_address(self):
        target = Target(target_id="T1", probe_profile="default")
        errors = validate_target(target)
        assert any("FQDN" in e or "IPAddress" in e for e in errors)

    def test_invalid_port(self):
        target = Target(target_id="T1", fqdn="x.com", probe_profile="default", ports=[80, 99999])
        errors = validate_target(target)
        assert any("99999" in e for e in errors)


class TestDeduplication:
    def test_keeps_last(self):
        t1 = Target(target_id="A", fqdn="first.com", probe_profile="default")
        t2 = Target(target_id="A", fqdn="second.com", probe_profile="default")
        result = deduplicate_targets([t1, t2])
        assert len(result) == 1
        assert result[0].fqdn == "second.com"


class TestMerge:
    def test_override_replaces(self):
        primary = [Target(target_id="A", fqdn="old.com", enabled=True, probe_profile="default")]
        overrides = [Target(target_id="A", fqdn="old.com", enabled=False, probe_profile="default", notes="maintenance")]
        result = merge_inventories(primary, overrides)
        assert len(result) == 1
        assert result[0].enabled is False

    def test_override_appends_new(self):
        primary = [Target(target_id="A", fqdn="a.com", probe_profile="default")]
        overrides = [Target(target_id="B", fqdn="b.com", probe_profile="default")]
        result = merge_inventories(primary, overrides)
        assert len(result) == 2


class TestFilter:
    def test_enabled_only(self):
        targets = [
            Target(target_id="A", fqdn="a.com", enabled=True, probe_profile="default"),
            Target(target_id="B", fqdn="b.com", enabled=False, probe_profile="default"),
        ]
        result = filter_targets(targets, enabled_only=True)
        assert len(result) == 1
        assert result[0].target_id == "A"

    def test_filter_by_location(self):
        targets = [
            Target(target_id="A", fqdn="a.com", location="Taiwan/TPEIP", probe_profile="default"),
            Target(target_id="B", fqdn="b.com", location="Singapore", probe_profile="default"),
        ]
        result = filter_targets(targets, location="Taiwan")
        assert len(result) == 1

    def test_filter_by_function(self):
        targets = [
            Target(target_id="A", fqdn="a.com", function="Cache Server", probe_profile="default"),
            Target(target_id="B", fqdn="b.com", function="EDI Server", probe_profile="default"),
        ]
        result = filter_targets(targets, function="cache")
        assert len(result) == 1


class TestJsonProvider:
    def test_load_valid_json(self, tmp_path):
        data = [
            {"TargetId": "T1", "FQDN": "a.com", "ProbeProfile": "default", "Ports": [80]},
            {"TargetId": "T2", "IPAddress": "10.0.0.1", "ProbeProfile": "default"},
        ]
        path = tmp_path / "targets.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        targets = load_json_inventory(path)
        assert len(targets) == 2
        assert targets[0].target_id == "T1"

    def test_invalid_target_raises(self, tmp_path):
        data = [{"TargetId": "", "ProbeProfile": "default"}]
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        with pytest.raises(ValueError):
            load_json_inventory(path)
