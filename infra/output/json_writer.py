"""JSON Lines output writer."""

from __future__ import annotations

import json
from pathlib import Path

from ..runner import RunResult
from ..analytics.scoring import score_target


def write_jsonl(run_result: RunResult, output_dir: str | Path) -> Path:
    """Write run results as JSON Lines (one JSON object per target per line).

    Args:
        run_result: Complete run results.
        output_dir: Directory to write the JSONL file.

    Returns:
        Path to the written JSONL file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"InfraHealthProbe_{run_result.run_id}.jsonl"
    filepath = output_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        for tr in run_result.target_results:
            ts = score_target(tr.target.target_id, tr.probe_results)

            record = {
                "run_id": run_result.run_id,
                "timestamp_utc": tr.timestamp_utc,
                "target_id": tr.target.target_id,
                "type": tr.target.type,
                "location": tr.target.location,
                "function": tr.target.function,
                "hostname": tr.target.hostname,
                "fqdn": tr.target.fqdn,
                "ip_address": tr.target.ip_address,
                "os": tr.target.os,
                "probe_profile": tr.target.probe_profile,
                "overall_status": tr.worst_status.value,
                "health_score": ts.health_score,
                "overall_verdict": ts.overall_verdict.value,
                "elapsed_ms": tr.elapsed_ms,
                "probes": {},
            }

            for pr in tr.probe_results:
                record["probes"][pr.probe_name] = {
                    "status": pr.status.value,
                    "latency_ms": pr.latency_ms,
                    "metrics": pr.metrics,
                    "error": pr.error,
                }

            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return filepath
