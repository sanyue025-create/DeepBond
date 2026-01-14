import json
import os
import time
from typing import Dict, List, Any

class ProfileManager:
    def __init__(self, profile_path: str = "./data/user_profile.json"):
        self.profile_path = profile_path
        self._ensure_data_dir()
        self.profile = self._load_profile()

    def _ensure_data_dir(self):
        os.makedirs(os.path.dirname(self.profile_path), exist_ok=True)

    def _load_profile(self) -> Dict[str, Any]:
        if os.path.exists(self.profile_path):
            try:
                with open(self.profile_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Profile] Load failed: {e}")
        return {
            "tags": [],
            "traits_ocean": {},
            "state_current": {},
            "advice_for_ai": "正常交流",
            "last_updated": 0
        }

    def save_profile(self, profile_data: Dict[str, Any]):
        """
        更新并保存画像。
        【科学更新】采用指数平滑策略 (Exponential Smoothing) 更新数值特质。
        NewScore = (OldScore * 0.8) + (ObservedScore * 0.2)
        """
        if not profile_data:
            return

        # 更新时间
        profile_data["last_updated"] = time.time()
        
        # 1. 提取并平滑数值特质
        alpha = 0.6 # 稳定性系数 (0.6 = 均衡, 允许更快迭代)
        
        # 辅助函数：平滑字典
        def smooth_dict(old_dict, new_dict):
            if not old_dict: return new_dict # 初始化
            merged = {}
            for k, v_new in new_dict.items():
                v_old = old_dict.get(k)
                if v_old is not None:
                    # 保留一位小数
                    merged[k] = round((v_old * alpha) + (v_new * (1 - alpha)), 1)
                else:
                    merged[k] = v_new
            return merged

        # 处理 OCEAN
        new_ocean = profile_data.get("traits_ocean")
        if new_ocean:
            old_ocean = self.profile.get("traits_ocean", {})
            profile_data["traits_ocean"] = smooth_dict(old_ocean, new_ocean)

        # 处理 State (状态可以波动大一点，alpha 调低?)
        # 暂时保持一致，或者让状态更敏感 (alpha=0.5)
        new_state = profile_data.get("state_current")
        if new_state:
            old_state = self.profile.get("state_current", {})
            # State alpha = 0.4 (对当前状态更敏感)
            state_alpha = 0.4
            def smooth_state(old_d, new_d):
                if not old_d: return new_d
                m = {}
                for k, vn in new_d.items():
                    vo = old_d.get(k)
                    if vo is not None:
                        m[k] = round((vo * state_alpha) + (vn * (1 - state_alpha)), 1)
                    else:
                        m[k] = vn
                return m
            profile_data["state_current"] = smooth_state(old_state, new_state)
        
        # 3. 覆盖文本字段
        self.profile.update(profile_data)
        
        try:
            with open(self.profile_path, "w", encoding="utf-8") as f:
                json.dump(self.profile, f, ensure_ascii=False, indent=2)
            print(f"[Profile] Updated Ocean: {self.profile.get('traits_ocean')}")
        except Exception as e:
            print(f"[Profile] Save failed: {e}")

    def get_profile_context(self) -> str:
        """
        生成用于注入 Prompt 的上下文描述。
        """
        if not self.profile:
            return ""
            
        traits = self.profile.get('traits_ocean', {})
        state = self.profile.get('state_current', {})

        # Format Ocean string
        ocean_str = ", ".join([f"{k}:{v}" for k,v in traits.items()]) if traits else "分析中..."
        state_str = ", ".join([f"{k}:{v}" for k,v in state.items()]) if state else "分析中..."

        return f"""
        【用户画像 (User Profile) - 科学侧写】
        1. **核心人格 (OCEAN)**: {ocean_str}
        2. **当前状态 (State)**: {state_str}
        3. **关键词**: {', '.join(self.profile.get('tags', []))}
        4. **建议**: {self.profile.get('advice_for_ai')}
        """
