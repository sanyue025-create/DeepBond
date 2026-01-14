import os
import json
import time
from typing import Dict, List, Any
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# [Memory System V2: JSON + Gemini Embedding]
# Why? Because Local Qdrant/Chroma persistence proved flaky in this environment.
# This system stores memories as a simple JSON list [text, embedding, timestamp].
# It is 100% persistent and process-safe (simple file write).

class MemoryManager:
    def __init__(self, persist_directory: str = None):
        if persist_directory is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.data_dir = os.path.join(base_dir, "data")
        else:
            self.data_dir = persist_directory

        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

        self.memory_file = os.path.join(self.data_dir, "memories.json")
        
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            print("[Memory] Warning: No API Key found.")
        else:
            genai.configure(api_key=self.api_key)

        self.memories = [] # List of {"text": str, "embedding": List[float], "timestamp": float}
        self.load_memories()

    def load_memories(self):
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    self.memories = json.load(f)
                print(f"[Memory] Loaded {len(self.memories)} memories from disk.")
            except Exception as e:
                print(f"[Memory] Failed to load memories: {e}")
                self.memories = []
        else:
            print("[Memory] No existing memory file found. Starting fresh.")
            self.memories = []

    def save_memories(self):
        try:
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.memories, f, ensure_ascii=False, indent=2)
            print("[Memory] Persisted to disk.")
        except Exception as e:
            print(f"[Memory] Save failed: {e}")

    def _get_embedding(self, text: str) -> List[float]:
        try:
            # Use 'retrieval_document' for storage
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=text,
                task_type="retrieval_document",
                title="Memory"
            )
            return result['embedding']
        except Exception as e:
            print(f"[Memory] Embedding failed: {e}")
            return []

    def add_memory(self, content: str, metadata: Dict = None):
        """
        Add a new memory string. 
        """
        print(f"[Memory] Adding: '{content[:50]}...'")
        
        # 1. Embed
        vector = self._get_embedding(content)
        if not vector:
            return

        # 2. Store
        memory_item = {
            "text": content,
            "embedding": vector,
            "timestamp": time.time(),
            "metadata": metadata or {}
        }
        self.memories.append(memory_item)
        
        # 3. Persist immediately
        self.save_memories()

    def delete_memory_by_source(self, source_id: str) -> int:
        """
        Delete memories linked to a specific source message ID.
        Returns count of deleted items.
        """
        initial_count = len(self.memories)
        self.memories = [
            m for m in self.memories 
            if m.get("metadata", {}).get("source_id") != source_id
        ]
        deleted_count = initial_count - len(self.memories)
        
        if deleted_count > 0:
            print(f"[Memory] Deleted {deleted_count} items via Source ID: {source_id}")
            self.save_memories()
        
        return deleted_count

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        if not v1 or not v2: return 0.0
        dot_product = sum(a*b for a,b in zip(v1, v2))
        magnitude1 = sum(a*a for a in v1) ** 0.5
        magnitude2 = sum(b*b for b in v2) ** 0.5
        if magnitude1 == 0 or magnitude2 == 0: return 0.0
        return dot_product / (magnitude1 * magnitude2)

    def query_memory(self, query: str, top_k: int = 3) -> str:
        if not self.memories:
            return ""

        print(f"[Memory] Searching for: '{query}'")
        
        # 1. Embed Query
        try:
            query_embed = genai.embed_content(
                model="models/text-embedding-004",
                content=query,
                task_type="retrieval_query"
            )['embedding']
        except Exception as e:
            print(f"[Memory] Query embedding failed: {e}")
            return ""

        # 2. Rank
        scored_memories = []
        for mem in self.memories:
            score = self._cosine_similarity(query_embed, mem["embedding"])
            scored_memories.append((score, mem))

        # Sort descending
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        
        # 3. Filter and Format
        top_results = scored_memories[:top_k]
        
        # Filter low relevance? (Optional)
        # top_results = [m for m in top_results if m[0] > 0.4]

        format_list = []
        for score, mem in top_results:
            print(f"  - Found (Score {score:.4f}): {mem['text'][:50]}...")
            format_list.append(f"- {mem['text']}")

        if not format_list:
            return ""

        return "【相关长期记忆】:\n" + "\n".join(format_list)

    def get_all_memories(self) -> List[Dict]:
        return self.memories

    def query_contextual(self, context_desc: str, top_k: int = 5) -> List[str]:
        # Alias for query_memory logic but returning raw list
        # We reuse query_memory for simplicity or duplicate logic
        # For now, let's keep it simple
        if not self.memories: return []
        
        try:
            query_embed = genai.embed_content(
                model="models/text-embedding-004",
                content=context_desc,
                task_type="retrieval_query"
            )['embedding']
            
            scored = []
            for mem in self.memories:
                score = self._cosine_similarity(query_embed, mem["embedding"])
                scored.append((score, mem))
            
            scored.sort(key=lambda x: x[0], reverse=True)
            return [m[1]["text"] for m in scored[:top_k]]
        except:
            return []
