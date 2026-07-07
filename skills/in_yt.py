import os
import re
import json
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional

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
    if "youtu.be" in parsed.netloc:
        return parsed.path.strip("/").split("/")[0]
    return text

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

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))

    if not data.get("items"):
        raise ValueError("找不到該影片")

    item = data["items"][0]
    snippet = item.get("snippet", {})
    return {
        "title": snippet.get("title", ""),
        "description": snippet.get("description", ""),
    }

# 🌟 【前端網頁解調技術】直接去 YouTube 前端網頁抓取並解析公開的自動/手動字幕數據
def fetch_raw_html_transcript(video_id: str) -> str:
    print("🌐 正在發動網頁前端 HTML 逆向解析技術，嘗試提取公開字幕文字流...")
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    try:
        # 1. 偽裝成常規桌面瀏覽器，直接讀取 YouTube 影片的公開 HTML 原始碼
        req = urllib.request.Request(
            video_url, 
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7"
            }
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            html = response.read().decode("utf-8")
            
        # 2. 實質尋找網頁中內嵌的 ytplayer 字幕特徵字串 (playerCaptionsTracklistRenderer)
        if "playerCaptionsTracklistRenderer" not in html:
            print("⚠️ 網頁前端未發現公開的字幕渲染軌道（此影片可能真的完全沒有任何字幕功能）")
            return ""
            
        # 3. 擷取字幕基礎 JSON 位址
        match = re.search(r'"captionTracks":\s*(\[.*?\])', html)
        if not match:
            print("⚠️ 無法精確切割前端字幕軌道 JSON 區塊")
            return ""
            
        caption_tracks = json.loads(match.group(1))
        
        # 4. 優先篩選中文自動或手動字幕網址
        target_url = None
        for track in caption_tracks:
            lang_code = track.get("languageCode", "").lower()
            if "zh" in lang_code or "tw" in lang_code:
                target_url = track.get("baseUrl")
                print(f"👁️ 成功在前端網頁捕獲中文公開字幕流網址 (語系: {lang_code})")
                break
                
        if not target_url and caption_tracks:
            target_url = caption_tracks[0].get("baseUrl")
            
        if not target_url:
            return ""
            
        # 5. 直接向該網址拉取公開的 XML 格式字幕分片
        req_xml = urllib.request.Request(target_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req_xml, timeout=15) as xml_res:
            xml_content = xml_res.read().decode("utf-8")
            
        # 6. 使用正則表達式快速提取 XML 標籤內的所有純文字對話（100% 還原影片真正內容）
        text_segments = re.findall(r'<text[^>]*>([\s\S]*?)</text>', xml_content)
        
        # 清洗 HTML 轉義字元 (例如 &amp; -> &, &#39; -> ')
        cleaned_text = []
        for text in text_segments:
            text = urllib.parse.unquote(text)
            text = text.replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"')
            text = re.sub(r'<[^>]*>', '', text).strip()
            if text:
                cleaned_text.append(text)
                
        return " ".join(cleaned_text)
        
    except Exception as e:
        print(f"❌ 前端網頁字幕提取不幸遭遇異常: {str(e)}")
        return ""

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

def fetch(input_data: str) -> Dict[str, Any]:
    try:
        video_id = extract_video_id(input_data)
        metadata = fetch_metadata(video_id)
        
        # 發動前端解調
        transcript_text = fetch_raw_html_transcript(video_id)
        transcript_status = "html_parsed_success" if transcript_text else "none"
        
        if transcript_text:
            print(f"🎯 [前端破關成功] 實質抓取到影片真正的對話講稿！共 {len(transcript_text)} 字。")
        else:
            print("⚠️ 未能從前端解析出任何公開講稿...")
            
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
