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
    
    response = ""
    if routing_chat == "ollama":
        response = ai_orchestration.ollama_generate(prompt)
    elif routing_chat == "openclaw":
        response = ai_orchestration.openclaw_generate(prompt)
    else:
        # Gemini logic
        import google.genai as genai
        try:
            client = genai.Client(api_key=ai_orchestration.api_key)
            resp = client.models.generate_content(model='gemini-flash-latest', contents=prompt)
            response = resp.text
        except:
            response = "Gemini failed."

    print(f"Chat Response: {response.strip()}")
    
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
