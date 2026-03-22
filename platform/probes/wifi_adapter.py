"""WiFi probe adapter — consumes Collect-WiFiMeetingTest output.

This adapter does NOT import or dot-source any PowerShell code.
It reads the JSONL/CSV files produced by Collect-WiFiMeetingTest
and converts them into canonical ProbeResult objects.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .base import BaseProbe, ProbeResult, ProbeStatus


class WiFiProbeAdapter(BaseProbe):
    """Adapter that consumes Collect-WiFiMeetingTest JSONL/CSV output."""

    @property
    def name(self) -> str:
        return "wifi"

    @property
    def timeout_ms(self) -> int:
        return 0  # Not applicable — reads files, doesn't probe live

    @property
    def expected_fields(self) -> list[str]:
        return [
            "signal_pct",
            "rssi_dbm",
            "gateway_latency_ms",
            "wan_latency_ms",
            "dns_latency_ms",
            "https_latency_ms",
            "overall_verdict",
            "health_score",
        ]

    def probe(self, target: dict) -> ProbeResult:
        """Not used for WiFi adapter — use parse_jsonl or parse_csv instead."""
        return ProbeResult(
            probe_name=self.name,
            target_id=target.get("TargetId", "unknown"),
            status=ProbeStatus.SKIPPED,
            detail="Use parse_jsonl() or parse_csv() to consume WiFi tool output",
        )

    def parse_jsonl(self, path: str | Path) -> list[dict]:
        """Parse JSONL output from Collect-WiFiMeetingTest.

        Args:
            path: Path to the .jsonl file produced by WiFi tool.

        Returns:
            List of sample dicts in canonical format.
        """
        samples = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    samples.append(self._normalize_sample(record))
                except json.JSONDecodeError:
                    continue
        return samples

    def parse_csv(self, path: str | Path) -> list[dict]:
        """Parse CSV output from Collect-WiFiMeetingTest.

        Args:
            path: Path to the .csv file produced by WiFi tool.

        Returns:
            List of sample dicts in canonical format.
        """
        samples = []
        with open(path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                samples.append(self._normalize_sample(row))
        return samples

    def parse_events_csv(self, path: str | Path) -> list[dict]:
        """Parse events CSV from Collect-WiFiMeetingTest.

        Args:
            path: Path to the events .csv file.

        Returns:
            List of event dicts.
        """
        events = []
        with open(path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                events.append(dict(row))
        return events

    @staticmethod
    def _normalize_sample(record: dict) -> dict:
        """Convert WiFi tool sample to canonical platform format."""

        def safe_float(val, default=None):
            if val is None or val == "":
                return default
            try:
                return float(val)
            except (ValueError, TypeError):
                return default

        return {
            "source": "wifi-probe",
            "timestamp_utc": record.get("Timestamp", record.get("TimestampUtc", "")),
            "signal_pct": safe_float(record.get("Signal(%)", record.get("SignalPct"))),
            "rssi_dbm": safe_float(record.get("RSSI(dBm)", record.get("RssiDbm"))),
            "ssid": record.get("SSID", ""),
            "bssid": record.get("BSSID", ""),
            "channel": record.get("Channel", ""),
            "band": record.get("Band", ""),
            "radio_type": record.get("RadioType", ""),
            "gateway_latency_ms": safe_float(record.get("GW_Avg(ms)", record.get("GatewayLatencyAvgMs"))),
            "wan_latency_ms": safe_float(record.get("Ext_Avg(ms)", record.get("WanLatencyAvgMs"))),
            "dns_latency_ms": safe_float(record.get("DNS(ms)", record.get("DnsLatencyMs"))),
            "tcp443_latency_ms": safe_float(record.get("TCP443(ms)", record.get("Tcp443LatencyMs"))),
            "https_latency_ms": safe_float(record.get("HTTPS(ms)", record.get("HttpsLatencyMs"))),
            "cpu_pct": safe_float(record.get("CPU(%)", record.get("CpuPct"))),
            "available_memory_mb": safe_float(record.get("AvailMem(MB)", record.get("AvailableMemoryMB"))),
            "overall_verdict": record.get("Verdict", record.get("OverallVerdict", "")),
        }
