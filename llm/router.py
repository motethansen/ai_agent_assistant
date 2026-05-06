"""
LLM router — single entry point for all LLM calls.

Task types map to providers via .config ROUTING_* keys.
Call pattern:
    from llm.router import ask, stream, provider_for
    response = ask("Summarise my tasks", task="planning")
    response = ask("Follow-up", task="chat", history=[{"role": "user", ...}, ...])
"""

import config
from typing import Literal, Generator

TaskType = Literal["chat", "planning", "notes", "quick", "offline", "reasoning"]

_PROVIDER_MAP = {
    "gemini-flash": ("llm.gemini",   {"model": "flash"}),
    "gemini-pro":   ("llm.gemini",   {"model": "pro"}),
    "groq":         ("llm.groq",     {}),
    "deepseek":     ("llm.deepseek", {}),
    "ollama":       ("llm.ollama",   {}),
}

# Preference order for fallback chain (primary is always tried first)
_FALLBACK_ORDER = ["gemini-flash", "gemini-pro", "groq", "deepseek", "ollama"]


def _routing_key(task: TaskType) -> str:
    return {
        "chat":      config.llm.routing_chat(),
        "planning":  config.llm.routing_planning(),
        "notes":     config.llm.routing_notes(),
        "quick":     config.llm.routing_quick(),
        "offline":   config.llm.routing_offline(),
        "reasoning": config.llm.routing_reasoning(),
    }[task]


def _import_provider(name: str):
    import importlib
    module_path, _ = _PROVIDER_MAP.get(name, ("llm.gemini", {}))
    return importlib.import_module(module_path)


def _kwargs_for(name: str) -> dict:
    _, kwargs = _PROVIDER_MAP.get(name, ("llm.gemini", {}))
    return kwargs


def provider_for(task: TaskType) -> str:
    return _routing_key(task)


def is_available(provider_name: str) -> bool:
    try:
        mod = _import_provider(provider_name)
        return mod.is_available()
    except Exception:
        return False


def ask(
    prompt: str,
    task: TaskType = "chat",
    system: str = "",
    history: list[dict] | None = None,
) -> str:
    """
    Send a prompt to the configured provider for this task type.
    Falls back through the chain if the primary provider fails.

    history: optional list of prior turns [{"role": "user"|"assistant", "content": str}, ...]
    """
    primary = _routing_key(task)
    candidates = _build_fallback_chain(primary)

    last_error = None
    for name in candidates:
        try:
            mod = _import_provider(name)
            if not mod.is_available():
                continue
            kwargs = _kwargs_for(name)
            return mod.chat(prompt, system=system, history=history, **kwargs)
        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(
        f"All LLM providers failed for task '{task}'. Last error: {last_error}\n"
        "Check your API keys in .config or run /status"
    )


def stream(
    prompt: str,
    task: TaskType = "chat",
    system: str = "",
    history: list[dict] | None = None,
) -> Generator[str, None, None]:
    """
    Stream response chunks from the configured provider.
    Falls back to ask() (non-streaming) if provider doesn't support streaming.

    history: optional list of prior turns [{"role": "user"|"assistant", "content": str}, ...]
    """
    primary = _routing_key(task)
    candidates = _build_fallback_chain(primary)

    for name in candidates:
        try:
            mod = _import_provider(name)
            if not mod.is_available():
                continue
            kwargs = _kwargs_for(name)
            if hasattr(mod, "stream"):
                yield from mod.stream(prompt, system=system, history=history, **kwargs)
                return
            else:
                yield mod.chat(prompt, system=system, history=history, **kwargs)
                return
        except Exception:
            continue

    yield "[Error: no LLM provider available — check /status]"


def _build_fallback_chain(primary: str) -> list[str]:
    return [primary] + [p for p in _FALLBACK_ORDER if p != primary]


def all_providers() -> list[dict]:
    """Return status info for all known providers — used by /status and /model."""
    results = []
    for name in _FALLBACK_ORDER:
        try:
            mod = _import_provider(name)
            info = mod.info()
            info["configured_for"] = [
                task for task in ("chat", "planning", "notes", "quick", "offline", "reasoning")
                if _routing_key(task) == name
            ]
            results.append(info)
        except Exception as e:
            results.append({"provider": name, "available": False, "error": str(e)})
    return results
