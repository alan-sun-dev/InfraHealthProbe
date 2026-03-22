"""CLI entry point for InfraHealthProbe."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .config import load_profile, merge_cli_overrides, Profile
from .inventory.core import filter_targets
from .inventory.local_json import load_json_inventory
from .inventory.local_csv import load_csv_inventory
from .output.csv_writer import write_csv
from .output.manifest import write_manifest
from .probes import list_probes
from .runner import run_all


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

    profile = merge_cli_overrides(profile, probes=args.probes)

    _log(f"Profile: {profile.name}", args.quiet)

    # Run probes
    _log(f"Running probes...", args.quiet)
    run_result = run_all(targets, profile, max_workers=args.workers)

    # Print summary
    _log("", args.quiet)
    for tr in run_result.target_results:
        status_icon = "OK" if tr.worst_status.value == "OK" else "!!"
        _log(
            f"  [{status_icon}] {tr.target.target_id:<40} "
            f"{tr.worst_status.value:<10} "
            f"({tr.ok_count}/{len(tr.probe_results)} probes OK, {tr.elapsed_ms:.0f}ms)",
            args.quiet,
        )

    _log("", args.quiet)

    # Write outputs
    csv_path = write_csv(run_result, args.output_dir)
    _log(f"CSV:      {csv_path}", args.quiet)

    manifest_path = write_manifest(
        run_result,
        args.output_dir,
        output_files={"csv": str(csv_path)},
    )
    _log(f"Manifest: {manifest_path}", args.quiet)

    # Summary line
    total = run_result.total_probes
    ok = sum(tr.ok_count for tr in run_result.target_results)
    fail = sum(tr.fail_count for tr in run_result.target_results)
    _log(f"\nDone. {len(targets)} targets, {total} probes, {ok} OK, {fail} failed. ({run_result.elapsed_ms:.0f}ms)", args.quiet)

    return 0


if __name__ == "__main__":
    sys.exit(main())
