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

# 🌟 實質引入語音解鎖與子程序執行所需的標準庫
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


# 🌟 核心防線：透過本地最新環境引導下載標準輕量音訊，交由 Gemini 進行原生多模態語音轉寫
def local_audio_whisper(video_id: str) -> str:
    print("🎵 官方字幕失效，實質啟動 Whisper 語音音訊攔截技術...")
    audio_filename = f"audio_{video_id}"
    audio_path = f"{audio_filename}.mp3"
    
    try:
        # 1. 使用優化後的標準輕量格式與無快取宣告下載，防禦 YouTube 的阻斷機制
        print("📥 正在從 YouTube 剝離並下載純音訊軌...")
        cmd_dl = [
            "yt-dlp",
            "-x", 
            "--audio-format", "mp3",
            "--audio-quality", "5",    # 標準可變位元率 (VBR)，降低流量特徵
            "--no-cache-dir",          # 徹底禁用快取，繞過重複請求偵測
            f"https://www.youtube.com/watch?v={video_id}",
            "-o", audio_filename
        ]
        
        # 實質呼叫終端機啟動下載
        subprocess.run(cmd_dl, check=True)
        
        if not os.path.exists(audio_path):
            raise FileNotFoundError("音訊下載失敗，虛擬機未成功產出 mp3 檔案")
            
        print("🎙️ 音訊擷取成功！正在使用 Gemini 多模態大腦進行精準語音轉文字辨識...")
        
        # 2. 連線 Gemini 大腦，直接將音訊檔案以 Audio 模態餵給 AI (免去額外 Whisper 伺服器部署成本)
        from google import genai
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        client = genai.Client(api_key=api_key)
        
        # 上傳音訊檔案到 Gemini 雲端暫存空間
        audio_file = client.files.upload(file=audio_path)
        
        # 使用 Flash 大腦高速解析
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                audio_file, 
                "請將這段財經影片的語音內容，逐字不漏地轉寫成繁體中文逐字稿。不用做任何摘要，只需要完整的語音文本。"
            ]
        )
        
        # 3. 實質清理本地與線上暫存，確保專案目錄與配額乾淨
        try:
            client.files.delete(name=audio_file.name)
            if os.path.exists(audio_path):
                os.remove(audio_path)
        except:
            pass
            
        return response.text if response.text else ""
        
    except Exception as e:
        print(f"❌ Whisper 語音防線不幸遭遇異常: {str(e)}")
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except:
                pass
        return ""


def fetch_transcript(video_id: str) -> Dict[str, Any]:
    preferred_languages = ["zh-TW", "zh-Hant", "en", "zh-CN"]
    try:
        # 🚂 第一防線：嘗試直接撈取官方提供或自動生成的現成文本字幕
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
        # 🚀 第二防線：官方完全撈不到了（例如新片上架），實質啟動上述 yt-dlp + Gemini 原生語音辨識
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
                "transcript_error": f"官方無字幕且 Whisper 語音攔截辨識宣告失敗: {str(e)}",
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
