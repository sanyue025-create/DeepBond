import os
import json
import logging
from memory import MemoryManager
import storage

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SESSION_ID = "3b986ef3"
SESSION_FILE = f"data/sessions/{SESSION_ID}.json"

def cleanup():
    # 1. Init Memory
    mm = MemoryManager()
    
    # 2. Load Session to find Linked Memories
    linked_deleted_count = 0
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r") as f:
                data = json.load(f)
                
            history = data.get("history", [])
            logging.info(f"Scanning {len(history)} messages for linked memories...")
            
            for msg in history:
                msg_id = msg.get("id")
                if msg_id:
                    count = mm.delete_memory_by_source(msg_id)
                    linked_deleted_count += count
            
            logging.info(f"Deleted {linked_deleted_count} linked memories.")
            
        except Exception as e:
            logging.error(f"Error scanning session file: {e}")
    else:
        logging.warning(f"Session file {SESSION_FILE} not found. Skipping memory scan.")

    # 3. Clear Scheduled Tasks (Decision Records)
    logging.info("Clearing scheduled tasks...")
    storage.clear_session_tasks(SESSION_ID)

    # 4. Delete Session File
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)
        logging.info("Session file deleted.")
        print(f"SUCCESS: Session {SESSION_ID} and all related data (Tasks, Memories) eradicated.")
    else:
        print(f"DONE: Session file already missing, but cleaned up Tasks/Memories.")

if __name__ == "__main__":
    cleanup()
