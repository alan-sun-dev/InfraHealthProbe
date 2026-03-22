"""HTTP/HTTPS response probe."""

from __future__ import annotations

import time
import urllib.request
import ssl

from .base import BaseProbe, ProbeResult, ProbeStatus


class HttpProbe(BaseProbe):
    @property
    def name(self) -> str:
        return "http"

    @property
    def timeout_ms(self) -> int:
        return 10000

    @property
    def expected_fields(self) -> list[str]:
        return ["latency_ms", "status_code", "url"]

    def probe(self, target: dict) -> ProbeResult:
        urls = target.get("Urls", [])
        if not urls:
            return ProbeResult(
                probe_name=self.name,
                target_id=target.get("TargetId", "unknown"),
                status=ProbeStatus.SKIPPED,
                detail="No URLs defined",
            )

        url_results = []
        worst_status = ProbeStatus.OK

        # Accept any cert for timing measurement (same rationale as WiFi tool)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        for url in urls:
            start = time.perf_counter()
            try:
                req = urllib.request.Request(url, method="HEAD")
                req.add_header("User-Agent", "InfraHealthProbe/0.1")
                resp = urllib.request.urlopen(req, timeout=self.timeout_ms / 1000, context=ctx)
                elapsed_ms = (time.perf_counter() - start) * 1000
                status_code = resp.getcode()
                resp.close()

                url_results.append({
                    "url": url,
                    "status_code": status_code,
                    "latency_ms": round(elapsed_ms, 2),
                    "reachable": True,
                })
            except Exception as exc:
                elapsed_ms = (time.perf_counter() - start) * 1000
                url_results.append({
                    "url": url,
                    "status_code": None,
                    "latency_ms": round(elapsed_ms, 2),
                    "reachable": False,
                    "error": str(exc),
                })
                worst_status = ProbeStatus.FAILED

        reachable_count = sum(1 for r in url_results if r.get("reachable"))
        avg_latency = None
        if reachable_count:
            avg_latency = round(
                sum(r["latency_ms"] for r in url_results if r.get("reachable")) / reachable_count, 2
            )

        if reachable_count == 0:
            worst_status = ProbeStatus.FAILED
        elif reachable_count < len(urls):
            worst_status = ProbeStatus.DEGRADED

        return ProbeResult(
            probe_name=self.name,
            target_id=target.get("TargetId", "unknown"),
            status=worst_status,
            latency_ms=avg_latency,
            metrics={"urls": url_results, "reachable_count": reachable_count, "total_count": len(urls)},
        )
