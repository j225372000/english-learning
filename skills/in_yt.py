import os
import re
import json
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)


def extract_video_id(input_data: str) -> str:
    text = input_data.strip()

    if re.fullmatch(r"[a-zA-Z0-9_-]{11}", text):
        return text

    parsed = urllib.parse.urlparse(text)

    if "youtube.com" in parsed.netloc:
        if parsed.path == "/watch":
            query = urllib.parse.parse_qs(parsed.query)
            video_id = query.get("v", [""])[0]
            if video_id:
                return video_id

        if parsed.path.startswith("/shorts/"):
            return parsed.path.split("/shorts/")[1].split("/")[0]

        if parsed.path.startswith("/embed/"):
            return parsed.path.split("/embed/")[1].split("/")[0]

    if "youtu.be" in parsed.netloc:
        return parsed.path.strip("/").split("/")[0]

    raise ValueError("無法解析 YouTube 影片 ID")


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
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(req, timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))

    if not data.get("items"):
        raise ValueError("找不到影片，可能是影片不存在、私人影片或地區限制")

    item = data["items"][0]
    snippet = item.get("snippet", {})
    statistics = item.get("statistics", {})
    content_details = item.get("contentDetails", {})

    thumbnails = snippet.get("thumbnails", {})
    thumbnail_url = ""

    if "maxres" in thumbnails:
        thumbnail_url = thumbnails["maxres"].get("url", "")
    elif "high" in thumbnails:
        thumbnail_url = thumbnails["high"].get("url", "")
    elif "medium" in thumbnails:
        thumbnail_url = thumbnails["medium"].get("url", "")
    elif "default" in thumbnails:
        thumbnail_url = thumbnails["default"].get("url", "")

    return {
        "title": snippet.get("title", ""),
        "description": snippet.get("description", ""),
        "channel": snippet.get("channelTitle", ""),
        "published_at": snippet.get("publishedAt", ""),
        "tags": snippet.get("tags", []),
        "category_id": snippet.get("categoryId", ""),
        "duration": content_details.get("duration", ""),
        "view_count": statistics.get("viewCount", ""),
        "like_count": statistics.get("likeCount", ""),
        "comment_count": statistics.get("commentCount", ""),
        "thumbnail_url": thumbnail_url,
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
        "linkedin",
        "tiktok",
        "discord",
        "patreon",
        "sponsor",
        "affiliate",
        "merch",
    ]

    lines = description.splitlines()
    cleaned_lines = []

    for line in lines:
        text = line.strip()

        if not text:
            continue

        lower = text.lower()

        if any(keyword in lower for keyword in remove_keywords):
            continue

        if text.startswith("http://") or text.startswith("https://"):
            continue

        cleaned_lines.append(text)

    return "\n".join(cleaned_lines)


def clean_transcript_text(text: str) -> str:
    if not text:
        return ""

    remove_patterns = [
        r"\[Music\]",
        r"\[Applause\]",
        r"\(music\)",
        r"\(applause\)",
        r"♪",
    ]

    for pattern in remove_patterns:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    text = re.sub(r"\s+", " ", text)
    return text.strip()


def transcript_items_to_text(items: List[Dict[str, Any]]) -> str:
    lines = []

    for item in items:
        text = item.get("text", "").replace("\n", " ").strip()

        if text:
            lines.append(text)

    return clean_transcript_text(" ".join(lines))


def fetch_transcript(video_id: str) -> Dict[str, Any]:
    preferred_languages = [
        "zh-TW",
        "zh-Hant",
        "en",
        "zh-CN",
        "ja",
    ]

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        available_transcripts = []

        for transcript in transcript_list:
            available_transcripts.append({
                "language": transcript.language,
                "language_code": transcript.language_code,
                "is_generated": transcript.is_generated,
            })

        selected = None

        try:
            selected = transcript_list.find_manually_created_transcript(preferred_languages)
        except Exception:
            pass

        if selected is None:
            try:
                selected = transcript_list.find_generated_transcript(preferred_languages)
            except Exception:
                pass

        if selected is None:
            selected = transcript_list.find_transcript(preferred_languages)

        items = selected.fetch()
        transcript_text = transcript_items_to_text(items)

        return {
            "transcript_status": "generated" if selected.is_generated else "official",
            "transcript_language": selected.language_code,
            "available_transcripts": available_transcripts,
            "transcript": transcript_text,
            "transcript_error": None,
        }

    except NoTranscriptFound:
        return {
            "transcript_status": "none",
            "transcript_language": None,
            "available_transcripts": [],
            "transcript": "",
            "transcript_error": "找不到可用字幕",
        }

    except TranscriptsDisabled:
        return {
            "transcript_status": "disabled",
            "transcript_language": None,
            "available_transcripts": [],
            "transcript": "",
            "transcript_error": "此影片已停用字幕",
        }

    except VideoUnavailable:
        return {
            "transcript_status": "video_unavailable",
            "transcript_language": None,
            "available_transcripts": [],
            "transcript": "",
            "transcript_error": "影片無法使用",
        }

    except Exception as e:
        return {
            "transcript_status": "error",
            "transcript_language": None,
            "available_transcripts": [],
            "transcript": "",
            "transcript_error": str(e),
        }


def fetch(input_data: str) -> Dict[str, Any]:
    try:
        video_id = extract_video_id(input_data)

        metadata = fetch_metadata(video_id)
        transcript_data = fetch_transcript(video_id)

        return {
            "success": True,
            "source": "youtube",
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",

            "title": metadata.get("title", ""),
            "channel": metadata.get("channel", ""),
            "published_at": metadata.get("published_at", ""),
            "description": metadata.get("description", ""),
            "clean_description": clean_description(metadata.get("description", "")),
            "duration": metadata.get("duration", ""),
            "view_count": metadata.get("view_count", ""),
            "like_count": metadata.get("like_count", ""),
            "comment_count": metadata.get("comment_count", ""),
            "tags": metadata.get("tags", []),
            "category_id": metadata.get("category_id", ""),
            "thumbnail_url": metadata.get("thumbnail_url", ""),

            "transcript_status": transcript_data.get("transcript_status"),
            "transcript_language": transcript_data.get("transcript_language"),
            "available_transcripts": transcript_data.get("available_transcripts"),
            "transcript": transcript_data.get("transcript"),
            "transcript_error": transcript_data.get("transcript_error"),

            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "source": "youtube",
            "video_id": None,
            "url": "",
            "title": "",
            "channel": "",
            "published_at": "",
            "description": "",
            "clean_description": "",
            "duration": "",
            "view_count": "",
            "like_count": "",
            "comment_count": "",
            "tags": [],
            "category_id": "",
            "thumbnail_url": "",
            "transcript_status": "error",
            "transcript_language": None,
            "available_transcripts": [],
            "transcript": "",
            "transcript_error": None,
            "error": str(e),
        }


if __name__ == "__main__":
    result = fetch("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    print(json.dumps(result, ensure_ascii=False, indent=2))
