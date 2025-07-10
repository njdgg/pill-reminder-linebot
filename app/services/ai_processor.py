# --- START OF FILE: app/services/ai_processor.py (最終整合版) ---

import os
from google.genai import types
from google import genai
from PIL import Image
import io
import json
import traceback
import pymysql
from typing import List, Dict, Any, Tuple
import time

# --- 輔助函式 ---
def get_db_connection(db_config: dict):
    """建立資料庫連線。"""
    try:
        # 確保 db_config 中的 port 是整數
        if 'port' in db_config and isinstance(db_config['port'], str):
            db_config['port'] = int(db_config['port'])
            
        return pymysql.connect(**db_config, cursorclass=pymysql.cursors.DictCursor)
    except (pymysql.MySQLError, TypeError) as e:
        print(f"[DB] 資料庫連線失敗: {e}")
        return None

def get_full_drug_database(conn) -> List[Dict[str, Any]]:
    """從資料庫獲取完整的藥物清單，作為 AI 的參考。"""
    drug_list = []
    if not conn: return []
    try:
        with conn.cursor() as cursor:
            query = "SELECT drug_id, drug_name_zh, drug_name_en, main_use, side_effects FROM drug_info"
            cursor.execute(query)
            drug_list = cursor.fetchall()
    except pymysql.MySQLError as e:
        print(f"[DB] 獲取完整藥物參考清單失敗: {e}")
    return drug_list

def get_frequency_database(conn) -> List[Dict[str, Any]]:
    """從資料庫獲取完整的頻率參考表。"""
    freq_list = []
    if not conn: return []
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT frequency_code, frequency_name, times_per_day, timing_description FROM frequency_code")
            freq_list = cursor.fetchall()
    except pymysql.MySQLError as e:
        print(f"[DB] 獲取頻率參考清單失敗: {e}")
    return freq_list


# --- 主要分析函式 ---
def run_analysis(image_bytes_list: List[bytes], db_config: dict, api_key: str) -> Tuple[Dict | None, Dict | None]:
    """
    使用 Gemini Vision 模型直接分析藥單圖片，並回傳結構化的 JSON 結果。
    此版本使用強化的 Prompt，包含分層判斷和計算邏輯。
    """
    start_time = time.time()
    print("[AI Vision] 開始執行圖片直接分析任務 (最終整合模式)...")
    
    if not image_bytes_list:
        print("[AI Vision] 錯誤：沒有提供任何圖片資料。")
        return None, None

    conn = get_db_connection(db_config)
    if not conn:
        # 如果連線失敗，回傳一個包含錯誤訊息的元組，方便上層處理
        return None, {"error": "資料庫連線失敗"}

    try:
        # 準備 Prompt 所需的參考資料
        drug_candidates = get_full_drug_database(conn)
        freq_codes = get_frequency_database(conn)

        drug_ref_str = json.dumps(drug_candidates, ensure_ascii=False, indent=2, default=str)
        freq_ref_str = json.dumps(freq_codes, ensure_ascii=False, indent=2, default=str)

        # 設定 Gemini API (遵循您的原始設定)
        client, model_name = genai.Client(api_key=api_key), "gemini-2.5-flash"
        
        # 植入帶有條件分支和計算的頻率解析演算法的 Prompt
        prompt_text = f"""
# 任務與角色
你是一位頂尖的醫療資訊分析師。你的任務是分析我提供的藥單圖片，並結合參考資料，將結果結構化為一個單一的 JSON 物件。

# 參考資料
1.  **藥品資料庫參考清單 (請從中選擇)**:
{drug_ref_str}

2.  **用藥頻率參考清單 (這是你唯一的頻率判斷依據)**:
{freq_ref_str}

# 輸出要求 (嚴格遵守)
請返回一個**單一的 JSON 物件**。這個物件必須包含全域資訊以及一個 `medications` 列表。列表中每一個物件對應圖片中的一筆藥物。

## 全域欄位
- `clinic_name`: (字串) 診所名稱。
- `doctor_name`: (字串) 醫師姓名。
- `visit_date`: (字串) 看診日期，必須轉為 `YYYY-MM-DD` 格式。
- `days_supply`: (字串) 總給藥天數。

## `medications` 列表中的物件欄位
- `matched_drug_id`: (字串或null) 從「藥品資料庫」中選出的最匹配藥物的 `drug_id`。如果找不到合理的匹配，此欄位必須為 `null`。
- `drug_name_zh`: (字串) 匹配到的藥物中文名，若無匹配則從圖片中提取。
- `drug_name_en`: (字串) 匹配到的藥物英文名，若無匹配則從圖片中提取。
- `main_use`: (字串) 匹配到的藥物主要用途。
- `side_effects`: (字串) 匹配到的藥物常見副作用。
- `dose_quantity`: (字串) 從圖片中解析出的「單次劑量」，包含數值和單位 (例如: '1 顆', '0.5 錠')。

- **【頻率解析演算法 (極其重要，你必須嚴格遵循此分層邏輯)】**:

    **第一步：確定全域天數 (`Global_Days`)**
    從圖片中找到總天數（例如 '本單發藥 3 日份'），將其數值（`3`）記錄為 `Global_Days`。這是後續計算的基礎。

    **第二步：對每種藥物進行分層判斷**

    *   **情況 A (明確指令詞)**: 如果藥物用法中包含明確的指令詞，如 `HS` (睡前), `BIDX` (早晚), 或 `PRN` (需要時)，請**直接**使用「用藥頻率參考清單」進行查找並填寫以下欄位。這是最高優先級。
        - `frequency_text`: 根據查到的 `frequency_name` 生成，例如 '一日二次' 或 '睡前服用'。
        - `frequency_count_code`: 填寫查到的 `frequency_code`，例如 `BIDX` 對應 `BID`。
        - `frequency_timing_code`: 如果有，則填寫 (例如 `AC`, `PC`)，否則為 `null`。

    *   **情況 B (需要計算)**: 如果藥物用法中**沒有**明確的指令詞 (例如只有 '飯前服用')，你**必須**啟用計算模式：
        1.  從該藥物行的用法欄中，找到總次數或總量（例如 `9.00/9` 中的 `9`）。將此記錄為 `Total_Doses`。
        2.  執行計算：`Daily_Count = Total_Doses / Global_Days`。 (例如: `9 / 3 = 3`)
        3.  使用計算出的 `Daily_Count` 值（`3`），去「用藥頻率參考清單」中查找 `times_per_day` 為 `3.0` 的項目，得到其 `frequency_code` (`TID`) 和 `frequency_name` ('一日三次')。
        4.  根據計算和查找結果，填寫以下欄位：
            - `frequency_text`: 組合 `frequency_name` 和圖片上的時機文字。例如 '一日三次 飯前服用'。
            - `frequency_count_code`: 填寫查到的 `frequency_code`，例如 `TID`。
            - `frequency_timing_code`: 從圖片的時機文字 ('飯前服用') 推斷出代碼，例如 `AC`。

請確保你的輸出是一個格式完全正確的 JSON 物件，並用 ```json ... ``` 包圍。
"""
        
        # 正確構建多模態的 Parts 列表
        prompt_parts = []
        prompt_parts.append(types.Part.from_text(text=prompt_text))
        for img_bytes in image_bytes_list:
            prompt_parts.append(types.Part(
                inline_data=types.Blob(
                    mime_type='image/jpeg',
                    data=img_bytes
                )
            ))
            
        # 恢復使用您原始的 AI 框架
        contents = [types.Content(role="user", parts=prompt_parts)]
        config = types.GenerateContentConfig(
            temperature=0, 
            thinking_config=types.ThinkingConfig(thinking_budget=0), 
            response_mime_type="application/json"
        )
        response_chunks = client.models.generate_content_stream(
            model=model_name, 
            contents=contents, 
            config=config
        )
        
        response_text = "".join([chunk.text for chunk in response_chunks if hasattr(chunk, "text") and chunk.text])
        
        if not response_text:
            print("[AI Vision] 模型沒有回傳任何文字內容。")
            return None, None

        analysis_result = json.loads(response_text)

        # 計算成功匹配的藥物數量
        if analysis_result and "medications" in analysis_result:
            successful_matches = [med for med in analysis_result.get("medications", []) if med.get("matched_drug_id")]
            analysis_result['successful_match_count'] = len(successful_matches)
        else:
            if analysis_result is None: analysis_result = {}
            analysis_result['successful_match_count'] = 0

        end_time = time.time()
        usage_info = {"model": model_name, "execution_time": end_time - start_time}
        print(f"[AI USAGE] Model: {model_name}, Execution Time: {usage_info['execution_time']:.4f} seconds")
        
        return analysis_result, usage_info

    except Exception as e:
        print(f"  [AI Vision] 分析處理錯誤: {e}"); traceback.print_exc()
        return None, None
    finally:
        if conn and conn.open:
            conn.close()

# --- END OF FILE: app/services/ai_processor.py ---