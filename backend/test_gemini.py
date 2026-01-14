
import asyncio
import os
from core import GeminiClient

async def test():
    client = GeminiClient(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
    print(f"Testing with model: {client.model_name}")
    try:
        response = await client.chat("Hello, are you working?", system_instruction="You are a helpful assistant.")
        print(f"Chat Response: {response}")
        
        print("Testing stream_chat...")
        async for chunk in client.stream_chat("Say a short greeting."):
            print(f"Chunk: {chunk}")
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(test())
