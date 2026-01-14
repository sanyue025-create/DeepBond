
import os
import asyncio
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

async def test_continuous_turn():
    if not api_key:
        print("No API Key")
        return

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-3-flash-preview')

    # Scenario: User says hi, Model says hello. 
    # Now we want Model to say something else WITHOUT User input.
    history = [
        {"role": "user", "parts": ["Hello"]},
        {"role": "model", "parts": ["Hi there! How are you?"]}
    ]

    print("\n[Test 1] Sending history ending with MODEL role (expecting error or continuation)...")
    try:
        # API Call
        response = await model.generate_content_async(history)
        print(f"SUCCESS! The model replied: {response.text}")
        print("Conclusion: Gemini DOES allow continuous turns (Model -> Model).")
    except Exception as e:
        print(f"FAILED. Error: {e}")
        print("Conclusion: Gemini ENFORCES User -> Model alternation.")

asyncio.run(test_continuous_turn())
