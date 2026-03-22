"""CLI entry point for InfraHealthProbe."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_profile, merge_cli_overrides, Profile
from .inventory.core import filter_targets
from .inventory.local_json import load_json_inventory
from .inventory.local_csv import load_csv_inventory
from .analytics.scoring import score_target
from .analytics.summary import write_summary
from .output.csv_writer import write_csv
from .output.json_writer import write_jsonl
from .output.html_report import write_html_report
from .output.manifest import write_manifest
from .probes import list_probes
from .runner import run_all
from .scheduler import Scheduler


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="infra",
        description="InfraHealthProbe — infrastructure health detection platform",
    )
    parser.add_argument(
        "--inventory", "-i",
        required=True,
        help="Path to inventory file (JSON or CSV)",
    )
    parser.add_argument(
        "--profile", "-p",
        default=None,
        help="Path to profile JSON (default: built-in defaults)",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default="./output",
        help="Output directory for results (default: ./output)",
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["oneshot", "scheduled"],
        default="oneshot",
        help="Run mode: oneshot (default) or scheduled (repeating)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Override schedule interval in minutes (scheduled mode)",
    )
    parser.add_argument(
        "--location",
        default=None,
        help="Filter targets by location (substring match)",
    )
    parser.add_argument(
        "--function",
        default=None,
        help="Filter targets by function (substring match)",
    )
    parser.add_argument(
        "--probes",
        default=None,
        nargs="+",
        help=f"Restrict to specific probes (available: {', '.join(list_probes())})",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Max parallel target workers (default: 8)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress output",
    )
    return parser.parse_args(argv)


def _load_inventory(path: str):
    """Load inventory from JSON or CSV based on file extension."""
    p = Path(path)
    if not p.exists():
        print(f"Error: inventory file not found: {path}", file=sys.stderr)
        sys.exit(1)

    ext = p.suffix.lower()
    if ext == ".json":
        return load_json_inventory(p)
    elif ext == ".csv":
        return load_csv_inventory(p)
    else:
        print(f"Error: unsupported inventory format: {ext} (use .json or .csv)", file=sys.stderr)
        sys.exit(1)


def _log(msg: str, quiet: bool = False):
    if not quiet:
        print(msg, file=sys.stderr)


def _run_oneshot(args, targets, profile) -> int:
    """Single probe run."""
    _log("Running probes...", args.quiet)
    run_result = run_all(targets, profile, max_workers=args.workers)

    # Per-target results
    _log("", args.quiet)
    for tr in run_result.target_results:
        ts = score_target(tr.target.target_id, tr.probe_results)
        icon = "OK" if ts.overall_verdict.value == "GOOD" else "!!"
        _log(
            f"  [{icon}] {tr.target.target_id:<40} "
            f"{ts.overall_verdict.value:<8} score={ts.health_score:<4} "
            f"({tr.ok_count}/{len(tr.probe_results)} probes OK, {tr.elapsed_ms:.0f}ms)",
            args.quiet,
        )
    _log("", args.quiet)

    # Write outputs
    output_dir = Path(args.output_dir)
    output_files: dict[str, str] = {}

    csv_path = write_csv(run_result, output_dir)
    output_files["csv"] = str(csv_path)
    _log(f"CSV:      {csv_path}", args.quiet)

    jsonl_path = write_jsonl(run_result, output_dir)
    output_files["jsonl"] = str(jsonl_path)
    _log(f"JSONL:    {jsonl_path}", args.quiet)

    summary_path = output_dir / f"InfraHealthProbe_{run_result.run_id}_summary.txt"
    write_summary(run_result, str(summary_path))
    output_files["summary"] = str(summary_path)
    _log(f"Summary:  {summary_path}", args.quiet)

    html_path = write_html_report(run_result, output_dir)
    output_files["html"] = str(html_path)
    _log(f"HTML:     {html_path}", args.quiet)

    manifest_path = write_manifest(run_result, output_dir, output_files=output_files)
    _log(f"Manifest: {manifest_path}", args.quiet)

    # Final line
    total = run_result.total_probes
    ok = sum(tr.ok_count for tr in run_result.target_results)
    fail = sum(tr.fail_count for tr in run_result.target_results)
    _log(f"\nDone. {len(targets)} targets, {total} probes, {ok} OK, {fail} failed. ({run_result.elapsed_ms:.0f}ms)", args.quiet)

    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Load inventory
    _log(f"Loading inventory: {args.inventory}", args.quiet)
    try:
        targets = _load_inventory(args.inventory)
    except (ValueError, FileNotFoundError) as e:
        print(f"Error loading inventory: {e}", file=sys.stderr)
        return 1

    # Filter
    targets = filter_targets(
        targets,
        location=args.location,
        function=args.function,
        enabled_only=True,
    )

    if not targets:
        print("No targets matched filters.", file=sys.stderr)
        return 1

    _log(f"Targets: {len(targets)}", args.quiet)

    # Load profile
    if args.profile:
        try:
            profile = load_profile(args.profile)
        except (FileNotFoundError, ValueError) as e:
            print(f"Error loading profile: {e}", file=sys.stderr)
            return 1
    else:
        profile = Profile(name="default")

    profile = merge_cli_overrides(profile, probes=args.probes, interval=args.interval)
    _log(f"Profile: {profile.name}", args.quiet)

    # Dispatch by mode
    if args.mode == "scheduled":
        scheduler = Scheduler(
            targets=targets,
            profile=profile,
            output_dir=args.output_dir,
            max_workers=args.workers,
            quiet=args.quiet,
        )
        return scheduler.run()
    else:
        return _run_oneshot(args, targets, profile)


if __name__ == "__main__":
    sys.exit(main())
