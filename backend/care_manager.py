import json
import os
import time
import uuid
from typing import Dict, List, Any, Optional

class CareManager:
    def __init__(self, data_path: str = "./data/care_list.json"):
        self.data_path = data_path
        self._ensure_data_dir()
        self.care_list = self._load_data()

    def _ensure_data_dir(self):
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)

    def _load_data(self) -> Dict[str, Any]:
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                # [Auto-Cleanup] Purge completed items heavily
                items = data.get("items", [])
                original_count = len(items)
                active_items = [i for i in items if i.get("status") != "completed"]
                
                if len(active_items) < original_count:
                    print(f"[CareManager] Auto-cleaned {original_count - len(active_items)} completed items.")
                    data["items"] = active_items
                    # Save back immediately to effectively scrub the file
                    # We can't call save_data() here because it might overwrite what we just loaded if not careful,
                    # but since we are in _load_data, self.care_list isn't set yet.
                    # It's safer to just return cleaned data and let the first add/update save it,
                    # OR we can write it back now. Writing back is cleaner to ensure file is small.
                    try:
                        with open(self.data_path, "w", encoding="utf-8") as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                    except: pass
                    
                return data
            except Exception as e:
                print(f"[CareManager] Load failed: {e}")
        
        # Default Structure
        return {
            "last_updated": 0,
            "items": []
        }

    def save_data(self):
        """Persist care list to disk."""
        self.care_list["last_updated"] = time.time()
        try:
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump(self.care_list, f, ensure_ascii=False, indent=2)
            # print(f"[CareManager] Saved {len(self.care_list['items'])} items.")
        except Exception as e:
            print(f"[CareManager] Save failed: {e}")

    def add_item(self, category: str, content: str, trigger_time: float, type: str = "one_off", recurrence: str = None) -> str:
        """Add a new care item."""
        new_item = {
            "id": str(uuid.uuid4()),
            "type": type, # one_off | recurring
            "category": category, # health | work | mood | routine
            "content": content,
            "trigger_time": trigger_time,
            "recurrence_rule": recurrence,
            "status": "pending",
            "created_at": time.time()
        }
        self.care_list["items"].append(new_item)
        self.save_data()
        return new_item["id"]

    def update_item_status(self, item_id: str, status: str):
        """
        Update status. 
        [Auto-Delete] If status is 'completed', REMOVE it from the list entirely.
        """
        original_count = len(self.care_list["items"])
        
        if status == "completed":
            # Remove item
            self.care_list["items"] = [
                item for item in self.care_list["items"] 
                if item["id"] != item_id
            ]
            if len(self.care_list["items"]) < original_count:
                print(f"[CareManager] Auto-deleted completed item: {item_id}")
        else:
            # Update status
            for item in self.care_list["items"]:
                if item["id"] == item_id:
                    item["status"] = status
                    break
        
        self.save_data()

    def get_pending_items(self) -> List[Dict]:
        """Get all pending items sorted by trigger time."""
        pending = [i for i in self.care_list["items"] if i["status"] == "pending"]
        pending.sort(key=lambda x: x["trigger_time"])
        return pending

    def get_due_items(self, buffer_seconds: int = 300) -> List[Dict]:
        """
        Get items that are due now or within buffer window.
        Items are considered due if trigger_time <= now + buffer.
        """
        now = time.time()
        due = []
        for item in self.get_pending_items():
            # If time is in the past OR nearing future (within buffer)
            if item["trigger_time"] <= (now + buffer_seconds):
                due.append(item)
        return due

    def get_context_string(self) -> str:
        """
        Format pending care items for LLM Context.
        Prioritizes immediate upcoming items.
        """
        pending = self.get_pending_items()
        if not pending:
            return "当前无任何特别关心事项。"
        
        lines = ["【待办关心事项 (Care List)】"]
        now = time.time()
        
        for item in pending[:5]: # Only show top 5 nearest
            dt = time.strftime("%Y-%m-%d %H:%M", time.localtime(item["trigger_time"]))
            delta = item["trigger_time"] - now
            
            if delta < 0:
                time_desc = f"已超时 {int(abs(delta)/60)} 分钟"
            elif delta < 3600:
                time_desc = f"{int(delta/60)} 分钟后"
            else:
                time_desc = f"{int(delta/3600)} 小时后"
                
            lines.append(f"- [{item['category']}] {item['content']} (时间: {dt}, 状态: {time_desc})")
            
        return "\n".join(lines)
