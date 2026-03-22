"""Summary generator — executive and technical summaries."""

from __future__ import annotations

from ..runner import RunResult, TargetResult
from ..probes.base import ProbeStatus
from .scoring import score_target, TargetScore
from .hints import get_hints, Hint
from .verdict import Verdict


def generate_summary(run_result: RunResult) -> str:
    """Generate a complete text summary for a run.

    Includes executive summary (top) and technical details (bottom).

    Args:
        run_result: Complete run results.

    Returns:
        Multi-line summary string.
    """
    lines: list[str] = []

    # Header
    lines.append("=" * 70)
    lines.append("InfraHealthProbe Run Summary")
    lines.append("=" * 70)
    lines.append(f"Run ID:    {run_result.run_id}")
    lines.append(f"Profile:   {run_result.profile_name}")
    lines.append(f"Start:     {run_result.start_time_utc}")
    lines.append(f"End:       {run_result.end_time_utc}")
    lines.append(f"Duration:  {run_result.elapsed_ms:.0f}ms")
    lines.append(f"Targets:   {run_result.target_count}")
    lines.append(f"Probes:    {run_result.total_probes}")
    lines.append("")

    # Score each target
    scored: list[tuple[TargetResult, TargetScore, list[Hint]]] = []
    for tr in run_result.target_results:
        ts = score_target(tr.target.target_id, tr.probe_results)
        hints = get_hints(tr.target.target_id, tr.probe_results)
        scored.append((tr, ts, hints))

    # Executive summary
    lines.append("-" * 70)
    lines.append("EXECUTIVE SUMMARY")
    lines.append("-" * 70)

    scores = [ts.health_score for _, ts, _ in scored]
    if scores:
        avg_score = round(sum(scores) / len(scores))
        worst_score = min(scores)
        lines.append(f"Average health score: {avg_score}/100")
        lines.append(f"Worst health score:   {worst_score}/100")
    else:
        lines.append("No targets were probed.")

    # Count by verdict
    verdict_counts: dict[str, int] = {}
    for _, ts, _ in scored:
        v = ts.overall_verdict.value
        verdict_counts[v] = verdict_counts.get(v, 0) + 1

    if verdict_counts:
        lines.append(f"Verdict distribution: {', '.join(f'{v}={c}' for v, c in sorted(verdict_counts.items()))}")

    # Targets needing attention
    problem_targets = [(tr, ts, hints) for tr, ts, hints in scored
                       if ts.overall_verdict in (Verdict.POOR, Verdict.SEVERE)]
    if problem_targets:
        lines.append(f"\nTargets needing attention: {len(problem_targets)}")
        for tr, ts, hints in problem_targets:
            lines.append(f"  - {tr.target.target_id}: {ts.overall_verdict.value} (score={ts.health_score})")
            if hints:
                lines.append(f"    Likely cause: {hints[0].cause}")
    else:
        lines.append("\nAll targets healthy.")

    lines.append("")

    # Technical detail per target
    lines.append("-" * 70)
    lines.append("TECHNICAL DETAIL")
    lines.append("-" * 70)

    for tr, ts, hints in scored:
        lines.append("")
        loc = tr.target.location or ""
        func = tr.target.function or ""
        header = f"{tr.target.target_id}"
        if loc or func:
            header += f" ({', '.join(filter(None, [loc, func]))})"
        lines.append(f"[{ts.overall_verdict.value}] {header}  — score={ts.health_score}")

        # Probe results
        for pr in tr.probe_results:
            latency = f"{pr.latency_ms:.1f}ms" if pr.latency_ms is not None else "n/a"
            error = f" — {pr.error}" if pr.error else ""
            lines.append(f"  {pr.probe_name:<8} {pr.status.value:<10} {latency}{error}")

        # Hints
        if hints:
            lines.append("  Hints:")
            for hint in hints:
                lines.append(f"    [{hint.confidence}] {hint.cause}")
                for ev in hint.evidence:
                    lines.append(f"      - {ev}")

    # Errors
    if run_result.errors:
        lines.append("")
        lines.append("-" * 70)
        lines.append("ERRORS")
        lines.append("-" * 70)
        for err in run_result.errors:
            lines.append(f"  {err}")

    lines.append("")
    lines.append("=" * 70)
    return "\n".join(lines)


def write_summary(run_result: RunResult, output_path: str) -> str:
    """Write summary to a text file.

    Args:
        run_result: Complete run results.
        output_path: Path to write the summary file.

    Returns:
        The summary text.
    """
    text = generate_summary(run_result)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
    return text
