"""Groq provider (free tier — Llama 3.3 70B)."""

import config

_client = None
_available: bool | None = None


def _get_client():
    global _client
    if _client is None:
        from groq import Groq
        api_key = config.llm.groq_api_key()
        if not api_key:
            raise RuntimeError("GROQ_API_KEY not set in .config")
        _client = Groq(api_key=api_key)
    return _client


def is_available() -> bool:
    global _available
    if _available is not None:
        return _available
    try:
        import groq
        _available = bool(config.llm.groq_api_key())
    except ImportError:
        _available = False
    return _available


def chat(prompt: str, system: str = "") -> str:
    client = _get_client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=config.llm.groq_model(),
        messages=messages,
    )
    return response.choices[0].message.content.strip()


def stream(prompt: str, system: str = ""):
    """Yield text chunks for streaming terminal output."""
    client = _get_client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    with client.chat.completions.create(
        model=config.llm.groq_model(),
        messages=messages,
        stream=True,
    ) as response:
        for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


def info() -> dict:
    return {
        "provider": "groq",
        "model": config.llm.groq_model(),
        "available": is_available(),
        "free_tier": "14,400 req/day",
    }
