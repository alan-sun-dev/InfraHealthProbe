"""Probe runner — dispatches probes against targets using ThreadPoolExecutor."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from .config import Profile
from .inventory.core import Target
from .probes import get_probe
from .probes.base import ProbeResult, ProbeStatus


@dataclass
class TargetResult:
    """Aggregated probe results for a single target."""

    target: Target
    probe_results: list[ProbeResult] = field(default_factory=list)
    timestamp_utc: str = ""
    elapsed_ms: float = 0.0

    def __post_init__(self):
        if not self.timestamp_utc:
            self.timestamp_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    @property
    def worst_status(self) -> ProbeStatus:
        """Return the worst status across all probe results."""
        if not self.probe_results:
            return ProbeStatus.SKIPPED
        priority = [ProbeStatus.ERROR, ProbeStatus.FAILED, ProbeStatus.TIMEOUT,
                     ProbeStatus.DEGRADED, ProbeStatus.OK, ProbeStatus.SKIPPED]
        for status in priority:
            if any(r.status == status for r in self.probe_results):
                return status
        return ProbeStatus.SKIPPED

    @property
    def ok_count(self) -> int:
        return sum(1 for r in self.probe_results if r.status == ProbeStatus.OK)

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.probe_results if r.status in
                   (ProbeStatus.FAILED, ProbeStatus.ERROR, ProbeStatus.TIMEOUT))


@dataclass
class RunResult:
    """Aggregated results for an entire run across all targets."""

    run_id: str
    target_results: list[TargetResult] = field(default_factory=list)
    start_time_utc: str = ""
    end_time_utc: str = ""
    elapsed_ms: float = 0.0
    profile_name: str = ""
    errors: list[str] = field(default_factory=list)

    @property
    def target_count(self) -> int:
        return len(self.target_results)

    @property
    def total_probes(self) -> int:
        return sum(len(tr.probe_results) for tr in self.target_results)


def _resolve_probes_for_target(target: Target, profile: Profile) -> list[str]:
    """Determine which probes to run for a target based on profile and target data."""
    # Start with probes that make sense for this target
    candidates = []

    # Always try ping and dns if target has an address
    if target.fqdn or target.ip_address:
        candidates.append("ping")
    if target.fqdn:
        candidates.append("dns")
    if target.ports:
        candidates.append("tcp")
    if target.urls:
        candidates.append("http")
    if 22 in target.ports or (target.os and target.os.lower() == "linux"):
        candidates.append("ssh")

    # Filter by profile enable/disable
    return [p for p in candidates if profile.is_probe_enabled(p)]


def _run_probe(probe_name: str, target_dict: dict, max_retries: int = 0) -> ProbeResult:
    """Run a single probe with optional retry (designed to run in a thread).

    Retries only on FAILED/TIMEOUT/ERROR, not on OK/DEGRADED/SKIPPED.
    """
    probe = get_probe(probe_name)
    result = probe.probe_safe(target_dict)

    retries = 0
    while (result.status in (ProbeStatus.FAILED, ProbeStatus.TIMEOUT, ProbeStatus.ERROR)
           and retries < max_retries):
        retries += 1
        time.sleep(0.5 * retries)  # brief backoff
        result = probe.probe_safe(target_dict)

    if retries > 0:
        prefix = f"{result.detail}; " if result.detail else ""
        result.detail = f"{prefix}retried {retries}x"

    return result


def run_probes_for_target(target: Target, profile: Profile, max_workers: int = 4, max_retries: int = 0) -> TargetResult:
    """Run all applicable probes against a single target in parallel.

    Args:
        target: The target to probe.
        profile: Profile controlling which probes run and their timeouts.
        max_workers: Max parallel probe threads per target.

    Returns:
        TargetResult with all probe results.
    """
    probe_names = _resolve_probes_for_target(target, profile)
    target_dict = target.to_dict()

    start = time.perf_counter()
    results: list[ProbeResult] = []

    if not probe_names:
        return TargetResult(
            target=target,
            probe_results=[],
            elapsed_ms=0.0,
        )

    with ThreadPoolExecutor(max_workers=min(max_workers, len(probe_names))) as executor:
        futures = {
            executor.submit(_run_probe, name, target_dict, max_retries): name
            for name in probe_names
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)

    elapsed = (time.perf_counter() - start) * 1000

    return TargetResult(
        target=target,
        probe_results=results,
        elapsed_ms=round(elapsed, 2),
    )


def run_all(targets: list[Target], profile: Profile, max_workers: int = 8) -> RunResult:
    """Run probes against all targets.

    Targets are probed in parallel (up to max_workers concurrent targets).

    Args:
        targets: List of targets to probe.
        profile: Profile configuration.
        max_workers: Max parallel target threads.

    Returns:
        RunResult with all target results.
    """
    run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    start_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    start = time.perf_counter()

    target_results: list[TargetResult] = []
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=min(max_workers, len(targets))) as executor:
        retries = profile.schedule.max_retries if profile.schedule.retry_on_failure else 0
        futures = {
            executor.submit(run_probes_for_target, target, profile, 4, retries): target
            for target in targets
        }
        for future in as_completed(futures):
            target = futures[future]
            try:
                tr = future.result()
                target_results.append(tr)
            except Exception as exc:
                errors.append(f"{target.target_id}: {exc}")

    elapsed = (time.perf_counter() - start) * 1000
    end_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    return RunResult(
        run_id=run_id,
        target_results=target_results,
        start_time_utc=start_utc,
        end_time_utc=end_utc,
        elapsed_ms=round(elapsed, 2),
        profile_name=profile.name,
        errors=errors,
    )
