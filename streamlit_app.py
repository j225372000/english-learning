import os
import re
import tempfile
import time
from pathlib import Path

import streamlit as st
import yt_dlp
from google import genai


st.set_page_config(page_title="YouTube 影片知識筆記", page_icon="🎬", layout="wide")

MODE_MAP = {
    "財經分析": "finance",
    "聯準會分析": "fed",
    "英文學習": "english",
    "一般知識筆記": "general",
}


def load_system_prompt(mode_label: str) -> tuple[str, str]:
    video_type = MODE_MAP.get(mode_label, "general")
    prompt_map = {
        "finance": "prompts/finance.txt",
        "fed": "prompts/fed.txt",
        "english": "prompts/english.txt",
        "general": "prompts/general.txt",
    }
    prompt_path = Path(prompt_map.get(video_type, "prompts/general.txt"))
    if prompt_path.exists():
        prompt = prompt_path.read_text(encoding="utf-8").strip()
        if prompt:
            return prompt, str(prompt_path)
    return (
        "你是一位專業研究助理。請針對提供的素材內容，"
        "製作一份結構清楚、重點明確、使用繁體中文的知識筆記。",
        "原程式預設 Prompt",
    )


def valid_youtube_url(url: str) -> bool:
    return bool(re.search(r"(youtube\.com/(watch\?v=|shorts/|live/)|youtu\.be/)[A-Za-z0-9_-]{11}", url))


def clean_vtt(content: str) -> str:
    lines = []
    previous = ""
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.isdigit() or "-->" in line:
            continue
        if line.startswith(("WEBVTT", "NOTE", "Kind:", "Language:")):
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if line and line != previous:
            lines.append(line)
            previous = line
    return "\n".join(lines)


def obtain_transcript(url: str) -> tuple[str, str]:
    with tempfile.TemporaryDirectory() as work_dir:
        output_template = str(Path(work_dir) / "caption")
        check_options = {"quiet": True, "skip_download": True, "list_subtitles": True}
        with yt_dlp.YoutubeDL(check_options) as ydl:
            info = ydl.extract_info(url, download=False)

        manual = info.get("subtitles") or {}
        automatic = info.get("automatic_captions") or {}
        available = manual or automatic
        if not available:
            raise RuntimeError("這部影片沒有可用的人工或自動字幕。免費雲端版未啟用 Whisper。")

        preferred = ["zh-Hant", "zh-TW", "zh", "en"]
        language = next((lang for lang in preferred if lang in available), next(iter(available)))
        download_options = {
            "quiet": True,
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": [language],
            "subtitlesformat": "vtt/best",
            "outtmpl": output_template,
        }
        with yt_dlp.YoutubeDL(download_options) as ydl:
            ydl.download([url])

        files = [path for path in Path(work_dir).iterdir() if path.is_file() and not path.name.endswith(".part")]
        if not files:
            raise RuntimeError("影片顯示有字幕，但雲端主機無法下載字幕內容。")
        transcript = clean_vtt(files[0].read_text(encoding="utf-8", errors="ignore"))
        if len(transcript.strip()) < 100:
            raise RuntimeError("取得的字幕內容為空白或過短。")
        return transcript, info.get("title") or "未命名 YouTube 影片"


def friendly_error(error: Exception) -> str:
    message = str(error)
    if "Sign in to confirm" in message or "not a bot" in message:
        return "YouTube要求登入以確認不是機器人；此雲端平台目前無法取得該影片字幕。"
    if "503" in message or "UNAVAILABLE" in message:
        return "Gemini目前流量過高，已完成自動重試但仍忙碌，請稍後再試。"
    if "429" in message or "RESOURCE_EXHAUSTED" in message:
        return "Gemini API使用額度或頻率已達上限，請稍後再試或檢查配額。"
    if "403" in message or "PERMISSION_DENIED" in message:
        return "Gemini API金鑰沒有模型使用權限，請確認已啟用 Gemini API。"
    return message[-1500:]


def generate_note(api_key: str, prompt: str) -> tuple[str, str]:
    client = genai.Client(api_key=api_key)
    last_error = None
    for model_name in ["gemini-2.5-pro", "gemini-2.5-flash"]:
        for attempt in range(3):
            try:
                response = client.models.generate_content(model=model_name, contents=prompt)
                result = (response.text or "").strip()
                if result:
                    return result, model_name
            except Exception as error:
                last_error = error
                message = str(error)
                if any(code in message for code in ["503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED"]):
                    time.sleep((attempt + 1) * 10)
                    continue
                break
    raise RuntimeError(f"所有 Gemini模型皆失敗：{last_error}")


st.title("🎬 YouTube 影片知識筆記")
st.caption("使用影片現有字幕，並依 GitHub 專案原始 Prompt 交由 Gemini 分析。")

with st.sidebar:
    url = st.text_input("YouTube 網址", placeholder="https://www.youtube.com/watch?v=...")
    api_key = st.text_input("Gemini API 金鑰", type="password", placeholder="AIza...")
    mode = st.selectbox("分析模式", list(MODE_MAP))
    analyze = st.button("開始分析", type="primary", use_container_width=True)
    st.caption("API 金鑰只用於本次請求，不會寫入檔案。")
    st.caption("免費測試版僅讀取影片現有字幕，不啟用 Whisper。")

if analyze:
    if not valid_youtube_url(url.strip()):
        st.error("請輸入有效的 YouTube 網址。")
    elif not api_key.strip():
        st.error("請輸入 Gemini API 金鑰。")
    else:
        try:
            with st.status("正在處理影片…", expanded=True) as status:
                st.write("正在取得 YouTube 字幕…")
                transcript, title = obtain_transcript(url.strip())
                st.write(f"字幕取得完成，共 {len(transcript):,} 字。")
                system_prompt, prompt_source = load_system_prompt(mode)
                st.write(f"分析模式：{mode}｜Prompt：{prompt_source}")
                final_prompt = (
                    f"{system_prompt}\n\n"
                    f"# 目標素材標題\n{title}\n\n"
                    f"# 目標素材內容\n{transcript[:600000]}"
                )
                st.write("正在呼叫 Gemini 產生筆記…")
                result, model = generate_note(api_key.strip(), final_prompt)
                status.update(label="分析完成", state="complete", expanded=False)
            st.success(f"完成｜字幕 {len(transcript):,} 字｜模型 {model}")
            st.markdown(result)
            safe_title = re.sub(r"[\\/*?:\"<>|]", "_", title).replace(" ", "_")[:50]
            st.download_button(
                "下載 Markdown 筆記",
                data=result.encode("utf-8"),
                file_name=f"分析報告_{safe_title}.md",
                mime="text/markdown",
            )
        except Exception as error:
            st.error(friendly_error(error))
else:
    st.info("請在左側輸入 YouTube 網址及 Gemini API 金鑰後開始分析。")
