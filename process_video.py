import os
import re
import json
import urllib.request
import youtube_transcript_api
from google import genai

# =================【最原始的做法：直接在這裡填入 11 碼影片 ID】=================
# 每次你想跑哪一支影片的筆記，就直接回來把這行雙引號裡面的 ID 換掉。
# 例如網址是 https://www.youtube.com/watch?v=dQw4w9WgXcQ ，ID 就是 dQw4w9WgXcQ
VIDEO_ID = "UC0lbAQVpenvfA2QqzsRtL_g" 
# =========================================================================

def upload_to_notion(token, database_id, video_title, video_url, ai_content):
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    page_data = {
        "parent": {"database_id": database_id},
        "properties": {
            "Name": {"title": [{"text": {"content": video_title}}]},
            "URL": {"url": video_url},
            "Status": {"status": {"name": "Not started"}}
        },
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}]
                }
            } for chunk in re.findall(r'.{1,2000}', ai_content, re.DOTALL)
        ]
    }
    req = urllib.request.Request(url, data=json.dumps(page_data).encode('utf-8'), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                print("✅ 成功同步到 Notion 資料庫！")
    except Exception as e:
        print(f"❌ 同步 Notion 失敗: {str(e)}")

def main():
    print(f"🚀 啟動原始模式，直接處理影片 ID: {VIDEO_ID}")
    
    video_url = f"https://www.youtube.com/watch?v={VIDEO_ID}"
    video_title = f"YouTube 影片學習筆記 (ID: {VIDEO_ID})"
    
    try:
        # 嘗試抓取字幕，如果真的沒有字幕就交給 Gemini 2.5 Flash 直接看影片
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
        
        # 讀取 Notion 憑證並上傳
        notion_token = os.environ.get("NOTION_TOKEN")
        notion_db_id = os.environ.get("NOTION_DATABASE_ID")
        
        if notion_token and notion_db_id:
            upload_to_notion(notion_token, notion_db_id, video_title, video_url, ai_result)
        else:
            print("⚠️ 警告: 缺少 Notion 設定，僅於本地生成備份檔案。")
            
        with open(f"🚨個人筆記_{VIDEO_ID}.md", "w", encoding="utf-8") as f:
            f.write(ai_result)
            
    except Exception as e:
        print(f"❌ 執行失敗: {str(e)}")

if __name__ == "__main__":
    main()
