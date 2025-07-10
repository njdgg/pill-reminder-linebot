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
            members = UserService.get_user_members(user_id)
            target_member = next((m for m in members if m['member'] == member_name), None)
            if target_member:
                reminders = reminder_service.ReminderService.get_reminders_for_member(user_id, member_name)
                liff_id = current_app.config['LIFF_ID_MANUAL_REMINDER']
                _reply_message(reply_token, flex_reminder.create_reminder_list_carousel(target_member, reminders, liff_id))

    elif action == 'add_from_prescription':
        member_name = data.get('member', [None])[0]
        if member_name:
            from app.utils.db import DB
            records = DB.get_records_by_member(user_id, member_name)
            _reply_message(reply_token, flex_reminder.create_prescription_records_carousel(member_name, records))

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
        _reply_message(reply_token, flex_member.create_deletable_members_flex(deletable_members))
        return

    members = UserService.get_user_members(user_id)
    target_member = next((m for m in members if m['member'] == text), None)
    if target_member:
        _reply_message(reply_token, flex_reminder.create_reminder_options_menu(target_member))
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