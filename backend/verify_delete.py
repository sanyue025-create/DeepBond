import requests
import uuid
import time
import json
from memory import MemoryManager

BASE_URL = "http://localhost:8000"

def test_delete_flow():
    # 1. New Session
    print("[Test] Creating Session...")
    s_res = requests.post(f"{BASE_URL}/sessions/new")
    session_id = s_res.json()["id"]
    print(f"Session: {session_id}")
    
    # 2. Send Message with ID (Simulating Frontend)
    test_id = f"msg-{uuid.uuid4()}"
    secret = f"My Secret Is {uuid.uuid4()}"
    print(f"[Test] Sending Message: {secret} (ID: {test_id})")
    
    res = requests.post(f"{BASE_URL}/chat", json={"message": secret, "id": test_id}, stream=True)
    # Consume stream
    for line in res.iter_lines(): 
        pass
    print("Chat Complete.")
    
    # Wait for Async Memory Add
    time.sleep(2)
    
    # 3. Verify Memory Exists
    mm = MemoryManager()
    found = False
    for m in mm.get_all_memories():
        if secret in m["text"]:
            found = True
            print("✅ ID-Linked Memory Found in DB.")
            if m.get("metadata", {}).get("source_id") == test_id:
                print("✅ Source ID Correctly Linked.")
            else:
                print(f"❌ Source ID Mismatch: {m.get('metadata')}")
            break
            
    if not found:
        print("❌ Memory Insertion Failed!")
        return

    # 4. Verify History Exists
    h_res = requests.get(f"{BASE_URL}/history")
    hist = h_res.json()
    found_h = False
    for msg in hist:
        # Note: /history endpoint returns formatted content, might not show ID.
        # But we check content
        if secret in msg["content"]:
            found_h = True
            print("✅ Message Found in History.")
            break
    if not found_h:
        print("❌ History Insertion Failed!")
        return

    # 5. EXECUTE DELETE
    print(f"[Test] Deleting Message {test_id}...")
    del_res = requests.delete(f"{BASE_URL}/messages/{test_id}")
    print(f"Delete Response: {del_res.json()}")
    
    # 6. Verify Erasure - Memory
    mm.load_memories() # Reload from disk
    found_after = False
    for m in mm.get_all_memories():
        if secret in m["text"]:
            found_after = True
            break
            
    if found_after:
        print("❌ Memory STILL EXISTS (Delete Failed)!")
    else:
        print("✅ Memory Successfully Erased.")

    # 7. Verify Erasure - History
    # Note: `app.state.chat_history` is in memory, need to check if endpoint uses state
    h_res_after = requests.get(f"{BASE_URL}/history")
    hist_after = h_res_after.json()
    found_h_after = False
    for msg in hist_after:
        if secret in msg["content"]:
            found_h_after = True
            break
            
    if found_h_after:
        print("❌ History STILL EXISTS (Delete Failed)!")
    else:
        print("✅ History Successfully Erased.")

if __name__ == "__main__":
    test_delete_flow()
