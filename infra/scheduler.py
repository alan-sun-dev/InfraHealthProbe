"""Scheduler — runs probe cycles at fixed intervals."""

from __future__ import annotations

import signal
import sys
import time
from pathlib import Path

from .config import Profile
from .inventory.core import Target
from .runner import run_all, RunResult
from .output.csv_writer import write_csv
from .output.json_writer import write_jsonl
from .output.manifest import write_manifest
from .analytics.summary import write_summary
from .analytics.scoring import score_target


class Scheduler:
    """Runs probe cycles at a fixed interval until stopped."""

    def __init__(
        self,
        targets: list[Target],
        profile: Profile,
        output_dir: str | Path,
        max_workers: int = 8,
        quiet: bool = False,
    ):
        self.targets = targets
        self.profile = profile
        self.output_dir = Path(output_dir)
        self.max_workers = max_workers
        self.quiet = quiet
        self._running = True
        self._cycle_count = 0

    def _log(self, msg: str):
        if not self.quiet:
            print(msg, file=sys.stderr)

    def _handle_signal(self, signum, frame):
        self._log(f"\nReceived signal {signum}, stopping after current cycle...")
        self._running = False

    def _run_cycle(self) -> RunResult:
        """Execute one probe cycle and write outputs."""
        self._cycle_count += 1
        self._log(f"--- Cycle {self._cycle_count} ---")

        run_result = run_all(self.targets, self.profile, max_workers=self.max_workers)

        # Per-target summary
        for tr in run_result.target_results:
            ts = score_target(tr.target.target_id, tr.probe_results)
            icon = "OK" if ts.overall_verdict.value == "GOOD" else "!!"
            self._log(
                f"  [{icon}] {tr.target.target_id:<40} "
                f"{ts.overall_verdict.value:<8} score={ts.health_score}"
            )

        # Write outputs
        output_files: dict[str, str] = {}

        csv_path = write_csv(run_result, self.output_dir)
        output_files["csv"] = str(csv_path)

        jsonl_path = write_jsonl(run_result, self.output_dir)
        output_files["jsonl"] = str(jsonl_path)

        summary_path = self.output_dir / f"InfraHealthProbe_{run_result.run_id}_summary.txt"
        write_summary(run_result, str(summary_path))
        output_files["summary"] = str(summary_path)

        write_manifest(run_result, self.output_dir, output_files=output_files)

        ok = sum(tr.ok_count for tr in run_result.target_results)
        fail = sum(tr.fail_count for tr in run_result.target_results)
        self._log(f"  {ok} OK, {fail} failed ({run_result.elapsed_ms:.0f}ms)")

        return run_result

    def run(self) -> int:
        """Run the scheduled loop. Returns exit code."""
        interval = self.profile.schedule.interval_minutes * 60

        # Handle Ctrl+C gracefully
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        self._log(f"Scheduled mode: every {self.profile.schedule.interval_minutes}min, "
                   f"{len(self.targets)} targets. Ctrl+C to stop.")
        self._log("")

        while self._running:
            self._run_cycle()

            if not self._running:
                break

            self._log(f"  Next cycle in {self.profile.schedule.interval_minutes}min...")
            self._log("")

            # Sleep in small increments so we can respond to signals
            deadline = time.monotonic() + interval
            while self._running and time.monotonic() < deadline:
                time.sleep(min(1.0, deadline - time.monotonic()))

        self._log(f"\nStopped after {self._cycle_count} cycle(s).")
        return 0
