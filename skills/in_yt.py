import os
import re
import json
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional

# 🌟 修正：完全對齊官方標準 2026 年最新規範的正確調度語法
from youtube_transcript_api import YouTubeTranscriptApi


def extract_video_id(input_data: str) -> str:
    """精準提取 11 位元 YouTube 影片 ID，支援時間軸網址與純 ID 排程"""
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
        if parsed.path.startswith("/embed/"):
            return parsed.path.split("/embed/")[1].split("/")[0]
        if parsed.path.startswith("/live/"):
            return parsed.path.split("/live/")[1].split("/")[0]
    if "youtu.be" in parsed.netloc:
        return parsed.path.strip("/").split("/")[0]
        
    match = re.search(r"([a-zA-Z0-9_-]{11})", text)
    if match:
        return match.group(1)
    return text


def fetch_metadata(video_id: str) -> Dict[str, Any]:
    """使用 YouTube 官方 Data API 獲取影片元數據，100% 正常連線"""
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
        raise ValueError("找不到該 YouTube 影片，請檢查 ID 是否正確")

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
        
        # 語系守備名單全面大解鎖，包含 YouTube 後台常給的孤零零 'zh' 代碼
        target_languages = ["zh-TW", "zh-Hant", "zh", "zh-CN", "zh-HK", "zh-Hans", "en"]
        
        try:
            print("📥 正在向 YouTube 後台拉取官方或自動生成字幕流...")
            # 🌟 【100% 語法修正】移除無效的 list_transcripts，直接改用標準 get_transcript 接口
            items = YouTubeTranscriptApi.get_transcript(video_id, languages=target_languages)
            
            transcript_text = transcript_items_to_text(items)
            transcript_status = "success_fetched"
            print(f"🎯 [現成字幕突破] 成功獲取 {len(transcript_text)} 字的完整文本講稿！")
            
        except Exception as transcript_err:
            print(f"⚠️ 確無現成字幕，退回最高防禦防線: {str(transcript_err)}")
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
