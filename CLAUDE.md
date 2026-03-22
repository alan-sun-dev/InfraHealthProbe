# CLAUDE.md - Development Guide for InfraHealthProbe

## Project Overview

Infrastructure health detection platform. Inventory-driven probe engine for server, network, and service monitoring across APAC sites.

## Architecture

```
InfraHealthProbe/
├── infra/                       # Core platform (Python 3.10+)
│   ├── __main__.py              # python -m infra
│   ├── cli.py                   # CLI entry point (argparse)
│   ├── config.py                # Profile loading + CLI merge
│   ├── runner.py                # Probe dispatcher (ThreadPoolExecutor)
│   ├── inventory/               # Target inventory providers
│   │   ├── core.py              # Target dataclass, validate, deduplicate, merge, filter
│   │   ├── local_json.py        # JSON file provider
│   │   └── local_csv.py         # CSV file provider
│   ├── probes/                  # Probe engine
│   │   ├── __init__.py          # Probe registry (PROBE_REGISTRY, get_probe, list_probes)
│   │   ├── base.py              # BaseProbe ABC + ProbeResult + ProbeStatus
│   │   ├── ping.py              # ICMP ping (Linux/Windows)
│   │   ├── dns.py               # DNS resolution timing
│   │   ├── tcp.py               # TCP port check (multi-port)
│   │   ├── http.py              # HTTP/HTTPS response + TLS timing
│   │   ├── ssh.py               # SSH reachability + banner detection
│   │   └── wifi_adapter.py      # Consumes Collect-WiFiMeetingTest JSONL/CSV output
│   ├── analytics/               # Verdict, scoring, root-cause hints
│   │   ├── verdict.py           # Per-metric verdict (GOOD/FAIR/POOR/SEVERE)
│   │   ├── scoring.py           # Weighted health score per target
│   │   ├── hints.py             # Rule-based root-cause hints (7 rules)
│   │   └── summary.py           # Executive + technical summary text
│   ├── output/                  # Output writers
│   │   ├── csv_writer.py        # ProbeResult → CSV (fixed column order)
│   │   ├── json_writer.py       # ProbeResult → JSON Lines
│   │   ├── html_report.py       # Standalone HTML report (inline CSS)
│   │   └── manifest.py          # Run metadata → JSON
│   └── scheduler.py             # Scheduled mode (repeating probe cycles)
│
├── schemas/                     # JSON Schema definitions
├── profiles/                    # Probe profiles per target type
├── inventory/                   # Target inventory data files
├── tests/                       # pytest test suite
└── docs/                        # Architecture and planning docs
```

### Why `infra/` not `platform/`

`platform` is a Python standard library module. Using it as a package name causes import conflicts.

### Modules added later (not in initial scaffold)

These will be created when their milestone is reached:

- `infra/output/` — CSV, JSON, HTML writers (M1)
- `infra/analytics/scoring.py`, `hints.py`, `summary.py` — diagnostics intelligence (M2)
- `infra/ai/` — LLM analysis layer (M4)
- `infra/integrations/` — ServiceNow, SharePoint (M4)
- `raspi/` — Raspberry Pi probe agent (M4)

## Relationship with Collect-WiFiMeetingTest

The WiFi diagnostics tool (`Collect-WiFiMeetingTest`) remains a **standalone project**. InfraHealthProbe consumes its output (JSONL/CSV) via `wifi_adapter.py` — it does NOT dot-source or import PowerShell internals. The contract between them is the JSONL/CSV column schema (v5.1: 55 columns, append-only).

## Build & Test

```bash
# Install dependencies
pip install -e ".[dev]"

# Run all tests (Tier 1 — no network required)
pytest tests/

# Run specific test file
pytest tests/test_inventory.py
pytest tests/test_probes.py
pytest tests/test_config.py

# Run platform
python -m infra --inventory inventory/targets.json --output-dir ./output

# Run with filters
python -m infra -i inventory/targets.json --location Taiwan --probes ping dns

# Run with custom profile
python -m infra -i inventory/targets.json -p profiles/default.json -o ./output

# Scheduled mode (repeat every 5 minutes, Ctrl+C to stop)
python -m infra -i inventory/targets.json --mode scheduled --interval 5
```

## Development Milestones

| Milestone | Focus | Deliverable |
|-----------|-------|-------------|
| M0 | Foundation | `infra/` rename, probe registry, profile loader |
| M1 | Can run | cli.py, runner.py, CSV output, manifest |
| M2 | Has diagnostic value | scoring, hints, summary, JSON output |
| M3 | Operational | scheduled mode, HTML report, retry logic |
| M4 | Extensions | AI, ServiceNow, SharePoint, Raspberry Pi |

**Principle: each milestone produces a usable tool.** Don't jump ahead.

## Key Design Decisions

### Probe contract (ABC)
Every probe implements: `name`, `probe(target) -> ProbeResult`, `timeout_ms`, `expected_fields`. New probes are added by implementing `BaseProbe` and registering in `PROBE_REGISTRY`.

### Probe registry
`infra/probes/__init__.py` maintains `PROBE_REGISTRY: dict[str, type[BaseProbe]]`. Use `get_probe("ping")` to instantiate, `list_probes()` to enumerate.

### Profile system
`profiles/*.json` define which probes to run, timeouts, and thresholds per target type. `infra/config.py` loads profiles and merges CLI overrides. Probes check `profile.is_probe_enabled(name)` before execution.

### Inventory provider pattern
All inventory sources (JSON, CSV, future SharePoint) normalize to canonical `Target` dataclass. Probe engine never knows the data source.

### AI is optional, never a dependency
AI analysis runs post-collection, only when explicitly enabled or when verdict is POOR/SEVERE. Platform must function fully without AI.

### WiFi tool integration is CLI/file-based
Platform triggers WiFi collection via SSH/WinRM/scheduled task on Windows endpoints, then fetches JSONL/CSV output. No PowerShell internals crossing the boundary.

## Testing Strategy (Tiered)

| Tier | Scope | Cost | Speed |
|------|-------|------|-------|
| Tier 1 | Inventory, analytics, config, probe registry | Free | Seconds |
| Tier 2 | Real network probe integration tests | Free (needs network) | Minutes |
| Tier 3 | AI analysis quality evaluation | API cost | Minutes |

Run Tier 1 first. Only run Tier 3 when AI modules change.

## Architecture Reference

See `docs/reference-gstack-analysis.md` for patterns adopted from garrytan/gstack:
- Probe contract registry (single source of truth)
- File-based coordination (git + shared schemas)
- Tiered testing (free/fast → paid/thorough)
- Multi-component philosophy (independent runtimes, canonical data models)

## Git Workflow

- `main`: stable releases
- Feature branches for development, merge to `main` via PR
