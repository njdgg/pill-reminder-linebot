# --- 請用此版本【完整覆蓋】您的 app/services/prescription_service.py ---

import base64
import traceback
from ..utils.db import DB
from .user_service import UserService
from . import ai_processor
from ..utils.helpers import convert_minguo_to_gregorian
from flask import current_app
# 移除不再需要的 line_bot_api 和 flex 導入
# from app import line_bot_api
# from ..utils.flex import prescription as flex_prescription

class PrescriptionService:
    """處理藥單分析與藥歷相關的業務邏輯"""

    @staticmethod
    def trigger_analysis(user_id: str, task_id: str):
        """
        觸發藥單深度分析，並將結果存回狀態。
        返回 True 表示成功，或拋出異常。
        """
        full_state = UserService.get_user_complex_state(user_id)
        last_task_info = full_state.get("last_task", {})

        if not last_task_info or last_task_info.get("task_id") != task_id:
            raise ValueError("找不到對應的分析任務，請重新操作。")
        
        image_b64_list = last_task_info.get("image_bytes_list", [])
        if not image_b64_list:
            raise ValueError("分析任務中缺少圖片資料，請重新操作。")
        
        try:
            image_bytes_list = [base64.b64decode(b64_str) for b64_str in image_b64_list]
            
            api_key = current_app.config['GEMINI_API_KEY']
            db_config = {
                'host': current_app.config['DB_HOST'], 'user': current_app.config['DB_USER'],
                'password': current_app.config['DB_PASSWORD'], 'database': current_app.config['DB_NAME'],
                'port': current_app.config['DB_PORT']
            }

            analysis_result, usage_info = ai_processor.run_analysis(
                image_bytes_list, db_config, api_key
            )

            if not analysis_result or not isinstance(analysis_result, dict) or 'medications' not in analysis_result:
                error_detail = usage_info.get("error") if isinstance(usage_info, dict) else "未知AI錯誤"
                raise RuntimeError(f"AI 分析失敗或回傳格式錯誤: {error_detail}")

            last_task_info["results"] = analysis_result
            full_state["last_task"] = last_task_info
            UserService.set_user_complex_state(user_id, full_state)
            
            return True

        except Exception as e:
            print(f"分析任務發生嚴重錯誤: {e}")
            traceback.print_exc()
            raise

    @staticmethod
    def save_prescription_from_state(user_id: str):
        """
        從使用者狀態中讀取分析結果並存入資料庫。
        """
        full_state = UserService.get_user_complex_state(user_id)
        task_to_save = full_state.get("last_task")

        if not task_to_save or 'results' not in task_to_save:
            raise ValueError("找不到可儲存的結果。")
        
        analysis_data = task_to_save['results']
        
        visit_date_str = analysis_data.get('visit_date')
        visit_date_gregorian = convert_minguo_to_gregorian(visit_date_str)
        if not visit_date_gregorian:
            # 【修正】這裡要確保狀態被正確設定，以便 handle_postback 能夠處理
            state_to_save = UserService.get_user_complex_state(user_id)
            state_to_save['state_info'] = {'state': 'AWAITING_VISIT_DATE'}
            UserService.set_user_complex_state(user_id, state_to_save)
            return "AWAITING_VISIT_DATE", None, None

        analysis_data['visit_date'] = visit_date_gregorian
        
        try:
            mm_id, is_update = DB.save_or_update_prescription(analysis_data, task_to_save, user_id)
            UserService.clear_user_complex_state(user_id)
            return "SUCCESS", mm_id, is_update
        except Exception as e:
            print(f"儲存藥歷時服務層發生錯誤: {e}")
            traceback.print_exc()
            raise

    @staticmethod
    def get_prescription_details(mm_id: int):
        """
        獲取單筆藥歷的完整資訊。
        """
        record = DB.get_prescription_by_mm_id(mm_id)
        if not record:
            return None
        
        all_drugs_info = {d['drug_id']: d for d in DB.get_all_drug_info()}
        
        for med in record.get("medications", []):
            if not isinstance(med, dict): continue
            matched_id = med.get('matched_drug_id')
            drug_info = all_drugs_info.get(matched_id)
            
            if drug_info:
                if not med.get('main_use'): med['main_use'] = drug_info.get('main_use')
                if not med.get('side_effects'): med['side_effects'] = drug_info.get('side_effects')
        
        return record

    @staticmethod
    def load_record_as_draft(user_id: str, mm_id: int):
        """
        將歷史藥歷記錄載入為草稿，供用戶編輯。
        """
        try:
            # 獲取歷史記錄
            record = DB.get_prescription_by_mm_id(mm_id)
            if not record:
                return False
            
            # 檢查權限 - 確保記錄屬於該用戶
            if record.get('recorder_id') != user_id:
                return False
            
            # 準備草稿資料
            medications_for_draft = []
            for med in record.get('medications', []):
                medications_for_draft.append({
                    "matched_drug_id": med.get('matched_drug_id'),
                    "drug_name_zh": med.get('drug_name_zh'),
                    "drug_name_en": med.get('drug_name_en'),
                    "dose_quantity": med.get('dose_quantity'),
                    "frequency_count_code": med.get('frequency_count_code'),
                    "frequency_timing_code": med.get('frequency_timing_code'),
                    "frequency_text": med.get('frequency_text'),
                    "main_use": med.get('main_use'),
                    "side_effects": med.get('side_effects')
                })
            
            # 準備完整的草稿結果
            draft_results = {
                "clinic_name": record.get('clinic_name'),
                "doctor_name": record.get('doctor_name'),
                "visit_date": record.get('visit_date').strftime('%Y-%m-%d') if record.get('visit_date') else None,
                "days_supply": record.get('days_supply'),
                "medications": medications_for_draft,
                "successful_match_count": len(medications_for_draft)
            }
            
            # 建立新的狀態，包含編輯標記
            import time
            initial_state = {
                "last_task": {
                    "task_id": f"edit_{user_id[:8]}_{int(time.time())}",
                    "line_user_id": user_id,
                    "member": record.get('member'),
                    "status": "completed",
                    "mm_id_to_update": mm_id,  # 標記為更新模式
                    "results": draft_results,
                    "source": "load_from_history"
                }
            }
            
            # 儲存狀態
            UserService.set_user_complex_state(user_id, initial_state)
            
            current_app.logger.info(f"歷史記錄已載入為草稿 - 用戶: {user_id}, mm_id: {mm_id}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"載入歷史記錄為草稿時發生錯誤: {e}")
            return False