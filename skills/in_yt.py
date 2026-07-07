import os
import re
import json
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional

from youtube_transcript_api import YouTubeTranscriptApi


def extract_video_id(input_data: str) -> str:
    text = input_data.strip()
    if len(text) == 11 and re.fullmatch(r"[a-zA-Z0-9_-]{11}", text):
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
        if parsed.path.startswith("/live/"):
            return parsed.path.split("/live/")[1].split("/")[0]
    if "youtu.be" in parsed.netloc:
        return parsed.path.strip("/").split("/")[0]
    match = re.search(r"([a-zA-Z0-9_-]{11})", text)
    if match:
        return match.group(1)
    raise ValueError(f"無法解析 YouTube 影片 ID: '{input_data}'")


def fetch_metadata(video_id: str) -> Dict[str, Any]:
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("缺少環境變數 YOUTUBE_API_KEY")

    url = (
        "https://www.googleapis.com/youtube/v3/videos"
        "?part=snippet"
        f"&id={video_id}"
        f"&key={api_key}"
    )

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))

    if not data.get("items"):
        raise ValueError("找不到影片")

    item = data["items"][0]
    snippet = item.get("snippet", {})
    return {
        "title": snippet.get("title", ""),
        "description": snippet.get("description", ""),
    }


def clean_description(description: str) -> str:
    if not description:
        return ""
    remove_keywords = ["subscribe", "follow me", "instagram", "facebook", "twitter", "x.com"]
    lines = description.splitlines()
    cleaned_lines = []
    for line in lines:
        text = line.strip()
        if not text or any(k in text.lower() for k in remove_keywords) or text.startswith("http"):
            continue
        cleaned_lines.append(text)
    return "\n".join(cleaned_lines)


def clean_transcript_text(text: str) -> str:
    if not text:
        return ""
    remove_patterns = [r"\[Music\]", r"\[Applause\]", r"\(music\)", r"\(applause\)", r"♪"]
    for pattern in remove_patterns:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def transcript_items_to_text(items: List[Dict[str, Any]]) -> str:
    return clean_transcript_text(" ".join([item.get("text", "").replace("\n", " ").strip() for item in items]))


def fetch(input_data: str) -> Dict[str, Any]:
    try:
        video_id = extract_video_id(input_data)
        metadata = fetch_metadata(video_id)
        
        transcript_text = ""
        transcript_status = "none"
        
        # 🌟 語系守備名單全面擴充
        target_languages = ["zh-TW", "zh-Hant", "zh", "zh-CN", "zh-HK", "zh-Hans", "en"]
        
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # 1. 優先找手動創建的字幕
            try:
                selected = transcript_list.find_manually_created_transcript(target_languages)
                transcript_status = "official"
            except Exception:
                selected = None
                
            # 2. 🌟 如果沒有手動字幕，強制抓取自動生成的字幕（治本核心）
            if selected is None:
                try:
                    selected = transcript_list.find_generated_transcript(target_languages)
                    transcript_status = "generated"
                except Exception:
                    selected = None
            
            # 3. 最後防線：盲抓任何可用的目標語系字幕
            if selected is None:
                selected = transcript_list.find_transcript(target_languages)
                transcript_status = "fallback_found"

            items = selected.fetch()
            transcript_text = transcript_items_to_text(items)
            print(f"🎯 [現成字幕突破] 成功獲取文本，語系為: [{selected.language_code}]，來源類型: {transcript_status}")
            
        except Exception as transcript_err:
            print(f"⚠️ 無法從 YouTube 後台撈取到任何文本字幕檔案: {str(transcript_err)}")
            transcript_text = ""

        return {
            "success": True,
            "source": "youtube",
            "video_id": video_id,
            "title": metadata.get("title", ""),
            "description": metadata.get("description", ""),
            "clean_description": clean_description(metadata.get("description", "")),
            "transcript_status": transcript_status,
            "transcript": transcript_text,
            "error": None,
        }
    except Exception as e:
        return {"success": False, "source": "youtube", "transcript": "", "error": str(e)}
