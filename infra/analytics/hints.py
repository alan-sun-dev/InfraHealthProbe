"""Root-cause hint engine — rule-based probable cause suggestions."""

from __future__ import annotations

from dataclasses import dataclass

from ..probes.base import ProbeResult, ProbeStatus


@dataclass
class Hint:
    """A root-cause hint with confidence level."""

    cause: str
    confidence: str  # "high", "medium", "low"
    evidence: list[str]


def get_hints(target_id: str, probe_results: list[ProbeResult]) -> list[Hint]:
    """Generate root-cause hints from probe results.

    Uses rule-based pattern matching to suggest probable causes.

    Args:
        target_id: Target identifier.
        probe_results: Probe results for this target.

    Returns:
        List of Hint objects, ordered by confidence.
    """
    hints: list[Hint] = []
    by_name = {pr.probe_name: pr for pr in probe_results}

    ping = by_name.get("ping")
    dns = by_name.get("dns")
    tcp = by_name.get("tcp")
    http = by_name.get("http")

    # Rule 1: All probes failed → host likely down or unreachable
    failed_probes = [pr for pr in probe_results if pr.status in
                     (ProbeStatus.FAILED, ProbeStatus.ERROR, ProbeStatus.TIMEOUT)]
    if len(failed_probes) == len(probe_results) and len(probe_results) > 0:
        hints.append(Hint(
            cause="Host appears down or unreachable",
            confidence="high",
            evidence=[f"{pr.probe_name}: {pr.status.value}" for pr in failed_probes],
        ))
        return hints  # No point analyzing further

    # Rule 2: Ping failed but DNS resolved → ICMP may be blocked
    if (ping and ping.status in (ProbeStatus.FAILED, ProbeStatus.TIMEOUT) and
            dns and dns.status == ProbeStatus.OK):
        hints.append(Hint(
            cause="ICMP may be blocked (ping failed but DNS resolved)",
            confidence="medium",
            evidence=[
                f"ping: {ping.status.value}",
                f"dns: OK ({dns.latency_ms}ms)",
            ],
        ))

    # Rule 3: DNS failed but ping OK → DNS resolution issue
    if (dns and dns.status in (ProbeStatus.FAILED, ProbeStatus.TIMEOUT) and
            ping and ping.status == ProbeStatus.OK):
        hints.append(Hint(
            cause="DNS resolution failure (ping OK, DNS failed)",
            confidence="high",
            evidence=[
                f"ping: OK",
                f"dns: {dns.status.value}" + (f" — {dns.error}" if dns.error else ""),
            ],
        ))

    # Rule 4: TCP port(s) closed → service not listening or firewall
    if tcp and tcp.status in (ProbeStatus.FAILED, ProbeStatus.DEGRADED):
        ports_info = tcp.metrics.get("ports", [])
        closed = [p for p in ports_info if not p.get("open")]
        if closed:
            hints.append(Hint(
                cause="TCP port(s) not reachable — service down or firewall",
                confidence="high" if tcp.status == ProbeStatus.FAILED else "medium",
                evidence=[f"port {p['port']}: {p.get('error', 'closed')}" for p in closed],
            ))

    # Rule 5: HTTP failed but TCP OK → application-layer issue
    if (http and http.status in (ProbeStatus.FAILED, ProbeStatus.DEGRADED) and
            tcp and tcp.status == ProbeStatus.OK):
        url_details = http.metrics.get("urls", [])
        failed_urls = [u for u in url_details if not u.get("reachable")]
        hints.append(Hint(
            cause="Application/web service issue (TCP OK but HTTP failed)",
            confidence="high",
            evidence=[f"{u['url']}: {u.get('error', 'unreachable')}" for u in failed_urls],
        ))

    # Rule 6: High latency across multiple probes → network path issue
    high_latency_probes = []
    if ping and ping.status == ProbeStatus.OK:
        avg = ping.metrics.get("latency_avg_ms")
        if avg is not None and avg > 30:
            high_latency_probes.append(f"ping: {avg}ms")
    if dns and dns.status == ProbeStatus.OK and dns.latency_ms and dns.latency_ms > 500:
        high_latency_probes.append(f"dns: {dns.latency_ms}ms")
    if tcp and tcp.status == ProbeStatus.OK and tcp.latency_ms and tcp.latency_ms > 500:
        high_latency_probes.append(f"tcp: {tcp.latency_ms}ms")
    if http and http.status == ProbeStatus.OK and http.latency_ms and http.latency_ms > 1000:
        high_latency_probes.append(f"http: {http.latency_ms}ms")

    if len(high_latency_probes) >= 2:
        hints.append(Hint(
            cause="High latency across multiple probes — possible network path issue",
            confidence="medium",
            evidence=high_latency_probes,
        ))

    # Rule 7: Packet loss detected
    if ping and ping.status in (ProbeStatus.OK, ProbeStatus.DEGRADED):
        loss = ping.metrics.get("packet_loss_pct")
        if loss is not None and loss > 0:
            conf = "high" if loss > 5 else "medium" if loss > 1 else "low"
            hints.append(Hint(
                cause="Packet loss detected — possible link instability",
                confidence=conf,
                evidence=[f"packet_loss: {loss}%"],
            ))

    return hints
