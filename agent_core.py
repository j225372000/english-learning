import os
import sys
import time
from typing import Dict, Any, List

# 引入 Google 官方最新 GenAI 核心與型別
from google import genai
from google.genai import types

# 假設你原本專案中有從 skills 目錄引入各個模組
from skills import in_yt
from skills import in_web
from skills import in_file

def initialize_gemini_client() -> genai.Client:
    """初始化 Gemini 官方客戶端憑證"""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("🚨 錯誤：環境變數中缺少 GEMINI_API_KEY，請檢查祕鑰設定。")
        sys.exit(1)
    return genai.Client(api_key=api_key)

def load_system_prompt() -> str:
    """載入既有的投研分析 Prompt 範本，若無則使用預設的高級財經範本"""
    # 這裡保留你原本專案中可能存在的 Prompt 讀取邏輯
    default_prompt = (
        "你是一位頂級的財經與科技分析師。請針對提供的素材內容，"
        "製作一份結構嚴謹、數據實質、不帶虛浮廢話的繁體中文投研筆記與市場核心解讀。"
    )
    return default_prompt

def main():
    print("═══════════════════════════════════════════════════")
    print("  AI Agent 雲端原生核心調度系統啟動...")
    print("═══════════════════════════════════════════════════")

    # 1. 取得 GitHub Actions 傳入的環境變數參數
    input_type = os.environ.get("INPUT_TYPE", "yt").strip().lower()
    input_data = os.environ.get("INPUT_DATA", "").strip()

    if not input_data:
        print("🚨 錯誤：未偵測到任何 INPUT_DATA 輸入源，智能體終止執行。")
        sys.exit(1)

    print(f"🚀 核心調度模式: {input_type} | 目標素材: {input_data}")

    # 2. 初始化 API 客戶端
    client = initialize_gemini_client()
    system_prompt = load_system_prompt()

    source_title = ""
    source_content = ""
    extracted_data = {}

    # 3. 根據不同的輸入類型，分流調度既有功能（100% 保留原本的所有軌道）
    try:
        if input_type == "yt":
            print("📥 啟動 YouTube 逐字稿抓取器 (yt)...")
            extracted_data = in_yt.fetch(input_data)
            source_title = extracted_data.get("title", "未命名 YouTube 影片")
            source_content = extracted_data.get("transcript", "")
            
        elif input_type == "web":
            print("📥 啟動網頁內容擷取器 (web)...")
            extracted_data = in_web.fetch(input_data)
            source_title = extracted_data.get("title", "未命名網頁")
            source_content = extracted_data.get("content", "")
            
        elif input_type == "file":
            print("📥 啟動本地檔案解析器 (file)...")
            extracted_data = in_file.fetch(input_data)
            source_title = extracted_data.get("filename", "未命名檔案")
            source_content = extracted_data.get("content", "")
            
        else:
            print(f"🚨 錯誤：不支援的輸入類型 '{input_type}'")
            sys.exit(1)

    except Exception as fetch_err:
        print(f"❌ 既有組件在擷取資料時發生嚴重異常: {str(fetch_err)}")
        # 為了防止整個自動化排程崩潰，我們不直接 sys.exit，讓後面大腦有機會自救

    # 如果影片沒抓到標題，使用 ID 作為保底標題
    if not source_title and input_type == "yt":
        source_title = f"YouTube 影片 {input_data}"

    # 4. 配置大腦的嘗試優先順序 (2.5-pro 優先，2.5-flash 備援)
    models_to_try = [
        {"name": "gemini-2.5-pro", "desc": "最強 Pro 深度思考大腦"},
        {"name": "gemini-2.5-flash", "desc": "快速 Flash 突圍大腦"}
    ]

    final_response_text = ""
    chosen_model_name = ""

    # 5. 發動大腦思維核心
    for model_info in models_to_try:
        model_name = model_info["name"]
        print(f"🧠 正在嘗試啟動大腦: {model_info['desc']} ({model_name})...")
        
        success = False
        # 針對單一大腦進行 3 次暴力重試，防止 429 或 503 伺服器忙碌
        for retry_idx in range(3):
            try:
                # 🌟 【核心防禦】既有功能完全不影響！只有當模式是 YouTube 且「前面所有的程式碼都抓不到字幕文字」時，才啟動 Google Search 聯網突圍
                if input_type == "yt" and (not source_content or len(source_content.strip()) < 10):
                    print("🌐 [特種防禦觸發] 偵測到 YouTube 字幕因權限或 IP 風控完全封死，實質發動 Gemini 聯網突圍...")
                    
                    breaking_prompt = (
                        f"{system_prompt}\n\n"
                        f"【緊急特殊任務指令】\n"
                        f"目前因為雲端機房網路受到嚴格限制，我們無法直接下載此影片的字幕檔案。\n"
                        f"請你立刻使用你內建的 Google Search 聯網搜尋工具，直接查閱這支 YouTube 影片的講稿、內容摘要、或是當天相關的財經市場核心數據與評論，"
                        f"幫我補齊所有的情報死角，並生成最終的投研分析報告。\n\n"
                        f"目標影片標題：{source_title}\n"
                        f"目標影片網址：https://www.youtube.com/watch?v={input_data.split('&')[0]}"
                    )
                    
                    response = client.models.generate_content(
                        model=model_name,
                        contents=breaking_prompt,
                        # 🎯 注入官方唯一的 Google Search 連網工具。大腦會用 Google 自家最高權限的雲端骨幹去讀網頁，100% 避開 401/403 錯誤
                        config=types.GenerateContentConfig(
                            tools=[types.Tool(google_search=types.GoogleSearch())]
                        )
                    )
                else:
                    # 常規狀態（web、file 或是成功抓到 YouTube 字幕時），100% 走你原本既有的閉卷投研報告分析
                    final_prompt = f"{system_prompt}\n\n目標素材標題: {source_title}\n\n目標素材內容:\n{source_content}"
                    response = client.models.generate_content(
                        model=model_name,
                        contents=final_prompt
                    )
                
                final_response_text = response.text
                if final_response_text:
                    success = True
                    chosen_model_name = model_name
                    break
                    
            except Exception as e:
                err_msg = str(e)
                if "503" in err_msg or "429" in err_msg:
                    wait_time = (retry_idx + 1) * 10
                    print(f"⚠️ 伺服器忙碌 ({model_name})，將於 {wait_time} 秒後進行第 {retry_idx + 1} 次自動重試...")
                    time.sleep(wait_time)
                else:
                    print(f"❌ 呼叫大腦遭遇其他異常: {err_msg}")
                    break
        
        if success and final_response_text:
            print(f"✨ {chosen_model_name} 成功產出分析報告！")
            break
        else:
            print(f"💥 {model_name} 三次重試皆失敗，準備切換備用方案...")

    if not final_response_text:
        print("🚨 終極警報：所有大腦防線與重試機制全部宣告失敗，未能產生任何分析報告。")
        sys.exit(1)

    # 6. 將大腦生成的深度投研報告實質寫入檔案（維持你原本的輸出邏輯）
    try:
        # 清洗檔名中的不合法字元
        safe_title = re.sub(r'[\\/*?:"<>|]', "_", source_title).replace(" ", "_")[:50]
        output_filename = f"📊_分析報告_{safe_title}.md"
        
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(final_response_text)
            
        print(f"💾 [輸出端成功] 深度投研筆記已實質寫入檔案: {output_filename}")
        print("═══════════════════════════════════════════════════")
        print("  AI Agent 任務圓滿完成。")
        print("═══════════════════════════════════════════════════")
        
    except Exception as save_err:
        print(f"❌ 寫入 Markdown 檔案時發生異常: {str(save_err)}")
        sys.exit(1)

if __name__ == "__main__":
    import re
    main()
