import os
import sys
import json

# Ensure the root directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ai_orchestration

def test_ai_functioning():
    print("--- 🤖 Testing AI Assistant Capabilities ---")

    # 1. Test Routing
    routing_chat = ai_orchestration.get_routing("chat")
    routing_scheduling = ai_orchestration.get_routing("scheduling")
    print(f"Current Routing: Chat -> {routing_chat}, Scheduling -> {routing_scheduling}")

    # 2. Test Generation (Chat)
    print(f"Testing Chat ({routing_chat})...")
    prompt = "Reply with 'OK' if you can hear me."

    response, model_used = ai_orchestration.generate(prompt)
    print(f"Chat Response ({model_used}): {response.strip()}")

    # 3. Test Scheduling (Lightweight)
    print(f"Testing Scheduling ({routing_scheduling})...")
    test_tasks = [{"task": "Verify AI is working", "category": "dev"}]
    test_busy = []

    schedule = ai_orchestration.generate_schedule(test_tasks, test_busy)
    if schedule and "schedule" in schedule:
        print("✅ Scheduling test passed.")
    else:
        print("❌ Scheduling test failed.")

if __name__ == "__main__":
    test_ai_functioning()
