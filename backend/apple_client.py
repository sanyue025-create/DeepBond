import subprocess
import time

def send_to_reminders(title: str, body: str = "来自 AI 的关心"):
    """
    通过 AppleScript 将消息发送到 macOS/iOS '提醒事项'。
    这会触发 iCloud 同步，导致 iPhone/Watch 震动。
    """
    # AppleScript: 创建一个立即到期的提醒，以触发通知
    script = f'''
    tell application "Reminders"
        make new reminder with properties {{name:"{title}", body:"{body}", remind me date:(current date)}}
    end tell
    '''
    
    try:
        # 运行 osascript
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[Apple] Notification sent: {title}")
            return True
        else:
            print(f"[Apple] Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"[Apple] Exception: {e}")
        return False

if __name__ == "__main__":
    # Test
    send_to_reminders("AI 连接测试", "如果您收到这条，说明手机推送已打通！")
