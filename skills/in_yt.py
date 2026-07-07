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


def make_base_opts() -> Dict[str, Any]:
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
                "player_client": ["android", "web"]
            }
        },
    }


def build_language_candidates(
    caption_info: Dict[str, Any],
    preferred_langs: List[str]
) -> List[Dict[str, str]]:
    manual_languages = caption_info.get("manual_languages", [])
    auto_languages = caption_info.get("auto_languages", [])

    candidates = []
    used = set()

    def add_candidate(subtitle_type: str, language: str):
        key = f"{subtitle_type}:{language}"
        if language and key not in used:
            candidates.append({
                "subtitle_type": subtitle_type,
                "language": language,
            })
            used.add(key)

    def find_exact(available: List[str], target: str) -> Optional[str]:
        target_lower = target.lower()
        for lang in available:
            if lang.lower() == target_lower:
                return lang
        return None

    def find_related(available: List[str], target: str) -> List[str]:
        target_lower = target.lower()
        related = []

        if target_lower == "en":
            for lang in available:
                lang_lower = lang.lower()
                if lang_lower in ["en-orig", "en", "en-us", "en-gb"]:
                    related.append(lang)

        elif target_lower.startswith("zh"):
            for lang in available:
                lang_lower = lang.lower()
                if lang_lower.startswith("zh"):
                    related.append(lang)

        return related

    # 1. 先按照 preferred_langs 找手動字幕
    for target in preferred_langs:
        exact = find_exact(manual_languages, target)
        if exact:
            add_candidate("manual", exact)

    # 2. 再按照 preferred_langs 找自動字幕
    for target in preferred_langs:
        exact = find_exact(auto_languages, target)
        if exact:
            add_candidate("auto", exact)

    # 3. 如果 preferred_langs 是 en，但實際只有 en-orig，也補上
    for target in preferred_langs:
        for lang in find_related(manual_languages, target):
            add_candidate("manual", lang)

        for lang in find_related(auto_languages, target):
            add_candidate("auto", lang)

    # 4. 最後補上其他手動字幕、自動字幕，避免完全沒候選
    for lang in manual_languages:
        add_candidate("manual", lang)

    for lang in auto_languages:
        add_candidate("auto", lang)

    return candidates


def download_one_subtitle(
    url: str,
    language: str,
    subtitle_type: str,
    base_opts: Dict[str, Any]
) -> Dict[str, Any]:
    remove_temp_subtitle_files()

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
                "subtitle_file": None,
                "error": "未找到下載後的字幕檔",
            }

        with open(subtitle_file, "r", encoding="utf-8", errors="ignore") as f:
            raw_text = f.read()

        transcript_text = clean_subtitle_text(raw_text)

        if not transcript_text or len(transcript_text.strip()) < 100:
            return {
                "success": False,
                "transcript": transcript_text,
                "subtitle_file": subtitle_file,
                "error": "字幕內容為空或過短",
            }

        return {
            "success": True,
            "transcript": transcript_text,
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
        remove_temp_subtitle_files()


def download_subtitle_by_ytdlp(url: str, langs: List[str]) -> Dict[str, Any]:
    remove_temp_subtitle_files()
    base_opts = make_base_opts()

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

        candidates = build_language_candidates(caption_info, langs)

        if not candidates:
            return {
                "success": False,
                "transcript": "",
                "transcript_status": "no_candidate_subtitles",
                "transcript_language": None,
                "manual_languages": caption_info["manual_languages"],
                "auto_languages": caption_info["auto_languages"],
                "error": "有字幕清單，但無可下載候選字幕",
            }

        print("🎯 字幕下載候選順序：")
        for item in candidates[:10]:
            print(f"   - {item['subtitle_type']} / {item['language']}")

        errors = []

        for candidate in candidates:
            subtitle_type = candidate["subtitle_type"]
            language = candidate["language"]

            result = download_one_subtitle(
                url=url,
                language=language,
                subtitle_type=subtitle_type,
                base_opts=base_opts,
            )

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

            error_msg = result.get("error", "unknown error")
            errors.append(f"{subtitle_type}/{language}: {error_msg}")
            print(f"⚠️ 下載失敗，改試下一個字幕：{subtitle_type} / {language}")

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
