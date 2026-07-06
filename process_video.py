import os
import urllib.request
import json
from datetime import datetime
from google import genai

def get_video_data_via_official_api(video_id, api_key):
    url = f"https://www.googleapis.com/v3/videos?part=snippet&id={video_id}&key={api_key}"
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
    # 📥 讀取 GitHub 動態輸入
    video_id = os.environ.get("VIDEO_ID", "").strip()
    prompt_type = os.environ.get("VIDEO_TYPE", "general").strip().lower()
    
    if not video_id:
        print("❌ 錯誤：未提供 VIDEO_ID！")
        return

    print(f"🚀 啟動萬用外部配置模式 | 影片 ID: {video_id} | 指定範本: {prompt_type}")

    # 📖 萬用核心：自動偵測並读取 prompts/ 下的 txt 檔案
    prompt_file_path = f"prompts/{prompt_type}.txt"
    if os.path.exists(prompt_file_path):
        with open(prompt_file_path, "r", encoding="utf-8") as f:
            selected_prompt = f.read()
        print(f"📂 成功套用專屬 Prompt 範本: {prompt_file_path}")
    else:
        # 🛡️ 安全保底機制：若找不到對應文字檔，自動調用最全面的 general 範本
        print(f"⚠️ 提示：找不到專屬範本 '{prompt_file_path}'")
        general_path = "prompts/general.txt"
        if os.path.exists(general_path):
            with open(general_path, "r", encoding="utf-8") as f:
                selected_prompt = f.read()
            print("🛡️ 已自動切換至 [通用綜合 (general)] 範本進行分析。")
        else:
            # 終極極端保底：防範 prompts 資料夾全空的狀況
            selected_prompt = "請針對以下影片內容進行結構化摘要，並提取關鍵知識點。"
            print("⚠️ 警告：連通用範本都不存在，啟動系統預設提示詞。")

    yt_api_key = os.environ.get("YOUTUBE_API_KEY")
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not yt_api_key or not api_key:
        print("❌ 缺少必要的環境變數 (YOUTUBE_API_KEY 或 GEMINI_API_KEY)")
        return

    # 1. 抓取影片官方資料
    video_title, video_description = get_video_data_via_official_api(video_id, yt_api_key)
    if not video_title:
        print("🛑 無法取得正確的影片素材，程式終止。")
        return

    print(f"🎯 成功載入影片: 【{video_title}】")
    
    try:
        # 2. 呼叫 Gemini
        client = genai.Client(api_key=api_key)
        final_prompt = f"""
        {selected_prompt}
        
        ---
        【待分析的影片真實數據】
        影片網址：https://www.youtube.com/watch?v={video_id}
        影片官方標題：{video_title}
        影片官方說明欄內容：
        {video_description}
        """
        
        print(f"🤖 正在呼叫 Gemini AI (gemini-2.5-flash) 進行多模態邏輯提煉...")
        response = client.models.generate_content(model='gemini-2.5-flash', contents=final_prompt)
        ai_result = response.text
        
        # 3. 檔名動態結合日期與分類，實現極致包容性歸檔
        current_date = datetime.now().strftime("%Y%m%d")
        filename = f"🚨{prompt_type.upper()}_{current_date}_{video_id}.md"
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(ai_result)
        print(f"✨ 【100% 成功】萬用筆記已完美寫入檔案：{filename}")
            
    except Exception as e:
        print(f"❌ 執行失敗: {str(e)}")

if __name__ == "__main__":
    main()
