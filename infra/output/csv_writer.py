"""CSV output writer — writes probe results to CSV."""

from __future__ import annotations

import csv
import os
from pathlib import Path

from ..runner import RunResult, TargetResult
from ..probes.base import ProbeStatus


# Fixed column order for CSV output stability
CSV_COLUMNS = [
    "RunId",
    "Timestamp",
    "TargetId",
    "Type",
    "Location",
    "Function",
    "Hostname",
    "FQDN",
    "IPAddress",
    "OS",
    "ProbeProfile",
    "OverallStatus",
    # Ping
    "PingStatus",
    "PingLatencyAvgMs",
    "PingLatencyMinMs",
    "PingLatencyMaxMs",
    "PingLossPct",
    # DNS
    "DnsStatus",
    "DnsLatencyMs",
    "DnsResolvedIps",
    # TCP
    "TcpStatus",
    "TcpLatencyMs",
    "TcpOpenCount",
    "TcpTotalCount",
    "TcpPortDetails",
    # HTTP
    "HttpStatus",
    "HttpLatencyMs",
    "HttpReachableCount",
    "HttpTotalCount",
    "HttpUrlDetails",
    # Meta
    "ElapsedMs",
    "ProbeCount",
    "OkCount",
    "FailCount",
]


def _extract_probe_metrics(tr: TargetResult) -> dict:
    """Extract per-probe metrics into flat dict for CSV."""
    row: dict = {}

    for pr in tr.probe_results:
        if pr.probe_name == "ping":
            row["PingStatus"] = pr.status.value
            row["PingLatencyAvgMs"] = pr.metrics.get("latency_avg_ms", "")
            row["PingLatencyMinMs"] = pr.metrics.get("latency_min_ms", "")
            row["PingLatencyMaxMs"] = pr.metrics.get("latency_max_ms", "")
            row["PingLossPct"] = pr.metrics.get("packet_loss_pct", "")

        elif pr.probe_name == "dns":
            row["DnsStatus"] = pr.status.value
            row["DnsLatencyMs"] = pr.latency_ms if pr.latency_ms is not None else ""
            ips = pr.metrics.get("resolved_ips", [])
            row["DnsResolvedIps"] = ";".join(ips) if ips else ""

        elif pr.probe_name == "tcp":
            row["TcpStatus"] = pr.status.value
            row["TcpLatencyMs"] = pr.latency_ms if pr.latency_ms is not None else ""
            row["TcpOpenCount"] = pr.metrics.get("open_count", "")
            row["TcpTotalCount"] = pr.metrics.get("total_count", "")
            ports = pr.metrics.get("ports", [])
            row["TcpPortDetails"] = ";".join(
                f"{p['port']}:{'open' if p.get('open') else 'closed'}" for p in ports
            ) if ports else ""

        elif pr.probe_name == "http":
            row["HttpStatus"] = pr.status.value
            row["HttpLatencyMs"] = pr.latency_ms if pr.latency_ms is not None else ""
            row["HttpReachableCount"] = pr.metrics.get("reachable_count", "")
            row["HttpTotalCount"] = pr.metrics.get("total_count", "")
            urls = pr.metrics.get("urls", [])
            row["HttpUrlDetails"] = ";".join(
                f"{u['url']}:{u.get('status_code', 'err')}" for u in urls
            ) if urls else ""

    return row


def write_csv(run_result: RunResult, output_dir: str | Path) -> Path:
    """Write run results to a CSV file.

    Args:
        run_result: Complete run results.
        output_dir: Directory to write the CSV file.

    Returns:
        Path to the written CSV file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"InfraHealthProbe_{run_result.run_id}.csv"
    filepath = output_dir / filename

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()

        for tr in run_result.target_results:
            row = {
                "RunId": run_result.run_id,
                "Timestamp": tr.timestamp_utc,
                "TargetId": tr.target.target_id,
                "Type": tr.target.type,
                "Location": tr.target.location,
                "Function": tr.target.function,
                "Hostname": tr.target.hostname,
                "FQDN": tr.target.fqdn,
                "IPAddress": tr.target.ip_address,
                "OS": tr.target.os,
                "ProbeProfile": tr.target.probe_profile,
                "OverallStatus": tr.worst_status.value,
                "ElapsedMs": tr.elapsed_ms,
                "ProbeCount": len(tr.probe_results),
                "OkCount": tr.ok_count,
                "FailCount": tr.fail_count,
            }

            row.update(_extract_probe_metrics(tr))
            writer.writerow(row)

    return filepath
