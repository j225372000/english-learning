import os
import tempfile
import urllib.request
import urllib.parse

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None


def is_url(input_data: str) -> bool:
    return input_data.startswith("http://") or input_data.startswith("https://")


def get_filename_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    filename = os.path.basename(parsed.path)

    if not filename:
        filename = "downloaded.pdf"

    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    return filename


def download_pdf(url: str) -> str:
    """
    下載遠端 PDF 到暫存檔，回傳本機暫存路徑。
    """
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/pdf,text/html,*/*",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        data = response.read()

    if not data:
        raise ValueError("下載到的 PDF 檔案為空")

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp_file.write(data)
    temp_file.close()

    return temp_file.name


def extract_pdf_text(file_path: str) -> str:
    """
    從 PDF 擷取文字。
    """
    reader = PdfReader(file_path)

    text_parts = []

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text_parts.append(page_text)

    text = "\n".join(text_parts).strip()

    return text


def fetch(input_data):
    """
    PDF 輸入技能積木。

    支援：
    1. 本機 PDF 路徑
    2. 遠端 PDF URL
    """

    if not PdfReader:
        return "錯誤", "未安裝 pypdf 庫"

    temp_pdf_path = None

    try:
        input_data = input_data.strip()

        if is_url(input_data):
            print(f"🌐 [PDF 技能] 偵測到遠端 PDF URL，開始下載：{input_data}")

            title = get_filename_from_url(input_data)
            temp_pdf_path = download_pdf(input_data)
            pdf_path = temp_pdf_path

        else:
            print(f"📄 [PDF 技能] 讀取本機 PDF：{input_data}")

            if not os.path.exists(input_data):
                return "找不到檔案", f"路徑不存在: {input_data}"

            title = os.path.basename(input_data)
            pdf_path = input_data

        text = extract_pdf_text(pdf_path)

        if not text or len(text.strip()) < 100:
            return "PDF 解析失敗", "PDF 可讀取，但擷取文字過短，可能是掃描檔、圖片型 PDF，或內容受保護。"

        return title, text

    except Exception as e:
        return "PDF 解析失敗", str(e)

    finally:
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            try:
                os.remove(temp_pdf_path)
            except Exception:
                pass
