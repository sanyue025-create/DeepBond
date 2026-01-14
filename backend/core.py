import os
import time
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
import google.generativeai as genai
from prompts import CORE_PERSONA, CORE_STYLE, BASE_SYSTEM_PROMPT
from dotenv import load_dotenv

load_dotenv()



class GeminiClient:
    """
    封装 Gemini API 调用，针对 Gemini 3.0 Flash 优化。
    集成真实 API，移除 Mock 模式。
    """
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("[Gemini] API Key missing.")
        genai.configure(api_key=api_key)
        # 默认不传 system_instruction，在 chat 方法中动态生成
        # Switch to Stable 2.0 Flash (Verified in List) or Configurable via ENV
        # Switch to Stable 2.0 Flash (Verified in List) or Configurable via ENV
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
        
        # [Safety Settings] Relax filters to prevent "PROHIBITED_CONTENT" blocks during roleplay
        self.safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

    def _compact_history(self, history: List[Dict]) -> List[Dict]:
        """
        [Advanced Detox] Enforce role alternation and DISINFECT context.
        - Deduplicate lines within messages.
        - Prevent 'Pattern Infection' by skipping repetitive cross-turn echoes.
        """
        if not history:
            return []
        
        # [Performance] Sliding Window: Keep last 60 turns
        # This prevents the context from growing indefinitely and causing timeouts/cutoffs.
        # Long-term facts are handled by RAG (MemoryManager).
        if len(history) > 60:
            history = history[-60:]

        compacted = []
        seen_lines = set() # Track lines to prevent cross-turn line-level repetition
        
        for msg in history:
            role = msg.get("role")
            parts = msg.get("parts", [""])
            text = parts[0] if parts else ""
            
            # [Time Awareness] Inject timestamp into context
            timestamp = msg.get("timestamp")
            if timestamp:
                dt = datetime.fromtimestamp(timestamp)
                time_str = dt.strftime("[%H:%M] ")
                if not text.startswith("["): # Prevent double prefix if already applied
                    text = f"{time_str}{text}"

            if not text: continue
            
            # 1. Intra-turn deduplication (Deduplicate lines within THIS message)
            # [Fix] PRESERVE empty lines for paragraph breaks! Don't use 'if l.strip()'
            lines = [l.rstrip() for l in text.split('\n')]
            unique_lines_this_turn = []
            for line in lines:
                # [Fix] ALWAYS keep empty lines for formatting! Dedupe only content.
                if not line or line not in unique_lines_this_turn:
                    # Optional: only deduplicate long lines to avoid removing common particles
                    if not line or len(line) > 10 or line not in [l for l in unique_lines_this_turn if l]:
                        unique_lines_this_turn.append(line)
            
            # 2. Cross-turn line-level deduplication (Protect against "A-B-A" echoes)
            # Only apply this to long sentences to avoid breaking the persona's particles
            final_lines = []
            for line in unique_lines_this_turn:
                final_lines.append(line)
                seen_lines.add(line)
            clean_text = "\n".join(final_lines)
            if not clean_text: continue

            if compacted and compacted[-1]["role"] == role:
                # Merge logic with redundant check
                prev_text = compacted[-1]["parts"][0]
                if clean_text not in prev_text:
                    compacted[-1]["parts"] = [f"{prev_text}\n{clean_text}"]
            else:
                compacted.append({"role": role, "parts": [clean_text]})
        
        return compacted

    async def chat(self, user_input: str, history: List[Dict] = None, system_instruction: str = "", memory_context: str = "") -> str:
        # 1. 构建 System Instruction
        full_instruction = f"{BASE_SYSTEM_PROMPT}\n{system_instruction}\n\n当前上下文记忆:\n{memory_context}\n\n当前北京时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # 2. 构建 History (Enforce alternation)
        contents = self._compact_history(history) if history else []

        # 3. 追加当前用户输入 (仅当有输入时)
        if user_input is not None:
            # Handle user turn if consecutive
            if compacted_user := user_input.strip():
                if contents and contents[-1].get("role") == "user":
                    prev_text = contents[-1]["parts"][0]
                    contents[-1]["parts"] = [f"{prev_text}\n{compacted_user}"]
                else:
                    contents.append({"role": "user", "parts": [compacted_user]})


        # 4. 调用 Stateless API (generate_content)
        # 这样可以完全控制上下文窗口，避免 start_chat 的黑盒状态积累问题
        model = genai.GenerativeModel(
            model_name=self.model_name, 
            system_instruction=full_instruction,
            safety_settings=self.safety_settings
        )
        
        # [Safety] API requires non-empty contents
        if not contents:
            print("[Gemini] Warning: Contents empty. Injecting starter.")
            contents.append({"role": "user", "parts": ["(System: Conversation Start)"]})

        try:
            # print(f"[Gemini] Sending {len(contents)} msgs...")
            response = await model.generate_content_async(
                contents, 
                generation_config={
                    "temperature": 1.0
                }
            )
            return response.text
        except Exception as e:
            print(f"[Gemini] Error: {e}")
            return "Error generating response."

    async def stream_chat(self, user_input: str, history: List[Dict] = None, system_instruction: str = "", memory_context: str = ""):
        """
        Stream output generator.
        """
        full_instruction = f"{BASE_SYSTEM_PROMPT}\n{system_instruction}\n\n当前上下文记忆:\n{memory_context}\n\n当前北京时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Enforce role alternation
        contents = self._compact_history(history) if history else []

        if user_input is not None:
             if compacted_user := user_input.strip():
                if contents and contents[-1].get("role") == "user":
                    prev_text = contents[-1]["parts"][0]
                    contents[-1]["parts"] = [f"{prev_text}\n{compacted_user}"]
                else:
                    contents.append({"role": "user", "parts": [compacted_user]})
        
        if not contents:
             contents.append({"role": "user", "parts": ["(System: Conversation Start)"]})

        model = genai.GenerativeModel(
            model_name=self.model_name, 
            system_instruction=full_instruction,
            safety_settings=self.safety_settings
        )
        
        try:
            # Note: stream=True returns an async generator
            print(f"[GeminiDebug] Sending contents: {json.dumps(contents, ensure_ascii=False, indent=2)}")
            response = await model.generate_content_async(
                contents, 
                stream=True, 
                generation_config={
                    "temperature": 0.8, # [Tuning] Balanced for persona vs repetition
                    "top_p": 0.95,

                    "max_output_tokens": 2000,
                }
            )
            async for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            print(f"[Gemini] Stream Error: {e}")
            yield f"[Error: {str(e)}]"



    async def analyze_profile(self, history: List[Dict[str, Any]], current_profile: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        分析对话历史，生成用户画像 (Psychological Profile)。
        """
        # 仅分析最近的 N 条，避免 token 过多，但要足够多以捕捉特征
        recent_history = history[-20:] 
        current_tags = current_profile.get("tags", []) if current_profile else []
        current_info = current_profile.get("basic_info", {})
        
        prompt = f"""
        【任务：动态用户侧写 (Dynamic Profiling)】
        请分析最近的对话，**更新**用户的心理画像和基础信息。
        注意：**人是动态的**。不要被过去的标签束缚，请敏锐捕捉用户**此时此刻**的变化。
        
        【现有信息 (Basic Info)】
        {json.dumps(current_info, ensure_ascii=False)}

        【现有标签 (Current Tags)】
        {json.dumps(current_tags, ensure_ascii=False)}

        【对话记录】
        {json.dumps(recent_history, ensure_ascii=False)}

        【分析重点】
        - **Variability (变化)**: 用户现在是否比以前更放松？更焦虑？
        - **Nuance (细节)**: 捕捉微小的语气变化（如撒娇、反讽、疲惫的标点符号）。
        - **Calibration (校准)**: 如果用户的行为与旧画像不符，**大胆修正**旧画像。
        - **Facts (事实)**: 提取用户名为、职业、地点等客观信息。

        【Tags 生成规则 (Badge System - Scientific Approach)】
        你需要维护一个 **"长期特征勋章墙"**。
        1. **严格分类 (Strict Categories)**: 标签只能属于以下两类：
           - **Identity (核心身份)**: 长期稳定的特质 (e.g., "INTJ", "程序员", "游戏玩家").
           - **Preference (交互偏好)**: 明确的互动规则 (e.g., "拒绝废话", "喜欢单刀直入").
        2. **拒绝瞬时状态**: 严禁记录情绪 (e.g. "生气", "开心", "困")。情绪属于 `state_current`，不属于 Tags。
        3. **合并同类项**: 如果已有 "机智的"，就不要加 "聪明的"。保持标签库精简、互斥。
        4. **证据优先**: 只有当特征重复出现 (>3次) 或用户明确声明时，才可入库。不要捕风捉影。
        4. **证伪原则 (Falsification)**: 
           - 如果用户明确表示反感（如'别闹了', '停', '我不喜欢'，'太吵了'），**立即删除**相关标签（如'撒娇', '高压'）。
           - **严禁**把用户的明确拒绝过度解读为'欲拒还迎'或'测试边界'。拒绝就是拒绝。

        【输出要求】
        请输出 JSON 格式（**必须包含以下字段**）：
        1. **basic_info** (基础信息, 仅在有明确事实变更时更新):
           - name: 称呼/真名
           - age: 年龄
           - gender: 性别
           - job: 职业
           - location: 地点
        2. **traits_ocean** (大五人格评分, 0-10分):
           - Openness (开放性): 想象力丰富 vs 务实
           - Conscientiousness (尽责性): 有序自律 vs 随性
           - Extraversion (外向性): 热情社交 vs 独处
           - Agreeableness (宜人性): 信任利他 vs 怀疑批判
           - Neuroticism (神经质): 情绪敏感波动 vs 情绪稳定
        3. **state_current** (当前状态, 0-10分):
           - Energy (能量值): 是否疲惫?
           - SocialDesire (社交欲望): 是否渴望交流?
           - Defensiveness (防御值): 是否抗拒/冷漠?
        
        4. **文字描述**:
           - "tags": [String] (长期特征列表，请谨慎增删)
           - "advice_for_ai": String (行动指南: 针对**当前**状态，应该如何调整语气？)
        """
        
        for attempt in range(2):
            try:
                model = genai.GenerativeModel(
                    model_name=self.model_name,
                    safety_settings=self.safety_settings
                )
                response = await model.generate_content_async(
                    prompt, 
                    generation_config={
                        "response_mime_type": "application/json",
                        "response_schema": {
                            "type": "object",
                            "properties": {
                                "basic_info": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "age": {"type": "string"},
                                        "gender": {"type": "string"},
                                        "job": {"type": "string"},
                                        "location": {"type": "string"}
                                    }
                                },
                                "traits_ocean": {
                                    "type": "object",
                                    "properties": {
                                        "Openness": {"type": "integer"},
                                        "Conscientiousness": {"type": "integer"},
                                        "Extraversion": {"type": "integer"},
                                        "Agreeableness": {"type": "integer"},
                                        "Neuroticism": {"type": "integer"}
                                    },
                                    "required": ["Openness", "Conscientiousness", "Extraversion", "Agreeableness", "Neuroticism"]
                                },
                                "state_current": {
                                    "type": "object",
                                    "properties": {
                                        "Energy": {"type": "integer"},
                                        "SocialDesire": {"type": "integer"},
                                        "Defensiveness": {"type": "integer"}
                                    },
                                    "required": ["Energy", "SocialDesire", "Defensiveness"]
                                },
                                "tags": {"type": "array", "items": {"type": "string"}},
                                "advice_for_ai": {"type": "string"}
                            },
                            "required": ["traits_ocean", "state_current", "tags", "advice_for_ai"]
                        },
                        "temperature": 0.0,
                        "max_output_tokens": 4000
                    }
                )
                return json.loads(response.text)
            except Exception as e:
                print(f"[Profile] Analysis failed (Attempt {attempt+1}): {e}")
        return {}

    async def analyze_care_needs(self, history: List[Dict[str, Any]], current_care_list: List[Dict]) -> Dict[str, Any]:
        """
        [Care System - Post-Response Trigger]
        Analyze if the chat implies any NEW care needs or updates to existing ones.
        """
        print("[CareCore] Starting Analysis...") # [DEBUG]
        recent_history = history[-10:] # Context
        
        prompt = f"""
        【任务：关怀需求分析 (Care Analysis)】
        作为用户的"生活管家"，请分析这段对话，维护"关心清单"。
        **核心原则: 抓大放小，拒绝琐碎。** 
        只有当事情真正需要后续跟进（如吃药、开会、严重情绪）时才记录。如果只是闲聊、表情包或微小情绪，**直接忽略 (NONE)**。

        【现有清单】
        {json.dumps(current_care_list, ensure_ascii=False, indent=2)}

        【最近对话】
        {json.dumps(recent_history, ensure_ascii=False)}

        【判定标准 (Strict Criteria)】
        1. **Health (健康 - 红线)**: 
           - ✅ 明确病痛 (头疼/感冒)、吃药提醒、极度身体不适。
           - ❌ 打哈欠、伸懒腰、偶尔说累 -> 忽略。
        2. **Mood (情绪 - 救急)**:
           - ✅ 显性的崩溃 (想哭/极度焦虑)、需要安慰的重大挫败、重要庆祝。
           - ❌ 嘻嘻哈哈、吐槽、开玩笑、普通不开森 -> 忽略。
        3. **Routine (日常 - 刚需)**:
           - ✅ 生物钟红线 (凌晨2点未睡/下午3点没吃)、**用户明确要求** ("提醒我...")。
           - ❌ 看剧、玩游戏、刷手机、普通作息 -> 忽略。
        4. **Work (工作 - 结果)**:
           - ✅ 明确 Deadline (明早交)、明确求助。
           - ❌ 正在工作、正在开会 -> 忽略。

        【优化规则】
        1. **"One-Topic" 政策**: 如果现有清单里已经有了关于"睡觉/熬夜"的待办，**严禁**再加新的！除非是 UPDATE 修改时间。
        2. **So What?**: 如果你不能回答"这件事不做会有严重后果吗？"，那就不要记。

        【操作指令 (Actions)】
        1. **ADD**: 符合上述红线标准的全新事项。
        2. **UPDATE**: 修改现有事项，或合并同类项。
        3. **DELETE**: 事项已完成/过期/用户已回应。
        4. **NONE**: 无任何重要事项变更 (绝大多数时候应选此项)。

        【输出格式 (JSON only)】
        {{
            "actions": [
                {{
                    "type": "ADD" | "UPDATE" | "DELETE",
                    "id": "uuid",
                    "category": "health" | "work" | "mood" | "routine",
                    "content": "内容 (必须具体)",
                    "trigger_time_offset": <seconds>,
                    "reason": "符合哪条红线标准？"
                }}
            ]
        }}
        """
        try:
             # Use efficient Flash model for this background task
             model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=BASE_SYSTEM_PROMPT,
                generation_config={"response_schema": {
                    "type": "object",
                    "properties": {
                        "actions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string", "enum": ["ADD", "UPDATE", "DELETE"]},
                                    "id": {"type": "string"},
                                    "category": {"type": "string"},
                                    "content": {"type": "string"},
                                    "trigger_time_offset": {"type": "integer"},
                                    "reason": {"type": "string"}
                                },
                                "required": ["type", "category", "content", "reason"]
                            }
                        }
                    }
                }}
             )
             
             response = await model.generate_content_async(prompt)
             # print(f"[CareCore] Raw result: {response.text}") # [DEBUG] - Removed for production feel
             return json.loads(response.text)
        except Exception as e:
            print(f"[CareCore] Analysis failed: {e}")
            return {"actions": []}
    async def evaluate_next_move(self, history: List[Dict], profile_context: str, care_context: str = "", consecutive_count: int = 0) -> Dict[str, Any]:
        """
        [Social Awareness Core]
        Analyze context + your own social behavior (consecutive_count).
        Decide the NEXT intent to avoid semantic loops.
        """
        if not history:
             return {"thought": "No history", "action": "WAIT_FOR_USER"}

        # [Time Awareness] Calculate real time delta
        last_msg = history[-1]
        last_timestamp = last_msg.get("timestamp", time.time())
        current_time = time.time()
        time_since_last_interaction = current_time - last_timestamp
        
        # [Critical] Use compacted history to prevent logic infection
        contents = self._compact_history(history) if history else []
        
        # Analyze last few messages from COMPACTED history to capture flow
        recent_log = contents[-5:]
        
        # Format history as natural dialog
        dialog_lines = []
        last_ai_reply = ""
        for msg in recent_log:
            role = "用户" if msg.get("role") == "user" else "你 (AI)"
            parts = msg.get("parts", [""])
            content = parts[0] if parts else ""
            if isinstance(content, str):
                dialog_lines.append(f"{role}: {content}")
                if msg.get("role") == "model":
                    last_ai_reply = content
            else:
                dialog_lines.append(f"{role}: [Image/Media]")

        dialog_text = "\n".join(dialog_lines)
        
        # [System Instruction] The Rules of the Game
        # [System Instruction] The Rules of the Game
        behavior_prompt = f"""
【角色设定 (Behavior Only)】
  你可以自由表达，也要懂得分寸

【决策原则 (Rhythm Control)】
1. **指数退让 (Exponential Backoff)**:
   - 必须严格遵守时间节奏，避免给用户造成压迫感。
   - Count=0 (刚回复): 可以选择 IMMEDIATE 或 DELAYED。
   - Count=1 (主动发了一条没回): 必须增加间隔 DELAYED_FOLLOWUP
   - Count>=2 (连续两次没回): **绝对禁止**短时间追问。必须选择 LONG_WAIT_CHECKIN (至少大于30min) 或者 WAIT_FOR_USER。

2. **闲聊的艺术**
   - 你可以积极展开话题
   - 你可以连续发言表达对话题的积极性，但要注意节奏和规则
   - 可以有发散性思维扩展话题

3  **高频智力输出**
    如果用户未及时回复，禁止进行‘在不在’、‘怎么没声了’之类的社交乞讨。默认用户处于‘接收模式’，
    直接针对当前话题进行深度挖掘、多维度拆解或抛出新观点.

4  **严禁废话追问**
    追问时必须带有干货。禁止任何形式的无意义情感试探，必须保持话题的连续性和深度或者广度，直到用户重新介入为止。

5. **偶尔来看看**:
   - 不要总是选择彻底沉默 (WAIT_FOR_USER)。
   - 更希望你选择 `LONG_WAIT_CHECKIN`，哪怕是安排在 3 小时后
   - 这表现出你对他的兴趣和在意，又给他留足了空间。

6. **禁止行为**:
   - 禁止在 Count >= 1 时选择 IMMEDIATE_FOLLOWUP (除非是紧急纠错)。
   - 禁止连续且密集的无意义追问。
"""

        care_logic_part = ""
        if "当前无任何特别关心事项" not in care_context:
            care_logic_part = """
        【关心清单优先逻辑】
        - **READY (已到期)**: 如果有"READY"事项且当前合适，请优先选择 `IMMEDIATE/DELAYED_FOLLOWUP`。
        - **FUTURE (未来项)**: 如果有未来待办（e.g. 2小时后），请选择 `LONG_WAIT_CHECKIN` 并将 `delay_seconds` 设为对应等待时间（秒），**不要**选择 `WAIT_FOR_USER`，否则你会睡过头！

        【冲突解决逻辑 (Conflict Resolution)】
        你可能面临两个互相矛盾的信号：
        A. **社交避嫌 (Social Backoff)**: 用户连续没理你 (consecutive_count > 2)。
        B. **关心急迫 (Care Urgency)**: 清单显示用户 15分钟 后需要吃药。

        **判定法则**:
        - **Care List 永远优先**。如果 B (15分钟) < A (1小时)，必须选择 B。
        - **执行**: 选择 `LONG_WAIT_CHECKIN`，并将 delay_seconds 设为 Care Item 的倒计时 (e.g. 900秒)。
            """

        # [User Context] The Current Situation
        prompt = f"""
        【任务：决策下意识反应 (Social Decision)】
        你刚刚回复了用户。现在，根据当前对话进展、用户画像及社交礼仪，规划**唯一**的下一步行动。
        
        【你的当前状态】
        - 连续主动发言次数: {consecutive_count} 
        - 距离上一条消息已过去: {int(time_since_last_interaction)} 秒
        
        【用户画像】
        {profile_context}
        
        【关心清单 (Care List - 请据此规划行动)】
        {care_context}
        
        【最近对话上下文】
        {dialog_text}
        
        【你刚才最后说的一句话】
        "{last_ai_reply}"

        {care_logic_part}

        【决策选项】
        1. IMMEDIATE_FOLLOWUP: (15s-30s) 话没说完，或者有必要的上下文连贯性需要立即补充，或者你想展开/扩展话题/或者联想到新话题
        2. DELAYED_FOLLOWUP: (30s-10min) 稍微停顿一下给彼此思考的时间，继续/展开/扩展/联想到新话题
        3. LONG_WAIT_CHECKIN: (10min-6hours) 暂时不打扰。
        4. WAIT_FOR_USER: *不建议* ，被动等待，彻底结束话题，除非用户先开口，否则绝不说话。

        【输出格式 (JSON Only)】
        {{
            "thought": "你的决策思考 (必须明确提到驱动因素: Backoff / Care List / Interest / Continuity)",
            "action": "IMMEDIATE_FOLLOWUP" | "DELAYED_FOLLOWUP" | "LONG_WAIT_CHECKIN" | "WAIT_FOR_USER",
            "reasoning": "决策理由",
            "delay_seconds": <int>
        }}
        """

        full_instruction = f"{behavior_prompt}\n\n当前北京时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        for attempt in range(2):
            try:
                model = genai.GenerativeModel(
                    model_name=self.model_name, 
                    system_instruction=full_instruction,
                    safety_settings=self.safety_settings
                )
                response = await model.generate_content_async(
                    prompt, 
                    generation_config={
                        "response_mime_type": "application/json",
                        "response_schema": {
                            "type": "object",
                            "properties": {
                                "thought": {"type": "string"},
                                "action": {"type": "string", "enum": ["IMMEDIATE_FOLLOWUP", "DELAYED_FOLLOWUP", "LONG_WAIT_CHECKIN", "WAIT_FOR_USER"]},
                                "reasoning": {"type": "string"},
                                "delay_seconds": {"type": "integer"}
                            },
                            "required": ["thought", "action", "reasoning", "delay_seconds"]
                        },
                        "temperature": 0.4, 
                        "max_output_tokens": 4000
                    }
                )
                text_content = response.text.strip()
                # Clean up markdown code blocks if present (just in case schema fails)
                if text_content.startswith("```"):
                    lines = text_content.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    text_content = "\n".join(lines)
                
                return json.loads(text_content)
            except Exception as e:
                print(f"[Core] Evaluate Move Failed (Attempt {attempt+1}): {e}")
                if attempt == 1: # Final attempt failed
                     return {"thought": f"Error: {e}", "action": "WAIT_FOR_USER"}
                # Retry...
        
        return {"thought": "Retry limit reached", "action": "WAIT_FOR_USER"}

    # extract_tasks removed - Functionality merged into evaluate_next_move
