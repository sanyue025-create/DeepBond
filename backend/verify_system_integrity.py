
import asyncio
import os
import sys

# Ensure backend path is in sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "."))

from unittest.mock import AsyncMock, MagicMock
import main
from main import app, Task
import time

async def run_verification():
    print("=== System Integrity Veficiation (Streaming Mode) ===")
    
    # 1. Mock Dependencies
    app.state.chat_history = []
    app.state.current_session_id = "test_integrity_session"
    app.state.is_chat_processing = False
    app.state.interrupt_event = asyncio.Event()
    
    # Mock Gemini Stream
    async def mock_stream_chat(*args, **kwargs):
        yield "This "
        yield "is "
        yield "a "
        yield "streamed "
        yield "test."
    
    main.gemini.stream_chat = mock_stream_chat
    
    # Mock Memory
    main.memory.add_memory = MagicMock()
    main.memory.query_memory = MagicMock(return_value="[Memory Context]")
    
    # Mock Storage
    main.storage.save_session = MagicMock()
    
    # Mock Background Tasks (to intercept schedule_next_event)
    # Since streaming endpoint creates tasks on the fly, we can't easily intercept FastAPI BackgroundTasks
    # But main.py uses asyncio.create_task for schedule_next_event in the generator.
    
    # 2. Simulate Chat Request
    request = main.ChatRequest(message="Hello System Check")
    
    # Typically we'd call the endpoint, but it returns a StreamingResponse.
    # We need to iterate the response body.
    
    # Mock BackgroundTasks
    mock_bg_tasks = MagicMock()
    
    print("[1] Testing Streaming Endpoint...")
    response_obj = await main.chat_endpoint(request, background_tasks=mock_bg_tasks)
    
    full_text = ""
    async for chunk in response_obj.body_iterator:
        full_text += chunk
        # print(f"Chunk: {chunk}")
        
    print(f"[Result] Full Text Received: '{full_text}'")
    assert full_text == "This is a streamed test.", "Stream Output Mismatch!"
    print("✅ Streaming works.")
    
    # 3. Verify Side Effects
    # Wait a bit for async tasks in the generator to finish (if any)
    await asyncio.sleep(0.5)
    
    print("[2] Verifying Chat History...")
    last_msg = app.state.chat_history[-1]
    assert last_msg["role"] == "model", "History not updated with model response"
    assert last_msg["parts"][0] == "This is a streamed test.", "History content mismatch"
    print("✅ Chat History updated.")
    
    print("[3] Verifying Memory add_memory...")
    # main.memory.add_memory.assert_called() # Might be async or sync depending on implementation checks
    # In main.py: memory.add_memory is called synchronously in the generator loop finalizer
    main.memory.add_memory.assert_called()
    call_args = main.memory.add_memory.call_args
    print(f"   Called with: {call_args}")
    print("✅ Memory saved.")
    
    print("[4] Verifying Storage save_session...")
    main.storage.save_session.assert_called()
    print("✅ Session persisted.")
    
    print("=== Verification Complete: ALL SYSTEMS GO ===")

if __name__ == "__main__":
    asyncio.run(run_verification())
