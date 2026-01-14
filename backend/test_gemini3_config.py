
import os
import asyncio
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

async def test_gemini3():
    print(f"Testing Gemini 3 Flash Preview with google.genai SDK...")
    
    client = genai.Client(api_key=api_key)
    
    # Test 1: Standard Config (No Penalties)
    try:
        print("\n[Test 1] Basic Generation...")
        response = await client.aio.models.generate_content(
            model="gemini-3-flash-preview",
            contents="Hello, who are you?",
            config=types.GenerateContentConfig(
                temperature=0.7,
            )
        )
        print(f"Success! Response: {response.text[:50]}...")
    except Exception as e:
        print(f"Test 1 Failed: {e}")

    # Test 2: With Penalties (snake_case)
    try:
        print("\n[Test 2] With presence_penalty (snake_case)...")
        response = await client.aio.models.generate_content(
            model="gemini-3-flash-preview",
            contents="Tell me a unique story.",
            config=types.GenerateContentConfig(
                temperature=0.7,
                presence_penalty=0.6,
                frequency_penalty=0.6
            )
        )
        print(f"Success! Response: {response.text[:50]}...")
    except Exception as e:
        print(f"Test 2 Failed: {e}")

    # Test 3: With Penalties (camelCase? - unlikely in Python SDK but worth trying args if kwargs allow)
    # The new SDK uses typed configs, so checking if fields exist.
    
    # Test 4: With 'thinking_level' (New Feature)
    try:
        print("\n[Test 4] With thinking_level='low'...")
        # Note: thinking_level might need specific keys or be in a different config
        # Based on search it might be a top level or config param
        # Let's try basic config first
        response = await client.aio.models.generate_content(
            model="gemini-3-flash-preview",
            contents="Solve a logic puzzle.",
            config=types.GenerateContentConfig(
                temperature=0.7,
                # thinking_level="low" # Might be invalid, commenting out for now unless I find type def
            )
        )
        print(f"Success! Response: {response.text[:50]}...")
    except Exception as e:
        print(f"Test 4 Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_gemini3())
