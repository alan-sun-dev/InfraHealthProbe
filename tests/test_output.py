"""Tests for output writers."""

import csv
import json

import pytest

from infra.inventory.core import Target
from infra.probes.base import ProbeResult, ProbeStatus
from infra.runner import TargetResult, RunResult
from infra.output.csv_writer import write_csv, CSV_COLUMNS
from infra.output.manifest import build_manifest, write_manifest


def _make_run_result() -> RunResult:
    """Create a minimal RunResult for testing."""
    return RunResult(
        run_id="20260323T100000Z",
        profile_name="test-profile",
        start_time_utc="2026-03-23T10:00:00Z",
        end_time_utc="2026-03-23T10:00:05Z",
        elapsed_ms=5000.0,
        target_results=[
            TargetResult(
                target=Target(
                    target_id="T1", fqdn="test.example.com",
                    ip_address="10.0.0.1", location="Taiwan/TPEIP",
                    function="Cache Server", probe_profile="default",
                ),
                probe_results=[
                    ProbeResult(
                        probe_name="ping", target_id="T1", status=ProbeStatus.OK,
                        latency_ms=5.0,
                        metrics={"latency_avg_ms": 5.0, "latency_min_ms": 3.0,
                                 "latency_max_ms": 8.0, "packet_loss_pct": 0.0},
                    ),
                    ProbeResult(
                        probe_name="dns", target_id="T1", status=ProbeStatus.OK,
                        latency_ms=42.0,
                        metrics={"latency_ms": 42.0, "resolved_ips": ["10.0.0.1"]},
                    ),
                    ProbeResult(
                        probe_name="tcp", target_id="T1", status=ProbeStatus.DEGRADED,
                        latency_ms=15.0,
                        metrics={"ports": [{"port": 80, "open": True, "latency_ms": 15.0},
                                           {"port": 443, "open": False, "error": "timeout"}],
                                 "open_count": 1, "total_count": 2},
                    ),
                ],
                elapsed_ms=120.5,
            ),
            TargetResult(
                target=Target(
                    target_id="T2", ip_address="10.0.0.2",
                    function="EDI Server", probe_profile="default",
                ),
                probe_results=[
                    ProbeResult(
                        probe_name="ping", target_id="T2", status=ProbeStatus.FAILED,
                        error="100% packet loss",
                        metrics={"packet_loss_pct": 100.0},
                    ),
                ],
                elapsed_ms=5010.0,
            ),
        ],
    )


class TestCsvWriter:
    def test_write_csv_creates_file(self, tmp_path):
        rr = _make_run_result()
        path = write_csv(rr, tmp_path)
        assert path.exists()
        assert path.name == "InfraHealthProbe_20260323T100000Z.csv"

    def test_csv_has_correct_headers(self, tmp_path):
        rr = _make_run_result()
        path = write_csv(rr, tmp_path)
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert list(reader.fieldnames) == CSV_COLUMNS

    def test_csv_has_correct_row_count(self, tmp_path):
        rr = _make_run_result()
        path = write_csv(rr, tmp_path)
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2  # 2 targets

    def test_csv_target_data(self, tmp_path):
        rr = _make_run_result()
        path = write_csv(rr, tmp_path)
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows[0]["TargetId"] == "T1"
        assert rows[0]["FQDN"] == "test.example.com"
        assert rows[0]["PingStatus"] == "OK"
        assert rows[0]["TcpStatus"] == "DEGRADED"
        assert rows[1]["TargetId"] == "T2"
        assert rows[1]["PingStatus"] == "FAILED"

    def test_csv_creates_output_dir(self, tmp_path):
        rr = _make_run_result()
        nested = tmp_path / "deep" / "nested"
        path = write_csv(rr, nested)
        assert path.exists()


class TestManifest:
    def test_build_manifest(self):
        rr = _make_run_result()
        manifest = build_manifest(rr, output_files={"csv": "/tmp/test.csv"})
        assert manifest["tool"] == "InfraHealthProbe"
        assert manifest["run_id"] == "20260323T100000Z"
        assert manifest["profile_name"] == "test-profile"
        assert manifest["target_count"] == 2
        assert manifest["total_probes"] == 4
        assert len(manifest["targets"]) == 2
        assert manifest["output_files"]["csv"] == "/tmp/test.csv"

    def test_write_manifest_creates_file(self, tmp_path):
        rr = _make_run_result()
        path = write_manifest(rr, tmp_path)
        assert path.exists()
        assert path.name == "InfraHealthProbe_20260323T100000Z_manifest.json"

    def test_manifest_is_valid_json(self, tmp_path):
        rr = _make_run_result()
        path = write_manifest(rr, tmp_path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["run_id"] == "20260323T100000Z"

    def test_manifest_target_summary(self, tmp_path):
        rr = _make_run_result()
        manifest = build_manifest(rr)
        t1 = manifest["targets"][0]
        assert t1["target_id"] == "T1"
        assert t1["probes_run"] == 3
        assert t1["ok"] == 2
        assert t1["fail"] == 0  # DEGRADED is not FAILED
