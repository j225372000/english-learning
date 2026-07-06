import os
import re
import feedparser
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai

# =================【填入你想監控的 YouTube 頻道 ID】=================
# 例如：打開頻道主頁，網址背後的 UCxxxxxx 字串
CHANNEL_ID = "UC0lbAQVpenvfA2QqzsRtL_g" 
# =========================================================================

def get_latest_youtube_video(channel_id):
    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    feed = feedparser.parse(rss_url)
    if not feed.entries:
        print("無法取得頻道資料，請檢查 CHANNEL_ID 是否正確。")
        return None, None
    latest_entry = feed.entries[0]
    title = latest_entry.title
    link = latest_entry.link
    video_id = latest_entry.yt_videoid if hasattr(latest_entry, 'yt_videoid') else link.split("v=")[1]
    return video_id, title

def upload_to_notion(token, database_id, video_title, video_url, ai_content):
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
    response = requests.post("https://api.notion.com/v1/pages", headers=headers, json=page_data)
    if response.status_code == 200:
        print("✅ 成功同步到 Notion 資料庫！")
    else:
        print(f"❌ 同步 Notion 失敗，錯誤碼: {response.status_code}, 回應: {response.text}")

def main():
    print(f"開始檢查頻道 {CHANNEL_ID} 的最新影片...")
    video_id, video_title = get_latest_youtube_video(CHANNEL_ID)
    if not video_id:
        return
        
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"偵測到最新影片：【{video_title}】")
    
    try:
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'zh-TW', 'zh-CN'])
        except Exception:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = " ".join([t['text'] for t in transcript_list])
        
        api_key = os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
        請針對以下提供的 YouTube 影片逐字稿進行深度分析，並「完全使用繁體中文（台灣）」輸出格式化結構漂亮的學習筆記。
        請包含以下四大區塊：
        ## 📝 1. 影片核心摘要 (Video Summary)
        - 請用 200-300 字精煉概述影片的核心主題。
        ## 💡 2. 10 個核心重點單字 (Key Vocabulary)
        - **單字 (詞性)** / 中文解釋 / 影片情境或實用例句。
        ## 🎯 3. 5 個實用片語與慣用語 (Phrases & Idioms)
        - **片語/短語** / 中文解釋 / 實用生活例句。
        ## 🧠 4. 關鍵思維或金句延伸 (Key Takeaway)
        - 點出影片最啟發人心的 1-2 句話。

        ---
        逐字稿內容：
        {transcript_text}
        """
        
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        ai_result = response.text
        
        notion_token = os.environ.get("NOTION_TOKEN")
        notion_db_id = os.environ.get("NOTION_DATABASE_ID")
        
        if notion_token and notion_db_id:
            upload_to_notion(notion_token, notion_db_id, video_title, video_url, ai_result)
        else:
            print("警告: 缺少 Notion 設定。")
            
        with open(f"🚨每日更新_{video_id}.md", "w", encoding="utf-8") as f:
            f.write(ai_result)
            
    except Exception as e:
        print(f"執行失敗: {str(e)}")

if __name__ == "__main__":
    main()
