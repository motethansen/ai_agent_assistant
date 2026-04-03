"""
NanoClaw host client.

Dispatches to a containerised NanoClaw Skill via `docker compose run` and
returns the parsed JSON response. When NANOCLAW_ENABLED=false every call
raises RuntimeError immediately — no Docker interaction occurs.

Usage:
    from nanoclaw.client import run_skill

    result = run_skill("obsidian_skill", "find_tasks")
    result = run_skill("obsidian_skill", "create_file", "Note.md", "# Hello", write=True)
    result = run_skill("logseq_skill", "list-later")
    result = run_skill("logseq_skill", "sync-to-obsidian", write=True)
"""
import json
import subprocess

from config_utils import get_config_value

NANOCLAW_ENABLED = get_config_value("NANOCLAW_ENABLED", "false").lower() == "true"

WRITE_ACTIONS = {
    "obsidian_skill": {"create_file", "update_file"},
    "logseq_skill": {"add-task", "mark-done", "sync-to-obsidian"},
}


def _build_mounts(skill_name: str, action: str, write: bool) -> list[str]:
    mounts = []

    if skill_name == "obsidian_skill":
        workspace_dir = get_config_value("WORKSPACE_DIR", "")
        mount_mode = "rw" if write else "ro"
        mounts.extend(["--volume", f"{workspace_dir}:/vault:{mount_mode}"])
        return mounts

    if skill_name == "logseq_skill":
        logseq_dir = get_config_value("LOGSEQ_DIR", "")
        logseq_mode = "rw" if write else "ro"
        mounts.extend(["--volume", f"{logseq_dir}:/logseq:{logseq_mode}"])

        if action == "sync-to-obsidian":
            workspace_dir = get_config_value("WORKSPACE_DIR", "")
            mounts.extend(["--volume", f"{workspace_dir}:/vault:rw"])

        return mounts

    workspace_dir = get_config_value("WORKSPACE_DIR", "")
    mount_mode = "rw" if write else "ro"
    mounts.extend(["--volume", f"{workspace_dir}:/vault:{mount_mode}"])
    return mounts


def run_skill(skill_name: str, action: str, *args, write: bool = False) -> dict:
    """
    Run a NanoClaw Skill action inside an isolated Docker container.

    skill_name: name of the Docker Compose service (e.g. "obsidian_skill")
    action:     action to execute inside the container (e.g. "find_tasks")
    *args:      positional arguments forwarded to the skill runner
    write:      when True, the vault volume is mounted read-write (rw);
                defaults to False (read-only). Callers must explicitly opt in
                for any mutation action (create_file, update_file).

    Returns the parsed JSON dict from the container's stdout.

    Raises RuntimeError when:
      - NANOCLAW_ENABLED is false
      - the container exits with a non-zero return code
      - the container's stdout is not valid JSON
    """
    if not NANOCLAW_ENABLED:
        raise RuntimeError(
            "NanoClaw is disabled (NANOCLAW_ENABLED=false in .config). "
            "Set NANOCLAW_ENABLED=true and rebuild the skill image to use containerised agents."
        )

    if action in WRITE_ACTIONS.get(skill_name, set()) and not write:
        raise RuntimeError(
            f"Skill {skill_name}/{action} requires write=True to enable a read-write volume mount."
        )

    cmd = [
        "docker", "compose", "run", "--rm",
        *_build_mounts(skill_name, action, write),
        skill_name,
        action,
        *[str(a) for a in args],
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Skill {skill_name}/{action} timed out after 30 seconds")

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(
            f"Skill {skill_name}/{action} failed (exit {result.returncode}): {stderr}"
        )

    raw = result.stdout.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Skill {skill_name}/{action} returned invalid JSON: {raw!r}"
        ) from exc
