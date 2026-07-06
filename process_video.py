import os
import urllib.request
import urllib.error
import json
from datetime import datetime
from google import genai

def get_video_data_via_official_api(video_id, api_key):
    clean_id = video_id.strip().replace('\r', '').replace('\n', '')
    clean_key = api_key.strip().replace('\r', '').replace('\n', '') if api_key else ""
    
    # 🎯【核心修正】：補上正確的 /youtube/v3/ 路由路徑
    url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={clean_id}&key={clean_key}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
        if not data.get("items"):
            return None, None
        snippet = data["items"][0]["snippet"]
        return snippet["title"], snippet["description"]
    except Exception as e:
        print(f"❌ 呼叫 YouTube API 發生異常: {str(e)}")
        return None, None

def main():
    video_id = os.environ.get("VIDEO_ID", "").strip()
    prompt_type = os.environ.get("VIDEO_TYPE", "general").strip().lower()
    yt_api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not video_id:
        print("❌ 錯誤：未提供 VIDEO_ID！")
        return

    print(f"🚀 啟動萬用外部配置模式 | 影片 ID: {video_id} | 指定範本: {prompt_type}")

    # 讀取外部 Prompt 檔案
    prompt_file_path = f"prompts/{prompt_type}.txt"
    if os.path.exists(prompt_file_path):
        with open(prompt_file_path, "r", encoding="utf-8") as f:
            selected_prompt = f.read()
        print(f"📂 成功套用專屬 Prompt 範本: {prompt_file_path}")
    else:
        print(f"⚠️ 提示：找不到專屬範本 '{prompt_file_path}'，自動切換至 general.txt")
        with open("prompts/general.txt", "r", encoding="utf-8") as f:
            selected_prompt = f.read()

    if not yt_api_key or not api_key:
        print("❌ 缺少必要的環境變數 (YOUTUBE_API_KEY 或 GEMINI_API_KEY)")
        return

    # 請求 YouTube 官方數據
    video_title, video_description = get_video_data_via_official_api(video_id, yt_api_key)
    if not video_title:
        print("🛑 無法取得正確的影片素材，程式終止。")
        return

    print(f"🎯 成功載入影片: 【{video_title}】")
    
    try:
        # 呼叫 Gemini 生成內容
        client = genai.Client(api_key=api_key)
        final_prompt = f"{selected_prompt}\n\n--- \n影片網址：https://www.youtube.com/watch?v={video_id}\n影片官方標題：{video_title}\n影片官方說明欄內容：\n{video_description}"
        
        print(f"🤖 正在呼叫 Gemini AI 進行多模態邏輯提煉...")
        response = client.models.generate_content(model='gemini-2.5-flash', contents=final_prompt)
        
        current_date = datetime.now().strftime("%Y%m%d")
        filename = f"🚨{prompt_type.upper()}_{current_date}_{video_id}.md"
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(response.text)
        print(f"✨ 【100% 成功】萬用筆記已完美寫入檔案：{filename}")
            
    except Exception as e:
        print(f"❌ 執行失敗: {str(e)}")

if __name__ == "__main__":
    main()
