import requests
import time
import json
import os
from datetime import datetime

# 配置
BASE_URL = "http://localhost:8000"

def test_contextual_memory():
    print("--- 1. Planting Contextual Memory ---")
    # 获取当前真实时间，确保能够由 proactive_search 匹配到
    current_dt = datetime.now()
    day_name = current_dt.strftime("%A") # e.g. Tuesday
    
    # 构造一条强相关的记忆
    # e.g. "On Tuesday nights, users usually feels tired and wants to eat pizza."
    memory_content = f"User explicitly said: On {day_name}s around this time, I always feel super lonely and want to talk about Sci-Fi movies."
    
    # 直接调用 Memory Add (模拟之前的对话)
    # 注意：我们的 backend/main.py 里的 chat 接口会存 Memory，我们直接发个 /chat 消息来植入
    print(f"Adding memory: '{memory_content}'")
    resp = requests.post(f"{BASE_URL}/chat", json={"message": memory_content})
    print(f"Seed Response: {resp.json()}")
    
    print("\n--- 2. Waiting for Proactive Trigger (Simulating Silence) ---")
    print("Keep this script running and watch the BACKEND LOGS.")
    print("Expected Log Sequence:")
    print(f"  1. [Proactive] Silence detected...")
    print(f"  2. [Memory] 🕵️ Contextual Search for: '...{day_name}...'")
    print(f"  3. [Memory] 💡 Associated ... (Should contain 'Sci-Fi' or 'lonely')")
    print(f"  4. [Proactive] AI decided to speak!")
    
    # 我们这里不做自动断言，因为 Proactive 是基于时间的，脚本很难自动捕获 console output（除非用 complex subprocess）。
    # 所以只是作为一个 Setup 脚本。
    print("\nNow, wait for ~30 seconds (or set PROACTIVE_CHECK_INTERVAL=10).")
    print("Check if the AI brings up 'Sci-Fi' or 'Lonely' automatically.")

if __name__ == "__main__":
    test_contextual_memory()
