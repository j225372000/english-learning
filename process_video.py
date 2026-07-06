import os
import urllib.request
import urllib.error
import json
from google import genai

def get_video_data_via_official_api(video_id, api_key):
    # 🌟 實質檢查：清除所有隱藏的換行或空白字元
    clean_id = video_id.strip().replace('\r', '').replace('\n', '')
    clean_key = api_key.strip().replace('\r', '').replace('\n', '') if api_key else ""
    
    # 拼接網址
    url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={clean_id}&key={clean_key}"
    
    # 在控制台印出安全屏蔽後的網址，用來檢查有沒有奇怪的斷行
    masked_key = clean_key[:6] + "..." if len(clean_key) > 6 else "None"
    print(f"🔍 [實質檢查 1] 實際發送的網址結構為: https://www.googleapis.com/youtube/v3/videos?part=snippet&id={clean_id}&key={masked_key}")
    print(f"🔍 [實質檢查 2] 影片 ID 長度: {len(clean_id)} 碼 (正常應為 11 碼)")
    print(f"🔍 [實質檢查 3] API 金鑰是否存在: {'是' if clean_key else '否 (None)'}")

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
        return "成功", "成功"
    except urllib.error.HTTPError as e:
        # 🚨 實質檢查 4：把 YouTube 伺服器回傳的真實錯誤 Body 全部倒出來
        error_body = e.read().decode('utf-8')
        print(f"\n❌ [實質檢查 4] YouTube 伺服器無情回報真實 Error 代碼: {e.code}")
        print("====== YouTube 官方給出的底層大實話 JSON 開始 ======")
        try:
            parsed_error = json.loads(error_body)
            print(json.dumps(parsed_error, indent=2, ensure_ascii=False))
        except:
            print(error_body)
        print("====== YouTube 官方給出的底層大實話 JSON 結束 ======\n")
        return None, None
    except Exception as e:
        print(f"❌ 系統非預期異常: {str(e)}")
        return None, None

def main():
    video_id = os.environ.get("VIDEO_ID", "").strip()
    prompt_type = os.environ.get("VIDEO_TYPE", "general").strip().lower()
    yt_api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    
    print(f"🚀 啟動實質診斷模式...")
    get_video_data_via_official_api(video_id, yt_api_key)

if __name__ == "__main__":
    main()
