---

## Completion Report

### 1. Files created/modified

- **Created**: `config.example` — new file at project root with all required settings
- **Modified**: `README.md` — added `### Configuration` subsection under Installation → Quick Start

### 2. Acceptance criteria

| Criteria | Status |
|---|---|
| `config.example` created at project root | ✅ |
| Contains only essential settings (no obscure/advanced options at top level) | ✅ |
| Every setting has a one-line comment | ✅ |
| Cloud API keys present but commented out | ✅ (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `CLAUDE_API_KEY`) |
| No OpenClaw references anywhere | ✅ |
| `README.md` references `config.example` in setup instructions | ✅ (added under Quick Start → Configuration) |
| `config.example` is NOT listed in `.gitignore` | ✅ (`.gitignore` only blocks `.config`, not `config.example`) |

### 3. Issues / deviations

None. The task spec content was applied verbatim. The existing `## Configuration` section in README (line ~77) was left intact — the new `### Configuration` subsection was added inside the Installation section where a new user would encounter it first, which is the more actionable location.