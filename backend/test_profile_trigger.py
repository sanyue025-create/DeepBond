import requests
import time
import json
import os

BASE_URL = "http://localhost:8000"

def trigger_profile_analysis():
    print("--- Flooding Chat to Trigger Profile Analysis (Threshold: 5) ---")
    
    # 定义一套“人设”鲜明的对话
    messages = [
        "我不喜欢吃甜食，太腻了。",
        "今天工作效率真低，烦死了。",
        "你能不能说话简单点？别啰嗦。",
        "算了，讲个冷笑话听听。",
        "这笑话一点都不好笑，重讲一个。" # 第5条，应该触发分析
    ]
    
    for i, msg in enumerate(messages):
        print(f"[{i+1}/5] User: {msg}")
        resp = requests.post(f"{BASE_URL}/chat", json={"message": msg})
        print(f"      AI: {resp.json()['response'][:30]}...") # 只打印前30个字
        time.sleep(1) # 稍微间隔一下
        
    print("\n--- Waiting for Background Analysis ---")
    print("Check backend logs for '[Profile] Triggering analysis...'")
    print("Then check './data/user_profile.json'")

if __name__ == "__main__":
    trigger_profile_analysis()
