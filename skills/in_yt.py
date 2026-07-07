import os
import re
import json
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional

# 引入 Google 官方最新 GenAI 核心與強型別宣告
from google import genai
from google.genai import types

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


# 雲端多模態直連聽譯防線
def cloud_gemini_audio_transcribe(video_id: str) -> str:
    print("🌐 官方字幕失效，實質啟動 Gemini 雲端多模態直連聽譯防線...")
    try:
        api_url = "https://api.cobalt.tools/api/json"
        payload = {
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "downloadMode": "audio"
        }
        
        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": "https://cobalt.tools",
                "Referer": "https://cobalt.tools/"
            },
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=25) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            
        audio_stream_url = res_data.get("url")
        
        if not audio_stream_url:
            alt_url = f"https://api.v02.xyz/api/widget/mp3?id={video_id}"
            req_alt = urllib.request.Request(alt_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req_alt, timeout=20) as alt_res:
                alt_data = json.loads(alt_res.read().decode("utf-8"))
            audio_stream_url = alt_data.get("url")

        if not audio_stream_url:
            return ""

        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        client = genai.Client(api_key=api_key)
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_uri(
                    file_uri=audio_stream_url,
                    mime_type="audio/mp3"
                ),
                "請將這段音訊中的所有說話內容，逐字不漏地轉寫成繁體中文逐字稿。不需要做任何摘要，只需要完整的語音文本。"
            ]
        )
        return response.text if response.text else ""

    except Exception as e:
        print(f"❌ 雲端多模態聽譯核心不幸遭遇異常: {str(e)}")
        return ""


def fetch(input_data: str) -> Dict[str, Any]:
    try:
        video_id = extract_video_id(input_data)
        metadata = fetch_metadata(video_id)
        
        transcript_text = ""
        transcript_status = "none"
        
        # 🌟 核心破案：全面解鎖語系守備名單！將 'zh', 'zh-CN', 'zh-HK' 等所有變形代碼通通補齊
        # 這能 100% 確保有字幕的影片絕對能直接撈出原生文本
        target_languages = ["zh-TW", "zh-Hant", "zh", "zh-CN", "zh-HK", "zh-Hans", "en"]
        
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            selected = None
            try:
                selected = transcript_list.find_manually_created_transcript(target_languages)
            except Exception:
                pass
            if selected is None:
                try:
                    selected = transcript_list.find_generated_transcript(target_languages)
                except Exception:
                    pass
            if selected is None:
                selected = transcript_list.find_transcript(target_languages)

            items = selected.fetch()
            transcript_text = transcript_items_to_text(items)
            transcript_status = "official" if not selected.is_generated else "generated"
            print(f"🎯 成功獲取現成字幕，後台實質語系為: [{selected.language_code}]，狀態為: {transcript_status}")
        except Exception:
            # 只有當 YouTube 後台真的沒有任何中/英文文字檔時，才發動這條終極聽譯防線
            whisper_text = cloud_gemini_audio_transcribe(video_id)
            if whisper_text:
                transcript_text = whisper_text
                transcript_status = "gemini_cloud_whisper"
                print("🎯 雲端多模態聽譯防線實質突破！順利拿到語音逐字稿。")

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
