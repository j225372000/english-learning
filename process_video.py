import os
import urllib.request
import json
from datetime import datetime
from google import genai

def get_video_data_via_official_api(video_id, api_key):
    url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={api_key}"
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

    # 請求 YouTube 官方數據取得標題
    video_title, video_description = get_video_data_via_official_api(video_id, yt_api_key)
    if not video_title:
        print("🛑 無法取得正確的影片素材，程式終止。")
        return

    print(f"🎯 成功載入影片標題: 【{video_title}】")
    
    try:
        # 呼叫 Gemini
        client = genai.Client(api_key=api_key)
        
        # 🌟【終極時空防禦修正】：強制提醒 AI 當前時間，並給予影片直連網址，要求它直接分析音訊/影片內容
        time_context = f"【極重要時空背景】：當前時間是 2026 年 7 月。這場影片標題為 {video_title} 的記者會已經完全召開並結束。這不是未來的事件！請直接根據以下提供的 YouTube 影片網址，利用你的多模態能力直接分析影片與音訊內容，提取真實發生的鮑爾原話，絕對不要編造或拒絕回答。"
        
        final_prompt = f"""
        {time_context}
        
        {selected_prompt}
        
        --- 
        【待分析的影片真實數據】
        影片網址：https://www.youtube.com/watch?v={video_id}
        影片官方標題：{video_title}
        影片官方說明欄內容（僅供參考）：
        {video_description}
        """
        
        print(f"🤖 正在呼叫 Gemini AI 並下達時空防禦指令，直接進行多模態音訊/影片分析...")
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
