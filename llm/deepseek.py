"""
DeepSeek provider — uses OpenAI-compatible API via openai SDK.

Models:
  deepseek-chat      → DeepSeek-V3 (default, ~$0.14/1M input tokens)
  deepseek-reasoner  → DeepSeek-R1 (chain-of-thought, ~$0.55/1M input tokens)

Free tier: new accounts receive $5 in trial credits.
Sign up at https://platform.deepseek.com
"""

import config

_client = None
_available: bool | None = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        api_key = config.llm.deepseek_api_key()
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY not set in .config")
        _client = OpenAI(
            api_key=api_key,
            base_url=config.llm.deepseek_base_url(),
        )
    return _client


def is_available() -> bool:
    global _available
    if _available is not None:
        return _available
    try:
        from openai import OpenAI  # noqa: F401
        _available = bool(config.llm.deepseek_api_key())
    except ImportError:
        _available = False
    return _available


def chat(prompt: str, system: str = "", history: list[dict] | None = None) -> str:
    client = _get_client()
    messages = _build_messages(prompt, system, history)
    response = client.chat.completions.create(
        model=config.llm.deepseek_model(),
        messages=messages,
    )
    return response.choices[0].message.content.strip()


def stream(prompt: str, system: str = "", history: list[dict] | None = None):
    """Yield text chunks for streaming terminal output."""
    client = _get_client()
    messages = _build_messages(prompt, system, history)
    with client.chat.completions.create(
        model=config.llm.deepseek_model(),
        messages=messages,
        stream=True,
    ) as response:
        for chunk in response:
            delta = chunk.choices[0].delta.content
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
        "provider": "deepseek",
        "model": config.llm.deepseek_model(),
        "available": is_available(),
        "free_tier": "$5 trial credits — then ~$0.14/1M tokens",
    }
