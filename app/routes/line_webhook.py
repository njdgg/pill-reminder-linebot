# --- 請用此最終版本【完整覆蓋】您的 app/routes/line_webhook.py ---

from flask import Blueprint, request, abort, current_app
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, PostbackEvent, FollowEvent, TextMessage, ImageMessage, TextSendMessage, FlexSendMessage
import traceback

from app import handler, line_bot_api
from .handlers import prescription_handler, reminder_handler
try:
    from .handlers import family_handler
except ImportError:
    family_handler = None

try:
    from .handlers import pill_handler
except ImportError:
    pill_handler = None

from ..services.user_service import UserService
from ..utils.flex import general as flex_general
from ..utils.flex import health as flex_health
from ..utils.flex import prescription as flex_prescription
from ..utils.flex import settings as flex_settings

webhook_bp = Blueprint('webhook', __name__)

@webhook_bp.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    current_app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception as e:
        current_app.logger.error(f"處理 Webhook 時發生錯誤: {e}")
        traceback.print_exc()
        abort(500)
    return 'OK'


@handler.add(MessageEvent, message=(TextMessage, ImageMessage))
def handle_message_dispatcher(event):
    user_id = event.source.user_id
    UserService.get_or_create_user(user_id)
    
    complex_state = UserService.get_user_complex_state(user_id)
    simple_state = UserService.get_user_simple_state(user_id)
    
    # 【核心修正】将图片讯息的处理，也纳入状态判断流程
    if isinstance(event.message, ImageMessage):
        # 优先检查是否为药丸辨识状态
        try:
            from .handlers import pill_handler as ph
            if ph and ph.handle_image_message(event):
                return
        except ImportError:
            pass
        
        # 然后检查是否为药单辨识状态
        if complex_state.get("state_info", {}).get("state") == "AWAITING_IMAGE":
            prescription_handler.handle(event)
        else:
            # 否则，回覆预设讯息
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="感謝您傳送的圖片，但目前我不知道如何處理它。如果您要辨識藥單，請先點擊「藥單辨識」；如果要辨識藥丸，請點擊「藥品辨識」喔！"))
        return

    if not isinstance(event.message, TextMessage):
        return
        
    text = event.message.text.strip()

    # 第一優先級：全局指令
    high_priority_keywords = {
        # 主選單相關
        "選單": lambda: line_bot_api.reply_message(event.reply_token, flex_general.create_main_menu()),
        "主選單": lambda: line_bot_api.reply_message(event.reply_token, flex_general.create_main_menu()),
        "menu": lambda: line_bot_api.reply_message(event.reply_token, flex_general.create_main_menu()),
        
        # 圖文選單按鈕 - 新的簡化名稱
        "藥品辨識": lambda: handle_pill_recognition(event),
        "用藥提醒": lambda: reminder_handler.handle(event),
        "健康紀錄": lambda: line_bot_api.reply_message(
            event.reply_token, 
            flex_health.generate_health_log_menu(f"https://liff.line.me/{current_app.config['LIFF_ID_HEALTH_FORM']}")
        ),
        "設定": lambda: handle_settings_menu(event),
        
        # 舊版本兼容性
        "用藥提醒管理": lambda: reminder_handler.handle(event),
        "家人綁定與管理": lambda: family_handler.handle(event),
        "藥丸辨識": lambda: handle_pill_recognition(event),
        "此功能正在開發中，敬請期待！": lambda: handle_pill_recognition(event),
        "健康記錄管理": lambda: handle_health_record_menu(event),
        
        # 其他功能
        "登入": lambda: handle_login_request(event),
        "會員登入": lambda: handle_login_request(event),
        "查詢個人藥歷": lambda: handle_query_prescription(event),
        "新增/查詢提醒": lambda: reminder_handler.handle(event),
        "管理提醒對象": lambda: reminder_handler.handle(event),
        "刪除提醒對象": lambda: reminder_handler.handle(event),
        "管理成員": lambda: reminder_handler.handle(event),
    }

    if text in high_priority_keywords:
        UserService.delete_user_simple_state(user_id)
        UserService.clear_user_complex_state(user_id)
        high_priority_keywords[text]()
        return

    # 第二優先級：特定流程的文字觸發
    # 檢查藥單相關訊息
    print(f"🔍 Webhook 檢查藥單訊息 - 文字: '{text}'")
    print(f"🔍 包含'照片上傳成功': {'照片上傳成功' in text}")
    print(f"🔍 包含'任務ID:': {'任務ID:' in text}")
    
    if ("照片上傳成功" in text and "任務ID:" in text) or text == '📝 預覽手動修改結果':
        print(f"✅ 訊息匹配成功，轉發到 prescription_handler")
        prescription_handler.handle(event)
        return
    
    # 新增：處理 LIFF 上傳的訊息（沒有任務ID的情況）
    if "照片上傳成功" in text and "正在分析中" in text:
        print(f"✅ LIFF 上傳訊息匹配成功，轉發到 prescription_handler")
        prescription_handler.handle(event)
        return
    # 處理直接發送的「掃描新藥單」文字訊息
    if text == '掃描新藥單' or text == '🤖 掃描新藥單':
        print(f"✅ 檢測到掃描新藥單文字訊息，直接執行掃描流程")
        # 直接執行掃描流程的邏輯 (與 action=start_scan_flow 相同)
        reply_message = flex_prescription.create_management_menu(
            title="📋 藥單辨識管理",
            primary_action_label="📲 掃描新藥單",
            primary_action_data="action=initiate_scan_process"
        )
        line_bot_api.reply_message(event.reply_token, reply_message)
        return
    
    if text.startswith("綁定"):
        family_handler.handle(event)
        return

    # 第三優先級：狀態相關處理
    if simple_state or complex_state.get("state_info", {}).get("state"):
        if text == '取消':
            UserService.delete_user_simple_state(user_id)
            UserService.clear_user_complex_state(user_id)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="操作已取消。"))
        elif state_belongs_to_family(simple_state):
            family_handler.handle(event)
        elif state_belongs_to_reminder(simple_state):
            reminder_handler.handle(event)
        return

    # 第四優先級：如果沒有狀態，檢查是否為成員名稱
    members = [m['member'] for m in UserService.get_user_members(user_id)]
    if text in members:
        reminder_handler.handle(event)
        return

def state_belongs_to_family(state):
    return state and (state.startswith("custom_relation:") or state.startswith("edit_nickname:") or state.startswith("relation_select:"))

def state_belongs_to_reminder(state):
    return state and (state.startswith("awaiting_new_member_name") or state.startswith("rename_member_profile:"))

def handle_query_prescription(event):
    """處理查詢個人藥歷的請求"""
    print("🚀 查詢個人藥歷函數被調用了！")
    current_app.logger.info("🚀 查詢個人藥歷函數被調用了！")
    
    try:
        user_id = event.source.user_id
        print(f"🔍 查詢藥歷 - 用戶ID: {user_id}")
        
        UserService.clear_user_complex_state(user_id)
        members = UserService.get_user_members(user_id)
        
        print(f"🔍 查詢藥歷 - 找到成員數量: {len(members)}")
        print(f"🔍 查詢藥歷 - 成員列表: {[m.get('member', 'Unknown') for m in members]}")
        
        reply_message = flex_prescription.create_patient_selection_message(members, 'query')
        line_bot_api.reply_message(event.reply_token, reply_message)
        print("✅ 藥歷查詢選單已發送")
        
    except Exception as e:
        print(f"❌ 查詢藥歷處理錯誤: {e}")
        current_app.logger.error(f"查詢藥歷處理錯誤: {e}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="查詢藥歷功能暫時無法使用，請稍後再試。"))

def handle_pill_recognition(event):
    """處理藥丸辨識的請求"""
    try:
        print(f"🔍 [Pill Recognition] 收到藥品辨識請求")
        # 先檢查全局導入的 pill_handler
        if pill_handler:
            print(f"✅ [Pill Recognition] 使用全局 pill_handler")
            pill_handler.handle(event)
            return
        
        # 如果全局導入失敗，嘗試動態導入
        from .handlers import pill_handler as ph
        if ph:
            print(f"✅ [Pill Recognition] 使用動態導入 pill_handler")
            ph.handle(event)
        else:
            print(f"❌ [Pill Recognition] pill_handler 模組存在但為 None")
            current_app.logger.error("pill_handler 模組存在但為 None")
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="藥丸辨識功能暫時無法使用，請稍後再試。"))
    except ImportError as e:
        print(f"❌ [Pill Recognition] 無法導入 pill_handler: {e}")
        current_app.logger.error(f"無法導入 pill_handler: {e}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="藥丸辨識功能暫時無法使用，請稍後再試。"))
    except Exception as e:
        print(f"❌ [Pill Recognition] 處理錯誤: {e}")
        current_app.logger.error(f"藥丸辨識處理錯誤: {e}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="藥丸辨識功能發生錯誤，請稍後再試。"))

def handle_settings_menu(event):
    """處理設定選單的請求"""
    try:
        settings_card = flex_settings.create_main_settings_menu()
        flex_message = FlexSendMessage(alt_text="設定選單", contents=settings_card)
        line_bot_api.reply_message(event.reply_token, flex_message)
    except Exception as e:
        current_app.logger.error(f"設定選單處理錯誤: {e}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="設定選單暫時無法使用，請稍後再試。"))

def handle_health_record_menu(event):
    """處理健康記錄選單的請求"""
    print("🚀 健康記錄選單函數被調用了！")
    current_app.logger.info("🚀 健康記錄選單函數被調用了！")
    
    try:
        import os
        env_liff_id = os.environ.get('LIFF_ID_HEALTH_FORM')
        config_liff_id = current_app.config['LIFF_ID_HEALTH_FORM']
        
        print(f"🔍 健康記錄 - 環境變數 LIFF_ID_HEALTH_FORM: {env_liff_id}")
        print(f"🔍 健康記錄 - Config LIFF_ID_HEALTH_FORM: {config_liff_id}")
        current_app.logger.info(f"🔍 健康記錄 - 環境變數 LIFF_ID_HEALTH_FORM: {env_liff_id}")
        current_app.logger.info(f"🔍 健康記錄 - Config LIFF_ID_HEALTH_FORM: {config_liff_id}")
        
        # 暫時強制使用正確的 LIFF ID
        correct_liff_id = "2007610723-GQX9MpVb"
        liff_url = f"https://liff.line.me/{correct_liff_id}"
        
        print(f"🔧 健康記錄 - 強制使用正確的 LIFF URL: {liff_url}")
        current_app.logger.info(f"🔧 健康記錄 - 強制使用正確的 LIFF URL: {liff_url}")
        
        flex_message = flex_health.generate_health_log_menu(liff_url)
        line_bot_api.reply_message(event.reply_token, flex_message)
        print("✅ 健康記錄選單已發送")
    except Exception as e:
        print(f"❌ 健康記錄選單處理錯誤: {e}")
        current_app.logger.error(f"健康記錄選單處理錯誤: {e}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="健康記錄功能暫時無法使用，請稍後再試。"))

def handle_login_request(event):
    """處理登入請求"""
    try:
        from flask import url_for
        login_url = url_for('auth.login', _external=True)
        login_card = flex_settings.create_login_card(login_url)
        flex_message = FlexSendMessage(alt_text="會員登入", contents=login_card)
        line_bot_api.reply_message(event.reply_token, flex_message)
    except Exception as e:
        current_app.logger.error(f"登入請求處理錯誤: {e}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="登入功能暫時無法使用，請稍後再試。"))

@handler.add(FollowEvent)
def handle_follow_event(event):
    """處理用戶第一次加入 Bot 的事件"""
    try:
        user_id = event.source.user_id
        current_app.logger.info(f"新用戶加入: {user_id}")
        
        # 建立或獲取用戶資料
        user_name = UserService.get_or_create_user(user_id)
        
        # 發送歡迎訊息
        welcome_text = f"🎉 歡迎加入家庭健康小幫手，{user_name}！\n\n為了提供您更完整的個人化服務，建議您先完成身份驗證。"
        
        # 建立登入卡片
        from flask import url_for
        login_url = url_for('auth.login', _external=True)
        login_card = flex_settings.create_login_card(login_url)
        
        # 發送歡迎訊息和登入卡片
        messages = [
            TextSendMessage(text=welcome_text),
            FlexSendMessage(alt_text="會員登入", contents=login_card)
        ]
        
        line_bot_api.reply_message(event.reply_token, messages)
        current_app.logger.info(f"已向新用戶 {user_name} ({user_id}) 發送歡迎訊息和登入卡片")
        
    except Exception as e:
        current_app.logger.error(f"處理新用戶加入事件錯誤: {e}")
        # 如果發生錯誤，至少發送基本歡迎訊息
        try:
            line_bot_api.reply_message(
                event.reply_token, 
                TextSendMessage(text="🎉 歡迎加入家庭健康小幫手！\n\n請輸入「選單」查看所有功能。")
            )
        except Exception as fallback_error:
            current_app.logger.error(f"發送備用歡迎訊息也失敗: {fallback_error}")

@handler.add(PostbackEvent)
def handle_postback_dispatcher(event):
    from urllib.parse import parse_qs, unquote
    
    data_str = event.postback.data
    
    if data_str.startswith('relation:'):
        family_handler.handle(event)
        return
    
    try:
        data = parse_qs(unquote(data_str))
        action = data.get('action', [None])[0]
    except (ValueError, IndexError, AttributeError):
        action = None
        
    if not action:
        current_app.logger.warning(f"收到一個無法解析的 Postback data: {data_str}")
        return

    if action == 'start_scan_flow':
        reply_message = flex_prescription.create_management_menu(
            title="📋 藥單辨識管理",
            primary_action_label="📲 掃描新藥單",
            primary_action_data="action=initiate_scan_process"
        )
        line_bot_api.reply_message(event.reply_token, reply_message)
        return
        
    if action == 'start_query_flow':
        reply_message = flex_prescription.create_management_menu(
            title="📂 藥歷查詢管理",
            primary_action_label="🔍 開始查詢藥歷",
            primary_action_data="action=initiate_query_process"
        )
        line_bot_api.reply_message(event.reply_token, reply_message)
        return

    prescription_actions = [
        'initiate_scan_process', 'initiate_query_process',
        'select_patient_for_scan', 'start_camera', 'manual_edit_liff', 'provide_visit_date', 
        'confirm_save_final', 'list_records', 'view_record_details', 
        'confirm_delete_record', 'execute_delete_record', 'load_record_as_draft', 'cancel_task'
    ]
    family_actions = [
        'gen_code', 'confirm_bind', 'manage_family', 'cancel_bind',
        'edit_nickname', 'delete_binding'
    ]
    reminder_actions = [
        'confirm_delete_reminder', 'execute_delete_reminder', 'clear_reminders_for_member',
        'add_member_profile', 'delete_member_profile_confirm', 'view_existing_reminders',
        'add_from_prescription', 'rename_member_profile', 'execute_delete_member_profile'
    ]
    pill_actions = [
        'select_model_mode', 'use_single_model', 'show_model_info', 'back_to_model_menu',
        'get_pill_info'
    ]
    settings_actions = [
        'login_settings', 'show_instructions'
    ]
    
    if action in prescription_actions:
        prescription_handler.handle(event)
    elif action in family_actions:
        family_handler.handle(event)
    elif action in reminder_actions:
        reminder_handler.handle(event)
    elif action in pill_actions:
        try:
            from .handlers import pill_handler as ph
            if ph:
                ph.handle(event)
            else:
                current_app.logger.warning("pill_handler 不可用")
        except ImportError:
            current_app.logger.error("无法导入 pill_handler")
    elif action in settings_actions:
        handle_settings_postback(event, action)
    else:
        current_app.logger.warning(f"收到一个未知的 Postback action: {action}")

def handle_settings_postback(event, action):
    """處理設定相關的 postback 事件"""
    try:
        if action == 'login_settings':
            from flask import url_for
            login_url = url_for('auth.login', _external=True)
            login_card = flex_settings.create_login_card(login_url)
            flex_message = FlexSendMessage(alt_text="會員登入", contents=login_card)
            line_bot_api.reply_message(event.reply_token, flex_message)
            
        elif action == 'show_instructions':
            instructions_card = flex_settings.create_instructions_card()
            flex_message = FlexSendMessage(alt_text="使用說明", contents=instructions_card)
            line_bot_api.reply_message(event.reply_token, flex_message)
            
    except Exception as e:
        current_app.logger.error(f"設定 postback 處理錯誤: {e}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="設定功能發生錯誤，請稍後再試。"))