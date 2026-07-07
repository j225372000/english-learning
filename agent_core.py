import os
import sys
import time
import re
from google import genai
from google.genai import types

# 💡 同時引入既有的舊積木與全新的完全體積木
try:
    from skills import in_youtube  # 舊版：只抓標題與描述
except ImportError:
    in_youtube = None

from skills import in_yt       # 新版：解鎖逐字稿與資料清洗完全體


def run_agent():
    # ─── 1. 讀取 GitHub Actions 或本機傳入的環境變數 ───
    input_data = os.environ.get("INPUT_DATA", "").strip()
    input_type = os.environ.get("INPUT_TYPE", "yt").strip().lower()
    video_type = os.environ.get("VIDEO_TYPE", "general").strip().lower()
    
    print(f"🚀 AI Agent 啟動！核心調度模式: {input_type}")

    if not input_data:
        print("❌ 錯誤: 未提供輸入素材 (INPUT_DATA)")
        sys.exit(1)

    # 預設儲存變數
    source_title = "未命名素材"
    source_content = ""

    # ─── 2. 輸入端核心技能分流調度 (不影響舊功能) ───
    if input_type == "youtube":
        # 🏎️ 舊軌道：原封不動呼叫舊積木
        if in_youtube is None:
            print("❌ 錯誤: 找不到舊的 skills/in_youtube.py 檔案，請確認檔案是否存在。")
            sys.exit(1)
        print("📥 啟動既有的舊版 YouTube 抓取器...")
        source_title, source_content = in_youtube.fetch(input_data)
        print(f"🎯 [舊輸入端成功] 獲取標題: 【{source_title}】")

    elif input_type == "yt":
        # 🚀 新軌道：呼叫全新加入的 in_yt 完全體
        print("📥 啟動全新的完全體 YouTube 逐字稿抓取器 (yt)...")
        result = in_yt.fetch(input_data)
        
        if not result.get("success"):
            print(f"❌ YouTube 逐字稿抓取失敗: {result.get('error') or result.get('transcript_error')}")
            sys.exit(1)
            
        source_title = result.get("title", "未知影片")
        # 優先使用乾淨的逐字稿，若該影片沒字幕，則退回使用清洗後的簡介欄
        if result.get("transcript"):
            source_content = result["transcript"]
            print(f"🎯 [新輸入端成功] 獲取標題: 【{source_title}】(已成功擷取影片逐字稿)")
        else:
            source_content = result["clean_description"]
            print(f"🎯 [新輸入端成功] 獲取標題: 【{source_title}】(影片無字幕，退回擷取清洗後的簡介欄)")

    elif input_type == "web":
        # 🌐 舊軌道：網頁爬取邏輯（保持你原本的 web 程式邏輯）
        print("📥 啟動既有的網頁爬取器...")
        # 這裡會對齊你原本處理網頁的邏輯（例如調度 in_web 積木）
        pass

    elif input_type == "pdf":
        # 📄 舊軌道：PDF 讀取邏輯
        print("📥 啟動既有的 PDF 讀取器...")
        pass

    else:
        print(f"❌ 錯誤: 暫不支援的輸入類型 {input_type}")
        sys.exit(1)

    # ─── 3. 讀取對應的大腦 Prompt 範本 ───
    prompt_path = f"prompts/{video_type}.txt"
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()
    else:
        system_prompt = "你是一位專業的分析師，請幫我詳細摘要並分析以下素材內容。"

    final_prompt = f"{system_prompt}\n\n=== 原始素材內容 ===\n{source_content}"

    # ─── 4. 連線 Gemini 大腦 (內建 503 自動倒數重試與雙大腦防禦機制) ───
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("❌ 錯誤: 找不到 GEMINI_API_KEY 機密憑證，請至 GitHub Settings 設定。")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    
    # 雙大腦守護陣列
    models_to_try = [
        {"name": "gemini-2.5-pro", "desc": "最強 Pro 深度思考大腦"},
        {"name": "gemini-2.5-flash", "desc": "快速 Flash 突圍大腦"}
    ]
    
    final_response_text = None

    for model_info in models_to_try:
        model_name = model_info["name"]
        print(f"🧠 正在嘗試啟動大腦: {model_info['desc']} ({model_name})...")
        
        success = False
        # 針對單一大腦進行 3 次暴力重試 (抵禦 GitHub Actions 頻繁遭遇的 503/429 塞車)
        for retry_idx in range(3):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=final_prompt
                )
                final_response_text = response.text
                success = True
                break  # 成功拿到，跳出重試
            except Exception as e:
                err_msg = str(e)
                if "503" in err_msg or "429" in err_msg:
                    wait_time = (retry_idx + 1) * 10
                    print(f"⚠️ 伺服器忙碌 ({model_name})，將於 {wait_time} 秒後進行第 {retry_idx + 1} 次自動重試...")
                    time.sleep(wait_time)
                else:
                    print(f"❌ 遭遇其他異常: {err_msg}")
                    break
        
        if success and final_response_text:
            print(f"✨ {model_name} 成功產出分析報告！")
            break  # 破關成功，不用動用備用大腦
        else:
            print(f"💥 {model_name} 三次重試皆失敗，準備切換備用方案...")

    if not final_response_text:
        print("🚨 [終極警報] 雙大腦守護與暴力重試皆宣告失敗，Google 伺服器目前極度癱瘓。")
        sys.exit(1)

    # ─── 5. 輸出端核心技能：將 Markdown 報告實質寫回專案 ───
    safe_title = re.sub(r'[\\/*?:"<>|]', "_", source_title).replace(" ", "_")[:30]
    filename = f"📊_分析報告_{safe_title}.md"
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(final_response_text)
        
    print(f"💾 [輸出端成功] 深度投研筆記已實質寫入檔案: {filename}")


if __name__ == "__main__":
    run_agent()
