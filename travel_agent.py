import json
import os
from google import genai
from google.genai import types
from config_utils import get_config_value

class TravelAgent:
    """
    Agent responsible for travel planning: flights, holiday plans, and booking links.
    Uses Google Search grounding through the Gemini API.
    """
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    def plan_travel(self, query):
        """
        Uses Gemini with Google Search tool to find travel information.
        """
        if not self.client:
            return "Error: GEMINI_API_KEY not set. Travel planning requires search grounding."

        prompt = f"""
        You are a professional Travel Planning Agent. 
        User Request: {query}

        TASK:
        1. Search for real-time travel information: flights, connecting flights, and suggested flight plans.
        2. Propose a suggested holiday plan and travel details.
        3. Provide direct URLs to official websites or reliable booking platforms for access (do NOT book anything).
        4. Be thorough and consider multiple options for flights and connections.

        RULES:
        - Do NOT perform any actual bookings.
        - Only provide information and links.
        - Return your findings in a structured, easy-to-read format.
        """

        try:
            # Using Gemini with the Google Search tool enabled
            response = self.client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                )
            )
            
            # Extract text and search metadata if available
            return response.text
        except Exception as e:
            return f"Error during travel planning: {e}"

if __name__ == "__main__":
    # Test
    agent = TravelAgent()
    print(agent.plan_travel("Find flights from Bangkok to London for next month and suggest a 5-day itinerary."))
