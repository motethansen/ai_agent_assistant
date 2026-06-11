"""
Central configuration loader for AI Agent Assistant.
Reads .config file from the project root. Run install.sh to generate it.
"""

import os
import sys
from pathlib import Path
from typing import Optional

_CONFIG_FILE = Path(__file__).parent / ".config"
_cache: dict = {}


def _load() -> dict:
    if _cache:
        return _cache
    if not _CONFIG_FILE.exists():
        return {}
    with open(_CONFIG_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                _cache[k.strip()] = v.strip()
    return _cache


def get(key: str, default: str = "") -> str:
    return _load().get(key, default)


def get_bool(key: str, default: bool = False) -> bool:
    val = get(key, "true" if default else "false").lower()
    return val in ("true", "1", "yes")


def get_int(key: str, default: int = 0) -> int:
    try:
        return int(get(key, str(default)))
    except ValueError:
        return default


def get_list(key: str, default: list[str] | None = None) -> list[str]:
    val = get(key, "")
    if not val:
        return default or []
    return [x.strip() for x in val.split(",") if x.strip()]


# ── Typed accessors ───────────────────────────────────────────────────────────

class paths:
    @staticmethod
    def obsidian() -> str:
        return get("WORKSPACE_DIR", "")

    @staticmethod
    def logseq() -> str:
        return get("LOGSEQ_DIR", "")

    @staticmethod
    def dashboard() -> str:
        base = get("WORKSPACE_DIR", "")
        name = get("OBSIDIAN_DASHBOARD_FILE", "Dashboard.md")
        return str(Path(base) / name) if base else ""

    @staticmethod
    def inbox_dir() -> str:
        base = get("WORKSPACE_DIR", "")
        return str(Path(base) / "000 Inbox") if base else ""

    @staticmethod
    def daily_dir() -> str:
        base = get("WORKSPACE_DIR", "")
        return str(Path(base) / "Daily") if base else ""

    @staticmethod
    def local_calendar() -> str:
        return get("LOCAL_CALENDAR_FILE", "output/local_calendar.ics")

    @staticmethod
    def output() -> str:
        return str(Path(__file__).parent / "output")

    @staticmethod
    def knowledge_graph() -> str:
        return str(Path(__file__).parent / "output" / "knowledge_graph.ttl")


class llm:
    @staticmethod
    def routing_chat() -> str:
        return get("ROUTING_CHAT", "gemini-flash")

    @staticmethod
    def routing_planning() -> str:
        return get("ROUTING_PLANNING", "gemini-pro")

    @staticmethod
    def routing_notes() -> str:
        return get("ROUTING_NOTES", "gemini-flash")

    @staticmethod
    def routing_quick() -> str:
        return get("ROUTING_QUICK", "groq")

    @staticmethod
    def routing_offline() -> str:
        return get("ROUTING_OFFLINE", "ollama")

    @staticmethod
    def routing_reasoning() -> str:
        return get("ROUTING_REASONING", "deepseek")

    @staticmethod
    def gemini_api_key() -> str:
        return get("GEMINI_API_KEY", "")

    @staticmethod
    def gemini_flash_model() -> str:
        return get("GEMINI_FLASH_MODEL", "gemini-2.0-flash")

    @staticmethod
    def gemini_pro_model() -> str:
        return get("GEMINI_PRO_MODEL", "gemini-2.5-flash-preview-04-17")

    @staticmethod
    def groq_api_key() -> str:
        return get("GROQ_API_KEY", "")

    @staticmethod
    def groq_model() -> str:
        return get("GROQ_MODEL", "llama-3.3-70b-versatile")

    @staticmethod
    def ollama_enabled() -> bool:
        return get_bool("OLLAMA_ENABLED", False)

    @staticmethod
    def ollama_model() -> str:
        return get("OLLAMA_MODEL", "qwen2.5:7b")

    @staticmethod
    def ollama_host() -> str:
        return get("OLLAMA_HOST", "http://localhost:11434")

    @staticmethod
    def deepseek_api_key() -> str:
        return get("DEEPSEEK_API_KEY", "")

    @staticmethod
    def deepseek_model() -> str:
        return get("DEEPSEEK_MODEL", "deepseek-chat")

    @staticmethod
    def deepseek_base_url() -> str:
        return get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")


class planning:
    @staticmethod
    def deep_work_start() -> str:
        return get("DEEP_WORK_START", "09:00")

    @staticmethod
    def deep_work_end() -> str:
        return get("DEEP_WORK_END", "12:00")

    @staticmethod
    def focus_categories() -> list[str]:
        return get_list("FOCUS_CATEGORIES", ["dev", "writing", "learning"])

    @staticmethod
    def chronotype() -> str:
        return get("CHRONOTYPE", "morning_owl")


class sync:
    @staticmethod
    def logseq_journal_days() -> int:
        return get_int("LOGSEQ_JOURNAL_DAYS", 2)

    @staticmethod
    def interval_minutes() -> int:
        return get_int("SYNC_INTERVAL_MINUTES", 30)


class calendar:
    @staticmethod
    def google_enabled() -> bool:
        return get_bool("GOOGLE_CAL_ENABLED", False)

    @staticmethod
    def google_credentials_file() -> str:
        return get("GOOGLE_CAL_CREDENTIALS", "")

    @staticmethod
    def apple_calendar_name() -> str:
        return get("APPLE_CALENDAR_NAME", "Home")

    @staticmethod
    def gcal_tag() -> str:
        return get("GCAL_TAG", "gcal")


# ── Validation ────────────────────────────────────────────────────────────────

REQUIRED_FOR_ONLINE = {
    "gemini-flash": ("GEMINI_API_KEY",  "Get a free key at https://aistudio.google.com"),
    "gemini-pro":   ("GEMINI_API_KEY",  "Get a free key at https://aistudio.google.com"),
    "groq":         ("GROQ_API_KEY",    "Get a free key at https://console.groq.com"),
    "deepseek":     ("DEEPSEEK_API_KEY","Sign up at https://platform.deepseek.com (free trial credits)"),
}


def validate(exit_on_error: bool = False) -> list[str]:
    """Return a list of warning strings. Prints them and optionally exits."""
    warnings = []

    if not get("WORKSPACE_DIR"):
        warnings.append("WORKSPACE_DIR not set — Obsidian vault path required")

    if not get("LOGSEQ_DIR"):
        warnings.append("LOGSEQ_DIR not set — LogSeq graph path required")

    for task in ("ROUTING_CHAT", "ROUTING_PLANNING", "ROUTING_NOTES", "ROUTING_QUICK", "ROUTING_REASONING"):
        provider = get(task, "")
        if provider in REQUIRED_FOR_ONLINE:
            key_name, hint = REQUIRED_FOR_ONLINE[provider]
            if not get(key_name):
                warnings.append(f"{key_name} missing — needed for {provider} ({hint})")

    if llm.ollama_enabled():
        import shutil
        if not shutil.which("ollama"):
            warnings.append("OLLAMA_ENABLED=true but ollama not found in PATH — run install.sh")

    if not _CONFIG_FILE.exists():
        warnings.append(
            f".config file not found at {_CONFIG_FILE}\n"
            "  Run: cp config.example .config  then fill in your paths and keys\n"
            "  Or run: ./install.sh"
        )

    if warnings and exit_on_error:
        for w in warnings:
            print(f"  ✗ {w}", file=sys.stderr)
        sys.exit(1)

    return warnings


def summary() -> dict:
    """Return a dict of all active settings for /status command."""
    return {
        "obsidian": paths.obsidian() or "(not set)",
        "logseq": paths.logseq() or "(not set)",
        "dashboard": paths.dashboard() or "(not set)",
        "llm_chat": llm.routing_chat(),
        "llm_planning": llm.routing_planning(),
        "llm_notes": llm.routing_notes(),
        "llm_quick": llm.routing_quick(),
        "llm_reasoning": llm.routing_reasoning(),
        "deepseek_key": "set" if llm.deepseek_api_key() else "not set",
        "ollama_enabled": llm.ollama_enabled(),
        "ollama_model": llm.ollama_model() if llm.ollama_enabled() else "—",
        "google_cal": calendar.google_enabled(),
        "gcal_tag": f"#{calendar.gcal_tag()}",
        "sync_interval": f"{sync.interval_minutes()} min",
        "deep_work": f"{planning.deep_work_start()} – {planning.deep_work_end()}",
    }
