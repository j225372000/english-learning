import os
import re
import json
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional
import subprocess

# 引入 Google 官方最新 GenAI 核心與型別宣告
from google import genai
from google.genai import types

from youtube_transcript_api import YouTubeTranscriptApi


def extract_video_id(input_data: str) -> str:
    """精準提取 11 位元 YouTube 影片 ID，支援帶有時間軸等雜質的網址"""
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
    return text


def fetch_metadata(video_id: str) -> Dict[str, Any]:
    """官方 API 憑證通道獲取元數據，百分之百穩定"""
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
        raise ValueError("找不到該影片，請確認影片 ID 是否正確")

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


# 🌟 【加固防線】使用本機已有的特製低頻寬指令抓取音訊，規避機房阻斷
def download_audio_safely(video_id: str, output_path: str) -> bool:
    try:
        print("📥 正在發動特種流式傳輸攔截純音訊軌...")
        # 🎯 利用 --extract-audio 配合外部 ffmpeg 強制壓縮成極小音訊，減少被 YouTube 伺服器偵測的機率
        cmd = [
            "yt-dlp", "-f", "ba", "-x", "--audio-format", "mp3", 
            "--audio-quality", "9", "--no-cache-dir",
            f"https://www.youtube.com/watch?v={video_id}", "-o", f"audio_{video_id}"
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(output_path):
            print("✨ 雲端音訊數據採集成功！")
            return True
    except Exception as e:
        print(f"⚠️ 流式音訊攔截失敗（可能遭遇封鎖）: {str(e)}")
    return False


def cloud_gemini_audio_transcribe(video_id: str) -> str:
    print("🎵 觸發語音轉寫防線，改由 Gemini 多模態核心進行大腦聽譯...")
    audio_path = f"audio_{video_id}.mp3"
    
    # 調用 Actions 安全下載
    if not download_audio_safely(video_id, audio_path):
        return ""
        
    try:
        print("🎙️ 音訊採集完成！正在讀取本地位元流並推送至 Gemini 語音辨識通道...")
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        client = genai.Client(api_key=api_key)
        
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
            
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(
                    data=audio_bytes,
                    mime_type="audio/mp3",
                ),
                "請將這段財經影片的語音內容，逐字不漏地轉寫成繁體中文逐字稿。不用做任何摘要，只需要完整的語音文本。"
            ]
        )
        
        if os.path.exists(audio_path):
            os.remove(audio_path)
            
        return response.text if response.text else ""
    except Exception as e:
        print(f"❌ Gemini 多模態語音轉譯核心異常: {str(e)}")
        if os.path.exists(audio_path):
            os.remove(audio_path)
        return ""


def fetch(input_data: str) -> Dict[str, Any]:
    try:
        video_id = extract_video_id(input_data)
        metadata = fetch_metadata(video_id)
        
        transcript_text = ""
        transcript_status = "none"
        
        # 語系守備名單擴充
        target_languages = ["zh-TW", "zh-Hant", "zh", "zh-CN", "zh-HK", "zh-Hans", "en"]
        
        # 🚂 軌道一：智慧撈取現成字幕 (官方/自動生成)
        try:
            print("📥 正在向 YouTube 後台拉取官方或自動生成字幕流...")
            # 🌟 使用已修正的正確 Class Method
            items = YouTubeTranscriptApi.get_transcript(video_id, languages=target_languages)
            transcript_text = transcript_items_to_text(items)
            transcript_status = "success_fetched"
            print(f"🎯 [智慧字幕成功] 順利秒讀 {len(transcript_text)} 字的原生文字！")
        except Exception:
            print("⚠️ 軌道一常規字幕不可用（可能遭遇 HTTP 429 限制或無字幕），自動啟動語音轉寫防線...")
            
            # 🚀 軌道二：智慧備援，改用 Gemini 代替本地 Whisper 聽音訊
            whisper_text = cloud_gemini_audio_transcribe(video_id)
            if whisper_text:
                transcript_text = whisper_text
                transcript_status = "gemini_cloud_whisper"
                print(f"🎯 [語音轉寫突破] 成功解鎖 {len(transcript_text)} 字的完整語音文本！")

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
