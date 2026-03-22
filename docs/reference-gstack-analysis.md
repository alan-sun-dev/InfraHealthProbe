# gstack Architecture Analysis

> Reference analysis of [garrytan/gstack](https://github.com/garrytan/gstack) v0.9.9 (2026-03-22)
> Purpose: Identify patterns applicable to InfraHealthProbe development

---

## 1. What is gstack

gstack is an AI engineering workflow system by Garry Tan (Y Combinator CEO). It enables single developers to build at scale with Claude Code through:

1. **Persistent headless browser daemon** — Playwright + Bun, 100-200ms latency, 50+ commands
2. **25 workflow skills** — Markdown-based prompts acting as virtual team members (CEO reviewer, eng manager, designer, QA lead, release engineer, debugger, etc.)
3. **Multi-agent parallelism** — via Conductor, 10-15 Claude Code sessions in git worktrees

Tech stack: TypeScript (Bun runtime), Playwright, Markdown skills. ~4,400 LOC browser + ~14,700 LOC skills.

---

## 2. Core Architecture

### Browser Daemon

```
Claude Code                     gstack
───────────────────────────────────────────
Tool call: $B snapshot   →     CLI binary (compiled)
                               ├─ Read .gstack/browse.json (port, token)
                               ├─ Health check existing server
                               └─ POST /command → localhost:port

                               ↓ HTTP (Bearer token auth)

                               Bun HTTP Server (server.ts)
                               ├─ Router: dispatch to command handlers
                               ├─ CircularBuffer: console/network/dialog logs
                               ├─ Idle timeout: 30 min (auto-shutdown)
                               └─ State file: .gstack/browse.json

                               ↓ CDP (Chrome DevTools Protocol)

                               Chromium (headless, persistent context)
```

First call starts server (~3s cold). Subsequent calls ~100ms. Persistent browser preserves login sessions, tabs, and cookies across commands.

### Skill System

25 skills deployed as Markdown files with YAML frontmatter. Each 400-1000 lines with structured workflows. Categories:

| Category | Skills |
|----------|--------|
| Planning | office-hours, plan-ceo-review, plan-eng-review, plan-design-review |
| Design | design-consultation, design-review |
| Development | review (code review), investigate (debugging), qa (QA testing) |
| Deployment | ship, land-and-deploy, canary, benchmark |
| Safety | careful, freeze, guard, unfreeze |
| Utilities | setup-browser-cookies, setup-deploy, document-release, retro |

Skills are template-driven (`.tmpl` → auto-generated `SKILL.md`), ensuring docs stay in sync with code.

---

## 3. Multi-Agent Collaboration Model

### Architecture: Conductor + Git Worktree

```
Conductor (external orchestrator)
├─ Worktree 1: Claude Code + /office-hours    ← brainstorm new feature
├─ Worktree 2: Claude Code + /review          ← review a PR
├─ Worktree 3: Claude Code + /qa              ← QA testing on staging
├─ Worktree 4: Claude Code + /ship            ← deploy to production
├─ ...
└─ Worktree 10-15: more parallel sprints
```

Each agent is a **completely independent Claude Code session**:
- Own working directory (git worktree)
- Own context window
- Specialized skill (role)
- No shared memory or IPC

### Coordination Mechanisms

| Layer | Mechanism | Description |
|-------|-----------|-------------|
| File | Git repo | Shared TODOS.md, CHANGELOG.md, design docs |
| Branch | Git branch | Each agent works on its own branch |
| PR | GitHub PR | review/ship skills understand branch targeting |
| Pipeline | Skill chaining | `/ship` auto-invokes `/document-release` |
| Routing | Proactive suggest | Agent suggests next appropriate skill based on context |

### Key Insight

> "Without a process, ten agents is ten sources of chaos. With a process — think, plan, build, review, test, ship — each agent knows exactly what to do and when to stop."

Multi-agent doesn't require complex frameworks. Git + files + structured process is sufficient.

---

## 4. Design Patterns

### 4.1 Command Registry (Single Source of Truth)

All 50+ browser commands defined in one file (`commands.ts`). Used by:
- Server dispatcher (routing)
- Skill validator (static checks)
- Test helpers (command extraction)
- Doc generator (reference tables)

Zero side effects — safe to import anywhere.

### 4.2 Circular Buffer for Logs

```typescript
class CircularBuffer<T> {
    // Ring buffer: O(1) append, bounded memory
    // Async disk flush every 500ms or on buffer full
    // Used for console, network, dialog logs
}
```

Prevents memory bloat in long-running daemon. Total overhead per command: <5ms.

### 4.3 Ref-Based Element Selection

Instead of CSS selectors or XPath, gstack uses W3C accessibility tree:
```
button "Submit" [@e1]
  input "Email" [@e2]
  input "Password" [@e3]
link "Sign up" [@e4]
```

Benefits: stable across CSS changes, AI-friendly, encourages semantic HTML.

### 4.4 Template-Driven Documentation

```
SKILL.md.tmpl
  ├── {{COMMAND_REFERENCE}}  → browse/src/commands.ts
  ├── {{SNAPSHOT_FLAGS}}     → browse/src/snapshot.ts
  └── {{PREAMBLE_BASH}}     → utility scripts
```

Single source of truth — docs always in sync with code, no copy-paste errors.

### 4.5 Tiered Testing

| Tier | Speed | Cost | What |
|------|-------|------|------|
| Tier 1 | 2 seconds | Free | Unit tests (snapshot, commands, config, skill validation) |
| Tier 2 | 15-25 min | ~$4/run | E2E tests (full skill workflows, LLM-as-judge) |
| Tier 3 | 5-7 min | Cheaper | Fast E2E (Sonnet model, structure tests only) |

Diff-based test selection: only run tests related to changed files.

### 4.6 LLM-as-Judge

Claude evaluates skill outputs on:
- Structure correctness
- Hallucination detection
- Safety compliance
- Planted bug detection (intentionally wrong output to test if agent catches it)

### 4.7 Handoff Protocol

```bash
$B handoff "Need user to verify design"   # Opens real Chrome
# ... user interacts ...
$B resume                                  # Returns to headless
```

For design approval, payment flows, 2FA — things AI can't do.

---

## 5. Applicability to InfraHealthProbe

### Adopted

| Pattern | gstack | InfraHealthProbe |
|---------|--------|-----------------|
| Probe/command registry | `commands.ts` — single registry for all commands | `BaseProbe` ABC + probe auto-discovery |
| File-based coordination | Git + shared files between agents | JSONL/CSV contract between platform, Windows, Raspberry Pi |
| Tiered testing | 3 tiers: free/fast → paid/thorough | Unit → network integration → AI eval |
| Circular buffer | Ring buffer for daemon logs | Bounded probe result history in platform daemon mode |
| Structured workflow | think → plan → build → review → test → ship | inventory → probe → analyze → AI → report → alert |

### Not Adopted

| Pattern | Reason |
|---------|--------|
| Persistent browser daemon | HTTP probe uses `urllib`/`httpx`; full browser overkill for health checks |
| Markdown skill system | InfraHealthProbe is a platform, not an AI dev assistant |
| Conductor orchestration | Our platform IS the orchestrator; no need for external agent manager |
| Bun/TypeScript stack | Already committed to Python (Linux) + PowerShell (Windows) |
| Accessibility tree refs | No browser DOM interaction needed |

### Future Consideration

- **URL content validation** — If clearance system URL checks need to verify login page presence or form elements, consider adding a `content_keywords` option to `HttpProbe` (check response body for expected strings) before reaching for a full browser solution.
- **Cookie import for SSO** — If probing Okta/SSO-protected internal URLs becomes necessary, gstack's cookie import pattern (export from real browser → inject into probe) could be adapted as a lightweight alternative to full browser automation.

---

## 6. Key Takeaways

1. **Multi-agent = process isolation + shared files** — No need for complex IPC or agent frameworks. Independent processes coordinated through git, files, and structured workflows.

2. **Registry pattern prevents drift** — A single source of truth for all probe types (like gstack's command registry) ensures server, tests, and docs never go out of sync.

3. **Tiered testing saves money** — Free unit tests catch 80% of bugs. Expensive AI evals run only when relevant code changes.

4. **Daemon + ring buffer for long-running** — When the platform runs as a persistent service, use bounded circular buffers for probe history to prevent memory growth.

5. **Template-driven docs** — When probe profiles and schemas stabilize, generate documentation from schema definitions rather than maintaining docs separately.
