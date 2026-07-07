import os
import sys
import time
import re

from google import genai

from skills import in_yt, in_web, in_pdf


def initialize_gemini_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    if not api_key:
        print("🚨 錯誤：環境變數中缺少 GEMINI_API_KEY。")
        sys.exit(1)

    return genai.Client(api_key=api_key)


def load_system_prompt(video_type: str) -> str:
    """
    依照 VIDEO_TYPE 載入不同 Prompt。
    對應資料夾：prompts/
    """

    prompt_map = {
        "finance": "prompts/finance.txt",
        "fed": "prompts/fed.txt",
        "english": "prompts/english.txt",
        "general": "prompts/general.txt",
    }

    prompt_path = prompt_map.get(video_type, "prompts/general.txt")

    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt = f.read().strip()

            if prompt:
                print(f"🧭 已載入分析模式：{video_type} → {prompt_path}")
                return prompt

    print(f"⚠️ 找不到 Prompt 檔案或內容為空：{prompt_path}，改用預設 Prompt。")

    return (
        "你是一位專業研究助理。請針對提供的素材內容，"
        "製作一份結構清楚、重點明確、使用繁體中文的知識筆記。"
    )


def normalize_input_result(result, default_title="未命名素材"):
    """
    統一不同 input skill 的回傳格式。

    支援：
    1. dict：in_yt 這類格式
    2. tuple(title, content)：in_web / in_pdf 這類格式
    """

    if isinstance(result, dict):
        title = result.get("title", default_title)

        content = (
            result.get("transcript")
            or result.get("content")
            or result.get("text")
            or ""
        )

        return {
            "success": result.get("success", True),
            "title": title,
            "content": content,
            "status": result.get("transcript_status", result.get("status", "ok")),
            "error": result.get("error"),
        }

    if isinstance(result, tuple) and len(result) >= 2:
        title, content = result[0], result[1]

        error_titles = [
            "錯誤",
            "找不到檔案",
            "PDF 解析失敗",
            "網址格式錯誤",
            "網頁抓取失敗",
        ]

        is_error = str(title).strip() in error_titles

        return {
            "success": not is_error,
            "title": title or default_title,
            "content": content or "",
            "status": "error" if is_error else "ok",
            "error": content if is_error else None,
        }

    return {
        "success": False,
        "title": default_title,
        "content": "",
        "status": "error",
        "error": "未知的 input skill 回傳格式",
    }


def main():
    print("═══════════════════════════════════════════════════")
    print("  AI Agent 雲端原生核心調度系統啟動...")
    print("═══════════════════════════════════════════════════")

    input_type = os.environ.get("INPUT_TYPE", "yt").strip().lower()
    input_data = os.environ.get("INPUT_DATA", "").strip()
    video_type = os.environ.get("VIDEO_TYPE", "general").strip().lower()

    if not input_data:
        print("🚨 錯誤：未偵測到 INPUT_DATA。")
        sys.exit(1)

    print(f"🚀 核心調度模式: {input_type}")
    print(f"🎯 分析模式: {video_type}")
    print(f"📌 目標素材: {input_data}")

    client = initialize_gemini_client()
    system_prompt = load_system_prompt(video_type)

    source_title = ""
    source_content = ""

    try:
        if input_type == "yt":
            print("📥 啟動 YouTube 逐字稿抓取器...")

            raw_result = in_yt.fetch(input_data)
            extracted_data = normalize_input_result(
                raw_result,
                default_title="未命名 YouTube 影片"
            )

            source_title = extracted_data["title"]
            source_content = extracted_data["content"]

            print(f"🎬 影片標題：{source_title}")
            print(f"📝 字幕狀態：{extracted_data.get('status', 'unknown')}")

        elif input_type == "web":
            print("🌐 啟動 Web 網頁擷取器...")

            raw_result = in_web.fetch(input_data)
            extracted_data = normalize_input_result(
                raw_result,
                default_title="未命名網頁"
            )

            source_title = extracted_data["title"]
            source_content = extracted_data["content"]

            print(f"🌐 網頁標題：{source_title}")
            print(f"📄 文字長度：{len(source_content)} 字")

        elif input_type == "pdf":
            print("📄 啟動 PDF 擷取器...")

            raw_result = in_pdf.fetch(input_data)
            extracted_data = normalize_input_result(
                raw_result,
                default_title="未命名 PDF"
            )

            source_title = extracted_data["title"]
            source_content = extracted_data["content"]

            print(f"📄 PDF 標題：{source_title}")
            print(f"📄 文字長度：{len(source_content)} 字")

        else:
            print(f"⚠️ 目前只支援 yt / web / pdf 模式，不支援：{input_type}")
            sys.exit(1)

        if not extracted_data.get("success", False):
            print(f"❌ 擷取失敗：{extracted_data.get('error')}")
            sys.exit(1)

    except Exception as fetch_err:
        print(f"❌ 擷取資料時發生異常: {str(fetch_err)}")
        sys.exit(1)

    if not source_content or len(source_content.strip()) < 100:
        print("⚠️ 未取得有效素材內容，停止產生正式知識筆記。")
        print("建議：確認輸入來源是否可讀取，或改用其他輸入方式。")
        sys.exit(1)

    models_to_try = [
        {
            "name": "gemini-2.5-pro",
            "desc": "最強 Pro 深度思考大腦",
        },
        {
            "name": "gemini-2.5-flash",
            "desc": "快速 Flash 備援大腦",
        },
    ]

    final_response_text = ""
    chosen_model_name = ""

    final_prompt = (
        f"{system_prompt}\n\n"
        f"# 目標素材標題\n"
        f"{source_title}\n\n"
        f"# 目標素材內容\n"
        f"{source_content}"
    )

    for model_info in models_to_try:
        model_name = model_info["name"]

        print(f"🧠 嘗試啟動：{model_info['desc']} ({model_name})")

        success = False

        for retry_idx in range(3):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=final_prompt,
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
                    print(
                        f"⚠️ 伺服器忙碌，"
                        f"{wait_time} 秒後重試第 {retry_idx + 1} 次..."
                    )
                    time.sleep(wait_time)
                else:
                    print(f"❌ Gemini 呼叫異常: {err_msg}")
                    break

        if success:
            print(f"✨ {chosen_model_name} 成功產出分析報告。")
            break

        print(f"💥 {model_name} 失敗，切換下一個模型。")

    if not final_response_text:
        print("🚨 所有模型皆失敗，未能產生分析報告。")
        sys.exit(1)

    try:
        safe_title = re.sub(r'[\\/*?:"<>|]', "_", source_title)
        safe_title = safe_title.replace(" ", "_")[:50]

        output_filename = f"📊_分析報告_{safe_title}.md"

        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(final_response_text)

        print(f"💾 輸出成功：{output_filename}")
        print("═══════════════════════════════════════════════════")
        print("  AI Agent 任務完成。")
        print("═══════════════════════════════════════════════════")

    except Exception as save_err:
        print(f"❌ 寫入 Markdown 檔案時發生異常: {str(save_err)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
