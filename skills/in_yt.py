import os
import re
import json
import html
import urllib.request
import urllib.parse
from typing import Dict, Any, List


try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import (
        NoTranscriptFound,
        TranscriptsDisabled,
        VideoUnavailable,
    )
except Exception:
    YouTubeTranscriptApi = None
    NoTranscriptFound = Exception
    TranscriptsDisabled = Exception
    VideoUnavailable = Exception


def extract_video_id(input_data: str) -> str:
    text = input_data.strip()

    if len(text) == 11 and re.fullmatch(r"[a-zA-Z0-9_-]{11}", text):
        return text

    if "v=" in text:
        match = re.search(r"v=([a-zA-Z0-9_-]{11})", text)
        if match:
            return match.group(1)

    parsed = urllib.parse.urlparse(text)

    if "youtube.com" in parsed.netloc:
        if parsed.path == "/watch":
            query = urllib.parse.parse_qs(parsed.query)
            video_id = query.get("v", [""])[0]
            if video_id:
                return video_id

        if parsed.path.startswith("/shorts/"):
            return parsed.path.split("/shorts/")[1].split("/")[0]

        if parsed.path.startswith("/live/"):
            return parsed.path.split("/live/")[1].split("/")[0]

    if "youtu.be" in parsed.netloc:
        return parsed.path.strip("/").split("/")[0]

    return text


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

    lines = description.splitlines()
    cleaned_lines = []

    for line in lines:
        text = line.strip()

        if not text:
            continue

        lower_text = text.lower()

        if any(k in lower_text for k in remove_keywords):
            continue

        if text.startswith("http"):
            continue

        cleaned_lines.append(text)

    return "\n".join(cleaned_lines)


def clean_transcript_text(text: str) -> str:
    if not text:
        return ""

    text = html.unescape(text)
    text = urllib.parse.unquote(text)
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def merge_transcript_items(items: List[Dict[str, Any]]) -> str:
    lines = []

    for item in items:
        text = item.get("text", "")
        text = clean_transcript_text(text)

        if text:
            lines.append(text)

    return " ".join(lines).strip()


def fetch_transcript_by_api(video_id: str) -> Dict[str, Any]:
    """
    優先使用 youtube-transcript-api。
    判斷官方字幕 / 自動字幕。
    """
    if YouTubeTranscriptApi is None:
        return {
            "success": False,
            "transcript": "",
            "transcript_status": "api_not_installed",
            "transcript_language": None,
            "official_languages": [],
            "generated_languages": [],
            "error": "尚未安裝 youtube-transcript-api",
        }

    preferred_languages = ["zh-TW", "zh-Hant", "zh", "en", "ja"]

    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)

        official_languages = []
        generated_languages = []

        for transcript in transcript_list:
            if transcript.is_generated:
                generated_languages.append(transcript.language_code)
            else:
                official_languages.append(transcript.language_code)

        selected = None
        selected_status = None

        for lang in preferred_languages:
            for transcript in transcript_list:
                if transcript.language_code == lang and not transcript.is_generated:
                    selected = transcript
                    selected_status = "official"
                    break
            if selected:
                break

        if not selected:
            for lang in preferred_languages:
                for transcript in transcript_list:
                    if transcript.language_code == lang and transcript.is_generated:
                        selected = transcript
                        selected_status = "generated"
                        break
                if selected:
                    break

        if not selected:
            for transcript in transcript_list:
                selected = transcript
                selected_status = "generated" if transcript.is_generated else "official"
                break

        if not selected:
            return {
                "success": False,
                "transcript": "",
                "transcript_status": "none",
                "transcript_language": None,
                "official_languages": official_languages,
                "generated_languages": generated_languages,
                "error": "找不到可用字幕",
            }

        items = selected.fetch()
        transcript_text = merge_transcript_items(items)

        if not transcript_text:
            return {
                "success": False,
                "transcript": "",
                "transcript_status": "empty",
                "transcript_language": selected.language_code,
                "official_languages": official_languages,
                "generated_languages": generated_languages,
                "error": "字幕內容為空",
            }

        return {
            "success": True,
            "transcript": transcript_text,
            "transcript_status": selected_status,
            "transcript_language": selected.language_code,
            "official_languages": official_languages,
            "generated_languages": generated_languages,
            "error": None,
        }

    except NoTranscriptFound:
        return {
            "success": False,
            "transcript": "",
            "transcript_status": "none",
            "transcript_language": None,
            "official_languages": [],
            "generated_languages": [],
            "error": "找不到字幕",
        }

    except TranscriptsDisabled:
        return {
            "success": False,
            "transcript": "",
            "transcript_status": "disabled",
            "transcript_language": None,
            "official_languages": [],
            "generated_languages": [],
            "error": "此影片停用字幕",
        }

    except VideoUnavailable:
        return {
            "success": False,
            "transcript": "",
            "transcript_status": "video_unavailable",
            "transcript_language": None,
            "official_languages": [],
            "generated_languages": [],
            "error": "影片無法使用",
        }

    except Exception as e:
        return {
            "success": False,
            "transcript": "",
            "transcript_status": "api_error",
            "transcript_language": None,
            "official_languages": [],
            "generated_languages": [],
            "error": str(e),
        }


def fetch_raw_html_transcript(video_id: str) -> Dict[str, Any]:
    """
    備援：直接解析 YouTube 前端 HTML 中公開字幕。
    不建議當主力，但可作為 youtube-transcript-api 失敗後的備援。
    """
    print("🌐 youtube-transcript-api 未成功，改用 HTML 字幕解析備援...")

    video_url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        req = urllib.request.Request(
            video_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )

        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read()
            html_text = raw.decode("utf-8", errors="ignore")

        if "playerCaptionsTracklistRenderer" not in html_text:
            return {
                "success": False,
                "transcript": "",
                "transcript_status": "html_no_caption_renderer",
                "transcript_language": None,
                "error": "HTML 中未發現字幕渲染軌道",
            }

        match = re.search(r'"captionTracks":\s*(\[.*?\])', html_text)

        if not match:
            return {
                "success": False,
                "transcript": "",
                "transcript_status": "html_no_caption_tracks",
                "transcript_language": None,
                "error": "無法切割 captionTracks",
            }

        caption_tracks = json.loads(match.group(1))

        target_track = None

        for track in caption_tracks:
            lang_code = track.get("languageCode", "").lower()
            if lang_code in ["zh-tw", "zh-hant", "zh"]:
                target_track = track
                break

        if not target_track:
            for track in caption_tracks:
                lang_code = track.get("languageCode", "").lower()
                if lang_code == "en":
                    target_track = track
                    break

        if not target_track and caption_tracks:
            target_track = caption_tracks[0]

        if not target_track:
            return {
                "success": False,
                "transcript": "",
                "transcript_status": "html_no_target_track",
                "transcript_language": None,
                "error": "沒有可用字幕軌",
            }

        target_url = target_track.get("baseUrl")
        target_lang = target_track.get("languageCode")

        if not target_url:
            return {
                "success": False,
                "transcript": "",
                "transcript_status": "html_no_base_url",
                "transcript_language": target_lang,
                "error": "字幕軌沒有 baseUrl",
            }

        req_xml = urllib.request.Request(
            target_url,
            headers={"User-Agent": "Mozilla/5.0"},
        )

        with urllib.request.urlopen(req_xml, timeout=15) as xml_res:
            xml_content = xml_res.read().decode("utf-8", errors="ignore")

        text_segments = re.findall(r"<text[^>]*>([\s\S]*?)</text>", xml_content)

        cleaned_text = []

        for segment in text_segments:
            text = clean_transcript_text(segment)
            text = re.sub(r"<[^>]*>", "", text).strip()

            if text:
                cleaned_text.append(text)

        transcript_text = " ".join(cleaned_text).strip()

        if not transcript_text:
            return {
                "success": False,
                "transcript": "",
                "transcript_status": "html_empty",
                "transcript_language": target_lang,
                "error": "HTML 字幕內容為空",
            }

        return {
            "success": True,
            "transcript": transcript_text,
            "transcript_status": "html_parsed_success",
            "transcript_language": target_lang,
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "transcript": "",
            "transcript_status": "html_error",
            "transcript_language": None,
            "error": str(e),
        }


def fetch(input_data: str) -> Dict[str, Any]:
    try:
        video_id = extract_video_id(input_data)
        metadata = fetch_metadata(video_id)

        print(f"🎬 YouTube 影片 ID：{video_id}")
        print(f"🎞️ 標題：{metadata.get('title', '')}")

        transcript_data = fetch_transcript_by_api(video_id)

        if transcript_data.get("success"):
            print(
                f"✅ 字幕抓取成功：{transcript_data.get('transcript_status')} "
                f"({transcript_data.get('transcript_language')})，"
                f"共 {len(transcript_data.get('transcript', ''))} 字。"
            )

        else:
            print(f"⚠️ youtube-transcript-api 失敗：{transcript_data.get('transcript_status')} / {transcript_data.get('error')}")

            html_data = fetch_raw_html_transcript(video_id)

            if html_data.get("success"):
                transcript_data = {
                    "success": True,
                    "transcript": html_data.get("transcript", ""),
                    "transcript_status": html_data.get("transcript_status"),
                    "transcript_language": html_data.get("transcript_language"),
                    "official_languages": transcript_data.get("official_languages", []),
                    "generated_languages": transcript_data.get("generated_languages", []),
                    "error": None,
                }

                print(
                    f"✅ HTML 備援字幕成功："
                    f"{transcript_data.get('transcript_language')}，"
                    f"共 {len(transcript_data.get('transcript', ''))} 字。"
                )

            else:
                transcript_data = {
                    "success": False,
                    "transcript": "",
                    "transcript_status": "none",
                    "transcript_language": None,
                    "official_languages": transcript_data.get("official_languages", []),
                    "generated_languages": transcript_data.get("generated_languages", []),
                    "error": html_data.get("error"),
                }

                print("⚠️ 所有字幕抓取方式都失敗，建議後續啟動 Whisper。")

        transcript_text = transcript_data.get("transcript", "")

        return {
            "success": True,
            "source": "youtube",
            "video_id": video_id,

            "title": metadata.get("title", ""),
            "description": metadata.get("description", ""),
            "clean_description": clean_description(metadata.get("description", "")),
            "channel": metadata.get("channel", ""),
            "published_at": metadata.get("published_at", ""),
            "duration": metadata.get("duration", ""),
            "view_count": metadata.get("view_count", ""),
            "like_count": metadata.get("like_count", ""),
            "comment_count": metadata.get("comment_count", ""),

            "transcript_status": transcript_data.get("transcript_status"),
            "transcript_language": transcript_data.get("transcript_language"),
            "official_languages": transcript_data.get("official_languages", []),
            "generated_languages": transcript_data.get("generated_languages", []),
            "transcript": transcript_text,
            "need_whisper": not bool(transcript_text and len(transcript_text.strip()) >= 100),

            "error": transcript_data.get("error"),
        }

    except Exception as e:
        return {
            "success": False,
            "source": "youtube",
            "video_id": None,
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
            "official_languages": [],
            "generated_languages": [],
            "transcript": "",
            "need_whisper": True,
            "error": str(e),
        }
