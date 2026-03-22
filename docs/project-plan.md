# Collect-WiFiMeetingTest v6 Project Plan

> Based on architecture research discussion (2026-03-22)
> Source: ChatGPT conversation "專案分析與架構研究"

---

## 1. Current State Assessment (v5.1)

**Overall Rating: 8.5/10**

### Strengths
1. **Field-friendly** - 10-min default collection, batch launcher, zero-install on PS 5.1
2. **Layered diagnostics** - Wi-Fi + LAN + WAN + DNS + TCP + HTTPS + system + meeting app
3. **Centralized config** - shared `Get-WiFiTestVerdict`, thresholds, display in `WiFiTest.Config.ps1`
4. **Test coverage** - 131 Pester tests across 5 test files
5. **Report-oriented** - CSV, JSONL, HTML report, compare overlay tool

### Limitations
1. Endpoint diagnostic tool, not a monitoring platform
2. HTTPS probe is diagnostic-only (accepts any cert)
3. PS 5.1 compatibility is both strength and ceiling
4. Repo maturity is internal-tool level (no releases/tags)

---

## 2. v6 Vision

**From single-run field diagnostics tool to a reusable, schedulable, extensible Wi-Fi/meeting diagnostics engine.**

Four pillars:
1. **Engine-ization** - clearer collector/probe/output/report boundaries
2. **Data model stabilization** - fixed schema, shared across all outputs
3. **Operational readiness** - baselines, scheduled runs, site metadata, batch comparison
4. **Extensibility** - pluggable probes without modifying core flow

---

## 3. v6 Roadmap

### Phase 1: v6.0 Core Stabilization

| Item | Description |
|------|-------------|
| Unified schema | `SchemaVersion`, `RunId`, `SampleId`, `TimestampUtc`, stable field set |
| Pipeline orchestration | Main script becomes `Initialize → Collect → Publish → Finalize` flow |
| Config separation | Split thresholds, defaults, rendering, verdict into dedicated modules |
| Internal sample object | All writers consume the same normalized object |
| Run manifest | `manifest.json` with tool version, profile, timings, output paths |

### Phase 2: v6.1 Diagnostics Intelligence

| Item | Description |
|------|-------------|
| Root-cause hint engine | Rule-based: signal+gateway → local RF, gateway OK + WAN bad → upstream, etc. |
| Baseline comparison | Compare current run vs historical/golden baseline |
| Executive summary | One-sentence conclusion + 3 key findings |
| Technical summary | Metric anomaly detail + time windows + suspected direction |

### Phase 3: v6.2 Fleet / Site Mode

| Item | Description |
|------|-------------|
| Site profiles | JSON profiles per site/room with targets, thresholds, expectations |
| Scheduled mode | `-Mode Scheduled` for Task Scheduler / cron recurring execution |
| Run modes | `OneShot`, `Scheduled`, `Report`, `Compare`, `Baseline` |
| Retention | Archive/cleanup policy for old runs |

### Phase 4: v6.5 Extension Platform

| Item | Description |
|------|-------------|
| Probe contract | Each probe implements: `Name`, `Invoke`, `Normalize`, `TimeoutMs`, `Enabled`, `ExpectedFields` |
| New probes | WebRTC preflight, iperf3, SSH/SFTP, captive portal, M365 connectivity |
| Enterprise adapters | ELK/Grafana/Power BI export adapters |

---

## 4. Module Restructuring

### Current (v5.1)
```
Config → Probes → Collectors → Output → Report → Compare
```

### Proposed (v6)
```
Collect-WiFiMeetingTest/
├─ Collect-WiFiMeetingTest.ps1          # thin entrypoint
├─ Convert-WiFiTestToReport.ps1         # thin entrypoint
├─ Compare-WiFiTestReports.ps1          # thin entrypoint
├─ WiFiTest-Launcher.bat
│
├─ modules/
│  ├─ WiFiTest.Core.ps1                 # orchestration, run context, lifecycle
│  ├─ WiFiTest.Schema.ps1               # sample/event/manifest object factories
│  ├─ WiFiTest.Defaults.ps1             # default values, naming, fallbacks
│  ├─ WiFiTest.Profiles.ps1             # profile load/merge/validate
│  ├─ WiFiTest.Analytics.ps1            # verdict, scoring, hints, summaries
│  │
│  ├─ probes/
│  │  ├─ WiFiTest.Probes.Network.ps1    # ping, DNS, TCP
│  │  ├─ WiFiTest.Probes.Https.ps1      # HTTPS timing
│  │  └─ WiFiTest.Probes.App.ps1        # meeting app metrics
│  │
│  ├─ collectors/
│  │  ├─ WiFiTest.Collectors.Wlan.ps1   # netsh parse, locale handling
│  │  ├─ WiFiTest.Collectors.System.ps1 # CPU, memory, processes
│  │  ├─ WiFiTest.Collectors.Nic.ps1    # NIC counters
│  │  └─ WiFiTest.Collectors.Power.ps1  # power plan, adapter power save
│  │
│  ├─ output/
│  │  ├─ WiFiTest.Output.Csv.ps1
│  │  ├─ WiFiTest.Output.Json.ps1
│  │  ├─ WiFiTest.Output.Events.ps1
│  │  ├─ WiFiTest.Output.Log.ps1
│  │  └─ WiFiTest.Output.Summary.ps1
│  │
│  └─ reporting/
│     ├─ WiFiTest.Reporting.Html.ps1
│     ├─ WiFiTest.Reporting.Compare.ps1
│     └─ WiFiTest.Reporting.Summary.ps1
│
├─ profiles/
│  ├─ Default.json
│  └─ {site-specific}.json
│
├─ schemas/
│  ├─ sample.schema.json
│  ├─ event.schema.json
│  ├─ manifest.schema.json
│  └─ profile.schema.json
│
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  └─ fixtures/
│     ├─ netsh-en-us.txt
│     ├─ netsh-zh-tw.txt
│     ├─ netsh-ja-jp.txt
│     └─ netsh-ko-kr.txt
│
├─ docs/
└─ examples/
```

### Key Design Patterns

**Thin entrypoints** - main scripts only dot-source modules and call `Start-*`:
```powershell
. "$PSScriptRoot\modules\WiFiTest.Core.ps1"
Start-WiFiTestCollection @PSBoundParameters
```

**Single writer pattern** - all outputs derive from one normalized sample object:
```powershell
$sample = New-WiFiSampleObject ...
Publish-WiFiSample -Sample $sample  # dispatches to CSV, JSON, events, summary
```

**Verdict → scoring engine** - upgrade from helper to full analytics:
- `Get-WiFiMetricVerdict` - per-field verdict
- `Get-WiFiSampleScore` - weighted health score (0-100)
- `Get-WiFiRootCauseHints` - rule-based probable causes
- `Get-WiFiRunScore` - overall run quality
- `Get-WiFiRunExecutiveSummary` / `Get-WiFiRunTechnicalSummary`

---

## 5. Data Models

### Sample Object
Key fields: `SchemaVersion`, `RunId`, `SampleId`, `TimestampUtc`, `SiteCode`, `ProfileName`, Wi-Fi metrics (SSID, BSSID, Signal, RSSI, Channel, Band, RadioType, change flags), network metrics (Gateway/WAN/DNS/TCP/HTTPS latency, jitter, loss), endpoint metrics (CPU, Memory, NIC, MeetingProcess), power state, per-metric verdicts, `HealthScore`, `OverallVerdict`, `EventIds`.

### Event Object
Fields: `SchemaVersion`, `RunId`, `EventId`, `SampleId`, `TimestampUtc`, `Severity`, `Category`, `RuleName`, `Message`, `MetricName`, `MetricValue`, `Threshold`, `RootCauseHint`.

### Manifest Object
Fields: `SchemaVersion`, `ToolVersion`, `RunId`, `ProfileName`, `HostName`, `Locale`, `StartTimeUtc`, `EndTimeUtc`, `IntervalSeconds`, `DurationMinutes`, `SampleCount`, `EventCount`, `Warnings`, `Errors`, `OutputFiles`, `ProfileSnapshot`.

### Profile JSON
Site/room-specific configuration: targets (gateway, WAN, DNS, TCP, HTTPS), process names, thresholds (per-metric GOOD/FAIR/POOR), weights (per-metric scoring weight), expectations (preferred band, power plan), probe enable/disable flags.

---

## 6. AI Integration (WiFiTest.AI.ps1)

### Architecture Decision
**Dual-layer: rule engine first, LLM explains** (not raw CSV → AI)

```
Collectors/Probes → Analytics.ps1 → Structured JSON payload → LLM API → Human-readable advice
```

### Recommended Stack
```
WiFiTest.AI.ps1 → LiteLLM Proxy → vLLM Server → gpt-oss-120b
```

- **LiteLLM**: OpenAI-compatible gateway with model alias routing, fallback, auth
- **vLLM**: inference backend serving the model
- **gpt-oss-120b**: internal 120B open-weight model (suitable as explanation layer: 9/10)

### Module Functions
| Function | Purpose |
|----------|---------|
| `Test-WiFiAiConfiguration` | Validate endpoint/key/model settings |
| `Protect-WiFiAiSensitiveData` | Redact hostname, username, SSID, BSSID, internal IPs |
| `New-WiFiAiPayload` | Build structured JSON from analytics results |
| `Get-WiFiAiSystemPrompt` | Conservative system prompt (evidence-only, JSON output) |
| `Invoke-WiFiAiAnalysis` | POST to OpenAI-compatible API |
| `Convert-WiFiAiResponseToObject` | Parse JSON response with fallback |
| `Write-WiFiAiSummary` | Output to ai-summary.txt |

### AI Output Structure
```json
{
  "executive_summary": "string",
  "technical_summary": "string",
  "probable_causes": [{ "cause": "", "confidence": "high|medium|low", "evidence": [] }],
  "recommended_actions": ["string"],
  "follow_up_checks": ["string"],
  "limitations": ["string"]
}
```

### Trigger Conditions
AI analysis runs only when:
- `-UseAI` explicitly specified, OR
- `OverallVerdict = POOR / SEVERE`, OR
- `EventCount >= threshold`

### POC Validation
5 test cases designed to validate model suitability:
1. Local Wi-Fi/RF issue (signal poor + gateway poor + roaming)
2. Upstream WAN issue (signal good + gateway good + WAN/HTTPS poor)
3. DNS resolver issue (ping/WAN OK + DNS very slow)
4. Endpoint bottleneck (network OK + CPU/memory high)
5. Mixed/insufficient evidence (tests model honesty)

Pass criteria: 5/5 valid JSON, 4/5 correct primary cause, POC-5 acknowledges uncertainty.

### LiteLLM Configuration
```yaml
model_list:
  - model_name: wifi-diagnostics-primary
    litellm_params:
      model: openai/gpt-oss-120b
      api_base: "http://vllm-server:8000/v1"

router_settings:
  num_retries: 2
  timeout: 90
  fallbacks:
    - wifi-diagnostics-primary: ["wifi-diagnostics-fallback"]
```

PowerShell client connects to LiteLLM (not vLLM directly):
```powershell
$AiEndpoint = "http://litellm.internal:4000/v1/chat/completions"
$AiModel    = "wifi-diagnostics-primary"
```

---

## 7. ServiceNow Integration (WiFiTest.ServiceNow.ps1)

### Approach
REST API `POST /now/table/incident` (recommended over email or browser automation).

### Module Functions
- `Test-WiFiServiceNowConfiguration`
- `New-WiFiServiceNowIncidentPayload`
- `Invoke-WiFiServiceNowCreateIncident`
- `Add-WiFiServiceNowWorkNote`
- `Write-WiFiServiceNowResult`

### Trigger Logic
Auto-create incident when:
- `OverallVerdict = POOR / SEVERE`
- `EventCount >= threshold`
- AI recommends escalated follow-up
- `-CreateServiceNowIncident` explicitly specified

### Incident Payload
- `short_description`: "Wi-Fi diagnostics detected degraded quality at {site} {room}"
- `description`: executive + technical summary + key metrics
- `work_notes`: AI recommendations, follow-up checks
- `category/subcategory`: Network / Wireless
- Custom fields: `u_health_score`, `u_run_id`, `u_report_path`

---

## 8. Platform Expansion Vision

### From WiFi Tool to Infrastructure Health Platform

```
Diagnostics Platform
├─ Endpoint Diagnostics (WiFi / meeting quality)
├─ Server Diagnostics (host / port / service / URL checks)
├─ Network Diagnostics (latency / DNS / route / availability)
├─ Analytics (verdict / scoring / correlation / hints)
├─ AI Layer (human-readable analysis / next steps)
└─ Ticketing / Reporting (ServiceNow / HTML / CSV / Email)
```

### 4-Layer Architecture
1. **Inventory** - target catalog (type, location, function, hostname, FQDN, IP, OS, URLs, ports, probe profile)
2. **Probe** - active checks (ping, DNS, TCP, HTTP/HTTPS, SSH, URL validation, service checks)
3. **Analytics** - target health score, service verdict, location summary, outage correlation
4. **Output/Action** - report, alert, AI summary, ServiceNow ticket

### Probe Profiles
- `clearance-system-linux`: ping, DNS, TCP 80/443, URL response, login page reachable
- `cache-server-linux`: ping, DNS, TCP 80/443/22, cache URL, latency trend
- `edi-server-windows`: ping, DNS, TCP 135/445/3389/app ports, WinRM/service checks

### Expansion Phases
1. **Server/Service Probe** - inventory-driven, multi-target, ping/DNS/TCP/HTTP
2. **Site/Role Analytics** - location summary, function summary, outage correlation
3. **AI + Ticketing** - AI analysis, ServiceNow incident creation
4. **Deep Service Checks** - SSH/WinRM, service status, process checks

---

## 9. Linux Migration Strategy

### Conclusion: "Platform on Linux, endpoint insight on Windows"

```
[Linux Control Node]                [Windows Endpoint Probe]
├─ Scheduler / Cron                 └─ Collect-WiFiMeetingTest.ps1
├─ Inventory management                 ├─ WLAN parsing
├─ Server/service probes                 ├─ Meeting app metrics
├─ Analytics                             ├─ NIC/power management
├─ LiteLLM / vLLM / AI                  └─ Windows-specific collectors
├─ ServiceNow integration
├─ Reporting / Dashboard
└─ Result storage
```

### What stays on Windows (cannot migrate)
- `netsh wlan show interfaces` parsing
- Teams/Zoom/WebEx process metrics
- Windows NIC counters, power plan, adapter power saving
- Endpoint meeting experience context

### What moves to Linux
- Inventory loader, probe scheduler
- Generic network probes (ping/DNS/TCP/HTTP)
- Service URL validation, result aggregation
- LiteLLM, vLLM, AI analysis
- ServiceNow REST integration
- HTML/JSON output, reporting

### Language Strategy
- Phase 1: PowerShell 7 cross-platform for shared modules
- Phase 2: Consider Python for platform control plane (after architecture stabilizes)

---

## 10. Inventory Modularization

### Provider/Plugin Architecture

```
Inventory Providers
├─ Local JSON Provider
├─ Local CSV Provider
└─ SharePoint Provider
         ↓
Inventory Core (normalize, validate, deduplicate, merge)
         ↓
Canonical Target Objects
         ↓
Probe Engine
```

### Canonical Target Schema
```json
{
  "TargetId": "TW-TPEIP-CACHE-YAMI",
  "Type": "Export",
  "Location": "Taiwan/TPEIP",
  "Function": "Local Cache Server",
  "Hostname": "yami",
  "FQDN": "yami.oth.apac.fedex.com",
  "IPAddress": "155.161.252.18",
  "OS": "Linux",
  "Urls": [],
  "Ports": [80, 443, 22],
  "ProbeProfile": "cache-server-linux",
  "Enabled": true,
  "Priority": "Normal",
  "OwnerGroup": "ACCS"
}
```

### Dispatcher Pattern
```powershell
Import-WiFiInventory -SourceType LocalJson  -Path .\targets.json
Import-WiFiInventory -SourceType LocalCsv   -Path .\targets.csv
Import-WiFiInventory -SourceType SharePoint  -SiteUrl ... -ListName ...
```

### Multi-Source Merge
- SharePoint = production inventory
- Local JSON = overrides, lab targets, maintenance flags
- Merge: `SharePoint + local override = effective inventory`

### Implementation Phases
1. **v1**: Local JSON + CSV providers
2. **v2**: SharePoint provider (Graph API / REST)
3. **v3**: Multi-source merge with local overrides

---

## 11. Migration Plan (v5.1 → v6.0)

### Phase A: Preserve existing CLI
- Create `modules/` directory
- Move functions from old scripts into new modules
- Old entrypoints become thin wrappers (dot-source + call)
- Keep parameter names unchanged

### Phase B: Schema first
- Add `RunId`, `SchemaVersion`, `Manifest`
- Report, compare, JSON export all benefit immediately

### Phase C: Split analytics
- Move `Get-WiFiTestVerdict` from Config to `WiFiTest.Analytics.ps1`
- Add scoring, root-cause hints

### Phase D: Isolate netsh parser
- Extract regex-based multi-locale parsing into dedicated module
- Add fixture tests (EN, ZH-TW, JA, KO, corrupted encoding)

### Phase E: Single writer pattern
- All CSV/JSON/events/summary output through normalized sample object

---

## 12. Priority Matrix

### Must-do first (highest ROI)
1. `SchemaVersion` + `RunId` in all outputs
2. Profile JSON system
3. Internal normalized sample object
4. Analytics module (split from Config)
5. netsh parser modularization with fixture tests
6. Run manifest
7. Executive / technical summary engine

### Should-do next
8. Baseline comparison mode
9. Compare tool upgrade (pairwise, baseline, group)
10. Scheduled mode

### Can-do later
11. AI integration (WiFiTest.AI.ps1)
12. ServiceNow module
13. Platform expansion (server/service probes)
14. Linux control plane
15. Plugin-style probe contract

---

## 13. Design Principles

### Do
- Keep PowerShell 5.1 compatibility on the main line
- Keep single-machine, zero-install deployment as default
- Stabilize core schema before adding features
- Let profile, analytics, reporting evolve independently
- Maintain "field engineer picks it up and runs it" simplicity

### Don't
- Don't rewrite as class-heavy framework
- Don't rush to PowerShell 7 only
- Don't build a server platform from day one
- Don't mix report logic back into collector logic
- Don't let AI become a core dependency (always optional)

---

## 14. Naming Considerations (Future)

If the project expands beyond WiFi diagnostics:
- `InfraHealthProbe`
- `Collect-NetworkServiceHealth`
- `SiteServiceHealthMonitor`

Current WiFi repo becomes a sub-module of the larger platform.

---

## Appendix: Key Architecture Diagrams

### AI Integration Flow
```
Collectors/Probes → Normalized Samples → Analytics.ps1 (verdicts/scores/hints)
    → WiFiTest.AI.ps1 (payload builder + redaction)
    → POST /v1/chat/completions → LiteLLM Proxy → vLLM → gpt-oss-120b
    → AI Response → Parse JSON → ai-summary.txt / report.html
```

### Platform Expansion Flow
```
Inventory (JSON/CSV/SharePoint) → Normalize/Validate
    → Probe Engine (ping/DNS/TCP/HTTP/HTTPS/SSH)
    → Analytics (health score/verdict/correlation)
    → Output (Report/Alert/AI Summary/ServiceNow Ticket)
```
