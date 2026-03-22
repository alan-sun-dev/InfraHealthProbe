"""DNS resolution probe."""

from __future__ import annotations

import socket
import time

from .base import BaseProbe, ProbeResult, ProbeStatus


class DnsProbe(BaseProbe):
    @property
    def name(self) -> str:
        return "dns"

    @property
    def timeout_ms(self) -> int:
        return 5000

    @property
    def expected_fields(self) -> list[str]:
        return ["latency_ms", "resolved_ips"]

    def probe(self, target: dict) -> ProbeResult:
        hostname = target.get("FQDN") or target.get("Hostname", "")
        if not hostname:
            return ProbeResult(
                probe_name=self.name,
                target_id=target.get("TargetId", "unknown"),
                status=ProbeStatus.ERROR,
                error="No hostname for DNS lookup",
            )

        socket.setdefaulttimeout(self.timeout_ms / 1000)
        start = time.perf_counter()
        try:
            results = socket.getaddrinfo(hostname, None)
            elapsed_ms = (time.perf_counter() - start) * 1000
            ips = sorted(set(r[4][0] for r in results))

            return ProbeResult(
                probe_name=self.name,
                target_id=target.get("TargetId", "unknown"),
                status=ProbeStatus.OK,
                latency_ms=round(elapsed_ms, 2),
                metrics={"latency_ms": round(elapsed_ms, 2), "resolved_ips": ips},
            )
        except socket.gaierror as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return ProbeResult(
                probe_name=self.name,
                target_id=target.get("TargetId", "unknown"),
                status=ProbeStatus.FAILED,
                latency_ms=round(elapsed_ms, 2),
                error=str(exc),
            )
        except socket.timeout:
            return ProbeResult(
                probe_name=self.name,
                target_id=target.get("TargetId", "unknown"),
                status=ProbeStatus.TIMEOUT,
                error=f"DNS lookup timed out after {self.timeout_ms}ms",
            )
