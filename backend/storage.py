import json
import os
import time
from typing import List, Dict, Any

# Ensure Absolute Path for Data
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")

def ensure_dirs():
    os.makedirs(SESSIONS_DIR, exist_ok=True)



# --- Sessions Persistence ---
def get_session_file(session_id: str) -> str:
    return os.path.join(SESSIONS_DIR, f"{session_id}.json")

def load_session(session_id: str) -> Dict[str, Any]:
    ensure_dirs()
    filepath = get_session_file(session_id)
    if not os.path.exists(filepath):
        return {"history": [], "logs": []}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
            # Sanitize History to prevent 'str' errors
            raw_history = data.get("history", [])
            if isinstance(data, list): raw_history = data # Legacy support 
            
            clean_history = [
                item for item in raw_history 
                if isinstance(item, dict) and "role" in item
            ]
            
            return {
                "history": clean_history,
                "logs": data.get("logs", []) if isinstance(data, dict) else []
            }
    except Exception as e:
        print(f"[Storage] Error loading session {session_id}: {e}")
        return {"history": [], "logs": []}

def save_session(session_id: str, history: List[Dict], logs: List[Dict] = None):
    ensure_dirs()
    filepath = get_session_file(session_id)
    
    # Preserve existing logs if not provided
    existing_logs = []
    if logs is None and os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                if isinstance(old_data, dict):
                    existing_logs = old_data.get("logs", [])
        except: pass
    
    final_logs = logs if logs is not None else existing_logs
    
    data = {
        "id": session_id,
        "updated_at": time.time(),
        "history": history,
        "logs": final_logs,
        "preview": history[-1]["parts"][0][:50] if history and isinstance(history[-1]["parts"], list) else "Empty"
    }
    
    # [Debug] Verify Logs
    if final_logs:
        print(f"[Storage] Saving {len(final_logs)} logs for session {session_id}.")
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Storage] Error saving session {session_id}: {e}")

# --- Persistent Tasks (The "Notebook") ---
TASKS_FILE = os.path.join(DATA_DIR, "scheduled_tasks.json")

def _load_all_tasks() -> List[Dict]:
    if not os.path.exists(TASKS_FILE):
        return []
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def _save_all_tasks(tasks: List[Dict]):
    try:
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Storage] Error saving tasks: {e}")

def add_scheduled_task(session_id: str, task_data: Dict):
    """
    Persist a future task.
    task_data: { "id": uuid, "trigger_time": float, "action": str, "thought": dict }
    """
    ensure_dirs()
    tasks = _load_all_tasks()
    # Add session_id to data
    task_data["session_id"] = session_id
    tasks.append(task_data)
    _save_all_tasks(tasks)
    print(f"[Storage] Task persisted: {task_data.get('action')} @ {task_data.get('trigger_time')}")

def get_scheduled_tasks(session_id: str) -> List[Dict]:
    """Get all pending tasks for a specific session."""
    all_tasks = _load_all_tasks()
    return [t for t in all_tasks if t.get("session_id") == session_id]

def remove_scheduled_task(task_id: str):
    """Remove a task after it's done or cancelled."""
    tasks = _load_all_tasks()
    new_tasks = [t for t in tasks if t.get("id") != task_id]
    if len(tasks) != len(new_tasks):
        _save_all_tasks(new_tasks)
        print(f"[Storage] Task {task_id} removed.")

def clear_session_tasks(session_id: str):
    """
    [Interrupt] Clear ALL pending tasks for a specific session.
    Used when user speaks, invalidating all previous future plans.
    """
    tasks = _load_all_tasks()
    original_count = len(tasks)
    new_tasks = [t for t in tasks if t.get("session_id") != session_id]
    
    if len(new_tasks) < original_count:
        _save_all_tasks(new_tasks)
        print(f"[Storage] Cleared {original_count - len(new_tasks)} tasks for session {session_id}")

def list_sessions() -> List[Dict]:
    ensure_dirs()
    sessions = []
    for filename in os.listdir(SESSIONS_DIR):
        if filename.endswith(".json"):
            filepath = os.path.join(SESSIONS_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sessions.append({
                        "id": data.get("id", filename.replace(".json", "")),
                        "updated_at": data.get("updated_at", 0),
                        "preview": data.get("preview", "No preview")
                    })
            except Exception as e:
                print(f"[Storage] Error loading session {filename}: {e}")
    
    # Sort by updated_at desc
    sessions.sort(key=lambda x: x["updated_at"], reverse=True)
    return sessions
