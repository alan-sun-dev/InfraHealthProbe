"""HTML report generator — standalone single-file HTML report."""

from __future__ import annotations

from pathlib import Path

from ..runner import RunResult
from ..probes.base import ProbeStatus
from ..analytics.scoring import score_target
from ..analytics.hints import get_hints
from ..analytics.verdict import Verdict


def _verdict_color(verdict: Verdict) -> str:
    return {
        Verdict.GOOD: "#22c55e",
        Verdict.FAIR: "#eab308",
        Verdict.POOR: "#f97316",
        Verdict.SEVERE: "#ef4444",
        Verdict.UNKNOWN: "#6b7280",
    }.get(verdict, "#6b7280")


def _status_color(status: ProbeStatus) -> str:
    return {
        ProbeStatus.OK: "#22c55e",
        ProbeStatus.DEGRADED: "#eab308",
        ProbeStatus.FAILED: "#ef4444",
        ProbeStatus.TIMEOUT: "#f97316",
        ProbeStatus.ERROR: "#ef4444",
        ProbeStatus.SKIPPED: "#6b7280",
    }.get(status, "#6b7280")


def _esc(text: str) -> str:
    """HTML-escape a string."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def write_html_report(run_result: RunResult, output_dir: str | Path) -> Path:
    """Generate a standalone HTML report.

    Args:
        run_result: Complete run results.
        output_dir: Directory to write the HTML file.

    Returns:
        Path to the written HTML file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filepath = output_dir / f"InfraHealthProbe_{run_result.run_id}_report.html"

    # Score all targets
    scored = []
    for tr in run_result.target_results:
        ts = score_target(tr.target.target_id, tr.probe_results)
        hints = get_hints(tr.target.target_id, tr.probe_results)
        scored.append((tr, ts, hints))

    scores = [ts.health_score for _, ts, _ in scored]
    avg_score = round(sum(scores) / len(scores)) if scores else 0
    worst_score = min(scores) if scores else 0

    # Build HTML
    html_parts: list[str] = []
    html_parts.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>InfraHealthProbe Report — {_esc(run_result.run_id)}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #f8fafc; color: #1e293b; padding: 24px; }}
  .container {{ max-width: 1200px; margin: 0 auto; }}
  h1 {{ font-size: 24px; margin-bottom: 8px; }}
  h2 {{ font-size: 18px; margin: 24px 0 12px; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; }}
  .meta {{ color: #64748b; font-size: 14px; margin-bottom: 20px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 24px; }}
  .card {{ background: #fff; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); text-align: center; }}
  .card .value {{ font-size: 32px; font-weight: 700; }}
  .card .label {{ font-size: 12px; color: #64748b; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden;
           box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 16px; }}
  th {{ background: #f1f5f9; text-align: left; padding: 10px 12px; font-size: 13px; font-weight: 600; color: #475569; }}
  td {{ padding: 10px 12px; border-top: 1px solid #e2e8f0; font-size: 13px; }}
  tr:hover {{ background: #f8fafc; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; color: #fff; }}
  .hint {{ background: #fffbeb; border-left: 3px solid #f59e0b; padding: 8px 12px; margin: 6px 0; font-size: 13px; border-radius: 0 4px 4px 0; }}
  .hint .conf {{ color: #92400e; font-weight: 600; }}
  .evidence {{ color: #64748b; font-size: 12px; margin-left: 16px; }}
  .footer {{ margin-top: 32px; text-align: center; color: #94a3b8; font-size: 12px; }}
</style>
</head>
<body>
<div class="container">
<h1>InfraHealthProbe Report</h1>
<div class="meta">
  Run: {_esc(run_result.run_id)} &nbsp;|&nbsp;
  Profile: {_esc(run_result.profile_name)} &nbsp;|&nbsp;
  {_esc(run_result.start_time_utc)} &mdash; {_esc(run_result.end_time_utc)} &nbsp;|&nbsp;
  {run_result.elapsed_ms:.0f}ms
</div>
""")

    # Summary cards
    ok_targets = sum(1 for _, ts, _ in scored if ts.overall_verdict == Verdict.GOOD)
    problem_targets = sum(1 for _, ts, _ in scored if ts.overall_verdict in (Verdict.POOR, Verdict.SEVERE))
    total_probes = run_result.total_probes
    ok_probes = sum(tr.ok_count for tr in run_result.target_results)

    html_parts.append(f"""
<div class="cards">
  <div class="card"><div class="value">{run_result.target_count}</div><div class="label">Targets</div></div>
  <div class="card"><div class="value" style="color:{_verdict_color(Verdict.GOOD)}">{ok_targets}</div><div class="label">Healthy</div></div>
  <div class="card"><div class="value" style="color:{_verdict_color(Verdict.SEVERE) if problem_targets else _verdict_color(Verdict.GOOD)}">{problem_targets}</div><div class="label">Problems</div></div>
  <div class="card"><div class="value">{avg_score}</div><div class="label">Avg Score</div></div>
  <div class="card"><div class="value">{ok_probes}/{total_probes}</div><div class="label">Probes OK</div></div>
</div>
""")

    # Target overview table
    html_parts.append("<h2>Target Overview</h2>\n<table>\n<tr><th>Target</th><th>Location</th><th>Function</th><th>Verdict</th><th>Score</th><th>Probes</th><th>Elapsed</th></tr>\n")
    for tr, ts, hints in scored:
        color = _verdict_color(ts.overall_verdict)
        html_parts.append(
            f'<tr><td><strong>{_esc(tr.target.target_id)}</strong></td>'
            f'<td>{_esc(tr.target.location)}</td>'
            f'<td>{_esc(tr.target.function)}</td>'
            f'<td><span class="badge" style="background:{color}">{ts.overall_verdict.value}</span></td>'
            f'<td>{ts.health_score}</td>'
            f'<td>{tr.ok_count}/{len(tr.probe_results)}</td>'
            f'<td>{tr.elapsed_ms:.0f}ms</td></tr>\n'
        )
    html_parts.append("</table>\n")

    # Per-target detail
    html_parts.append("<h2>Probe Details</h2>\n")
    for tr, ts, hints in scored:
        color = _verdict_color(ts.overall_verdict)
        html_parts.append(
            f'<h3 style="margin-top:20px">'
            f'<span class="badge" style="background:{color}">{ts.overall_verdict.value}</span> '
            f'{_esc(tr.target.target_id)} — score={ts.health_score}</h3>\n'
        )

        html_parts.append("<table>\n<tr><th>Probe</th><th>Status</th><th>Latency</th><th>Details</th></tr>\n")
        for pr in tr.probe_results:
            sc = _status_color(pr.status)
            latency = f"{pr.latency_ms:.1f}ms" if pr.latency_ms is not None else "—"
            detail = _esc(pr.error or pr.detail or "")
            html_parts.append(
                f'<tr><td>{_esc(pr.probe_name)}</td>'
                f'<td><span class="badge" style="background:{sc}">{pr.status.value}</span></td>'
                f'<td>{latency}</td>'
                f'<td>{detail}</td></tr>\n'
            )
        html_parts.append("</table>\n")

        # Hints
        if hints:
            for hint in hints:
                html_parts.append(
                    f'<div class="hint"><span class="conf">[{_esc(hint.confidence)}]</span> '
                    f'{_esc(hint.cause)}'
                )
                for ev in hint.evidence:
                    html_parts.append(f'<div class="evidence">— {_esc(ev)}</div>')
                html_parts.append("</div>\n")

    # Footer
    html_parts.append(f"""
<div class="footer">
  Generated by InfraHealthProbe v0.1.0
</div>
</div>
</body>
</html>""")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("".join(html_parts))

    return filepath
