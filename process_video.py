import os
import re
import urllib.request
from google import genai

# =================【最原始的做法：直接在這裡填入 11 碼影片 ID】=================
# 每次你想跑哪一支影片的筆記，就直接回來把這行雙引號裡面的 ID 換掉。
# 請確保一定是 11 碼（例如：dQw4w9WgXcQ），不能是 24 碼的 UC... 頻道 ID
VIDEO_ID = "-uh6wdAmgHk" 
# =========================================================================

def verify_and_get_youtube_html(video_id):
    """
    【第一道檢查機制】
    在呼叫 AI 之前，先模擬瀏覽器親自去檢查這支 YouTube 影片是否能被正常存取，
    並從網頁原始碼中抽取出關鍵的標題與防錯特徵，確保不是抓到 403 阻擋頁面。
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"🔍 [檢查機制] 正在檢測 YouTube 影片網址: {url}")
    
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7'
            }
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode('utf-8')
        
        # 檢查網頁內容是否被 YouTube 阻擋或要求登入驗證
        if "LOGIN_REQUIRED" in html or "Sign in to confirm your age" in html:
            print("❌ [檢查回報] 失敗：此影片被 YouTube 限制，要求登入帳號驗證，AI 無法直接读取。")
            return None, None
            
        # 從網頁中精確撈出影片標題，作為內容正確性的鐵證
        title_match = re.search(r'<meta name="title" content="([^"]+)">', html)
        video_title = title_match.group(1) if title_match else f"YouTube Video ({video_id})"
        
        print(f"🎯 [檢查回報] 成功！偵測到正確的影片標題: 【{video_title}】")
        return html, video_title

    except Exception as e:
        print(f"❌ [檢查回報] 失敗：連線 YouTube 發生異常錯誤: {str(e)}")
        return None, None

def main():
    print(f"🚀 啟動防錯檢查模式，處理影片 ID: {VIDEO_ID}")
    
    if len(VIDEO_ID) != 11:
        print(f"❌ [嚴重錯誤] 填入的 ID 長度為 {len(VIDEO_ID)} 碼！YouTube 影片 ID 必須剛好是 11 碼。請檢查是否誤填了頻道 ID。")
        return

    # 執行第一道檢查
    html_content, video_title = verify_and_get_youtube_html(VIDEO_ID)
    
    if not html_content:
        print("🛑 [安全終止] 由於 YouTube 網頁內容檢查未通過，為防止 AI 產生錯誤筆記，程式已自動安全終止。")
        return

    try:
        # 初始化 Gemini 用戶端
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("❌ [錯誤] 找不到 GEMINI_API_KEY 環境變數，請檢查 GitHub Secrets 設定。")
            return
            
        client = genai.Client(api_key=api_key)
        
        # 核心提示詞：將檢查通過的網頁結構和網址一併送出
        prompt = f"""
        請針對以下提供的 YouTube 影片網頁原始數據與連結進行深度分析，請確保提取的內容「完全符合」該影片標題：{video_title}。
        請「完全使用繁體中文（台灣）」輸出格式化結構漂亮的學習筆記。
        
        請包含以下四大區塊：
        ## 📝 1. 影片核心摘要 (Video Summary)
        - 請用 200-300 字精煉概述影片的核心主題。
        ## 💡 2. 10 個核心重點單字 (Key Vocabulary)
        - **單字 (詞性)** / 中文解釋 / 影片情境或實用例句。
        ## 🎯 3. 5 個實用片語與慣用語 (Phrases & Idioms)
        - **片語/短語** / 中文解釋 / 實用生活例句。
        ## 🧠 4. 關鍵思維或金句延伸 (Key Takeaway)
        - 點出影片最啟發人心的 1-2 句話。

        影片網址：https://www.youtube.com/watch?v={VIDEO_ID}
        影片可視標題：{video_title}
        """
        
        print("🤖 [AI 階段] 檢查完全通過！正在呼叫 Gemini AI 生成精準筆記...")
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
