import os
from google import genai

def main():
    # 1. 讀取外部配置變數
    input_data = os.environ.get("INPUT_DATA", "").strip()
    input_type = os.environ.get("INPUT_TYPE", "youtube").strip().lower()
    prompt_type = os.environ.get("VIDEO_TYPE", "general").strip().lower()
    output_type = os.environ.get("VIDEO_OUTPUT", "markdown").strip().lower()
    api_key = os.environ.get("GEMINI_API_KEY")

    print(f"🚀 [中央管理架構啟動]")
    print(f"├── 📥 輸入技能: skills/in_{input_type}.py")
    print(f"├── 🧠 大腦範本: prompts/{prompt_type}.txt")
    print(f"└── 📤 輸出技能: skills/out_{output_type}.py")

    # 2. 【動態調度：輸入端技能】
    try:
        in_module_name = f"skills.in_{input_type}"
        in_module = __import__(in_module_name, fromlist=['fetch'])
        source_title, source_content = in_module.fetch(input_data)
        print(f"🎯 [輸入端成功] 獲取素材標題: 【{source_title}】")
    except ModuleNotFoundError:
        print(f"❌ 錯誤：找不到指定的輸入技能 'skills/in_{input_type}.py'")
        return
    except Exception as e:
        print(f"❌ 執行輸入技能失敗: {str(e)}")
        return

    # 3. 讀取 Prompt 大腦
    prompt_file_path = f"prompts/{prompt_type}.txt"
    with open(prompt_file_path if os.path.exists(prompt_file_path) else "prompts/general.txt", "r", encoding="utf-8") as f:
        selected_prompt = f.read()

    # 4. 呼叫 Gemini (對齊最新 3.5 Flash 萬用多模態)
    try:
        client = genai.Client(api_key=api_key)
        time_context = f"【時空背景】：當前是 2026 年 7 月。請針對素材【{source_title}】內容，結合你的多模態能力，按照提示詞規範進行繁體中文的深度分析。"
        media_url_context = f"影片直連網址：https://www.youtube.com/watch?v={input_data}\n" if input_type == "youtube" else ""
        
        final_prompt = f"{time_context}\n\n{selected_prompt}\n\n---\n素材標題：{source_title}\n{media_url_context}素材文本內容：\n{source_content}"
        
        print(f"🤖 正在呼叫 Gemini AI (gemini-3.5-flash) 進行核心推理...")
        response = client.models.generate_content(model='gemini-3.5-flash', contents=final_prompt)
        ai_result = response.text
    except Exception as e:
        print(f"❌ Gemini 推理失敗: {str(e)}")
        return

    # 5. 【動態調度：輸出端技能】
    try:
        out_module_name = f"skills.out_{output_type}"
        out_module = __import__(out_module_name, fromlist=['execute'])
        
        safe_id = input_data.replace("/", "_").replace(":", "_")[:15]
        out_module.execute(ai_result, safe_id, prompt_type)
        print("🏁 [完工] 全積木化 Skills 工作流完美結束。")
    except ModuleNotFoundError:
        print(f"❌ 錯誤：找不到指定的輸出技能 'skills/out_{output_type}.py'")
    except Exception as e:
        print(f"❌ 執行輸出技能失敗: {str(e)}")

if __name__ == "__main__":
    main()
