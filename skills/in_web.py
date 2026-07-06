import urllib.request
import re

def fetch(url):
    """
    網頁輸入技能積木：抓取指定 URL 的網頁純文字，並自動剔除 HTML 標籤
    """
    if not url.startswith("http://") and not url.startswith("https://"):
        return "網址格式錯誤", f"輸入的資料似乎不是合法的網址: {url}"

    print(f"🌐 [Web 技能] 正在連線爬取網頁: {url}")
    try:
        # 使用與主程式相同的瀏覽器偽裝 Header，防止部分網站擋爬蟲
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        
        with urllib.request.urlopen(req, timeout=15) as response:
            # 讀取網頁原始碼並嘗試以 UTF-8 解碼
            html_content = response.read().decode('utf-8', errors='ignore')

        # 🧹 【核心清洗邏輯】：利用正規表示式暴力拔除非文字標籤
        # 1. 移除不必要的樣式表 <style>...</style> 與腳本 <script>...</script>
        html_content = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', html_content, flags=re.I)
        html_content = re.sub(r'<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>', '', html_content, flags=re.I)
        
        # 2. 移除所有的 HTML 標籤（例如 <div>, <a>, <p> 等）
        clean_text = re.sub(r'<[^>]+>', '', html_content)
        
        # 3. 壓縮多餘的連續換行與空白，讓文本更緊湊、省 Token
        clean_text = re.sub(r'\n\s*\n', '\n', clean_text)
        clean_text = clean_text.strip()

        # 4. 試圖抓取網頁標題作為 Metadata (找不到就用網址代替)
        title_match = re.search(r'<title>(.*?)</title>', html_content, flags=re.I)
        page_title = title_match.group(1).strip() if title_match else url

        return page_title, clean_text[:30000]  # 限制最大抓取字數，防止過大網頁塞爆

    except Exception as e:
        print(f"❌ Web 爬取技能異常: {str(e)}")
        return "網頁抓取失敗", f"在嘗試讀取該網頁時發生錯誤: {str(e)}"
