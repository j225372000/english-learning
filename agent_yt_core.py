import os
import sys
import time
import re
from google import genai
from google.genai import types

# 💡 引入存在於 skills 資料夾底下的新萬用 YouTube 積木
from skills import in_yt

def run_youtube_agent():
    # ─── 1. 讀取環境變數與參數 ───
    input_data = os.environ.get("INPUT_DATA", "").strip()
    video_type = os.environ.get("VIDEO_TYPE", "general").strip().lower()
    
    print(f"🚀 YouTube AI Agent 啟動！目標影片: {input_data}")

    if not input_data:
        print("❌ 錯誤: 未提供輸入素材 (INPUT_DATA)")
        sys.exit(1)

    # ─── 2. 呼叫新 YouTube 技能積木 ───
    print("📥 正在啟動完全體 YouTube 知識抓取器...")
    result = in_yt.fetch(input_data)
    
    if not result.get("success"):
        print(f"❌ YouTube 抓取失敗: {result.get('error') or result.get('transcript_error')}")
        sys.exit(1)
        
    source_title = result.get("title", "未知影片")
    
    # 核心優先級：優先使用逐字稿 (Transcript)，若無字幕才用清洗後的簡介欄 (Clean Description)
    if result.get("transcript"):
        source_content = result["transcript"]
        print(f"🎯 [輸入端成功] 獲取影片標題: 【{source_title}】(已實質擷取逐字稿)")
    else:
        source_content = result["clean_description"]
        print(f"🎯 [輸入端成功] 獲取影片標題: 【{source_title}】(無字幕，已擷取清洗後的簡介欄)")

    # ─── 3. 讀取大腦 Prompt 範本 ───
    prompt_path = f"prompts/{video_type}.txt"
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()
    else:
        system_prompt = "你是一位專業的財經與科技分析師，請幫我詳細摘要並分析以下素材內容。"

    final_prompt = f"{system_prompt}\n\n=== 原始素材內容 ===\n{source_content}"

    # ─── 4. 連線 Gemini 大腦 (503 自動重試與雙大腦切換) ───
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("❌ 錯誤: 找不到 GEMINI_API_KEY 機密憑證")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    
    models_to_try = [
        {"name": "gemini-2.5-pro", "desc": "最強 Pro 深度思考大腦"},
        {"name": "gemini-2.5-flash", "desc": "快速 Flash 突圍大腦"}
    ]
    
    final_response_text = None

    for model_info in models_to_try:
        model_name = model_info["name"]
        print(f"🧠 正在嘗試啟動大腦: {model_info['desc']} ({model_name})...")
        
        success = False
        for retry_idx in range(3):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=final_prompt
                )
                final_response_text = response.text
                success = True
                break
            except Exception as e:
                err_msg = str(e)
                if "503" in err_msg or "429" in err_msg:
                    wait_time = (retry_idx + 1) * 10
                    print(f"⚠️ 伺服器忙碌，將於 {wait_time} 秒後進行第 {retry_idx + 1} 次自動重試...")
                    time.sleep(wait_time)
                else:
                    print(f"❌ 遭遇其他異常: {err_msg}")
                    break
        
        if success and final_response_text:
            print(f"✨ {model_name} 成功產出分析報告！")
            break
        else:
            print(f"💥 {model_name} 重試失敗，準備切換備用方案...")

    if not final_response_text:
        print("🚨 [終極警報] 雙大腦與重試皆失敗，Google 伺服器目前極度癱瘓。")
        sys.exit(1)

    # ─── 5. 將 Markdown 報告寫回專案 ───
    safe_title = re.sub(r'[\\/*?:"<>|]', "_", source_title).replace(" ", "_")[:30]
    filename = f"📊_YouTube分析_{safe_title}.md"
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(final_response_text)
        
    print(f"💾 [輸出端成功] 深度投研筆記已寫入檔案: {filename}")

if __name__ == "__main__":
    run_youtube_agent()
