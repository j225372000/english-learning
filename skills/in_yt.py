import os
import re
import json
import html
import glob
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional

import yt_dlp


def extract_video_id(input_data: str) -> str:
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


def fetch_metadata(video_id: str) -> Dict[str, Any]:
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()

    if not api_key:
        raise ValueError("缺少環境變數 YOUTUBE_API_KEY")

    url = (
        "https://www.googleapis.com/youtube/v3/videos"
        "?part=snippet,contentDetails,statistics"
        f"&id={video_id}"
        f"&key={api_key}"
    )

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )

    with urllib.request.urlopen(req, timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))

    if not data.get("items"):
        raise ValueError("找不到該影片，可能是影片不存在、私人影片或地區限制。")

    item = data["items"][0]
    snippet = item.get("snippet", {})
    statistics = item.get("statistics", {})
    content_details = item.get("contentDetails", {})

    return {
        "title": snippet.get("title", ""),
        "description": snippet.get("description", ""),
        "channel": snippet.get("channelTitle", ""),
        "published_at": snippet.get("publishedAt", ""),
        "duration": content_details.get("duration", ""),
        "view_count": statistics.get("viewCount", ""),
        "like_count": statistics.get("likeCount", ""),
        "comment_count": statistics.get("commentCount", ""),
    }


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
    if not raw_text:
        return ""

    text = html.unescape(raw_text)
    text = urllib.parse.unquote(text)

    lines = text.splitlines()
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

        if line.startswith("{") or line.startswith("["):
            continue

        line = re.sub(r"<[^>]+>", "", line)
        line = html.unescape(line).strip()

        if line:
            clean_lines.append(line)

    final_text = " ".join(clean_lines)
    final_text = re.sub(r"\s+", " ", final_text)
    return final_text.strip()


def remove_temp_subtitle_files():
    for file in glob.glob("temp_sub*"):
        try:
            os.remove(file)
        except Exception:
            pass


def find_downloaded_subtitle_file() -> Optional[str]:
    candidates = []

    for file in glob.glob("temp_sub*"):
        if file.endswith(".part"):
            continue
        if os.path.isfile(file):
            candidates.append(file)

    if not candidates:
        return None

    candidates.sort(key=lambda x: os.path.getsize(x), reverse=True)
    return candidates[0]


def detect_caption_type(info: Dict[str, Any]) -> Dict[str, Any]:
    subtitles = info.get("subtitles", {}) or {}
    auto_captions = info.get("automatic_captions", {}) or {}

    return {
        "manual_languages": list(subtitles.keys()),
        "auto_languages": list(auto_captions.keys()),
        "has_manual": bool(subtitles),
        "has_auto": bool(auto_captions),
    }


def get_base_opts() -> Dict[str, Any]:
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
                "player_client": ["web"]
            }
        },
    }


def lang_priority(mode: str) -> List[str]:
    """
    重點：
    - 英文影片優先抓 en-orig / en，交給 Gemini 輸出繁中筆記。
    - 財金中文影片若有中文原字幕，會抓中文。
    - 不再一次下載多語言。
    """
    mode = (mode or "").lower()

    if mode == "english":
        return [
            "en-orig", "en", "en-US", "en-GB",
            "zh-Hant", "zh-TW", "zh", "zh-Hans"
        ]

    return [
        "en-orig",
        "zh-TW", "zh-Hant", "zh", "zh-Hans",
        "en", "en-US", "en-GB"
    ]


def sort_languages(available: List[str], mode: str) -> List[str]:
    priority = lang_priority(mode)
    priority_lower = [p.lower() for p in priority]

    def score(lang: str) -> int:
        lang_lower = lang.lower()

        if lang_lower in priority_lower:
            return priority_lower.index(lang_lower)

        if lang_lower.endswith("-orig"):
            return 5

        if lang_lower.startswith("zh"):
            return 20

        if lang_lower.startswith("en"):
            return 30

        return 100

    return sorted(available, key=score)


def build_subtitle_candidates(caption_info: Dict[str, Any], mode: str) -> List[Dict[str, str]]:
    """
    建立候選字幕清單。
    原則：
    1. 先試手動字幕
    2. 再試自動字幕
    3. 每次只下載一種語言
    """
    candidates = []

    manual_languages = sort_languages(caption_info.get("manual_languages", []), mode)
    auto_languages = sort_languages(caption_info.get("auto_languages", []), mode)

    for lang in manual_languages:
        candidates.append({
            "subtitle_type": "manual",
            "language": lang
        })

    for lang in auto_languages:
        candidates.append({
            "subtitle_type": "auto",
            "language": lang
        })

    return candidates


def download_one_subtitle(url: str, language: str, subtitle_type: str) -> Dict[str, Any]:
    """
    只下載單一字幕。
    這是修正重點：避免 en 成功後又因 zh-Hant 429 導致整體失敗。
    """
    remove_temp_subtitle_files()

    base_opts = get_base_opts()

    ydl_opts_down = {
        **base_opts,
        "writesubtitles": subtitle_type == "manual",
        "writeautomaticsub": subtitle_type == "auto",
        "subtitleslangs": [language],
        "subtitlesformat": "vtt/srt/best",
        "outtmpl": "temp_sub",
    }

    try:
        print(f"⬇️ 嘗試下載字幕：{subtitle_type} / {language}")

        with yt_dlp.YoutubeDL(ydl_opts_down) as ydl_down:
            ydl_down.download([url])

        subtitle_file = find_downloaded_subtitle_file()

        if not subtitle_file:
            return {
                "success": False,
                "transcript": "",
                "error": "未找到下載後的字幕檔",
                "subtitle_file": None,
            }

        with open(subtitle_file, "r", encoding="utf-8", errors="ignore") as f:
            raw_text = f.read()

        transcript_text = clean_subtitle_text(raw_text)

        if not transcript_text or len(transcript_text.strip()) < 100:
            return {
                "success": False,
                "transcript": transcript_text,
                "error": "字幕內容為空或過短",
                "subtitle_file": subtitle_file,
            }

        return {
            "success": True,
            "transcript": transcript_text,
            "error": None,
            "subtitle_file": subtitle_file,
        }

    except Exception as e:
        return {
            "success": False,
            "transcript": "",
            "error": str(e),
            "subtitle_file": None,
        }

    finally:
        remove_temp_subtitle_files()


def download_subtitle_by_ytdlp(url: str, langs: List[str]) -> Dict[str, Any]:
    """
    使用 yt-dlp 下載字幕。

    這版不再直接使用 langs 一次下載多語言。
    langs 保留是為了相容舊呼叫方式。
    真正策略改為：
    1. 先列出實際存在的字幕
    2. 依 VIDEO_TYPE 排序
    3. 每次只下載一種字幕
    4. 失敗才換下一個候選
    """
    remove_temp_subtitle_files()

    base_opts = get_base_opts()
    mode = os.environ.get("VIDEO_TYPE", "general").strip().lower()

    try:
        print("🔎 使用 yt-dlp 檢查字幕清單...")

        with yt_dlp.YoutubeDL({
            **base_opts,
            "list_subtitles": True,
        }) as ydl:
            info = ydl.extract_info(url, download=False)

        caption_info = detect_caption_type(info)

        print(f"📌 手動字幕語言：{caption_info['manual_languages']}")
        print(f"📌 自動字幕語言：{caption_info['auto_languages']}")

        if not caption_info["has_manual"] and not caption_info["has_auto"]:
            return {
                "success": False,
                "transcript": "",
                "transcript_status": "no_subtitles",
                "transcript_language": None,
                "manual_languages": [],
                "auto_languages": [],
                "error": "沒有找到手動字幕或自動字幕",
            }

        candidates = build_subtitle_candidates(caption_info, mode)

        if not candidates:
            return {
                "success": False,
                "transcript": "",
                "transcript_status": "no_candidate_subtitle",
                "transcript_language": None,
                "manual_languages": caption_info["manual_languages"],
                "auto_languages": caption_info["auto_languages"],
                "error": "有字幕清單，但沒有可用候選字幕",
            }

        print("🎯 字幕候選順序：")
        for c in candidates[:10]:
            print(f"   - {c['subtitle_type']} / {c['language']}")

        errors = []

        for candidate in candidates:
            subtitle_type = candidate["subtitle_type"]
            language = candidate["language"]

            result = download_one_subtitle(url, language, subtitle_type)

            if result.get("success"):
                transcript_status = "official" if subtitle_type == "manual" else "generated"

                return {
                    "success": True,
                    "transcript": result.get("transcript", ""),
                    "transcript_status": transcript_status,
                    "transcript_language": language,
                    "manual_languages": caption_info["manual_languages"],
                    "auto_languages": caption_info["auto_languages"],
                    "subtitle_file": result.get("subtitle_file"),
                    "error": None,
                }

            errors.append(f"{subtitle_type}/{language}: {result.get('error')}")
            print(f"⚠️ 失敗，改試下一個字幕：{subtitle_type} / {language}")

        return {
            "success": False,
            "transcript": "",
            "transcript_status": "all_subtitles_failed",
            "transcript_language": None,
            "manual_languages": caption_info["manual_languages"],
            "auto_languages": caption_info["auto_languages"],
            "error": " | ".join(errors[:5]),
        }

    except Exception as e:
        return {
            "success": False,
            "transcript": "",
            "transcript_status": "ytdlp_failed",
            "transcript_language": None,
            "manual_languages": [],
            "auto_languages": [],
            "error": str(e),
        }

    finally:
        remove_temp_subtitle_files()


def fetch(input_data: str) -> Dict[str, Any]:
    try:
        video_id = extract_video_id(input_data)
        url = build_youtube_url(input_data)

        metadata = fetch_metadata(video_id)

        print(f"🎬 YouTube 影片 ID：{video_id}")
        print(f"🎞️ 標題：{metadata.get('title', '')}")

        preferred_langs = ["en", "zh-TW", "zh-Hant", "zh"]

        subtitle_data = download_subtitle_by_ytdlp(url, preferred_langs)

        if subtitle_data.get("success"):
            transcript_text = subtitle_data.get("transcript", "")

            print(
                f"✅ 字幕抓取成功：{subtitle_data.get('transcript_status')} "
                f"({subtitle_data.get('transcript_language')})，"
                f"共 {len(transcript_text)} 字。"
            )

        else:
            transcript_text = ""

            print(
                f"⚠️ yt-dlp 字幕抓取失敗："
                f"{subtitle_data.get('transcript_status')} / "
                f"{subtitle_data.get('error')}"
            )

        return {
            "success": True,
            "source": "youtube",
            "video_id": video_id,
            "url": url,

            "title": metadata.get("title", ""),
            "description": metadata.get("description", ""),
            "clean_description": clean_description(metadata.get("description", "")),
            "channel": metadata.get("channel", ""),
            "published_at": metadata.get("published_at", ""),
            "duration": metadata.get("duration", ""),
            "view_count": metadata.get("view_count", ""),
            "like_count": metadata.get("like_count", ""),
            "comment_count": metadata.get("comment_count", ""),

            "transcript_status": subtitle_data.get("transcript_status"),
            "transcript_language": subtitle_data.get("transcript_language"),
            "manual_languages": subtitle_data.get("manual_languages", []),
            "auto_languages": subtitle_data.get("auto_languages", []),
            "transcript": transcript_text,
            "need_whisper": not bool(transcript_text and len(transcript_text.strip()) >= 100),

            "error": subtitle_data.get("error"),
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
            "like_count": "",
            "comment_count": "",
            "transcript_status": "error",
            "transcript_language": None,
            "manual_languages": [],
            "auto_languages": [],
            "transcript": "",
            "need_whisper": True,
            "error": str(e),
        }
