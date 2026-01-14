
import os
import sys
from dotenv import load_dotenv

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from memory import MemoryManager

def test_memory():
    print("Testing MemoryManager with Gemini 3 Flash Preview...")
    
    load_dotenv()
    key = os.getenv("GEMINI_API_KEY")
    print(f"DEBUG: GEMINI_API_KEY is {'Set' if key else 'None'} (Length: {len(key) if key else 0})")
    
    try:
        mm = MemoryManager()
        if not mm.memory:
            print("❌ Verification Failed: MemoryManager init failed.")
            return

        print("\n[Test 1] Adding Memory...")
        test_content = "My favorite color is #FF0000 (Red)."
        mm.add_memory(test_content)
        print("✅ Added.")

        print("\n[Test 2] Querying Memory...")
        query = "What is my favorite color?"
        result = mm.query_memory(query)
        print(f"Query Result: {result}")
        
        if "Red" in result or "#FF0000" in result:
             print("✅ Verification Success: Memory recalled correctly.")
        else:
             print("❌ Verification Failed: Recalled text did not match.")

    except Exception as e:
        print(f"❌ Verification Exception: {e}")

if __name__ == "__main__":
    test_memory()
