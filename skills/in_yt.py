import os
import re
import glob
import html
import urllib.parse
from typing import Dict, Any, List, Optional

import yt_dlp


# =========================
# 1. 基礎工具
# =========================

def extract_video_id(input_data: str) -> str:
    """
    支援：
    - YouTube video_id
    - https://www.youtube.com/watch?v=xxxx
    - https://youtu.be/xxxx
    - shorts / live
    - 含 &t=561s 的網址
    """
    text = input_data.strip()

    if re.fullmatch(r"[a-zA-Z0-9_-]{11}", text):
        return text

    parsed = urllib.parse.urlparse(text)

    if "youtube.com" in parsed.netloc:
        query = urllib.parse.parse_qs(parsed.query)

        if "v" in query and query["v"]:
            return query["v"][0]

        if parsed.path.startswith("/shorts/"):
            return parsed.path.split("/shorts/")[1].split("/")[0]

        if parsed.path.startswith("/live/"):
            return parsed.path.split("/live/")[1].split("/")[0]

    if "youtu.be" in parsed.netloc:
        return parsed.path.strip("/").split("/")[0]

    match = re.search(r"([a-zA-Z0-9_-]{11})", text)
    if match:
        return match.group(1)

    raise ValueError("無法解析 YouTube video_id")


def build_youtube_url(input_data: str) -> str:
    video_id = extract_video_id(input_data)
    return f"https://www.youtube.com/watch?v={video_id}"


def clean_description(description: str) -> str:
    if not description:
        return ""

    remove_keywords = [
        "subscribe",
        "follow me",
        "instagram",
        "facebook",
        "twitter",
        "x.com",
        "discord",
        "patreon",
        "sponsor",
        "merch",
        "加入會員",
        "訂閱",
        "追蹤",
    ]

    cleaned_lines = []

    for line in description.splitlines():
        text = line.strip()
        lower_text = text.lower()

        if not text:
            continue

        if text.startswith("http"):
            continue

        if any(k in lower_text for k in remove_keywords):
            continue

        cleaned_lines.append(text)

    return "\n".join(cleaned_lines)


def clean_subtitle_text(raw_text: str) -> str:
    """
    清理 VTT / SRT 字幕。
    """
    if not raw_text:
        return ""

    raw_text = html.unescape(raw_text)

    lines = raw_text.splitlines()
    clean_lines = []

    for line in lines:
        line = line.strip()

        if not line:
            continue

        if line.isdigit():
            continue

        if "-->" in line:
            continue

        if line.startswith("WEBVTT"):
            continue

        if line.startswith("Kind:"):
            continue

        if line.startswith("Language:"):
            continue

        if line.startswith("NOTE"):
            continue

        line = re.sub(r"<[^>]+>", "", line)
        line = html.unescape(line).strip()

        if line:
            clean_lines.append(line)

    text = " ".join(clean_lines)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def remove_temp_files(temp_dir: str) -> None:
    for file in glob.glob(os.path.join(temp_dir, "yt_sub_*")):
        try:
            os.remove(file)
        except Exception:
            pass


# =========================
# 2. yt-dlp 設定
# =========================

def get_base_ydl_opts() -> Dict[str, Any]:
    return {
        "quiet": True,
        "skip_download": True,
        "nocheckcertificate": True,
        "ignoreerrors": False,
        "no_warnings": False,
        "geo_bypass": True,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        },
        "extractor_args": {
            "youtube": {
                # 字幕抓取不需要 android，避免 SABR / android client 額外問題
                "player_client": ["web"]
            }
        },
    }


def fetch_video_info(url: str) -> Dict[str, Any]:
    """
    只抓 metadata 與字幕清單，不下載影片。
    """
    opts = get_base_ydl_opts()

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        raise RuntimeError("yt-dlp 無法取得影片資訊")

    return info


# =========================
# 3. 字幕選擇邏輯
# =========================

def normalize_lang(lang: str) -> str:
    return lang.lower().replace("_", "-")


def lang_score(lang: str) -> int:
    """
    分數越低優先權越高。
    針對你的需求：中文優先，其次英文。
    """
    l = normalize_lang(lang)

    priority = [
        "zh-tw",
        "zh-hant",
        "zh",
        "zh-hans",
        "en",
        "en-us",
        "en-gb",
    ]

    if l in priority:
        return priority.index(l)

    if l.startswith("zh"):
        return 10

    if l.startswith("en"):
        return 20

    return 100


def choose_best_subtitle(info: Dict[str, Any]) -> Dict[str, Any]:
    """
    先看手動字幕，再看自動字幕。
    但不是硬猜語言，而是從實際存在的字幕清單中選。
    """
    subtitles = info.get("subtitles", {}) or {}
    auto_captions = info.get("automatic_captions", {}) or {}

    manual_languages = list(subtitles.keys())
    auto_languages = list(auto_captions.keys())

    if subtitles:
        best_lang = sorted(manual_languages, key=lang_score)[0]
        return {
            "available": True,
            "subtitle_type": "official",
            "language": best_lang,
            "manual_languages": manual_languages,
            "auto_languages": auto_languages,
        }

    if auto_captions:
        best_lang = sorted(auto_languages, key=lang_score)[0]
        return {
            "available": True,
            "subtitle_type": "generated",
            "language": best_lang,
            "manual_languages": manual_languages,
            "auto_languages": auto_languages,
        }

    return {
        "available": False,
        "subtitle_type": "none",
        "language": None,
        "manual_languages": manual_languages,
        "auto_languages": auto_languages,
    }


# =========================
# 4. 字幕下載
# =========================

def find_downloaded_subtitle_file(temp_dir: str) -> Optional[str]:
    files = [
        f for f in glob.glob(os.path.join(temp_dir, "yt_sub_*"))
        if os.path.isfile(f) and not f.endswith(".part")
    ]

    if not files:
        return None

    return max(files, key=os.path.getsize)


def download_selected_subtitle(
    url: str,
    language: str,
    subtitle_type: str,
    temp_dir: str = "."
) -> Dict[str, Any]:
    """
    只下載已確認存在的單一字幕語言，降低 429 機率。
    """
    remove_temp_files(temp_dir)

    outtmpl = os.path.join(temp_dir, "yt_sub_%(id)s")

    opts = {
        **get_base_ydl_opts(),
        "writesubtitles": subtitle_type == "official",
        "writeautomaticsub": subtitle_type == "generated",
        "subtitleslangs": [language],
        "subtitlesformat": "vtt/srt/best",
        "outtmpl": outtmpl,
    }

    try:
        print(f"⬇️ 下載字幕：{subtitle_type} / {language}")

        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        subtitle_file = find_downloaded_subtitle_file(temp_dir)

        if not subtitle_file:
            return {
                "success": False,
                "transcript": "",
                "subtitle_file": None,
                "error": "yt-dlp 顯示有字幕，但沒有產生字幕檔案",
            }

        with open(subtitle_file, "r", encoding="utf-8", errors="ignore") as f:
            raw_text = f.read()

        transcript = clean_subtitle_text(raw_text)

        if len(transcript.strip()) < 100:
            return {
                "success": False,
                "transcript": transcript,
                "subtitle_file": subtitle_file,
                "error": "字幕內容過短，可能下載失敗或字幕無效",
            }

        return {
            "success": True,
            "transcript": transcript,
            "subtitle_file": subtitle_file,
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "transcript": "",
            "subtitle_file": None,
            "error": str(e),
        }

    finally:
        remove_temp_files(temp_dir)


# =========================
# 5. 主 Skill
# =========================

def fetch(input_data: str) -> Dict[str, Any]:
    """
    YouTube Input Skill v2

    回傳格式維持相容 agent_core.py：
    - title
    - transcript
    - transcript_status
    - need_whisper
    """
    try:
        video_id = extract_video_id(input_data)
        url = build_youtube_url(input_data)

        print(f"🎬 YouTube 影片 ID：{video_id}")
        print("🔎 使用 yt-dlp 取得影片資訊與字幕清單...")

        info = fetch_video_info(url)

        title = info.get("title", "未命名 YouTube 影片")
        description = info.get("description", "") or ""
        channel = info.get("channel", "") or info.get("uploader", "")
        published_at = str(info.get("upload_date", "") or "")
        duration = info.get("duration", "")
        view_count = info.get("view_count", "")

        print(f"🎞️ 標題：{title}")

        subtitle_choice = choose_best_subtitle(info)

        print(f"📌 手動字幕：{subtitle_choice.get('manual_languages')}")
        print(f"📌 自動字幕：{subtitle_choice.get('auto_languages')}")

        transcript = ""
        transcript_status = "none"
        transcript_language = None
        subtitle_error = None

        if subtitle_choice["available"]:
            transcript_status = subtitle_choice["subtitle_type"]
            transcript_language = subtitle_choice["language"]

            result = download_selected_subtitle(
                url=url,
                language=transcript_language,
                subtitle_type=transcript_status,
                temp_dir=".",
            )

            if result["success"]:
                transcript = result["transcript"]
                print(
                    f"✅ 字幕成功：{transcript_status} / "
                    f"{transcript_language}，共 {len(transcript)} 字。"
                )
            else:
                subtitle_error = result["error"]
                transcript_status = f"{transcript_status}_download_failed"
                print(f"⚠️ 字幕下載失敗：{subtitle_error}")

        else:
            subtitle_error = "影片沒有可用字幕"
            print("⚠️ 沒有手動字幕或自動字幕。")

        need_whisper = not bool(transcript and len(transcript.strip()) >= 100)

        if need_whisper:
            print("⚠️ 未取得有效逐字稿，建議啟動 Whisper 備援。")

        return {
            "success": True,
            "source": "youtube",
            "video_id": video_id,
            "url": url,

            "title": title,
            "description": description,
            "clean_description": clean_description(description),
            "channel": channel,
            "published_at": published_at,
            "duration": duration,
            "view_count": view_count,

            "transcript": transcript,
            "content": transcript,

            "transcript_status": transcript_status,
            "transcript_language": transcript_language,
            "manual_languages": subtitle_choice.get("manual_languages", []),
            "auto_languages": subtitle_choice.get("auto_languages", []),
            "need_whisper": need_whisper,

            "metadata": {
                "title": title,
                "channel": channel,
                "published_at": published_at,
                "duration": duration,
                "view_count": view_count,
                "url": url,
            },

            "status": {
                "input_success": True,
                "transcript_status": transcript_status,
                "transcript_language": transcript_language,
                "need_whisper": need_whisper,
            },

            "error": subtitle_error,
        }

    except Exception as e:
        return {
            "success": False,
            "source": "youtube",
            "video_id": None,
            "url": input_data,

            "title": "",
            "description": "",
            "clean_description": "",
            "channel": "",
            "published_at": "",
            "duration": "",
            "view_count": "",

            "transcript": "",
            "content": "",

            "transcript_status": "error",
            "transcript_language": None,
            "manual_languages": [],
            "auto_languages": [],
            "need_whisper": True,

            "metadata": {},
            "status": {
                "input_success": False,
                "transcript_status": "error",
                "need_whisper": True,
            },

            "error": str(e),
        }
