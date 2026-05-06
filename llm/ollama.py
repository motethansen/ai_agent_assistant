"""Ollama provider (local — optional, enabled via OLLAMA_ENABLED=true)."""

import config

_available: bool | None = None


def is_available() -> bool:
    global _available
    if _available is not None:
        return _available
    if not config.llm.ollama_enabled():
        _available = False
        return False
    try:
        import ollama as _ollama
        _ollama.list()
        _available = True
    except Exception:
        _available = False
    return _available


def chat(prompt: str, system: str = "", history: list[dict] | None = None) -> str:
    import ollama as _ollama
    messages = _build_messages(prompt, system, history)
    response = _ollama.chat(model=config.llm.ollama_model(), messages=messages)
    return response["message"]["content"].strip()


def stream(prompt: str, system: str = "", history: list[dict] | None = None):
    """Yield text chunks for streaming terminal output."""
    import ollama as _ollama
    messages = _build_messages(prompt, system, history)
    for chunk in _ollama.chat(
        model=config.llm.ollama_model(),
        messages=messages,
        stream=True,
    ):
        delta = chunk["message"]["content"]
        if delta:
            yield delta


def _build_messages(prompt: str, system: str, history: list[dict] | None) -> list[dict]:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": prompt})
    return messages


def info() -> dict:
    return {
        "provider": "ollama",
        "model": config.llm.ollama_model(),
        "host": config.llm.ollama_host(),
        "available": is_available(),
        "free_tier": "local / unlimited",
    }
