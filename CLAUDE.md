# CLAUDE.md - Development Guide for InfraHealthProbe

## Project Overview

Infrastructure health detection platform. Inventory-driven probe engine for server, network, and service monitoring across APAC sites. Hybrid architecture: Python platform on Linux, PowerShell endpoint probes on Windows, Python lightweight probes on Raspberry Pi.

## Architecture

```
InfraHealthProbe/
├── platform/                    # Linux control plane (Python)
│   ├── main.py                  # Platform entry point
│   ├── config.py                # Platform configuration
│   ├── inventory/               # Target inventory providers
│   │   ├── core.py              # Normalize, validate, deduplicate, merge
│   │   ├── local_json.py        # JSON file provider
│   │   ├── local_csv.py         # CSV file provider
│   │   └── sharepoint.py        # SharePoint list provider
│   ├── probes/                  # Probe engine
│   │   ├── base.py              # Probe contract (ABC)
│   │   ├── ping.py              # ICMP ping
│   │   ├── dns.py               # DNS resolution timing
│   │   ├── tcp.py               # TCP port check
│   │   ├── http.py              # HTTP/HTTPS response + TLS timing
│   │   ├── ssh.py               # SSH reachability
│   │   └── wifi_adapter.py      # Consumes Collect-WiFiMeetingTest output
│   ├── analytics/               # Verdict, scoring, root-cause hints
│   │   ├── verdict.py           # Per-metric verdict (GOOD/FAIR/POOR/SEVERE)
│   │   ├── scoring.py           # Weighted health score
│   │   ├── hints.py             # Rule-based root-cause hints
│   │   └── summary.py           # Executive / technical summaries
│   ├── ai/                      # AI analysis layer
│   │   ├── client.py            # OpenAI-compatible API caller
│   │   ├── payload.py           # Structured payload builder
│   │   ├── prompts.py           # System/user prompt templates
│   │   └── redaction.py         # Sensitive data masking
│   ├── integrations/            # External system integrations
│   │   └── servicenow.py        # ServiceNow incident creation
│   └── output/                  # Output writers
│       ├── csv_writer.py
│       ├── json_writer.py
│       ├── html_report.py
│       └── manifest.py
│
├── raspi/                       # Raspberry Pi probe agent (Python)
│   ├── main.py                  # Lightweight probe runner
│   ├── wifi_scanner.py          # iwconfig/iw-based WiFi scanning
│   ├── probes.py                # Subset of platform probes
│   └── reporter.py              # Send results to platform
│
├── endpoint/                    # Windows endpoint probe (PowerShell)
│   └── (references Collect-WiFiMeetingTest repo)
│
├── schemas/                     # JSON Schema definitions
├── profiles/                    # Probe profiles per target type
├── inventory/                   # Target inventory data files
├── tests/                       # pytest test suite
├── docs/                        # Architecture and planning docs
└── deploy/                      # Deployment configs (Docker, LiteLLM)
```

## Relationship with Collect-WiFiMeetingTest

The WiFi diagnostics tool (`Collect-WiFiMeetingTest`) remains a **standalone project**. InfraHealthProbe consumes its output (JSONL/CSV) via `wifi_adapter.py` — it does NOT dot-source or import PowerShell internals. The contract between them is the JSONL/CSV column schema (v5.1: 55 columns, append-only).

## Build & Test

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/

# Run platform
python -m platform.main --inventory inventory/targets.json

# Run Raspberry Pi probe
python -m raspi.main --config raspi/config.json
```

## Key Design Decisions

### Probe contract (ABC)
Every probe must implement: `name`, `probe(target) -> ProbeResult`, `timeout_ms`, `expected_fields`. New probes (SSH, SFTP, WebRTC) are added by implementing this interface.

### Inventory provider pattern
All inventory sources (JSON, CSV, SharePoint) normalize to canonical `Target` objects. Probe engine never knows the data source.

### AI is optional, never a dependency
AI analysis runs post-collection, only when explicitly enabled or when verdict is POOR/SEVERE. Platform must function fully without AI.

### Dual-layer diagnostics
Rule engine (analytics/) does evidence organization first. AI (ai/) explains and suggests second. Never raw data -> AI.

### WiFi tool integration is CLI/file-based
Platform triggers WiFi collection via SSH/WinRM/scheduled task on Windows endpoints, then fetches JSONL/CSV output. No PowerShell internals crossing the boundary.

## Language Boundaries

| Component | Language | Platform | Why |
|-----------|----------|----------|-----|
| Platform control plane | Python | Linux | daemon/scheduler/Docker/GPU serving ecosystem |
| Raspberry Pi probes | Python | Linux (ARM) | lightweight, native network tools |
| Windows endpoint probes | PowerShell 5.1 | Windows | netsh, NIC, Teams, power mgmt — Windows-only APIs |

## Testing Strategy (Tiered)

Inspired by gstack's tiered testing approach:

| Tier | Scope | Cost | Speed |
|------|-------|------|-------|
| Tier 1 | Inventory, analytics, verdict unit tests | Free | Seconds |
| Tier 2 | Real network probe integration tests | Free (needs network) | Minutes |
| Tier 3 | AI analysis quality evaluation (LLM-as-judge) | API cost | Minutes |

Run Tier 1 first. Only run Tier 3 when AI modules change.

## Architecture Reference: gstack Patterns

Analysis of [garrytan/gstack](https://github.com/garrytan/gstack) (v0.9.9) identified patterns applicable to this project:

### Adopted patterns

- **Probe contract registry** — gstack uses a single command registry (`commands.ts`) shared by server, validator, and tests. Our `BaseProbe` ABC serves the same purpose; extend with auto-discovery in `platform/probes/__init__.py`.
- **File-based coordination** — gstack agents coordinate via git + files, not IPC. Same as our WiFi tool integration (JSONL/CSV contract) and Linux↔Windows↔Raspberry Pi boundary.
- **Tiered testing** — Tier 1 free/fast (unit), Tier 2 network-dependent (integration), Tier 3 paid (AI eval). Prevents wasting API cost on every test run.
- **Circular buffer for long-running probe** — gstack uses ring buffers for console/network logs in its persistent daemon. Apply to platform daemon mode for bounded probe result history.

### Noted but not adopted

- **Persistent headless browser** — gstack's core is a Chromium daemon for QA. Not needed; our HTTP probe uses `urllib`/`httpx` for URL checks. If deep URL content validation is needed later, consider adding a lightweight `content_check` option to `HttpProbe` (keyword matching in response body) rather than a full browser.
- **Markdown skill system** — gstack's 25 workflow skills simulate team roles (CEO, QA, designer). Not applicable; InfraHealthProbe is a platform, not an AI dev assistant.
- **Conductor multi-agent orchestration** — gstack uses Conductor to run 10-15 parallel Claude Code sessions in git worktrees. Our platform IS the orchestrator (scheduler + probe dispatcher), so external agent coordination is not needed.

### Multi-agent philosophy (from gstack)

gstack proves that multi-component coordination doesn't need complex frameworks:
- **Git + files + structured process** is sufficient
- Each component (Linux platform, Windows probe, Raspberry Pi) runs independently
- Coordination happens through shared schemas and file contracts
- This matches our architecture: independent runtimes, canonical data models, file-based integration

## Git Workflow

- `main`: stable releases
- Feature branches for development, merge to `main` via PR
