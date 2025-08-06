# --- 修正後的 app/routes/handlers/reminder_handler.py ---

from flask import current_app
from linebot.models import TextSendMessage, QuickReply, QuickReplyButton, MessageAction
from urllib.parse import parse_qs, unquote, quote

from app.services.user_service import UserService
from app.services import reminder_service
from app.utils.flex import reminder as flex_reminder, general as flex_general, member as flex_member

def _reply_message(reply_token, messages):
    from app import line_bot_api
    if not isinstance(messages, list): messages = [messages]
    line_bot_api.reply_message(reply_token, messages)

def handle(event):
    """用藥提醒處理器的主入口函式"""
    user_id = event.source.user_id
    if event.type == 'postback':
        handle_postback(event, user_id)
    elif event.type == 'message' and hasattr(event.message, 'text'):
        handle_message(event, user_id)

def handle_postback(event, user_id):
    """處理用藥提醒流程中的 Postback 事件"""
    data = parse_qs(unquote(event.postback.data))
    action = data.get('action', [None])[0]
    reply_token = event.reply_token

    if action == 'confirm_delete_reminder':
        reminder_id = data.get('reminder_id', [None])[0]
        _reply_message(reply_token, flex_general.create_simple_confirmation(
            alt_text="確認刪除提醒", title="⚠️ 確定要刪除？", text="您確定要刪除這筆用藥提醒嗎？",
            confirm_label="是，刪除", confirm_data=f"action=execute_delete_reminder&reminder_id={reminder_id}"
        ))

    elif action == 'execute_delete_reminder':
        reminder_id = int(data.get('reminder_id', [0])[0])
        if reminder_service.ReminderService.delete_reminder(reminder_id, user_id) > 0:
            _reply_message(reply_token, TextSendMessage(text="✅ 已成功刪除該筆用藥提醒。"))
        else:
            _reply_message(reply_token, TextSendMessage(text="❌ 操作失敗，找不到提醒或權限不足。"))

    elif action == 'clear_reminders_for_member':
        member_id = int(data.get('member_id', [0])[0])
        try:
            member_name, count = reminder_service.ReminderService.clear_reminders_for_member(user_id, member_id)
            _reply_message(reply_token, TextSendMessage(text=f"✅ 已成功清除「{member_name}」的所有用藥提醒 (共 {count} 筆)！"))
        except ValueError as e:
            _reply_message(reply_token, TextSendMessage(text=f"❌ 操作失敗：{e}"))
            
    elif action == 'rename_member_profile':
        member_id = int(data.get('member_id', [0])[0])
        from app.utils.db import DB
        member_info = DB.get_member_by_id(member_id)
        if member_info:
            UserService.save_user_simple_state(user_id, f"rename_member_profile:{member_info['member']}")
            _reply_message(reply_token, TextSendMessage(
                text=f"請輸入「{member_info['member']}」的新名稱：\n\n❌ 輸入「取消」可結束操作",
                quick_reply=QuickReply(items=[QuickReplyButton(action=MessageAction(label="取消", text="取消"))])
            ))

    elif action == 'delete_member_profile_confirm':
        member_id = int(data.get('member_id', [0])[0])
        _reply_message(reply_token, flex_general.create_simple_confirmation(
            alt_text="確認刪除對象", title="⚠️ 確定要刪除？",
            text="刪除後將同時移除該對象的所有相關用藥提醒，此操作無法復原！",
            confirm_label="是，刪除",
            confirm_data=f"action=execute_delete_member_profile&member_id={member_id}"
        ))

    elif action == 'execute_delete_member_profile':
        member_id = int(data.get('member_id', [0])[0])
        from app.utils.db import DB
        target_member = DB.get_member_by_id(member_id)
        if target_member:
            try:
                UserService.delete_member(user_id, target_member['member'])
                _reply_message(reply_token, TextSendMessage(text=f"✅ 已成功刪除對象「{target_member['member']}」。"))
            except ValueError as e:
                _reply_message(reply_token, TextSendMessage(text=f"❌ 刪除失敗：{e}"))

    elif action == 'add_member_profile':
        UserService.save_user_simple_state(user_id, "awaiting_new_member_name")
        _reply_message(reply_token, TextSendMessage(
            text="📝 請輸入要新增的提醒對象名稱：\n💡 例如：媽媽、爸爸、運動提醒\n\n❌ 輸入「取消」可結束操作",
            quick_reply=QuickReply(items=[QuickReplyButton(action=MessageAction(label="取消", text="取消"))])
        ))

    elif action == 'view_existing_reminders':
        member_name = data.get('member', [None])[0]
        if member_name:
            # 解碼 URL 編碼的成員名稱（unquote 已在函數開始導入）
            member_name = unquote(member_name)
            print(f"🔍 [view_existing_reminders] 查詢成員: '{member_name}'")
            
            members = UserService.get_user_members(user_id)
            print(f"🔍 [view_existing_reminders] 用戶所有成員: {[m['member'] for m in members]}")
            
            target_member = next((m for m in members if m['member'] == member_name), None)
            if target_member:
                reminders = reminder_service.ReminderService.get_reminders_for_member(user_id, member_name)
                print(f"🔍 [view_existing_reminders] 找到 {len(reminders)} 個提醒")
                
                # 如果沒有提醒，額外檢查是否有其他可能的成員名稱
                if not reminders:
                    print(f"⚠️ [view_existing_reminders] 沒有找到提醒，檢查相似成員名稱...")
                    # 檢查是否有相似的成員名稱
                    for m in members:
                        if m['member'].strip() == member_name.strip():
                            print(f"🔍 發現相似成員: '{m['member']}'")
                            reminders = reminder_service.ReminderService.get_reminders_for_member(user_id, m['member'])
                            if reminders:
                                target_member = m
                                member_name = m['member']
                                print(f"✅ 使用成員 '{member_name}' 找到 {len(reminders)} 個提醒")
                                break
                
                liff_id = current_app.config['LIFF_ID_MANUAL_REMINDER']
                _reply_message(reply_token, flex_reminder.create_reminder_list_carousel(target_member, reminders, liff_id))
            else:
                print(f"❌ [view_existing_reminders] 找不到成員: '{member_name}'")
                _reply_message(reply_token, TextSendMessage(text=f"❌ 找不到成員「{member_name}」"))

    elif action == 'add_from_prescription':
        member_name = data.get('member', [None])[0]
        if member_name:
            from app.utils.db import DB
            records = DB.get_records_by_member(user_id, member_name)
            _reply_message(reply_token, flex_reminder.create_prescription_records_carousel(member_name, records))

    elif action == 'delete_reminder':
        reminder_id = data.get('reminder_id', [None])[0]
        _reply_message(reply_token, flex_general.create_simple_confirmation(
            alt_text="確認刪除提醒", title="⚠️ 確定要刪除？", text="您確定要刪除這筆用藥提醒嗎？",
            confirm_label="是，刪除", confirm_data=f"action=execute_delete_reminder&reminder_id={reminder_id}"
        ))
    
    elif action == 'view_reminders_page':
        member_name = data.get('member', [None])[0]
        page = int(data.get('page', [1])[0])
        
        if member_name:
            members = UserService.get_user_members(user_id)
            target_member = next((m for m in members if m['member'] == member_name), None)
            
            if target_member:
                reminders = reminder_service.ReminderService.get_reminders_for_member(user_id, member_name)
                liff_id = current_app.config['LIFF_ID_MANUAL_REMINDER']
                _reply_message(reply_token, flex_reminder.create_reminder_list_carousel(target_member, reminders, liff_id, page))
            else:
                _reply_message(reply_token, TextSendMessage(text="❌ 找不到該成員"))
        else:
            _reply_message(reply_token, TextSendMessage(text="❌ 成員名稱錯誤"))

def handle_message(event, user_id):
    """處理用藥提醒流程中的 Message 事件"""
    text = event.message.text.strip()
    reply_token = event.reply_token
    state = UserService.get_user_simple_state(user_id)

    if state:
        if text == '取消':
            UserService.delete_user_simple_state(user_id)
            _reply_message(reply_token, TextSendMessage(text="操作已取消。"))
            return
            
        if state == "awaiting_new_member_name":
            handle_add_member_name(user_id, text, reply_token)
            return
        elif state.startswith("rename_member_profile:"):
            old_name = state.split(':', 1)[1]
            handle_rename_member(user_id, old_name, text, reply_token)
            return

    # 處理用藥提醒相關指令 (支援新舊版本)
    if text in ["用藥提醒管理", "用藥提醒"]:
        _reply_message(reply_token, flex_reminder.create_reminder_management_menu())
        return

    if text == "新增/查詢提醒":
        members = UserService.get_user_members(user_id)
        # 手動處理 datetime 和 Decimal
        from datetime import date, datetime
        from decimal import Decimal
        for member in members:
            for key, value in member.items():
                if isinstance(value, (datetime, date)):
                    member[key] = value.isoformat()
                elif isinstance(value, Decimal):
                    member[key] = str(value)

        items = [QuickReplyButton(action=MessageAction(label=m['member'], text=m['member'])) for m in members]
        if not items:
            _reply_message(reply_token, TextSendMessage(text="您尚未建立任何提醒對象，請先至「管理提醒對象」新增。"))
        else:
            # 設定用戶狀態，表示正在選擇成員進行提醒操作
            UserService.save_user_simple_state(user_id, "selecting_member_for_reminder")
            _reply_message(reply_token, TextSendMessage(
                text="請選擇要查詢或設定提醒的對象：",
                quick_reply=QuickReply(items=items[:13])
            ))
        return

    if text in ["管理提醒對象", "管理成員"]:
        summary = reminder_service.ReminderService.get_reminders_summary_for_management(user_id)
        # 【核心修正】補上缺少的 liff_id 參數
        liff_id = current_app.config['LIFF_ID_MANUAL_REMINDER']
        _reply_message(reply_token, flex_reminder.create_member_management_carousel(summary, liff_id))
        return

    if text == "刪除提醒對象":
        deletable_members = UserService.get_deletable_members(user_id)
        _reply_message(reply_token, flex_member.create_deletable_members_flex(deletable_members, user_id))
        return

    if text == "新增提醒對象":
        UserService.save_user_simple_state(user_id, "awaiting_new_member_name")
        _reply_message(reply_token, TextSendMessage(
            text="📝 請輸入要新增的提醒對象名稱：\n💡 例如：媽媽、爸爸\n\n❌ 輸入「取消」可結束操作",
            quick_reply=QuickReply(items=[QuickReplyButton(action=MessageAction(label="取消", text="取消"))])
        ))
        return

    members = UserService.get_user_members(user_id)
    target_member = next((m for m in members if m['member'] == text), None)
    if target_member:
        # 檢查用戶狀態，如果是從「新增/查詢提醒」來的，則顯示選項選單
        user_state = UserService.get_user_simple_state(user_id)
        print(f"🔍 [reminder_handler] 用戶狀態: {user_state}")
        print(f"🔍 [reminder_handler] 選擇的成員: {text}")
        
        if user_state == "selecting_member_for_reminder":
            # 清除狀態並顯示提醒選項選單（新增或查詢）
            UserService.delete_user_simple_state(user_id)
            print(f"✅ [reminder_handler] 顯示提醒選項選單")
            _reply_message(reply_token, flex_reminder.create_reminder_options_menu(target_member))
        else:
            # 其他情況直接顯示該成員的提醒列表
            print(f"✅ [reminder_handler] 顯示提醒列表，成員: '{text}'")
            reminders = reminder_service.ReminderService.get_reminders_for_member(user_id, text)
            print(f"🔍 [reminder_handler] 查詢到 {len(reminders)} 個提醒")
            
            # 如果沒有提醒，輸出更多調試資訊
            if not reminders:
                print(f"⚠️ [reminder_handler] 沒有找到提醒，成員名稱: '{text}', user_id: '{user_id}'")
                # 直接查詢資料庫確認
                try:
                    from app.utils.db import get_db_connection
                    db = get_db_connection()
                    if db:
                        with db.cursor() as cursor:
                            cursor.execute("SELECT COUNT(*) as count FROM medicine_schedule WHERE recorder_id = %s AND member = %s", (user_id, text))
                            result = cursor.fetchone()
                            db_count = result['count'] if result else 0
                            print(f"🔍 [reminder_handler] 資料庫直接查詢結果: {db_count} 個提醒")
                            
                            # 查看該用戶的所有提醒
                            cursor.execute("SELECT member, drug_name FROM medicine_schedule WHERE recorder_id = %s", (user_id,))
                            all_reminders = cursor.fetchall()
                            print(f"🔍 [reminder_handler] 該用戶所有提醒: {all_reminders}")
                except Exception as e:
                    print(f"❌ [reminder_handler] 資料庫查詢錯誤: {e}")
            
            liff_id = current_app.config['LIFF_ID_MANUAL_REMINDER']
            _reply_message(reply_token, flex_reminder.create_reminder_list_carousel(target_member, reminders, liff_id))
        return

def handle_add_member_name(user_id, name, reply_token):
    if not (0 < len(name) <= 20):
        _reply_message(reply_token, TextSendMessage(text="❌ 名稱長度需介於1-20個字之間，請重新輸入。"))
        return
    try:
        UserService.add_new_member(user_id, name)
        UserService.delete_user_simple_state(user_id)
        _reply_message(reply_token, TextSendMessage(text=f"✅ 提醒對象「{name}」已成功新增！"))
    except ValueError as e:
        _reply_message(reply_token, TextSendMessage(text=f"⚠️ {e}"))

def handle_rename_member(user_id, old_name, new_name, reply_token):
    try:
        UserService.rename_member(user_id, old_name, new_name)
        UserService.delete_user_simple_state(user_id)
        _reply_message(reply_token, TextSendMessage(text=f"✅ 已成功將「{old_name}」重命名為「{new_name}」。"))
    except ValueError as e:
        _reply_message(reply_token, TextSendMessage(text=f"❌ 重命名失敗：{e}"))