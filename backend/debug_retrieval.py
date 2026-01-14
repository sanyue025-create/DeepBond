from memory import MemoryManager
import time
from dotenv import load_dotenv
import os

load_dotenv()

def test_json_memory():
    # 1. Initialize
    print("[Test] Init...")
    mm = MemoryManager()
    
    # 2. Add
    print("[Test] Adding Memory...")
    mm.add_memory("My favorite color is #FF0000 (Red)")
    
    # 3. Query Immediate
    print("[Test] Querying...")
    res = mm.query_memory("What is my favorite color?", top_k=1)
    print(f"Result: {res}")
    
    if "FF0000" in res:
        print("✅ Immediate Recall Success")
    else:
        print("❌ Immediate Recall Failed")
        
    # 4. Verify File
    if os.path.exists(mm.memory_file):
        print(f"✅ Persistence File Exists: {mm.memory_file}")
    else:
        print("❌ Persistence File Missing")

    # 5. Semantic Test (Cross-Lingual)
    print("[Test] Semantic Query (Chinese)...")
    res_cn = mm.query_memory("它还是想不起来什么颜色")
    print(f"Result CN: {res_cn}")
    
    if "FF0000" in res_cn:
         print("✅ Semantic Recall Success")
    else:
         print("❌ Semantic Recall Failed")


if __name__ == "__main__":
    test_json_memory()
