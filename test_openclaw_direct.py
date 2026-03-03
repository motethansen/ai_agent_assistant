import sys
import os
import json
import requests

# Add current dir to path to import local modules
sys.path.append(os.getcwd())

import ai_orchestration
from config_utils import get_config_value

def test_openclaw():
    print("--- 🤖 Testing OpenClaw Direct ---")
    
    endpoint = get_config_value('OPENCLAW_ENDPOINT', 'http://localhost:18789/v1')
    enabled = get_config_value('ENABLE_OPENCLAW', 'true').lower() == 'true'
    
    print(f"Target Endpoint: {endpoint}")
    print(f"Model Enabled in .config: {enabled}")
    
    prompt = "Reply with exactly one word: 'SUCCESS'"
    
    try:
        # We call the generation function directly, bypassing routing fallbacks
        response = ai_orchestration.openclaw_generate(prompt)
        print(f"
OpenClaw Response: {response}")
        
        if "SUCCESS" in response.upper():
            print("
✅ OpenClaw is WORKING correctly!")
        else:
            print("
⚠️ OpenClaw responded, but the output was unexpected.")
            
    except Exception as e:
        print(f"
❌ OpenClaw test FAILED: {e}")
        print("
Possible solutions:")
        print(f"1. Make sure your local server is running on {endpoint}")
        print("2. Check if your API key is required (configured in .config)")
        print("3. Ensure the model 'gpt-3.5-turbo' (default) is loaded in your server")

if __name__ == "__main__":
    test_openclaw()
