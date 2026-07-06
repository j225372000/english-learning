import urllib.request
import json
import os

def fetch(input_data):
    """
    YouTube 輸入技能積木：將 ID 轉為影片標題與描述
    """
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={input_data}&key={api_key}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
        if not data.get("items"):
            return "未知影片", "無描述"
        snippet = data["items"][0]["snippet"]
        return snippet["title"], snippet["description"]
    except Exception as e:
        print(f"❌ YouTube Skill 異常: {str(e)}")
        return "抓取失敗", str(e)
