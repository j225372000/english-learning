import os
from datetime import datetime

def execute(ai_result, video_id, prompt_type):
    """
    Markdown 輸出技能積木
    """
    try:
        current_date = datetime.now().strftime("%Y%m%d")
        filename = f"🚨{prompt_type.upper()}_{current_date}_{video_id}.md"
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(ai_result)
        print(f"✨ 【技能成功】萬用筆記已完美寫入檔案：{filename}")
        return True
    except Exception as e:
        print(f"❌ Markdown 輸出技能失敗: {str(e)}")
        return False
