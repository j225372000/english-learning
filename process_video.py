import os
import re
import urllib.request
import json
import feedparser
from google import genai

# 使用回你一開始完全正確的 RSS 網址與頻道 ID
RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id=UC01bAQVpenvfA2QqzSRtL_g"

def get_latest_youtube_video(rss_url):
    try:
        req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            feed = feedparser.parse(response.read())
        if not feed.entries:
            return None, None
        latest_entry = feed.entries[0]
        title = latest_entry.title
        video_id = latest_entry.yt_videoid if hasattr(latest_entry, 'yt_videoid') else latest_entry.link.split("v=")[1]
        return video_id, title
    except Exception as e:
        print(f"❌ 抓取 RSS 發生異常: {str(e)}")
        return None, None

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
    print("🚀 開始自動偵測最新影片...")
    video_id, video_title = get_latest_youtube_video(RSS_URL)
    if not video_id:
        print("❌ 無法獲取影片資料。")
        return
        
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"🎯 成功獲取影片：【{video_title}】")
    
    try:
        # 徹底移除 youtube-transcript-api 阻礙！
        # 直接把 YouTube 網址給 Gemini，讓 Gemini 去理解內容並生成繁體中文筆記
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

        影片連結：
        {video_url}
        """
        
        print("🤖 正在呼叫 Gemini AI 生成筆記（此步驟免逐字稿，會花費 15-30 秒）...")
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        ai_result = response.text
        
        # 讀取 Notion 憑證並上傳
        notion_token = os.environ.get("NOTION_TOKEN")
        notion_db_id = os.environ.get("NOTION_DATABASE_ID")
        
        if notion_token and notion_db_id:
            upload_to_notion(notion_token, notion_db_id, video_title, video_url, ai_result)
        else:
            print("⚠️ 警告: 缺少 Notion 設定，僅於本地生成備份檔案。")
            
        with open(f"🚨每日更新_{video_id}.md", "w", encoding="utf-8") as f:
            f.write(ai_result)
            
    except Exception as e:
        print(f"❌ 執行失敗: {str(e)}")

if __name__ == "__main__":
    main()
