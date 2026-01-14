# DeepBond (AI Companion Core) 🧠 ❤️

**A Proactive, scientifically-profiled AI Companion that actually gives a damn.**

> "Most AIs wait for you to speak. DeepBond waits for you to go silent, then gets worried."

## What is this?
DeepBond is not just another LLM wrapper. It is an **Autonomous Emotional Agent** designed to build a long-term psychological bond with the user. 
It features a **"Proactive Heartbeat"** system that allows it to initiate conversations based on silence, context, and its own "Mood".

### Key Features (USP)
1.  **🧬 Scientific Profiling (OCEAN + Evidence Tags)**: 
    *   Tracks your **Big Five Personality Traits** (Openness, Conscientiousness, etc.) in real-time.
    *   Maintains a "Badge Wall" of your traits (e.g., `details-lover`, `night-owl`) based on evidence, not just bias.
    *   **Anti-Paranoia Logic**: If you say "Stop", it deletes the tag. It doesn't hallucinate "hard to get".

2.  **💓 Proactive Heartbeat**:
    *   It doesn't sleep when you stop typing. It **thinks**.
    *   If you are silent for too long, it decides whether to check on you, tease you, or leave you alone based on your current `SocialDesire` score.

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
MIT
