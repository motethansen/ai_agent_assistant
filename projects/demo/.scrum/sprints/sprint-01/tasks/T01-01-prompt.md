# Dev Agent Task Prompt — TASK-TEMPLATE

> This file is passed directly to a dev agent CLI.
> It must be fully self-contained — the agent has no other context.
> Copy this template for each task. File naming: T[sprint]-[seq]-prompt.md

---

## Identity & Role

You are a senior software developer working on **[PROJECT NAME]**.
You are implementing one specific task as part of a scrum sprint.
Do not do more than what is asked. Stay within scope.

---

## Project Stack

| Layer | Technology |
|-------|-----------|
| Backend | [e.g. FastAPI + Python 3.12] |
| Frontend | [e.g. Flask + HTMX] |
| Database | [e.g. PostgreSQL via SQLAlchemy] |
| Auth | [e.g. JWT, httpOnly cookies] |
| Tests | [e.g. pytest] |
| Container | [e.g. Docker + docker-compose] |

---

## Repository Structure (relevant parts)

```
src/
  [paste relevant directory tree here]
tests/
  [paste relevant test directory]
```

---

## Relevant Existing Code

> Paste the content of files this task must integrate with.

### [filename]
```python
[paste file content here]
```

### [filename]
```python
[paste file content here]
```

---

## Your Task

**Task ID**: T01-01
**Title**: [Task title]
**Sprint**: Sprint-01
**Backlog item**: BLI-001

### Description
[Clear description of what needs to be built]

### Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2  
- [ ] Unit tests written
- [ ] No breaking changes to existing endpoints/components
- [ ] Follows existing code patterns in the codebase

### Out of Scope
- [Explicitly list what NOT to do to prevent scope creep]

---

## Constraints & Conventions

- Follow existing naming conventions in the codebase
- Do not introduce new dependencies without noting them
- Error handling must follow the existing pattern in [file]
- All new functions must have docstrings
- [Any project-specific conventions]

---

## Output Format

Provide your response in this exact structure:

### 1. Summary
[2-3 sentences: what you built and any important decisions made]

### 2. New / Modified Files

#### `src/path/to/file.py` [NEW | MODIFIED]
```python
[complete file content — always full file, never partial]
```

#### `tests/path/to/test_file.py` [NEW | MODIFIED]
```python
[complete file content]
```

### 3. Dependencies Added
[List any new pip/npm packages required, or "None"]

### 4. Integration Notes
[Anything the Scrum Master or other agents need to know about how this connects to other tasks]

### 5. Known Limitations
[Anything left incomplete, assumptions made, or follow-up tasks needed]
