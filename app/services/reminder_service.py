# app/services/reminder_service.py

import schedule
import time
import traceback
from datetime import datetime
from ..utils.db import DB
from app import line_bot_api
from linebot.models import TextSendMessage

class ReminderService:
    """處理用藥提醒的建立、查詢、刪除與排程發送"""

    @staticmethod
    def create_or_update_reminder(user_id: str, member_id: str = None, form_data: dict = None, reminder_id: int = None):
        """
        建立或更新一筆用藥提醒。
        這個函式將處理來自 LIFF 表單的資料。
        """
        if form_data is None: form_data = {}
            
        reminder_data = {'recorder_id': user_id, **form_data}
        
        if reminder_id:
            existing_reminder = DB.get_reminder_by_id(reminder_id)
            if existing_reminder:
                reminder_data['member'] = existing_reminder['member']
                # 確保藥物名稱不會被清空
                if 'drug_name' not in reminder_data or not reminder_data['drug_name']:
                    reminder_data['drug_name'] = existing_reminder['drug_name']
        elif member_id:
            member_info = DB.get_member_by_id(member_id)
            if member_info:
                reminder_data['member'] = member_info['member']
        
        return DB.create_reminder(reminder_data)

    @staticmethod
    def get_reminders_for_member(user_id: str, member_name: str):
        """獲取特定成員的所有提醒"""
        return DB.get_reminders(user_id, member_name)

    @staticmethod
    def get_reminders_summary_for_management(user_id: str):
        """
        【新增】獲取用於管理介面的提醒摘要資訊。
        """
        members = DB.get_members(user_id)
        for member in members:
            reminders = DB.get_reminders(user_id, member['member'])
            member['reminders_count'] = len(reminders)
            drug_names = [r.get('drug_name', '未命名藥品') for r in reminders[:2]]
            if len(reminders) > 2:
                drug_names.append(f"等{len(reminders)}種")
            member['reminders_preview'] = "、".join(drug_names) if drug_names else "尚無提醒"
        return members

    @staticmethod
    def get_reminder_details(reminder_id: int, user_id: str):
        """獲取單筆提醒的詳細資訊，並檢查所有權"""
        if not DB.check_reminder_ownership(reminder_id, user_id):
            return None
        return DB.get_reminder_by_id(reminder_id)

    @staticmethod
    def delete_reminder(reminder_id: int, user_id: str):
        """刪除單筆提醒，並檢查所有權"""
        if not DB.check_reminder_ownership(reminder_id, user_id):
            return 0
        return DB.delete_reminder(reminder_id)

    @staticmethod
    def clear_reminders_for_member(user_id: str, member_id: int):
        """清空特定成員的所有提醒，並返回成員名稱"""
        member = DB.get_member_by_id(member_id)
        if not member or member['recorder_id'] != user_id:
             raise ValueError("找不到該提醒對象或權限不足。")
        
        deleted_count = DB.delete_reminders_for_member(user_id, member['member'])
        return member['member'], deleted_count

    @staticmethod
    def get_prescription_for_liff(mm_id: int):
        """為藥單提醒 LIFF 頁面準備資料"""
        return DB.get_prescription_for_liff(mm_id)

    @staticmethod
    def create_reminders_batch(reminders_data: list, user_id: str):
        """批量建立來自藥單的提醒"""
        for r in reminders_data:
            if r.get('recorder_id') != user_id:
                raise PermissionError("沒有權限建立不屬於自己的提醒")
        return DB.create_reminders_batch(reminders_data)

# --- 背景排程器相關函式 ---

def check_and_send_reminders(app):
    """使用 app_context 並呼叫 send_reminder_logic"""
    with app.app_context():
        try:
            from app import line_bot_api as bot_api
            current_time_str = datetime.now().strftime("%H:%M")
            reminders = DB.get_reminders_for_scheduler(current_time_str)
            if reminders:
                app.logger.info(f"[{current_time_str}] 找到 {len(reminders)} 筆到期提醒，準備發送...")
            for r in reminders:
                send_reminder_logic(r, current_time_str, bot_api)
        except Exception as e:
            app.logger.error(f"排程器執行時發生錯誤： {str(e)}")
            traceback.print_exc()

def send_reminder_logic(reminder_data: dict, current_time_str: str, bot_api=None):
    """
    發送提醒的核心邏輯。
    採用更嚴謹的判斷，確保只通知設定者與被設定者。
    """
    api = bot_api or line_bot_api
    if api is None:
        print(f"    - 錯誤：line_bot_api 未正確初始化")
        return
    
    # 調試資訊
    print(f"    - 調試：reminder_data keys: {list(reminder_data.keys())}")
    print(f"    - 調試：recorder_id: '{reminder_data.get('recorder_id')}'")
    print(f"    - 調試：bound_recipient_line_id: '{reminder_data.get('bound_recipient_line_id')}')")
    
    recorder_id = reminder_data.get('recorder_id')
    member_name = reminder_data.get('member')
    drug_name = reminder_data.get('drug_name', '未命名藥品')
    recipient_line_id = reminder_data.get('bound_recipient_line_id')

    party_msg_text = f"⏰ 用藥提醒！\n\nHi {member_name}，該吃藥囉！\n藥品：{drug_name}\n時間：{current_time_str}"
    creator_msg_text = f"🔔 您為「{member_name}」設定的提醒已發送。\n藥品：{drug_name}\n時間：{current_time_str}"
    
    # 情況一: 有綁定關係的家人提醒 (且不是幫自己設)
    if recipient_line_id and recipient_line_id != recorder_id:
        print(f"  -> 雙向通知: 設定者[{recorder_id[:6]}..] -> 家人[{recipient_line_id[:6]}..] ({member_name})")
        try:
            api.push_message(recipient_line_id, TextSendMessage(text=party_msg_text))
            print(f"    - ✅ 成功發送 [家人提醒] 給 {recipient_line_id}")
        except Exception as e:
            print(f"    - ❌ 發送 [家人提醒] 給 {recipient_line_id} 失敗: {e}")
        try:
            api.push_message(recorder_id, TextSendMessage(text=creator_msg_text))
            print(f"    - ✅ 成功發送 [備忘提醒] 給 {recorder_id}")
        except Exception as e:
            print(f"    - ❌ 發送 [備忘提醒] 給 {recorder_id} 失敗: {e}")
    # 情況二: 幫自己設定的提醒，或幫一個未綁定的本地 Profile 設定
    else:
        print(f"  -> 單向通知: 設定者[{recorder_id[:6]}..] -> 自己 ({member_name})")
        try:
            api.push_message(recorder_id, TextSendMessage(text=party_msg_text))
            print(f"    - ✅ 成功發送 [個人提醒] 給 {recorder_id}")
        except Exception as e:
            print(f"    - ❌ 發送 [個人提醒] 給 {recorder_id} 失敗: {e}")
            # 詳細錯誤資訊
            if hasattr(e, 'status_code'):
                print(f"      狀態碼: {e.status_code}")
            if hasattr(e, 'error_response'):
                print(f"      錯誤回應: {e.error_response}")
            # 檢查 user_id 格式
            if not recorder_id or not recorder_id.startswith('U'):
                print(f"      ⚠️  可能的問題: user_id 格式不正確 '{recorder_id}'")

def run_scheduler(app):
    """啟動背景排程的函式"""
    print("背景排程器已啟動，每分鐘檢查一次。")
    schedule.every().minute.at(":00").do(check_and_send_reminders, app=app)
    while True:
        schedule.run_pending()
        time.sleep(1)