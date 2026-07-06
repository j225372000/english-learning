import os
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

def fetch(file_path):
    """
    PDF 輸入技能積木：讀取專案內的 PDF 檔案並提取文字
    """
    if not PdfReader:
        return "錯誤", "未安裝 pypdf 庫"
    if not os.path.exists(file_path):
        return "找不到檔案", f"路徑不存在: {file_path}"
    try:
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        title = os.path.basename(file_path)
        return title, text
    except Exception as e:
        return "PDF 解析失敗", str(e)
