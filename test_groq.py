"""Test Groq/Mistral integration via ai_orchestration."""
from ai_orchestration import generate_with, is_groq_available, _build_llm
from config_utils import get_config_value

def test_groq():
    print("=== Groq / Mistral test ===\n")

    # 1. Availability check
    available = is_groq_available()
    key = get_config_value("GROQ_API_KEY", "")
    model = get_config_value("GROQ_MODEL", "mistral-saba-24b")
    print(f"Provider:  groq")
    print(f"Model:     {model}")
    print(f"Key set:   {'yes (' + key[:8] + '...)' if key else 'NO'}")
    print(f"Available: {available}\n")

    if not available:
        print("SKIP — GROQ not enabled or key missing.")
        return

    # 2. Simple hello
    print("--- Test 1: simple hello ---")
    resp, used = generate_with("groq", "Say hello in one sentence.")
    print(f"Model used : {used}")
    print(f"Response   : {resp}\n")

    # 3. Short reasoning task
    print("--- Test 2: reasoning ---")
    resp2, used2 = generate_with(
        "groq",
        "List 3 benefits of using a local LLM over a cloud LLM. Be brief.",
        system="You are a concise technical assistant."
    )
    print(f"Model used : {used2}")
    print(f"Response   :\n{resp2}\n")

    # 4. Streaming check
    print("--- Test 3: streaming ---")
    llm, label = _build_llm("groq")
    chunks = []
    for chunk in llm.stream([("human", "Count from 1 to 5, one number per line.")]):
        chunks.append(chunk.content)
    streamed = "".join(chunks)
    print(f"Model used : {label}")
    print(f"Streamed   :\n{streamed}\n")

    print("=== All Groq tests passed ===")

if __name__ == "__main__":
    test_groq()
