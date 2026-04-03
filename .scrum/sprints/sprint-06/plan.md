# Sprint-06 Plan — Distributed & Secure Agentic Architecture

**Sprint**: 06
**Goal**: Introduce LM Studio as a second local inference backend, isolate ObsidianAgent and LogSeqAgent in NanoClaw containers, migrate Google Calendar auth to n8n Universal Task Sync, and reduce the Python host to a lightweight router.
**Status**: 📋 Planned (awaiting Sprint-05 ICS engine + PO confirmation)
**Epics**: E14, E15, E16, E17

---

## Task Summary

| Task | BLI | Title | Estimate | LLM Agent | Wave |
|------|-----|-------|----------|-----------|------|
| T06-01 | BLI-036 | LM Studio CLI integration — provider, health check, `/status` row | M | **Claude Code** | Wave 1 | ✅ Done 2026-04-03 |
| T06-02 | BLI-037 | NanoClaw ObsidianAgent Skill — Dockerfile, skill.yaml, JSON interface | L | **Claude Code** | Wave 1 | ✅ Done 2026-04-03 |
| T06-03 | BLI-038 | NanoClaw LogSeqAgent Skill — list-later, add-task, mark-done actions | M | **Codex** | Wave 2 |
| T06-04 | BLI-039 | Universal Task Sync — n8n workflow JSON, conflict rules, `/sync-universal` | L | **Gemini** | Wave 3 |
| T06-05 | BLI-040 | CLI Router — `route()`, `send_to_n8n()`, delegation layer in ai_orchestration.py | L | **Claude Code** | Wave 3 |

---

## Execution Waves

```
Wave 1 (parallel — start immediately):
  ┌──────────────────────────────┐   ┌──────────────────────────────────────┐
  │ T06-01 LM Studio (Claude)    │   │ T06-02 NanoClaw ObsidianAgent (Claude)│
  │ ai_orchestration.py          │   │ nanoclaw/skills/obsidian_skill/       │
  │ update_manager.py            │   │ docker-compose.yml                    │
  └──────────────────────────────┘   └──────────────────────────────────────┘

Wave 2 (after T06-02 complete):
  ┌──────────────────────────────────────┐
  │ T06-03 NanoClaw LogSeqAgent (Codex)  │
  │ nanoclaw/skills/logseq_skill/        │
  │ follows pattern established in T06-02│
  └──────────────────────────────────────┘

Wave 3 (after T06-02 + T06-03 + Sprint-05 ICS engine):
  ┌──────────────────────────────────┐   ┌───────────────────────────────────┐
  │ T06-04 Universal Sync (Gemini)   │   │ T06-05 CLI Router (Claude Code)   │
  │ n8n-workflows/universal_task_    │   │ ai_orchestration.route()          │
  │ sync.json                        │   │ cli_commands send_to_n8n()        │
  └──────────────────────────────────┘   └───────────────────────────────────┘
```

**Why this order:**
- T06-01 and T06-02 share zero files — safe to run in parallel
- T06-03 needs T06-02's `Dockerfile` base image and compose setup before building the LogSeq variant
- T06-04 needs `local_calendar_agent.py` (Sprint-05 BLI-030) to exist for the ICS side of the sync payload
- T06-05 needs NanoClaw Skills (T06-02, T06-03) to dispatch to — meaningless without them
- T06-04 and T06-05 don't overlap (different files entirely) — safe to run in parallel in Wave 3

---

## New Config Keys (Sprint-06)

| Key | Default | Used by |
|-----|---------|---------|
| `ENABLE_LM_STUDIO` | `false` | `ai_orchestration.py`, `update_manager.py` |
| `LM_STUDIO_MODEL` | _(none)_ | `ai_orchestration.py` — must match loaded model name |
| `NANOCLAW_ENABLED` | `false` | `ai_orchestration.py`, `cron_job.py` |

---

## Definition of Done

- [ ] All 5 task prompts executed and code committed
- [ ] `pytest tests/ -v` — zero failures (run via `bash scripts/run_tests.sh`)
- [ ] `python main.py` starts cleanly when all new config keys are `false`
- [ ] `python scripts/status.py` shows LM Studio row
- [ ] `nanoclaw/skills/` directory exists with both Skill manifests
- [ ] `n8n-workflows/universal_task_sync.json` importable into n8n UI
- [ ] All existing CLI commands unchanged when `NANOCLAW_ENABLED=false`
- [ ] `config.example` updated with all three new keys (commented out)
- [ ] `INSTALL.md` updated: LM Studio setup, NanoClaw/Docker prerequisites, Universal Task Sync n8n credential setup
