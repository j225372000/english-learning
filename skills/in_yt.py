import os
import re
import json
import html
import tempfile
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List


try:
    from youtube_transcript_api import YouTubeTranscriptApi
except Exception:
    YouTubeTranscriptApi = None


def extract_video_id(input_data: str) -> str:
    text = input_data.strip()

    if re.fullmatch(r"[a-zA-Z0-9_-]{11}", text):
        return text

    parsed = urllib.parse.urlparse(text)

    if "youtube.com" in parsed.netloc:
        if parsed.path == "/watch":
            return urllib.parse.parse_qs(parsed.query).get("v", [""])[0]
        if parsed.path.startswith("/shorts/"):
            return parsed.path.split("/shorts/")[1].split("/")[0]
        if parsed.path.startswith("/live/"):
            return parsed.path.split("/live/")[1].split("/")[0]

    if "youtu.be" in parsed.netloc:
        return parsed.path.strip("/").split("/")[0]

    match = re.search(r"v=([a-zA-Z0-9_-]{11})", text)
    if match:
        return match.group(1)

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
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))

    if not data.get("items"):
        raise ValueError("找不到該影片，可能是私人影片、刪除影片或地區限制。")

    item = data["items"][0]
    snippet = item.get("snippet", {})
    content_details = item.get("contentDetails", {})
    statistics = item.get("statistics", {})

    return {
        "title": snippet.get("title", ""),
        "description": snippet.get("description", ""),
        "channel": snippet.get("channelTitle", ""),
        "published_at": snippet.get("publishedAt", ""),
        "duration": content_details.get("duration", ""),
        "view_count": statistics.get("viewCount", ""),
    }


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = html.unescape(text)
    text = urllib.parse.unquote(text)
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_description(description: str) -> str:
    if not description:
        return ""

    remove_keywords = [
        "subscribe", "follow me", "instagram", "facebook",
        "twitter", "x.com", "discord", "patreon", "sponsor"
    ]

    lines = []

    for line in description.splitlines():
        t = line.strip()
        if not t:
            continue
        if t.startswith("http"):
            continue
        if any(k in t.lower() for k in remove_keywords):
            continue
        lines.append(t)

    return "\n".join(lines)


def fetch_transcript_api(video_id: str) -> Dict[str, Any]:
    """
    第一優先：youtube-transcript-api
    """
    if YouTubeTranscriptApi is None:
        return {
            "success": False,
            "transcript": "",
            "status": "api_not_installed",
            "language": None,
            "error": "youtube-transcript-api 未安裝",
        }

    preferred_languages = ["zh-TW", "zh-Hant", "zh", "en"]

    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)

        selected = None
        selected_status = None

        # 先找官方字幕
        for lang in preferred_languages:
            for t in transcript_list:
                if t.language_code == lang and not t.is_generated:
                    selected = t
                    selected_status = "official"
                    break
            if selected:
                break

        # 再找自動字幕
        if not selected:
            for lang in preferred_languages:
                for t in transcript_list:
                    if t.language_code == lang and t.is_generated:
                        selected = t
                        selected_status = "generated"
                        break
                if selected:
                    break

        # 還是沒有就拿第一個可用字幕
        if not selected:
            for t in transcript_list:
                selected = t
                selected_status = "generated" if t.is_generated else "official"
                break

        if not selected:
            return {
                "success": False,
                "transcript": "",
                "status": "none",
                "language": None,
                "error": "沒有可用字幕",
            }

        items = selected.fetch()

        parts = []
        for item in items:
            text = clean_text(item.get("text", ""))
            if text:
                parts.append(text)

        transcript = " ".join(parts).strip()

        return {
            "success": bool(transcript),
            "transcript": transcript,
            "status": selected_status,
            "language": selected.language_code,
            "error": None if transcript else "字幕內容為空",
        }

    except Exception as e:
        return {
            "success": False,
            "transcript": "",
            "status": "api_failed",
            "language": None,
            "error": str(e),
        }


def parse_vtt_file(path: Path) -> str:
    """
    清理 yt-dlp 抓下來的 .vtt 字幕
    """
    text = path.read_text(encoding="utf-8", errors="ignore")

    lines = []
    previous = ""

    for line in text.splitlines():
        line = line.strip()

        if not line:
            continue

        if line.startswith("WEBVTT"):
            continue

        if "-->" in line:
            continue

        if re.match(r"^\d+$", line):
            continue

        if line.startswith("Kind:") or line.startswith("Language:"):
            continue

        line = re.sub(r"<[^>]+>", "", line)
        line = clean_text(line)

        if not line:
            continue

        # 避免 VTT 重複字幕
        if line == previous:
            continue

        lines.append(line)
        previous = line

    return " ".join(lines).strip()


def fetch_transcript_ytdlp(video_id: str) -> Dict[str, Any]:
    """
    第二優先：yt-dlp 抓官方字幕 / 自動字幕
    這是參考 SubDown 的核心做法。
    """
    video_url = f"https://www.youtube.com/watch?v={video_id}"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        cmd = [
            "yt-dlp",
            "--skip-download",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs", "zh-Hant,zh-TW,zh,en",
            "--sub-format", "vtt",
            "-o", str(tmp_path / "%(id)s.%(ext)s"),
            video_url,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "transcript": "",
                    "status": "ytdlp_failed",
                    "language": None,
                    "error": result.stderr,
                }

            vtt_files = list(tmp_path.glob("*.vtt"))

            if not vtt_files:
                return {
                    "success": False,
                    "transcript": "",
                    "status": "ytdlp_no_subtitle",
                    "language": None,
                    "error": "yt-dlp 未產生字幕檔",
                }

            # 優先順序
            priority = ["zh-Hant", "zh-TW", "zh", "en"]

            selected_file = None

            for lang in priority:
                for file in vtt_files:
                    if lang.lower() in file.name.lower():
                        selected_file = file
                        break
                if selected_file:
                    break

            if not selected_file:
                selected_file = vtt_files[0]

            transcript = parse_vtt_file(selected_file)

            return {
                "success": bool(transcript),
                "transcript": transcript,
                "status": "ytdlp_success",
                "language": selected_file.name,
                "error": None if transcript else "字幕檔內容為空",
            }

        except Exception as e:
            return {
                "success": False,
                "transcript": "",
                "status": "ytdlp_error",
                "language": None,
                "error": str(e),
            }


def fetch(input_data: str) -> Dict[str, Any]:
    try:
        video_id = extract_video_id(input_data)
        metadata = fetch_metadata(video_id)

        print(f"🎬 YouTube 影片 ID：{video_id}")
        print(f"🎞️ 標題：{metadata.get('title', '')}")

        # 1. 先用 youtube-transcript-api
        transcript_result = fetch_transcript_api(video_id)

        if transcript_result["success"]:
            print(
                f"✅ youtube-transcript-api 成功："
                f"{transcript_result['status']} / {transcript_result['language']} / "
                f"{len(transcript_result['transcript'])} 字"
            )
        else:
            print(
                f"⚠️ youtube-transcript-api 失敗："
                f"{transcript_result['status']} / {transcript_result['error']}"
            )

            # 2. 再用 yt-dlp
            transcript_result = fetch_transcript_ytdlp(video_id)

            if transcript_result["success"]:
                print(
                    f"✅ yt-dlp 字幕抓取成功："
                    f"{transcript_result['language']} / "
                    f"{len(transcript_result['transcript'])} 字"
                )
            else:
                print(
                    f"⚠️ yt-dlp 也失敗："
                    f"{transcript_result['status']} / {transcript_result['error']}"
                )

        transcript = transcript_result.get("transcript", "")

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

            "transcript_status": transcript_result.get("status"),
            "transcript_language": transcript_result.get("language"),
            "transcript": transcript,
            "need_whisper": not bool(transcript and len(transcript.strip()) >= 100),
            "error": transcript_result.get("error"),
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
            "transcript_status": "error",
            "transcript_language": None,
            "transcript": "",
            "need_whisper": True,
            "error": str(e),
        }
