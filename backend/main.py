import os
import asyncio
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from typing import List, Optional
from datetime import datetime
from prompts import BASE_SYSTEM_PROMPT, get_task_prompt
from pydantic import BaseModel
from core import GeminiClient
from memory import MemoryManager
from profile_manager import ProfileManager
from care_manager import CareManager # [Critical Fix] Re-Import
from dotenv import load_dotenv
import storage
import uuid
import json
import google.generativeai as genai 

load_dotenv()

app = FastAPI(title="Local AI Companion Backend")

# 允许跨域，方便前端调试
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化核心组件
# Allow MemoryManager to use its smart absolute path default if env var is not set
memory = MemoryManager(persist_directory=os.getenv("SUPERMEMORY_LOCAL_PATH"))
gemini = GeminiClient(api_key=os.getenv("GEMINI_API_KEY"))
profile_manager = ProfileManager()
care_manager = CareManager() # [Re-Fix] Init Care Manager

class ChatRequest(BaseModel):
    message: str
    id: Optional[str] = None



# 记录最后互动时间
active_connections: List[WebSocket] = []



@app.get("/history")
async def get_chat_history():
    """
    获取当前内存中的对话历史，供前端刷新后恢复上下文。
    """
    formatted_history = []
    for turn in app.state.chat_history:
        if not isinstance(turn, dict):
            continue
            
        role = "assistant" if turn.get("role") == "model" else "user"
        # parts 可能是字符串或列表，兼容处理
        parts = turn.get("parts", "")
        if isinstance(parts, list) and parts:
            content = parts[0]
        else:
            content = str(parts)
            
        formatted_history.append({
            "id": turn.get("id"), # [Fix] Expose ID for deletion
            "role": role,
            "content": content
        })
    return formatted_history

@app.get("/sessions")
async def list_sessions():
    return storage.list_sessions()

@app.get("/care-list")
async def get_care_list():
    """
    Get current active care items.
    """
    return care_manager.get_pending_items()

@app.post("/sessions/new")
async def new_session():
    # 【优化】如果当前会话已经是空的（没有任何消息），则直接复用，防止生成大量空文件
    if len(app.state.chat_history) == 0:
        print(f"[Session] Reusing empty session: {app.state.current_session_id}")
        return {
            "id": app.state.current_session_id,
            "message": "Session reused (already empty)",
            "chat_history": [],
            "logs": []
        }

    new_id = str(uuid.uuid4())[:8]
    app.state.current_session_id = new_id
    app.state.chat_history = []
    # [Persistence] Clear logs
    app.state.session_logs = []
    
    # 【懒加载优化 (Lazy Save)】
    # 不再立即创建空文件。只有当第一条消息产生时（在 /chat 接口），才会实际写入文件。
    
    print(f"[Session] New session started (InMemory): {new_id}")
    return {
        "id": new_id, 
        "message": "New session started (Ready)",
        "chat_history": [],
        "logs": []
    }

@app.delete("/messages/{msg_id}")
async def delete_message(msg_id: str):
    """
    Delete a message by ID from the current session history and memory.
    """
    if not app.state.chat_history:
        return {"status": "ignored", "detail": "History empty"}
        
    # 1. Remove from Memory (Linked)
    deleted_memories = memory.delete_memory_by_source(msg_id)
    
    # 2. Remove from Chat History
    original_len = len(app.state.chat_history)
    app.state.chat_history = [
        msg for msg in app.state.chat_history 
        if msg.get("id") != msg_id
    ]
    
    deleted_chat = original_len - len(app.state.chat_history)
    
    # 3. Persist
    storage.save_session(app.state.current_session_id, app.state.chat_history)
        
    return {
        "status": "success", 
        "deleted_chat_count": deleted_chat, 
        "deleted_memory_count": deleted_memories
    }

@app.post("/sessions/{session_id}/load")
async def load_session(session_id: str):
    data = storage.load_session(session_id)
    history = data.get("history", [])
    logs = data.get("logs", [])
    # [Defensive] Ensure History is LIST
    if isinstance(history, dict):
        print(f"[Session] WARN: History loaded as DICT (Len: {len(history)}). Resetting to list.")
        history = list(history.values()) if history else []
    elif not isinstance(history, list):
         print(f"[Session] WARN: History loaded as {type(history)}. Resetting to [].")
         history = []

    app.state.current_session_id = session_id
    app.state.chat_history = history
    # [Persistence] Restore logs
    app.state.session_logs = logs 
    
    return {
        "id": session_id, 
        "item_count": len(history), 
        "log_count": len(logs),
        "logs": logs # [Fix] Return actual data so frontend can see it!
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            # 保持连接
            await websocket.receive_text()
    except:
        active_connections.remove(websocket)


async def recursive_analyze_wrapper(session_id: str, profile_context: str, delay: int):
    await asyncio.sleep(delay)
    await schedule_next_event(session_id, profile_context)

@app.post("/chat")
async def chat_endpoint(request: ChatRequest, background_tasks: BackgroundTasks):
    import traceback
    from fastapi.responses import JSONResponse
    
    # 【Event-Driven INTERRUPT】
    # 用户说话了！立刻取消所有 pending 的主动事件，清空计划列表
    if hasattr(app.state, "scheduled_events"):
        print(f"[Interrupt] User spoke. Cancelling {len(app.state.scheduled_events)} pending events.")
        for future in app.state.scheduled_events:
            if not future.done():
                future.cancel()
        app.state.scheduled_events = [] # Clear tracking list
        
        # [Persistence Check] Clear disk tasks too, to prevent Hydration resurrection!
        storage.clear_session_tasks(app.state.current_session_id)

    # 【重要】逻辑对应：既然用户打断了，之前的"长时计划"也作废，由 AI 回复后重新规划

    # [Serialization Lock] Prevent "Barge-in" from killing the current stream.
    # User complained that "next sentence is cut off".
    # Solution: Wait for previous stream to finish (Serialize).
    wait_start = time.time()
    while getattr(app.state, "is_chat_processing", False):
        await asyncio.sleep(0.1)
        if time.time() - wait_start > 30: # Safety Timeout
            print("[Chat] Wait Timeout - Forcing lock break.")
            break


    # [State] Idle (Reset on chat start to be safe, but actually we want Listening?)
    # No, keep previous state. But after chat processing, we should set to Idle.
    
    # 【原子锁】上锁：在处理用户消息期间，禁止主动逻辑插嘴
    app.state.is_chat_processing = True
    start_time = time.time()
    
    try:
        # 重置主动搭讪计数器
        app.state.last_interaction = time.time()
        app.state.consecutive_proactive_count = 0
        
        # 1. 记录用户输入
        t1 = time.time()
        
        # [Identity] Ensure Message ID exists for linking
        user_msg_id = request.id or str(uuid.uuid4())
        
        # 1. 记录用户输入 (Async) - WITH ID LINKING
        asyncio.create_task(asyncio.to_thread(
            memory.add_memory, 
            request.message, 
            metadata={"role": "user", "source_id": user_msg_id}
        ))
        print(f"[Perf] Memory Add: {(time.time() - t1):.3f}s")
        
        # [State] Memory Recall
        for conn in active_connections:
            try: await conn.send_json({"type": "state", "phase": "memory"})
            except: pass

        # 2. 并行检索上下文 (Parallel Context Loading)
        # [Optimization] Run expensive fetches in parallel threads to reduce latency
        t2 = time.time()
        
        async def fetch_memory():
            try: return memory.query_memory(request.message)
            except Exception as e:
                print(f"[Chat] Memory Query Warning: {e}")
                return ""
                
        async def fetch_profile():
            return profile_manager.get_profile_context()
            
        async def fetch_care():
            return care_manager.get_context_string()

        # Run all three concurrently
        results = await asyncio.gather(
            asyncio.to_thread(memory.query_memory, request.message),
            asyncio.to_thread(profile_manager.get_profile_context),
            asyncio.to_thread(care_manager.get_context_string)
        )
        
        memory_context, profile_context, care_raw = results
        print(f"[Perf] Parallel Context Load: {(time.time() - t2):.3f}s")

        if care_raw.strip():
            care_context = f"""
【待办关心事项 (Care List)】
{care_raw}

【植入逻辑 (Insertion Logic)】
1. **时机 (Timing)**: 仅在事项状态为 **READY** 或 **OVERDUE** 时主动提及。对于未来的事项，除非用户问起日程，否则不要提及。
2. **话题 (Topic)**: 如果当前话题非常严肃/悲伤，**推迟**提及任何非紧急事项，优先回应情绪。
3. **自然 (Natural)**: 不要生硬转折。尝试将关心融入当前对话流。
"""
        else:
            care_context = ""

        dynamic_system_prompt = f"{profile_context}\n\n{care_context}"
        
        # [State] Generating (Thinking)
        for conn in active_connections:
            try: await conn.send_json({"type": "state", "phase": "thinking"})
            except: pass

        t4 = time.time()
        t4 = time.time()
        
        # 4. 流式生成回复 (Streaming Response)
        async def response_streamer():
             full_response = ""
             try:
                 try:
                    async for chunk in gemini.stream_chat(
                        request.message, 
                        history=app.state.chat_history, 
                        memory_context=memory_context, 
                        system_instruction=dynamic_system_prompt
                    ):
                        # [Debug] Verify Context Injection
                        if not full_response:
                            print(f"[Chat] Debug Context Length: Mem={len(memory_context)}, Profile={len(profile_context)}")
                            if len(memory_context) > 0: print(f"[Chat] Memory Preview: {memory_context[:100]}...")
                        
                        full_response += chunk
                        yield chunk
                 except Exception as e:
                     print(f"[Streaming] Error: {e}")
                     yield f"[System Error: {str(e)}]"
                     # Continue to finally block
                     
                 print(f"[Perf] Gemini Stream Complete: {(time.time() - t4):.3f}s")

                 # --- Post-Stream Side Effects (Previously Sync) ---
                 if full_response: # Only save if we got something
                     # 【关键修复】显式追加历史记录
                     # [Defensive] Check Type
                     if not isinstance(app.state.chat_history, list):
                         print(f"[Chat] CRITICAL: chat_history is {type(app.state.chat_history)}. Resetting.")
                         app.state.chat_history = []
                         
                     timestamp_now = time.time()
                     app.state.chat_history.append({
                         "id": user_msg_id, # [Link] Store ID in history
                         "role": "user", 
                         "parts": [request.message],
                         "timestamp": timestamp_now 
                     })
                     
                     app.state.chat_history.append({
                         "id": str(uuid.uuid4()), # [Link] Give AI ID too
                         "role": "model", 
                         "parts": [full_response],
                         "timestamp": time.time() 
                     })
                     storage.save_session(app.state.current_session_id, app.state.chat_history)
                 
                     # 7. 后台任务
                    app.state.message_count = getattr(app.state, "message_count", 0) + 1
                    
                    # [Logic] Regular Schedule
                    should_analyze = (app.state.message_count <= 2) or (app.state.message_count % 10 == 0)
                    
                    # [Logic] Emergency Trigger (Anti-Paranoia)
                    # If user says "Stop", update profile IMMEDIATELY to apply the Falsification Principle.
                    emergency_keywords = ["stop", "don't", "quit", "shut", "off", "停", "不要", "闭嘴", "烦", "吵", "够了"]
                    if any(k in request.message.lower() for k in emergency_keywords):
                        print(f"[Profile] Emergency Trigger detected in: '{request.message}'")
                        should_analyze = True

                    if should_analyze:
                        background_tasks.add_task(run_profile_analysis, list(app.state.chat_history))
                 
                     # [CareSystem + Decision Chain] 
                     async def shielded_care_sequence(prompt_str):
                         try:
                             # 1. Update Care List
                             await run_care_update(list(app.state.chat_history))
                            
                             # 2. Conditionally Schedule
                             current_gap = time.time() - app.state.last_interaction
                             if current_gap < 0.5: 
                                 print(f"[Sequence] User active (gap {current_gap:.2f}s), skipping proactive schedule.")
                                 return

                             sche_task = asyncio.create_task(schedule_next_event(app.state.current_session_id, prompt_str, 1))
                             app.state.scheduled_events.append(sche_task)
                             sche_task.add_done_callback(lambda f: app.state.scheduled_events.remove(f) if f in app.state.scheduled_events else None)
                            
                         except Exception as e:
                             print(f"[Sequence] Error: {e}")

                     asyncio.create_task(shielded_care_sequence(str(dynamic_system_prompt)))
             
             finally:
                 # [Unlock] Serialization Complete - ALWAYS RUNS
                 print("[Chat] Releasing Lock.")
                 app.state.is_chat_processing = False
                 for conn in active_connections:
                     try: await conn.send_json({"type": "state", "phase": "idle"})
                     except: pass

        return StreamingResponse(response_streamer(), media_type="text/plain")

    except Exception as e:
        error_msg = str(e)
        app.state.is_chat_processing = False # Unlock on error
        if "429" in error_msg or "quota" in error_msg.lower():
            print(f"[Chat] Quota Exceeded: {error_msg}")
            return JSONResponse(status_code=429, content={"detail": "Quota Exceeded"})
            
        full_trace = traceback.format_exc()
        print(f"Chat Endpoint Error: {error_msg}\n{full_trace}")
        return JSONResponse(status_code=500, content={"detail": f"System Error: {error_msg}"})

# run_task_extraction REMOVED - Unified into schedule_next_event

async def run_profile_analysis(history):
    print("[Profile] Analyzing user persona...")
    
    # [State] Profile Update
    for conn in active_connections:
        try: await conn.send_json({"type": "state", "phase": "profile"})
        except: pass


        
    current_profile = profile_manager.profile
    profile_data = await gemini.analyze_profile(history, current_profile)
    if profile_data:
        profile_manager.save_profile(profile_data)
        
    # [State] Return to Idle (or whatever previous state was, but idle is safe)
    # Actually, don't force idle here, as it might happen in parallel? 
    # Profile usually happens AFTER chat. So let's briefy flash it then idle.
    await asyncio.sleep(1)
    for conn in active_connections:
        await conn.send_json({"type": "state", "phase": "idle"})

async def run_care_update(history):
    """
    [Care System] Background Task
    """
    try:
        print("[CareSystem] Triggering analysis...")
        current_list = care_manager.care_list["items"]
        # Use a copy of history to avoid race conditions
        history_copy = [h for h in history]
        
        result = await gemini.analyze_care_needs(history_copy, current_list)
        
        if result and "actions" in result:
            actions = result["actions"]
            if actions:
                print(f"[CareSystem] Found {len(actions)} actions: {actions}")
                for action in actions:
                    act_type = action.get("type")
                    if act_type == "ADD":
                        care_manager.add_item(
                            category=action.get("category", "general"),
                            content=action.get("content"),
                            trigger_time=time.time() + action.get("trigger_time_offset", 3600),
                            type="one_off" # Smartly detect recurring later
                        )
                    elif act_type == "UPDATE":
                        # Logic to update
                        pass 
                    elif act_type == "DELETE":
                        care_manager.update_item_status(action.get("id"), "completed")
            else:
                 print("[CareSystem] No actions needed.")
    except Exception as e:
        print(f"[CareSystem] Update failed: {e}")

async def task_executor(thought_data: dict):
    """
    [Event-Driven] Executes a scheduled logic from memory.
    """
    task_content = thought_data.get("analysis", "Checkin")
    print(f"[Scheduler] Executing memory task: {task_content}")
    
    # Use descriptive trigger to avoid "ellipses" hallucination
    trigger_msg = "(用户默认在场，请直接继续你的发言)" 
    last_ai_reply = app.state.chat_history[-1].get("parts", [""])[0] if app.state.chat_history and app.state.chat_history[-1].get("role") == "model" else "无"
    
    intent = thought_data.get("decision", "下意识互动")
    
    # [Detox] Unified clean instructions with Intent Awareness
    sys_instruction = f"""【系统指令】执行此任务：{task_content}。
    你现在的社交意图是：【{intent}】。
    
    【执行原则】
    1. 根据上下文自然介入，直接输出台词。
    2. 语气必须符合你的 CORE_PERSONA 。
    3. 严禁复读。你刚才最后说的一句话是："{last_ai_reply}"。禁止生成与之语义/意图高度雷同的内容。
    """
    
    try:
        response_text = await gemini.chat(
            user_input=trigger_msg, # Trigger
            history=app.state.chat_history, # Use full history for context
            system_instruction=sys_instruction,
            memory_context="" 
        )

        if "CANCEL_REPETITION" in response_text:
            print(f"[Scheduler] 🛑 Task {task_content} cancelled due to intent/repetition check.")
            # return
            pass

        if response_text:
            print(f"[Scheduler] Generated: {response_text}")
            for conn in active_connections:
                await conn.send_json({"type": "proactive", "content": response_text, "thought": task_content})
            
            # [Apple Integration] Smart Notification
            # Rule: Only notify if user has been away for > 2 minutes (120s)
            idle_time = time.time() - getattr(app.state, "last_interaction", 0)
            if idle_time > 120:
                from apple_client import send_to_reminders
                # Run sync in thread to avoid blocking main loop
                asyncio.create_task(asyncio.to_thread(send_to_reminders, title="AI 关心提醒", body=response_text))
            else:
                print(f"[Apple] Muted (Idle: {int(idle_time)}s < 120s)")
            
            # [Disinfect] Don't add proactive message to long-term memory to avoid pattern infection
            # memory.add_memory(response_text, metadata={"role": "assistant", "type": "task"})
            
            app.state.chat_history.append({
                "role": "model", 
                "parts": [response_text],
                "timestamp": time.time()
            })
            storage.save_session(app.state.current_session_id, app.state.chat_history)
            
            # [CareSystem] Loop Closure: Analyze proactive interaction to update list
            # (e.g. Mark "Reminder" as done if we just said it)
            asyncio.create_task(run_care_update(list(app.state.chat_history)))

        # memory.add_memory(response_text, metadata={"role": "assistant", "type": "proactive_task"})
        
        # Increment Proactive Counter
        app.state.consecutive_proactive_count = getattr(app.state, "consecutive_proactive_count", 0) + 1
        
        # [Fix] Fetch fresh profile context for the Next Move analysis
        # Otherwise the AI forgets "Who it is" and "Who user is" in the next loop.
        next_profile_context = profile_manager.get_profile_context()

        # Don't auto-schedule next event immediately. 
        # Wait for user response? Or should the AI continue thinking? 
        # Let's trigger a light post-action analysis to see if it wants to follow up.
        asyncio.create_task(schedule_next_event(app.state.current_session_id, next_profile_context))
        
    except Exception as e:
        print(f"[Scheduler] Execution failed: {e}")

async def schedule_next_event(session_id: str, profile_context: str, delay: int = 1):
    """
    [Event-Driven] The Brain. 
    Decides the SINGLE next move after an interaction.
    Uses a simple lock to prevent parallel analysis race conditions.
    """
    if getattr(app.state, "is_analyzing", False):
        return # Skip if already thinking
    
    app.state.is_analyzing = True
    try:
        await asyncio.sleep(delay)
    
        if app.state.current_session_id != session_id:
            return

        current_count = getattr(app.state, "consecutive_proactive_count", 0)
        print(f"[Scheduler] Thinking about next move... (Count: {current_count})")
        
        # [CareSystem] Inject context for decision making
        care_context = care_manager.get_context_string()
        
        result = await gemini.evaluate_next_move(app.state.chat_history, profile_context, care_context=care_context, consecutive_count=current_count)
        action = result.get("action")
        print(f"[Scheduler] Decision: {result}")
        
        # Broadcast Thought
        # Broadcast Thought
        model_thought = {
            "observation": "Events Planning",
            "analysis": result.get("thought", "No thought"),
            "decision": action,
            "schedule": f"{result.get('delay_seconds', 0)}s"
        }
        
        # [Persistence] Save Thought to Session Logs
        app.state.session_logs.append({
            "type": "thought",
            "content": model_thought, # JSON object
            "timestamp": time.strftime("%H:%M:%S")
        })
        storage.save_session(app.state.current_session_id, app.state.chat_history, app.state.session_logs)

        # Broadcast Thought
        # Broadcast Thought (Safe Mode)
        for conn in list(active_connections): # Copy list to avoid modification errors during iteration
            try:
                await conn.send_json({"type": "thought", "content": model_thought})
            except Exception as e:
                print(f"[Scheduler] Broadcast Error: {e}")
                # Optional: Remove dead connection right here?
                # Better to let the receive loop handle removal, but we can't wait.
                # If we remove it here, we might race with the receive loop.
                # Just ignore failure is safest.

        if action == "WAIT" or action == "WAIT_FOR_USER":
            print(f"[Scheduler] 💤 Decided to wait. Reason: {result.get('thought', 'No thought')}")
            return

        # Handle Actions
        task_content = result.get("reasoning", "Thinking...")
        delay_seconds = result.get("delay_seconds", 30)
        try:
            delay_seconds = int(delay_seconds)
        except:
            delay_seconds = 30
            
        # --- 分流逻辑 (Unified Persistence) ---
        # All autonomous actions (except WAIT) are now Persistent Tasks.
        # They survive refresh, hydrate on load, and expire if missed.
        
        # [Clean Up] Legacy Reminder Logic Removed
        # Unified Persistence: All internal schedule checks are now Persistent Tasks
        
        target_actions = ["LONG_WAIT_CHECKIN", "IMMEDIATE_FOLLOWUP", "DELAYED_FOLLOWUP"]
        
        if action in ["LONG_WAIT_CHECKIN", "IMMEDIATE_FOLLOWUP", "DELAYED_FOLLOWUP"]:
             # [Clean] Pure Memory Execution (No Task Persistence)
             if action == "IMMEDIATE_FOLLOWUP":
                 delay_seconds = 15 # [Changed from 5 to 15] Safety Buffer
             elif action == "DELAYED_FOLLOWUP":
                 if delay_seconds < 10: delay_seconds = 30
             
             print(f"[Scheduler] Scheduling Memory Timer ({action}): {delay_seconds}s")
             
             async def memory_trigger():
                 try:
                     # Calculate absolute trigger time
                     trigger_ts = time.time() + delay_seconds
                     
                     # [Persistence] Save Task Intent
                     task_id = str(uuid.uuid4())
                     task_data = {
                         "id": task_id,
                         "trigger_time": trigger_ts,
                         "action": action,
                         "thought": model_thought
                     }
                     storage.add_scheduled_task(session_id, task_data)
                     
                     # [Execution] Wait and Trigger
                     if delay_seconds > 0:
                         await asyncio.sleep(delay_seconds)
                     
                     if app.state.current_session_id == session_id: # Strict Isolation
                         # [Persistence] Remove task from disk before executing
                         storage.remove_scheduled_task(task_id)
                         # [Action] Execute the thought
                         # We need to find task_executor. It must be defined in global scope or passed in.
                         # Since hydrate calls it, it must be global.
                         await task_executor(model_thought.copy())
                         
                 except asyncio.CancelledError:
                     pass
                 except Exception as e:
                     print(f"[Scheduler] Trigger Error: {e}")
                     
             future = asyncio.create_task(memory_trigger())
             app.state.scheduled_events.append(future)
             future.add_done_callback(lambda f: app.state.scheduled_events.remove(f) if f in app.state.scheduled_events else None)

    finally:
        app.state.is_analyzing = False

def hydrate_session_tasks(session_id: str):
    """
    [Recovery] Load pending tasks from disk and re-schedule them.
    """
    print(f"[Hydration] Checking tasks for session {session_id}...")
    tasks = storage.get_scheduled_tasks(session_id)
    now = time.time()
    count = 0
    
    for task in tasks:
        trigger_time = task.get("trigger_time", now)
        delay = trigger_time - now
        task_id = task.get("id")
        thought = task.get("thought", {})
        
        # Define re-hydrated trigger
        async def rehydrated_trigger(d, t_id, th):
            try:
                if d > 0:
                    print(f"[Hydration] Resuming task {t_id} (Wait {int(d)}s)")
                    await asyncio.sleep(d)
                else:
                    print(f"[Hydration] Catch-up task {t_id} (Overdue by {int(-d)}s)")
                
                if app.state.current_session_id == session_id:
                     storage.remove_scheduled_task(t_id)
                     await task_executor(th)
            except Exception as e:
                print(f"[Hydration] Error executing task {t_id}: {e}")

        future = asyncio.create_task(rehydrated_trigger(delay, task_id, thought))
        app.state.scheduled_events.append(future)
        future.add_done_callback(lambda f: app.state.scheduled_events.remove(f) if f in app.state.scheduled_events else None)
        count += 1
        
    if count > 0:
        print(f"[Hydration] Restored {count} pending tasks.")

@app.on_event("startup")
async def startup_event():
    # 初始化全局状态
    app.state.interrupt_event = asyncio.Event()
    app.state.is_chat_processing = False
    app.state.last_interaction = time.time()
    app.state.consecutive_proactive_count = 0
    
    # Event Driven State
    app.state.scheduled_events = [] # List of asyncio.Task
    
    print("[Startup] System initialized (Active Protocols DELETED).")
    print("[Startup] Cleanup complete.")

    # 初始化 Session (尝试加载最近的)
    sessions = storage.list_sessions()
    if sessions:
        latest_session = sessions[0]
        app.state.current_session_id = latest_session["id"]
        # Legacy load
        session_data = storage.load_session(latest_session["id"])
        app.state.chat_history = session_data.get("history", [])
        app.state.session_logs = session_data.get("logs", [])
        print(f"[Startup] Resumed session: {app.state.current_session_id} ({len(app.state.chat_history)} msgs)")
        
        # [Hydration] Restore timers
        hydrate_session_tasks(app.state.current_session_id)
    else:
        app.state.current_session_id = str(uuid.uuid4())[:8]
        app.state.chat_history = [] 
        app.state.session_logs = []
        print(f"[Startup] New session: {app.state.current_session_id}")
    
    # No more proactive_loop()
    print("[Startup] Event-Driven Scheduler ready. Waiting for input.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
