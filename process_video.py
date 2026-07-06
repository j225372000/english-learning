import os
import re
from google import genai

# =================【直接在這裡填入你今天想看的 11 碼影片 ID】=================
# 請確認這是一串 11 碼的英數字組合（例如：dQw4w9WgXcQ 這種格式）
VIDEO_ID = "-VFQHTRVBws" 
# =========================================================================

def main():
    print(f"🚀 啟動 Gemini 原生多模態模式，直接分析影片 ID: {VIDEO_ID}")
    video_url = f"https://www.youtube.com/watch?v={VIDEO_ID}"
    
    try:
        # 初始化 Gemini 用戶端
        api_key = os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        
        # 這裡不帶任何第三方字幕，直接把 YouTube 連結丟給 Gemini 2.5 讓它直接看影片！
        prompt = f"""
        請針對以下提供的 YouTube 影片內容進行深度分析，並「完全使用繁體中文（台灣）」輸出格式化結構漂亮的學習筆記。
        請包含以下四大區塊：
        ## 📝 1. 影片核心摘要 (Video Summary)
        - 請用 200-300 字精煉概述影片的核心主題。
        ## 💡 2. 10 個核心重點單字 (Key Vocabulary)
        - **單字 (詞性)** / 中文解釋 / 影片情境或實用例句。
        ## 🎯 3. 5 個實用片語與慣用語 (Phrases & Idioms)
        - **片語/短語** / 中文解釋 / 實用生活例句。
        ## 🧠 4. 關鍵思維或金句延伸 (Key Takeaway)
        - 點出影片最啟發人心的 1-2 句話。

        影片網址：{video_url}
        """
        
        print("🤖 正在呼叫 Gemini AI 直接分析影片（此步驟會由 AI 直接觀看影片，請稍候 15-30 秒）...")
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        ai_result = response.text
        
        # 輸出成 Markdown 檔案
        filename = f"🚨每日更新_{VIDEO_ID}.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(ai_result)
        print(f"✨ 【成功】正確的財經筆記已成功寫入檔案：{filename}")
            
    except Exception as e:
        print(f"❌ 執行失敗: {str(e)}")

if __name__ == "__main__":
    main()
