import os
import re
import urllib.request
import json
from google import genai

# =================【最原始的做法：直接在這裡填入 11 碼影片 ID】=================
VIDEO_ID = "-uh6wdAmgHk" 
# =========================================================================

def get_video_data_via_official_api(video_id, api_key):
    """
    【官方檢查機制】
    拿著 Google 官方通行證去要資料，百分之百粉碎 YouTube 的登入牆阻擋，
    直接抓出正確的影片標題、說明欄（Description），作為給 Gemini 的最高品質分析素材！
    """
    url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={api_key}"
    print(f"🔍 [檢查機制] 正在使用官方 API 驗證影片 ID: {video_id}")
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        if not data.get("items"):
            print("❌ [檢查回報] 失敗：YouTube 官方 API 回報找不到此影片 ID，請檢查是否填錯。")
            return None, None
            
        snippet = data["items"][0]["snippet"]
        title = snippet["title"]
        description = snippet["description"]
        
        print(f"🎯 [檢查回報] 官方驗證成功！")
        print(f"   👉 影片標題: 【{title}】")
        return title, description

    except Exception as e:
        print(f"❌ [檢查回報] 失敗：呼叫 YouTube API 發生異常: {str(e)}")
        return None, None

def main():
    print(f"🚀 啟動官方 API 防錯模式，處理影片 ID: {VIDEO_ID}")
    
    if len(VIDEO_ID) != 11:
        print(f"❌ [嚴重錯誤] ID 長度不對！必須剛好是 11 碼。")
        return

    # 讀取 GitHub Secrets 裡的官方金鑰
    yt_api_key = os.environ.get("YOUTUBE_API_KEY")
    if not yt_api_key:
        print("❌ [安全終止] 找不到 YOUTUBE_API_KEY，請先去 GitHub Secrets 設定它。")
        return

    # 執行官方第一道檢查
    video_title, video_description = get_video_data_via_official_api(VIDEO_ID, yt_api_key)
    
    if not video_title:
        print("🛑 [安全終止] 由於無法取得正確的影片素材，程式已自動安全終止。")
        return

    try:
        # 初始化 Gemini 用戶端
        api_key = os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        
        # 將官方拿到的「正確標題」與「正確說明欄（內含主講人的財經大綱重點）」完整餵給 Gemini
        prompt = f"""
        請針對以下提供的 YouTube 官方影片數據進行深度分析，請確保提取的內容「完全符合」該影片標題：{video_title}。
        請「完全使用繁體中文（台灣）」輸出格式化結構漂亮的學習筆記。
        
        請包含以下四大區塊：
        ## 📝 1. 影片核心摘要 (Video Summary)
        - 請用 200-300 字精煉概述影片的核心主題（例如當天財經大事件）。
        ## 💡 2. 10 個核心重點單字 (Key Vocabulary)
        - **單字 (詞性)** / 中文解釋 / 影片情境或實用例句。
        ## 🎯 3. 5 個實用片語與慣用語 (Phrases & Idioms)
        - **片語/短語** / 中文解釋 / 實用生活例句。
        ## 🧠 4. 關鍵思維或金句延伸 (Key Takeaway)
        - 點出影片最啟發人心的 1-2 句話。

        影片網址：https://www.youtube.com/watch?v={VIDEO_ID}
        影片官方標題：{video_title}
        影片官方說明與大綱：
        {video_description}
        """
        
        print("🤖 [AI 階段] 素材完全正確！正在呼交 Gemini AI 生成精準筆記...")
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        ai_result = response.text
        
        # 輸出成 Markdown 檔案
        filename = f"🚨每日更新_{VIDEO_ID}.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(ai_result)
        print(f"✨ 【100% 成功】正確的財經筆記已成功寫入檔案：{filename}")
            
    except Exception as e:
        print(f"❌ [系統異常] 執行失敗: {str(e)}")

if __name__ == "__main__":
    main()
