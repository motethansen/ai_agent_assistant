# Architecture & Design Decisions — [PROJECT NAME]

> This file is CRITICAL for team handoffs. Every significant decision must be logged here.
> Any new Scrum Master or dev agent team reads this before starting work.

---

## How to Use This File

When making a decision that affects:
- Technology choices
- File/folder structure
- API contracts
- Auth / security approaches
- Data models
- External service integrations

...add an entry here. Future agents (and you) will thank you.

---

## Decisions Log

### ADR-001 — [Decision Title]
- **Date**: [DATE]
- **Sprint**: Sprint-XX
- **Team**: [LLM team that made this decision, e.g. Claude agents]
- **Status**: Accepted | Superseded by ADR-XXX | Deprecated

**Context**:
What situation or problem prompted this decision?

**Decision**:
What was decided?

**Reasoning**:
Why this choice over alternatives?

**Consequences**:
What does this affect? What must future agents know?

**Affected files**:
- `src/path/to/file.py`

---

### ADR-002 — [Decision Title]
- **Date**: 
- **Sprint**: 
- **Team**: 
- **Status**: Accepted

**Context**:

**Decision**:

**Reasoning**:

**Consequences**:

**Affected files**:

---

## Stack Reference

> Quick reference for any incoming agent team.

| Layer | Technology | Version | Notes |
|-------|-----------|---------|-------|
| Backend | | | |
| Frontend | | | |
| Database | | | |
| Auth | | | |
| Payments | | | |
| Infra | | | |
| Tests | | | |

---

## External Services & Credentials Locations

> Never store credentials here. Just note where they live.

| Service | Credential location | Notes |
|---------|-------------------|-------|
| [Service name] | .env / Vault / etc | |
