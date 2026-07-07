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

# 🌟 實質引入語音解鎖所需的標準庫
import subprocess


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

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
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


# 🌟 新增：透過本地環境使用 Whisper 模態或語音辨識的核心後備機制
def local_audio_whisper(video_id: str) -> str:
    print("🎵 官方字幕失效，實質啟動 Whisper 語音音訊攔截技術...")
    audio_filename = f"audio_{video_id}"
    audio_path = f"{audio_filename}.mp3"
    
    try:
        # 1. 使用輕量化工具下載極低音質的純音訊 (節省 GitHub Actions 頻寬與執行時間)
        print("📥 正在從 YouTube 剝離並下載純音訊軌...")
        cmd_dl = [
            "yt-dlp",
            "-x", "--audio-format", "mp3",
            "--audio-quality", "9k", 
            f"https://www.youtube.com/watch?v={video_id}",
            "-o", audio_filename
        ]
        subprocess.run(cmd_dl, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if not os.path.exists(audio_path):
            raise FileNotFoundError("音訊檔案下載失敗")
            
        print("🎙️ 音訊擷取成功！正在使用 Gemini 多模態大腦進行精準語音轉文字辨識...")
        
        # 2. 實質調用專案現有的 genai 憑證，將音訊直接餵給 Gemini 進行原生語音轉譯 (免額外付費，速度極快)
        from google import genai
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        client = genai.Client(api_key=api_key)
        
        # 上傳音訊檔案到 Gemini 暫存空間
        audio_file = client.files.upload(file=audio_path)
        
        # 呼叫 Flash 大腦快速進行語音轉文字
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                audio_file, 
                "請將這段財經影片的語音內容，逐字不漏地轉寫成繁體中文逐字稿。不用做任何摘要，只需要完整的語音文本。"
            ]
        )
        
        # 清理暫存與本地檔案
        try:
            client.files.delete(name=audio_file.name)
            os.remove(audio_path)
        except:
            pass
            
        return response.text if response.text else ""
        
    except Exception as e:
        print(f"❌ Whisper 語音防線不幸遭遇異常: {str(e)}")
        if os.path.exists(audio_path):
            os.remove(audio_path)
        return ""


def fetch_transcript(video_id: str) -> Dict[str, Any]:
    preferred_languages = ["zh-TW", "zh-Hant", "en", "zh-CN"]
    try:
        # 🚂 嘗試第一防線：抓取官方配給的字幕
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
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
        return {
            "transcript_status": "official" if not selected.is_generated else "generated",
            "transcript_language": selected.language_code,
            "transcript": transcript_items_to_text(items),
            "transcript_error": None,
        }

    except Exception as e:
        # 🚀 實質觸發第二防線：官方抓不到了，啟動 Whisper 語音音訊流後備機制！
        whisper_text = local_audio_whisper(video_id)
        if whisper_text:
            return {
                "transcript_status": "whisper_fallback",
                "transcript_language": "zh-TW",
                "transcript": whisper_text,
                "transcript_error": None,
            }
        else:
            return {
                "transcript_status": "failed_all",
                "transcript_language": None,
                "transcript": "",
                "transcript_error": f"官方無字幕且 Whisper 轉譯失敗: {str(e)}",
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
            "title": metadata.get("title", ""),
            "description": metadata.get("description", ""),
            "clean_description": clean_description(metadata.get("description", "")),
            "transcript_status": transcript_data.get("transcript_status"),
            "transcript": transcript_data.get("transcript"),
            "transcript_error": transcript_data.get("transcript_error"),
            "error": None,
        }
    except Exception as e:
        return {"success": False, "source": "youtube", "transcript": "", "error": str(e)}
