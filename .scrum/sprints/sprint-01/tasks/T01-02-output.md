I need permission to edit `PLAN.md`. Please approve the file write permission, then I'll clean the remaining OpenClaw references in that file. Here's a summary of what needs to change in `PLAN.md`:

| Line | Current | Change to |
|------|---------|-----------|
| 33 | `### Phase 6: OpenClaw and Ollama Integration` | `### Phase 6: Ollama Integration` |
| 34 | `Add OpenClaw and Ollama modules...` | `Add Ollama module...` |
| 35 | `install Ollama and OpenClaw locally` | `install Ollama locally` |
| 86 | `Gemini, Ollama, OpenClaw` | `Gemini, Ollama` |
| 88 | `local models (Ollama, OpenClaw)` | `local models (Ollama)` |
| 127 | `Ollama/OpenClaw` | `Ollama` |
| 139 | `Add ensure_openclaw()...` | Remove line |
| 140 | `-> OpenClaw/OpenAI/Claude` | `-> OpenAI/Claude/Gemini` |

**Status of the 5 core targets from the acceptance criteria:**

| File | Status |
|------|--------|
| `ai_orchestration.py` | ✅ Already clean — no openclaw references |
| `main.py` | ✅ Already clean — no openclaw references |
| `config.template` | ✅ Already clean — routing defaults are `ollama`, LLM_PRIORITY is `ollama,gemini,openai,claude` |
| `README.md` | ✅ Already clean — only has a progress log entry noting the removal |
| `INSTALL.md` | ✅ Already clean |
| `PLAN.md` | ⚠️ Needs 8 line edits — awaiting write permission |

The T01-01 and T01-02 work appears to have already been applied to the core files. The only remaining work is cleaning historical references in `PLAN.md`. Can you grant write permission so I can complete that?