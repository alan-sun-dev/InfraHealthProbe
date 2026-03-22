"""ICMP ping probe."""

from __future__ import annotations

import subprocess
import re
import sys

from .base import BaseProbe, ProbeResult, ProbeStatus


class PingProbe(BaseProbe):
    @property
    def name(self) -> str:
        return "ping"

    @property
    def timeout_ms(self) -> int:
        return 5000

    @property
    def expected_fields(self) -> list[str]:
        return ["latency_avg_ms", "latency_min_ms", "latency_max_ms", "packet_loss_pct"]

    def probe(self, target: dict) -> ProbeResult:
        host = target.get("FQDN") or target.get("IPAddress") or target.get("Hostname", "")
        if not host:
            return ProbeResult(
                probe_name=self.name,
                target_id=target.get("TargetId", "unknown"),
                status=ProbeStatus.ERROR,
                error="No host address available",
            )

        count = 4
        timeout_sec = self.timeout_ms // 1000

        if sys.platform == "win32":
            cmd = ["ping", "-n", str(count), "-w", str(self.timeout_ms), host]
        else:
            cmd = ["ping", "-c", str(count), "-W", str(timeout_sec), host]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec + 5)
            output = result.stdout

            loss = self._parse_loss(output)
            avg, min_ms, max_ms = self._parse_latency(output)

            if loss is not None and loss >= 100:
                status = ProbeStatus.FAILED
            elif loss is not None and loss > 0:
                status = ProbeStatus.DEGRADED
            else:
                status = ProbeStatus.OK

            return ProbeResult(
                probe_name=self.name,
                target_id=target.get("TargetId", "unknown"),
                status=status,
                latency_ms=avg,
                metrics={
                    "latency_avg_ms": avg,
                    "latency_min_ms": min_ms,
                    "latency_max_ms": max_ms,
                    "packet_loss_pct": loss,
                },
            )
        except subprocess.TimeoutExpired:
            return ProbeResult(
                probe_name=self.name,
                target_id=target.get("TargetId", "unknown"),
                status=ProbeStatus.TIMEOUT,
                error=f"Ping timed out after {timeout_sec}s",
            )

    @staticmethod
    def _parse_loss(output: str) -> float | None:
        # Linux: "1 received, 0% packet loss"
        # Windows: "(0% loss)"
        m = re.search(r"(\d+)%\s*(?:packet\s+)?loss", output, re.IGNORECASE)
        return float(m.group(1)) if m else None

    @staticmethod
    def _parse_latency(output: str) -> tuple[float | None, float | None, float | None]:
        # Linux: "rtt min/avg/max/mdev = 1.234/2.345/3.456/0.5 ms"
        m = re.search(r"rtt\s+min/avg/max/\S+\s*=\s*([\d.]+)/([\d.]+)/([\d.]+)", output)
        if m:
            return float(m.group(2)), float(m.group(1)), float(m.group(3))
        # Windows: "Minimum = 1ms, Maximum = 3ms, Average = 2ms"
        m = re.search(
            r"Minimum\s*=\s*(\d+)\s*ms.*Maximum\s*=\s*(\d+)\s*ms.*Average\s*=\s*(\d+)\s*ms",
            output,
            re.IGNORECASE,
        )
        if m:
            return float(m.group(3)), float(m.group(1)), float(m.group(2))
        return None, None, None
