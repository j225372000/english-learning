import os
import re
import urllib.request
import youtube_transcript_api
from google import genai

# =================【直接在這裡填入 11 碼影片 ID】=================
# 每次你想跑哪一支影片的筆記，就直接回來把這行雙引號裡面的 ID 換掉。
VIDEO_ID = "-VFQHTRVBws" 
# =========================================================================

def main():
    print(f"🚀 啟動純檔案模式，直接處理影片 ID: {VIDEO_ID}")
    video_url = f"https://www.youtube.com/watch?v={VIDEO_ID}"
    
    try:
        # 嘗試抓取字幕
        try:
            transcript_list = youtube_transcript_api.get_transcript(VIDEO_ID, languages=['en', 'zh-TW', 'zh-CN'])
        except Exception:
            try:
                transcript_list = youtube_transcript_api.get_transcript(VIDEO_ID)
            except Exception:
                transcript_list = []
                
        if transcript_list:
            transcript_text = " ".join([t['text'] for t in transcript_list])
            print("📝 成功取得影片逐字稿！")
        else:
            transcript_text = "此影片無提供直接字幕檔，請直接分析影片內容。"
            print("⚠️ 影片無提供直接字幕檔，將交由 Gemini 2.5 進行多模態分析。")
        
        # 呼叫 Gemini AI
        api_key = os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        
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

        影片連結：{video_url}
        逐字稿內容（若有）：{transcript_text}
        """
        
        print("🤖 正在呼叫 Gemini AI 生成筆記...")
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        ai_result = response.text
        
        # 輸出成 Markdown 檔案
        filename = f"🚨每日更新_{VIDEO_ID}.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(ai_result)
        print(f"✨ 【成功】筆記已成功寫入檔案：{filename}")
            
    except Exception as e:
        print(f"❌ 執行失敗: {str(e)}")

if __name__ == "__main__":
    main()
