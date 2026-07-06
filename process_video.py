import os
import re
import urllib.request
import json
import youtube_transcript_api
from google import genai

# 正確鎖定「早晨財經速解讀」的官方 RSS 網址
RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id=UC01bAQVpenvfA2QqzSRtL_g"

def get_latest_video_id(rss_url):
    """
    透過標準官方 RSS 網址抓取最新影片 ID，並加入防禦性 Headers 徹底破解 403 阻擋
    """
    try:
        # 建立請求，並加入完整的瀏覽器模擬標頭，讓 YouTube 伺服器放行
        req = urllib.request.Request(
            rss_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7'
            }
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            xml_content = response.read().decode('utf-8')
            
        # 從 XML 內容中精確提取最新影片的 yt:videoId 標籤
        video_ids = re.findall(r'<yt:videoId>([^<]+)</yt:videoId>', xml_content)
        if video_ids:
            return video_ids[0]
            
        # 備用方案：如果標籤格式有變，嘗試從連結中抓取
        video_urls = re.findall(r'<link rel="alternate" href="https://www.youtube.com/watch\?v=([^"]+)"/>', xml_content)
        if video_urls:
            return video_urls[0]
            
        print("❌ 無法從 RSS 內容中解析出任何影片 ID")
        return None
    except Exception as e:
        print(f"❌ 抓取 RSS 過程發生異常: {str(e)}")
        return None

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
    print("🚀 開始偵測 YouTube 頻道的最新影片...")
    video_id = get_latest_video_id(RSS_URL)
    if not video_id:
        print("❌ 無法獲取影片 ID，程式終止。")
        return
        
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    video_title = f"早晨財經速解讀最新影片 (ID: {video_id})"
    print(f"🎯 成功獲取 YouTube 影片 ID: {video_id}")
    
    try:
        # 抓取字幕
        try:
            transcript_list = youtube_transcript_api.get_transcript(video_id, languages=['en', 'zh-TW', 'zh-CN'])
        except Exception:
            transcript_list = youtube_transcript_api.get_transcript(video_id)
            
        transcript_text = " ".join([t['text'] for t in transcript_list])
        print("📝 成功取得影片逐字稿！")
        
        # 呼叫 Gemini AI
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
            
        with open(f"🚨每日更新_{video_id}.md", "w", encoding="utf-8") as f:
            f.write(ai_result)
            
    except Exception as e:
        print(f"❌ 執行失敗: {str(e)}")

if __name__ == "__main__":
    main()
