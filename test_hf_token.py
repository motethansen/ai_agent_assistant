"""Test HuggingFace AI_Assistant_Token against multiple models via the Inference API."""
import sys
from config_utils import get_config_value  # also sets HF_TOKEN in os.environ

token = get_config_value("AI_Assistant_Token", None) or get_config_value("HF_TOKEN", None)

print("=== HuggingFace Token Test ===\n")
print(f"Token : {'yes (' + token[:8] + '...)' if token else 'NOT FOUND'}")

if not token:
    print("FAIL — no token found under AI_Assistant_Token or HF_TOKEN")
    sys.exit(1)

# ── 1. Validate token via whoami ──────────────────────────────────────────────
print("\n--- Auth check (whoami) ---")
try:
    from huggingface_hub import HfApi
    api = HfApi(token=token)
    info = api.whoami()
    plan = info.get("plan", {})
    plan_name = plan.get("name", "free") if isinstance(plan, dict) else str(plan)
    print(f"Authenticated as : {info['name']}")
    print(f"Account type     : {info.get('type', 'user')}")
    print(f"Plan             : {plan_name}")
    print("Auth: PASS\n")
except Exception as e:
    print(f"Auth: FAIL — {e}\n")
    sys.exit(1)

from huggingface_hub import InferenceClient
client = InferenceClient(token=token)

results = []

# ── 2. Model 1: Summarisation — facebook/bart-large-cnn ──────────────────────
print("--- Model 1: facebook/bart-large-cnn (summarisation) ---")
try:
    text = (
        "HuggingFace is an AI company that builds tools for machine learning. "
        "They host thousands of open-source models, datasets, and spaces. "
        "Their Inference API allows developers to run models in the cloud without "
        "managing infrastructure, making it easy to experiment with state-of-the-art models."
    )
    out = client.summarization(text, model="facebook/bart-large-cnn")
    summary = out.summary_text if hasattr(out, "summary_text") else str(out)
    print(f"Output : {summary.strip()}")
    print("PASS\n")
    results.append(("facebook/bart-large-cnn", True))
except Exception as e:
    print(f"FAIL — {e}\n")
    results.append(("facebook/bart-large-cnn", False))

# ── 3. Model 2: Chat / reasoning — Qwen/Qwen2.5-72B-Instruct ─────────────────
print("--- Model 2: Qwen/Qwen2.5-72B-Instruct (chat / reasoning) ---")
try:
    out = client.chat_completion(
        messages=[{"role": "user", "content": "Name 2 benefits of open-source LLMs. Be brief."}],
        model="Qwen/Qwen2.5-72B-Instruct",
        max_tokens=100,
    )
    reply = out.choices[0].message.content.strip()
    print(f"Output : {reply}")
    print("PASS\n")
    results.append(("Qwen/Qwen2.5-72B-Instruct", True))
except Exception as e:
    print(f"FAIL — {e}\n")
    results.append(("Qwen/Qwen2.5-72B-Instruct", False))

# ── 4. Model 3: Code generation — Qwen/Qwen2.5-Coder-32B-Instruct ────────────
print("--- Model 3: Qwen/Qwen2.5-Coder-32B-Instruct (code generation) ---")
try:
    out = client.chat_completion(
        messages=[{"role": "user", "content": "Write a Python one-liner that reverses a string."}],
        model="Qwen/Qwen2.5-Coder-32B-Instruct",
        max_tokens=80,
    )
    reply = out.choices[0].message.content.strip()
    print(f"Output : {reply}")
    print("PASS\n")
    results.append(("Qwen/Qwen2.5-Coder-32B-Instruct", True))
except Exception as e:
    print(f"FAIL — {e}\n")
    results.append(("Qwen/Qwen2.5-Coder-32B-Instruct", False))

# ── Summary ───────────────────────────────────────────────────────────────────
print("=== Results ===")
passed = sum(1 for _, ok in results if ok)
for model, ok in results:
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {model}")
print(f"\n{passed}/{len(results)} models passed")
sys.exit(0 if passed == len(results) else 1)
