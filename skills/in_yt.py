import os
import re
import json
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional
import subprocess

# 引入 Google 官方最新 GenAI 模態庫
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
        "?part=snippet,contentDetails,statistics"
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


# 🌟 全新升級：整合本地端與工業級 Cobalt 萬用解鎖閘道的音訊下載核心
def download_audio_fallback(video_id: str, output_path: str) -> bool:
    # ─── 軌道 A：本地 yt-dlp 衝鋒 ───
    try:
        print("📥 [軌道 A] 正在嘗試使用本機最新 yt-dlp 原始鏈接解鎖音訊...")
        cmd_dl = [
            "yt-dlp", "-x", "--audio-format", "mp3", "--audio-quality", "5", "--no-cache-dir",
            f"https://www.youtube.com/watch?v={video_id}", "-o", f"audio_{video_id}"
        ]
        subprocess.run(cmd_dl, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(output_path):
            print("✨ [軌道 A] yt-dlp 順利突圍下載成功！")
            return True
    except Exception:
        print("⚠️ [軌道 A] GitHub Actions 機房 IP 遭到 YouTube 風控限制，立刻觸發軌道 B 後備防禦...")

    # ─── 軌道 B：切換 2026 工業級免鎖 IP 的 Cobalt 全球網路閘道 ───
    try:
        print("🌐 [軌道 B] 正在向 Cobalt 萬能智能體解鎖網關發送音訊提取請求...")
        api_url = "https://api.cobalt.tools/"
        
        # 構建符合 Cobalt API 規範的標準 JSON 請求體
        payload = {
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "downloadMode": "audio",
            "audioFormat": "mp3",
            "audioBitrate": "128"
        }
        
        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=25) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            
        # Cobalt 成功破防後會直接吐出高速直連的純 mp3 下載位址
        download_url = res_data.get("url")
        if download_url:
            print("🚀 外部 Cobalt 網關成功突圍！正在以高速通道拉取音訊字節流...")
            req_file = urllib.request.Request(download_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req_file, timeout=40) as file_res:
                with open(output_path, "wb") as f:
                    f.write(file_res.read())
                    
            if os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
                print("✨ [軌道 B] 外部解鎖通道下載完畢！音訊檔案已成功躺在虛擬機環境中。")
                return True
    except Exception as err:
        print(f"❌ [軌道 B] 外部解鎖網關遭遇異常: {str(err)}")

    return False


def local_audio_whisper(video_id: str) -> str:
    audio_path = f"audio_{video_id}.mp3"
    
    download_success = download_audio_fallback(video_id, audio_path)
    if not download_success:
        print("🚨 [終極警報] 雙軌音訊下載均遭封鎖，此影片暫時無法開啟語音轉寫防線。")
        return ""
        
    try:
        print("🎙️ 音訊本地解鎖成功！正在調用 Gemini 官方標準位元流協議...")
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        client = genai.Client(api_key=api_key)
        
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
            
        print("🧠 正在將音訊直接推播至 Gemini 多模態語音解析核心...")
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
        print(f"❌ Gemini 多模態語音模態轉譯遭遇異常: {str(e)}")
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except:
                pass
        return ""


def fetch(input_data: str) -> Dict[str, Any]:
    try:
        video_id = extract_video_id(input_data)
        metadata = fetch_metadata(video_id)
        
        transcript_text = ""
        transcript_status = "none"
        
        # 🚂 優先嘗試常規手段：撈取官方提供或自動生成的現成文本字幕
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            selected = None
            try:
                selected = transcript_list.find_manually_created_transcript(["zh-TW", "zh-Hant", "en"])
            except Exception:
                pass
            if selected is None:
                try:
                    selected = transcript_list.find_generated_transcript(["zh-TW", "zh-Hant", "en"])
                except Exception:
                    pass
            if selected is None:
                selected = transcript_list.find_transcript(["zh-TW", "zh-Hant", "en"])

            items = selected.fetch()
            transcript_text = transcript_items_to_text(items)
            transcript_status = "official" if not selected.is_generated else "generated"
            print(f"🎯 成功獲取現成字幕，狀態為: {transcript_status}")
        except Exception:
            # 🚀 官方完全撈不到字幕（例如你截圖中這支美股上太空的新片），立刻實質發動雙軌語音防線
            whisper_text = local_audio_whisper(video_id)
            if whisper_text:
                transcript_text = whisper_text
                transcript_status = "whisper_fallback"
                print("🎯 雙軌語音防線實質突破！順利拿到語音逐字稿。")

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
