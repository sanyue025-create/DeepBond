# DeepBond (AI Companion Core) 🧠 ❤️

**A Proactive, scientifically-profiled AI Companion that actually gives a damn.**

> "Most AIs wait for you to speak. DeepBond waits for you to go silent, then gets worried."

## What is this?
DeepBond is not just another LLM wrapper. It is an **Autonomous Emotional Agent** designed to build a long-term psychological bond with the user. 
Unlike traditional chatbots that strictly "respond to input", DeepBond possesses an **Autonomous Decision Engine**. It "thinks" even when you are silent.

> **"It doesn't just replay. It decides."**

### Key Features (USP)
1.  **🤖 Autonomous Decision Engine (The "Heartbeat")**:
    *   **Self-Initiative**: The AI runs on an independent clock. It wakes up to check on you, tease you, or respect your silence based on its own decision logic.
    *   **Not a Script**: It uses a real-time LLM loop to evaluate: *"Should I speak now? Or should I wait?"*
    *   **Context Aware**: It knows the difference between "You are busy" (Wait) and "You are lonely" (Engage).

2.  **🧬 Scientific Profiling (OCEAN + Evidence Tags)**: 
    *   Tracks your **Big Five Personality Traits** (Openness, Conscientiousness, etc.) in real-time.
    *   Maintains a "Badge Wall" of your traits (e.g., `details-lover`, `night-owl`) based on evidence, not just bias.
    *   **Anti-Paranoia Logic**: If you say "Stop", it deletes the tag. It doesn't hallucinate "hard to get".

3.  **🧠 Local & Private**: 
    *   Built on **FastAPI + ChromaDB (Mem0)**. 
    *   Your psychological profile stays on your disk.


## Installation

### Backend
1.  `cd backend`
2.  `python -m venv venv` & `source venv/bin/activate`
3.  `pip install -r requirements.txt`
4.  `cp .env.example .env` (Put your Gemini API Key here)
5.  `python main.py`

### Frontend (Atomic UI)
1.  `cd frontend`
2.  `npm install`
3.  `npm run dev`

## Roadmap
- [x] Memory System
- [x] Automatic Profiling
- [ ] Voice Input/Output
- [ ] Telegram/Discord Integration

## License
Apache 2.0
