"""Manifest writer — records run metadata as JSON."""

from __future__ import annotations

import json
import sys
import socket
import locale
from pathlib import Path

from ..runner import RunResult


def build_manifest(run_result: RunResult, output_files: dict[str, str] | None = None) -> dict:
    """Build a manifest dict from run results.

    Args:
        run_result: Complete run results.
        output_files: Optional dict of output file paths (e.g. {"csv": "/path/to/file.csv"}).

    Returns:
        Manifest dict.
    """
    target_summary = []
    for tr in run_result.target_results:
        target_summary.append({
            "target_id": tr.target.target_id,
            "status": tr.worst_status.value,
            "probes_run": len(tr.probe_results),
            "ok": tr.ok_count,
            "fail": tr.fail_count,
            "elapsed_ms": tr.elapsed_ms,
        })

    return {
        "tool": "InfraHealthProbe",
        "version": "0.1.0",
        "run_id": run_result.run_id,
        "profile_name": run_result.profile_name,
        "hostname": socket.gethostname(),
        "python_version": sys.version.split()[0],
        "locale": locale.getdefaultlocale()[0] or "",
        "start_time_utc": run_result.start_time_utc,
        "end_time_utc": run_result.end_time_utc,
        "elapsed_ms": run_result.elapsed_ms,
        "target_count": run_result.target_count,
        "total_probes": run_result.total_probes,
        "errors": run_result.errors,
        "output_files": output_files or {},
        "targets": target_summary,
    }


def write_manifest(run_result: RunResult, output_dir: str | Path, output_files: dict[str, str] | None = None) -> Path:
    """Write manifest JSON to output directory.

    Args:
        run_result: Complete run results.
        output_dir: Directory to write the manifest.
        output_files: Optional dict of output file paths.

    Returns:
        Path to the written manifest file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest(run_result, output_files)

    filename = f"InfraHealthProbe_{run_result.run_id}_manifest.json"
    filepath = output_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return filepath
