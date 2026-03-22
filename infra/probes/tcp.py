"""TCP port connectivity probe."""

from __future__ import annotations

import socket
import time

from .base import BaseProbe, ProbeResult, ProbeStatus


class TcpProbe(BaseProbe):
    @property
    def name(self) -> str:
        return "tcp"

    @property
    def timeout_ms(self) -> int:
        return 5000

    @property
    def expected_fields(self) -> list[str]:
        return ["latency_ms", "port", "open"]

    def probe(self, target: dict) -> ProbeResult:
        host = target.get("FQDN") or target.get("IPAddress") or target.get("Hostname", "")
        ports = target.get("Ports", [])

        if not host:
            return ProbeResult(
                probe_name=self.name,
                target_id=target.get("TargetId", "unknown"),
                status=ProbeStatus.ERROR,
                error="No host address available",
            )

        if not ports:
            return ProbeResult(
                probe_name=self.name,
                target_id=target.get("TargetId", "unknown"),
                status=ProbeStatus.SKIPPED,
                detail="No ports defined",
            )

        port_results = []
        worst_status = ProbeStatus.OK
        total_latency = 0.0

        for port in ports:
            start = time.perf_counter()
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.timeout_ms / 1000)
                sock.connect((host, int(port)))
                elapsed_ms = (time.perf_counter() - start) * 1000
                sock.close()
                port_results.append({"port": port, "open": True, "latency_ms": round(elapsed_ms, 2)})
                total_latency += elapsed_ms
            except socket.timeout:
                elapsed_ms = (time.perf_counter() - start) * 1000
                port_results.append({"port": port, "open": False, "error": "timeout"})
                worst_status = ProbeStatus.FAILED
            except OSError as exc:
                elapsed_ms = (time.perf_counter() - start) * 1000
                port_results.append({"port": port, "open": False, "error": str(exc)})
                worst_status = ProbeStatus.FAILED

        open_count = sum(1 for r in port_results if r.get("open"))
        avg_latency = round(total_latency / open_count, 2) if open_count else None

        if open_count == 0:
            worst_status = ProbeStatus.FAILED
        elif open_count < len(ports):
            worst_status = ProbeStatus.DEGRADED

        return ProbeResult(
            probe_name=self.name,
            target_id=target.get("TargetId", "unknown"),
            status=worst_status,
            latency_ms=avg_latency,
            metrics={"ports": port_results, "open_count": open_count, "total_count": len(ports)},
        )
