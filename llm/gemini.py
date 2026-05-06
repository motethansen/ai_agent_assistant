"""Gemini provider — uses google.genai (google-genai package, not deprecated generativeai)."""

import config

_client = None
_available: bool | None = None


def _get_client():
    global _client
    if _client is None:
        from google import genai
        api_key = config.llm.gemini_api_key()
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set in .config")
        _client = genai.Client(api_key=api_key)
    return _client


def is_available() -> bool:
    global _available
    if _available is not None:
        return _available
    try:
        from google import genai  # noqa: F401
        _available = bool(config.llm.gemini_api_key())
    except ImportError:
        _available = False
    return _available


def _model_name(model: str) -> str:
    if model == "pro":
        return config.llm.gemini_pro_model()
    return config.llm.gemini_flash_model()


def chat(prompt: str, model: str = "flash", system: str = "", history: list[dict] | None = None) -> str:
    from google.genai import types
    client = _get_client()
    contents = _build_contents(prompt, history, types)
    config_obj = types.GenerateContentConfig(system_instruction=system) if system else None

    response = client.models.generate_content(
        model=_model_name(model),
        contents=contents,
        config=config_obj,
    )
    return response.text.strip()


def stream(prompt: str, model: str = "flash", system: str = "", history: list[dict] | None = None):
    """Yield text chunks for streaming terminal output."""
    from google.genai import types
    client = _get_client()
    contents = _build_contents(prompt, history, types)
    config_obj = types.GenerateContentConfig(system_instruction=system) if system else None

    for chunk in client.models.generate_content_stream(
        model=_model_name(model),
        contents=contents,
        config=config_obj,
    ):
        if chunk.text:
            yield chunk.text


def _build_contents(prompt: str, history: list[dict] | None, types):
    if not history:
        return prompt
    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
    contents.append(types.Content(role="user", parts=[types.Part(text=prompt)]))
    return contents


def info() -> dict:
    return {
        "provider": "gemini",
        "flash_model": config.llm.gemini_flash_model(),
        "pro_model": config.llm.gemini_pro_model(),
        "available": is_available(),
        "free_tier": "15 RPM flash / 2 RPM pro",
    }
