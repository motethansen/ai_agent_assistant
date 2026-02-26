from google import genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Error: GEMINI_API_KEY not found in .env file.")
else:
    try:
        client = genai.Client(api_key=api_key)
        print("Available Models:")
        for model in client.models.list():
            print(f"Name: {model.name}, Supported Actions: {model.supported_actions}")
    except Exception as e:
        print(f"Error listing models: {e}")
