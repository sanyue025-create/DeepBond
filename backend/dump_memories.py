
import os
import sys
from dotenv import load_dotenv

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from memory import MemoryManager

def dump_memories():
    print("Dumping all memories from Qdrant/Mem0...")
    load_dotenv()
    
    try:
        mm = MemoryManager()
        if not mm.memory:
            print("❌ MemoryManager init failed.")
            return

        all_memories = mm.get_all_memories()
        
        print(f"\nFound {len(all_memories)} memory items:\n")
        import pprint
        pprint.pprint(all_memories)
    except Exception as e:
        print(f"❌ Dump Exception: {e}")

if __name__ == "__main__":
    dump_memories()
