import storage
import os
import sys

print("Listing sessions...", flush=True)
sessions = storage.list_sessions()
print(f"Found {len(sessions)} sessions.", flush=True)

if sessions:
    sid = sessions[0]["id"]
    print(f"Loading session {sid}...", flush=True)
    data = storage.load_session(sid)
    history = data.get("history")
    print(f"History Type: {type(history)}", flush=True)
    
    if isinstance(history, list):
         print("History is a list. Trying append...", flush=True)
         history.append({"role": "test"})
         print("Append successful.", flush=True)
    else:
         print(f"CRITICAL: History is {type(history)}", flush=True)
else:
    print("No sessions found.", flush=True)
