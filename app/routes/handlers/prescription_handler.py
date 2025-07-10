# --- 修正後的 app/routes/handlers/prescription_handler.py ---

from flask import current_app
from linebot.models import TextSendMessage, ImageMessage
from urllib.parse import parse_qs, unquote
import time
import traceback
import base64
from app import line_bot_api

from app.services.user_service import UserService
from app.services import prescription_service
from app.utils.flex import prescription as flex_prescription, general as flex_general
from app.utils.db import DB

def start_loading_animation(user_id, seconds=10):
    """启动 LINE Chat Loading 动画"""
    try:
        import requests
        from flask import current_app
        
        loading_url = "https://api.line.me/v2/bot/chat/loading/start"
        headers = {
            "Authorization": f"Bearer {current_app.config['LINE_CHANNEL_ACCESS_TOKEN']}",
            "Content-Type": "application/json"
        }
        data = {
            "chatId": user_id,
            "loadingSeconds": min(max(seconds, 10), 60)
        }
        
        response = requests.post(loading_url, headers=headers, json=data)
        if response.status_code == 202:
            print(f"✅ 已為用戶 {user_id} 啟動藥單分析載入動畫")
        else:
            print(f"⚠️ 藥單分析載入動畫啟動失敗: {response.status_code}")
    except Exception as e:
        print(f"❌ 藥單分析載入動畫啟動異常: {e}")

def _reply_message(reply_token, messages):
    if not isinstance(messages, list):
        messages = [messages]
    line_bot_api.reply_message(reply_token, messages)

def handle(event):
    """藥單處理器的主入口函式"""
    user_id = event.source.user_id
    
    print(f"🔍 [PrescriptionHandler] handle 被調用 - 事件類型: {event.type}")
    
    if event.type == 'postback':
        handle_postback(event, user_id)
    elif event.type == 'message':
        if isinstance(event.message, ImageMessage):
            handle_image_message(event, user_id)
        else:
            handle_text_message(event, user_id)

def handle_postback(event, user_id):
    """處理藥單流程中的 Postback 事件"""
    data = parse_qs(unquote(event.postback.data))
    action = data.get('action', [None])[0]
    reply_token = event.reply_token
    
    if action == 'initiate_scan_process':
        UserService.clear_user_complex_state(user_id)
        members = UserService.get_user_members(user_id)
        _reply_message(reply_token, flex_prescription.create_patient_selection_message(members, 'scan'))
        return

    if action == 'initiate_query_process':
        UserService.clear_user_complex_state(user_id)
        members = UserService.get_user_members(user_id)
        _reply_message(reply_token, flex_prescription.create_patient_selection_message(members, 'query'))
        return

    if action == 'select_patient_for_scan':
        member_name = data.get('member', [None])[0]
        if member_name:
            state = {"state_info": {"state": "AWAITING_IMAGE"}, "last_task": {"member": member_name}}
            UserService.set_user_complex_state(user_id, state)
            
            # 恢復原本的拍照方式選擇，並添加 taskId 參數
            from linebot.models import QuickReply, QuickReplyButton, CameraAction, URIAction
            import time
            task_id = f"task_{int(time.time())}"
            
            # 更新狀態包含 task_id
            state["last_task"]["task_id"] = task_id
            UserService.set_user_complex_state(user_id, state)
            
            # 修正 LIFF URL 格式，使用正確的查詢參數格式
            liff_url = f"https://liff.line.me/{current_app.config['LIFF_ID_CAMERA']}?taskId={task_id}"
            
            quick_reply = QuickReply(items=[
                QuickReplyButton(action=CameraAction(label="📸 開啟相機拍照")),
                QuickReplyButton(action=URIAction(label="📤 上傳圖片", uri=liff_url))
            ])
            
            _reply_message(reply_token, TextSendMessage(
                text=f"為「{member_name}」掃描藥單\n\n📋 上傳藥單照片須知：\n請選擇拍照方式：",
                quick_reply=quick_reply
            ))
        return

    if action == 'start_camera':
        # 重新拍照功能 - 重新顯示拍照選項
        state = UserService.get_user_complex_state(user_id)
        member_name = state.get("last_task", {}).get("member", "")
        
        if member_name:
            # 重新生成 task_id 和拍照選項
            import time
            task_id = f"task_{int(time.time())}"
            
            # 更新狀態
            state["state_info"] = {"state": "AWAITING_IMAGE"}
            state["last_task"]["task_id"] = task_id
            UserService.set_user_complex_state(user_id, state)
            
            # 重新顯示拍照選項
            from linebot.models import QuickReply, QuickReplyButton, CameraAction, URIAction
            liff_url = f"https://liff.line.me/{current_app.config['LIFF_ID_CAMERA']}?taskId={task_id}"
            
            quick_reply = QuickReply(items=[
                QuickReplyButton(action=CameraAction(label="📸 開啟相機拍照")),
                QuickReplyButton(action=URIAction(label="📤 上傳圖片", uri=liff_url))
            ])
            
            _reply_message(reply_token, TextSendMessage(
                text=f"為「{member_name}」重新掃描藥單\n\n📋 上傳藥單照片須知：\n請選擇拍照方式：",
                quick_reply=quick_reply
            ))
        else:
            _reply_message(reply_token, TextSendMessage(text="找不到成員資訊，請重新開始。"))
        return

    if action == 'manual_edit_liff':
        try:
            liff_url = f"https://liff.line.me/{current_app.config['LIFF_ID_EDIT']}"
            from app.utils.flex.general import create_liff_button
            _reply_message(reply_token, create_liff_button("✏️ 手動編輯", liff_url, "開啟編輯頁面"))
        except Exception as e:
            print(f"開啟編輯頁面時發生錯誤: {e}")
            UserService.clear_user_complex_state(user_id)
            _reply_message(reply_token, TextSendMessage(text="開啟編輯頁面失敗，請稍後再試。"))
        return

    if action == 'provide_visit_date':
        visit_date = data.get('visit_date', [None])[0]
        if visit_date:
            try:
                state = UserService.get_user_complex_state(user_id)
                if 'last_task' in state and 'results' in state['last_task']:
                    state['last_task']['results']['visit_date'] = visit_date
                    UserService.set_user_complex_state(user_id, state)
                    _reply_message(reply_token, TextSendMessage(text=f"✅ 看診日期已設定為：{visit_date}\n\n請繼續完成儲存流程。"))
                else:
                    _reply_message(reply_token, TextSendMessage(text="❌ 找不到分析結果，請重新開始。"))
            except Exception as e:
                print(f"設定看診日期時發生錯誤: {e}")
                _reply_message(reply_token, TextSendMessage(text="設定日期失敗，請稍後再試。"))
        return

    if action == 'confirm_save_final':
        try:
            status, mm_id, is_update = prescription_service.PrescriptionService.save_prescription_from_state(user_id)
            if status == "SUCCESS":
                action_text = "更新" if is_update else "新增"
                
                # 詢問是否要設定批量提醒
                from linebot.models import QuickReply, QuickReplyButton, URIAction, MessageAction
                liff_reminder_url = f"https://liff.line.me/{current_app.config['LIFF_ID_PRESCRIPTION_REMINDER']}?mm_id={mm_id}"
                
                quick_reply = QuickReply(items=[
                    QuickReplyButton(action=URIAction(label="🔔 設定用藥提醒", uri=liff_reminder_url)),
                    QuickReplyButton(action=MessageAction(label="⏭️ 跳過，結束流程", text="跳過提醒設定")),
                    QuickReplyButton(action=MessageAction(label="📂 查看藥歷", text="查詢個人藥歷"))
                ])
                
                _reply_message(reply_token, TextSendMessage(
                    text=f"✅ 藥歷{action_text}成功！\n\n💡 接下來您可以為這些藥物設定用藥提醒，確保按時服藥：",
                    quick_reply=quick_reply
                ))
            elif status == "AWAITING_VISIT_DATE":
                _reply_message(reply_token, TextSendMessage(text="❌ 缺少看診日期，請提供正確的日期格式。"))
            else:
                _reply_message(reply_token, TextSendMessage(text="❌ 儲存失敗，請稍後再試。"))
        except Exception as e:
            print(f"儲存藥歷時發生錯誤: {e}")
            UserService.clear_user_complex_state(user_id)
            _reply_message(reply_token, TextSendMessage(text=f"儲存失敗：{str(e)}"))
        return

    if action == 'list_records':
        member_name = data.get('member', [None])[0]
        if member_name:
            records = DB.get_records_by_member(user_id, member_name)
            _reply_message(reply_token, flex_prescription.create_records_carousel(member_name, records))
        return

    if action in ['view_record_details', 'confirm_delete_record', 'execute_delete_record', 'load_record_as_draft']:
        handle_record_management(event, user_id, action, data)
        return

    if action == 'cancel_task':
        state = UserService.get_user_complex_state(user_id)
        if state:
            task_info = state.get("last_task", {})
            member_name = task_info.get("member", "")
            if member_name:
                UserService.set_user_complex_state(user_id, {"last_task": {"member": member_name}})
            else:
                UserService.clear_user_complex_state(user_id)
        _reply_message(reply_token, TextSendMessage(text="操作已取消。"))
        return

def handle_message(event, user_id):
    """處理藥單流程中的 Message 事件"""
    if not isinstance(event.message, (ImageMessage, TextSendMessage)):
        return

    if isinstance(event.message, ImageMessage):
        handle_image_upload(event, user_id)
    elif hasattr(event.message, 'text'):
        handle_text_message(event, user_id)

def handle_image_upload(event, user_id):
    """處理圖片上傳"""
    try:
        # 啟動載入動畫
        start_loading_animation(user_id, seconds=60)
        message_content = line_bot_api.get_message_content(event.message.id)
        image_bytes = message_content.content
        
        state = UserService.get_user_complex_state(user_id)
        if not state or state.get("state_info", {}).get("state") != "AWAITING_IMAGE":
            _reply_message(event.reply_token, TextSendMessage(text="目前不在圖片上傳流程中，請先選擇「掃描新藥單」。"))
            return

        task_id = f"task_{int(time.time())}"
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        
        state["last_task"]["task_id"] = task_id
        state["last_task"]["image_bytes_list"] = [image_b64]
        state["state_info"]["state"] = "IMAGE_UPLOADED"
        UserService.set_user_complex_state(user_id, state)

        # 直接執行分析並回覆結果，不需要額外步驟
        try:
            # 1. 觸發分析 (此為同步操作，會等待結果)
            prescription_service.PrescriptionService.trigger_analysis(user_id, task_id)
            
            # 2. 重新獲取更新後的狀態
            updated_state = UserService.get_user_complex_state(user_id)
            results = updated_state.get('last_task', {}).get('results')
            if not results:
                raise RuntimeError("分析已執行，但無法從狀態中獲取結果。")

            # 3. 驗證分析結果的合理性
            if not validate_analysis_result(results):
                _reply_message(event.reply_token, TextSendMessage(
                    text="⚠️ 檢測到的內容可能不準確。\n\n請確認您拍攝的是清晰的藥單照片，並重新嘗試。"
                ))
                return

            # 4. 準備 Flex Message
            freq_map_list = DB.get_frequency_map()
            frequency_map = {item['frequency_code']: item for item in freq_map_list}
            liff_edit_id = current_app.config['LIFF_ID_EDIT']
            liff_reminder_id = current_app.config['LIFF_ID_PRESCRIPTION_REMINDER']
            member_name = updated_state.get('last_task', {}).get('member', '')

            messages = flex_prescription.generate_analysis_report_messages(
                results, frequency_map, liff_edit_id, liff_reminder_id, member_name
            )

            # 5. 使用 Reply API 發送結果
            _reply_message(event.reply_token, messages)
            
        except Exception as analysis_error:
            print(f"執行同步分析時發生嚴重錯誤: {analysis_error}")
            traceback.print_exc()
            UserService.clear_user_complex_state(user_id)
            _reply_message(event.reply_token, TextSendMessage(text=f"分析失敗，請稍後再試一次。\n錯誤：{analysis_error}"))

    except Exception as e:
        print(f"處理圖片上傳時發生錯誤: {e}")
        traceback.print_exc()
        UserService.clear_user_complex_state(user_id)
        _reply_message(event.reply_token, TextSendMessage(text="圖片處理失敗，請稍後再試。"))

def handle_text_message(event, user_id):
    """處理文字訊息，特別是來自 LIFF 的分析請求"""
    text = event.message.text.strip()
    reply_token = event.reply_token

    # 處理來自 LIFF 的上傳成功訊息，改為同步分析並直接回覆
    print(f"🔍 [PrescriptionHandler] 檢查訊息匹配 - 文字: '{text}'")
    print(f"🔍 [PrescriptionHandler] 包含'照片上傳成功': {'照片上傳成功' in text}")
    print(f"🔍 [PrescriptionHandler] 包含'正在分析中': {'正在分析中' in text}")
    
    if "照片上傳成功" in text and "正在分析中" in text:
        # 1. 啟動載入動畫
        start_loading_animation(user_id, seconds=60)
        
        # 2. 同步執行分析並直接回覆結果
        try:
            # 獲取任務ID（從狀態中）
            state = UserService.get_user_complex_state(user_id)
            task_id = state.get("last_task", {}).get("task_id")
            
            print(f"🔍 開始處理藥單分析 - 用戶: {user_id}, 任務ID: {task_id}")
            
            if not task_id:
                print(f"❌ 找不到任務ID - 用戶: {user_id}")
                _reply_message(reply_token, TextSendMessage(text="❌ 找不到任務ID，請重新操作。"))
                return
            
            # 執行同步分析
            print(f"🔄 開始執行同步分析 - 任務ID: {task_id}")
            prescription_service.PrescriptionService.trigger_analysis(user_id, task_id)
            print(f"✅ 同步分析完成 - 任務ID: {task_id}")
            
            # 獲取分析結果
            updated_state = UserService.get_user_complex_state(user_id)
            results = updated_state.get('last_task', {}).get('results')
            
            print(f"📊 分析結果狀態 - 有結果: {bool(results)}")
            if results:
                print(f"📋 結果內容預覽: {str(results)[:200]}...")
            
            if results:
                # 驗證分析結果
                if not validate_analysis_result(results):
                    _reply_message(reply_token, TextSendMessage(
                        text="⚠️ 檢測到的內容可能不準確。\n\n請確認您上傳的是清晰的藥單照片，並重新嘗試。"
                    ))
                    return
                
                # 準備分析結果訊息
                freq_map_list = DB.get_frequency_map()
                frequency_map = {item['frequency_code']: item for item in freq_map_list}
                liff_edit_id = current_app.config['LIFF_ID_EDIT']
                liff_reminder_id = current_app.config['LIFF_ID_PRESCRIPTION_REMINDER']
                member_name = state.get('last_task', {}).get('member_name', '')
                
                messages = flex_prescription.generate_analysis_report_messages(
                    results, frequency_map, liff_edit_id, liff_reminder_id, member_name, 
                    is_direct_view=False, source=""
                )
                
                # 直接用 reply_message 發送結果
                _reply_message(reply_token, messages)
                print(f"✅ 藥單分析完成並已用 Reply 發送結果給用戶 {user_id}")
                
            else:
                _reply_message(reply_token, TextSendMessage(text="❌ 分析過程中發生錯誤，請重新上傳照片。"))
                print(f"❌ 藥單分析失敗，已通知用戶 {user_id}")
                
        except Exception as e:
            print(f"❌ 藥單分析處理失敗: {e}")
            traceback.print_exc()
            _reply_message(reply_token, TextSendMessage(text="❌ 分析過程中發生錯誤，請重新上傳照片。"))
        
        return
    
    # 處理預覽手動修改結果的訊息
    if text == "📝 預覽手動修改結果":
        print(f"🔍 處理預覽手動修改結果 - 用戶: {user_id}")
        try:
            # 獲取用戶狀態
            state = UserService.get_user_complex_state(user_id)
            task_info = state.get("last_task", {})
            results = task_info.get("results")
            
            print(f"📊 用戶狀態 - 有結果: {bool(results)}")
            if results:
                print(f"📋 結果內容預覽: {str(results)[:200]}...")
            
            if results:
                # 準備分析結果訊息
                freq_map_list = DB.get_frequency_map()
                frequency_map = {item['frequency_code']: item for item in freq_map_list}
                liff_edit_id = current_app.config['LIFF_ID_EDIT']
                liff_reminder_id = current_app.config['LIFF_ID_PRESCRIPTION_REMINDER']
                member_name = task_info.get('member', '')
                
                messages = flex_prescription.generate_analysis_report_messages(
                    results, frequency_map, liff_edit_id, liff_reminder_id, member_name, 
                    is_direct_view=False, source="manual_edit"
                )
                
                # 發送預覽結果
                _reply_message(reply_token, messages)
                print(f"✅ 手動修改預覽完成並已發送結果給用戶 {user_id}")
                
            else:
                _reply_message(reply_token, TextSendMessage(text="❌ 找不到修改後的資料，請重新操作。"))
                print(f"❌ 找不到修改後的資料 - 用戶: {user_id}")
                
        except Exception as e:
            print(f"❌ 處理手動修改預覽失敗: {e}")
            traceback.print_exc()
            _reply_message(reply_token, TextSendMessage(text="❌ 預覽過程中發生錯誤，請稍後再試。"))
        
        return
    
    # 處理跳過提醒設定的訊息
    if text == "跳過提醒設定":
        _reply_message(reply_token, TextSendMessage(text="✅ 藥歷儲存完成！\n\n您可以隨時到「用藥提醒管理」為藥物設定提醒。"))
        return

def validate_analysis_result(results):
    """驗證分析結果的合理性"""
    if not results or not isinstance(results, dict):
        return False
    
    # 安全取得各項資訊
    clinic_name = results.get('clinic_name') or ''
    clinic_name = clinic_name.strip() if clinic_name else ''
    
    doctor_name = results.get('doctor_name') or ''
    doctor_name = doctor_name.strip() if doctor_name else ''
    
    visit_date = results.get('visit_date') or ''
    medications = results.get('medications', [])
    
    # 1. 檢查是否為已知的記憶幻覺模式
    suspicious_clinics = ['佑民醫療社團法人佑民醫院', '佑民醫院']
    if clinic_name in suspicious_clinics:
        print(f"[驗證] 拒絕：檢測到疑似記憶幻覺 - {clinic_name}")
        return False
    
    # 2. 檢查是否完全沒有醫療相關資訊
    has_medical_info = any([
        clinic_name,      # 醫療機構名稱
        doctor_name,      # 醫師姓名  
        visit_date,       # 看診日期
        medications       # 藥物資訊
    ])
    
    if not has_medical_info:
        print("[驗證] 拒絕：完全沒有醫療相關資訊")
        return False
    
    print(f"[驗證] 通過：診所={clinic_name or '無'}, 醫師={doctor_name or '無'}, 藥物={len(medications)}種")
    return True

def execute_synchronous_analysis(user_id, reply_token):
    """執行同步分析並回傳結果"""
    try:
        state = UserService.get_user_complex_state(user_id)
        task_id = state.get("last_task", {}).get("task_id")
        if not task_id:
            raise ValueError("任務 ID 遺失，無法開始分析。")
        
        # 1. 觸發分析 (此為同步操作，會等待結果)
        prescription_service.PrescriptionService.trigger_analysis(user_id, task_id)
        
        # 2. 重新獲取更新後的狀態
        state = UserService.get_user_complex_state(user_id)
        results = state.get('last_task', {}).get('results')
        if not results:
            raise RuntimeError("分析已執行，但無法從狀態中獲取結果。")

        # 3. 準備 Flex Message
        freq_map_list = DB.get_frequency_map()
        frequency_map = {item['frequency_code']: item for item in freq_map_list}
        liff_edit_id = current_app.config['LIFF_ID_EDIT']
        liff_reminder_id = current_app.config['LIFF_ID_PRESCRIPTION_REMINDER']
        member_name = state.get('last_task', {}).get('member', '')

        messages = flex_prescription.generate_analysis_report_messages(
            results, frequency_map, liff_edit_id, liff_reminder_id, member_name
        )

        # 4. 使用 Reply API 發送結果
        _reply_message(reply_token, messages)

    except Exception as e:
        print(f"執行同步分析時發生嚴重錯誤: {e}")
        traceback.print_exc()
        UserService.clear_user_complex_state(user_id)
        _reply_message(reply_token, TextSendMessage(text=f"分析失敗，請稍後再試一次。\n錯誤：{e}"))

def validate_analysis_result(results):
    """驗證 AI 分析結果的合理性，防止記憶幻覺"""
    if not results or not isinstance(results, dict):
        return False
    
    # 安全取得各項資訊
    clinic_name = results.get('clinic_name') or ''
    clinic_name = clinic_name.strip() if clinic_name else ''
    
    doctor_name = results.get('doctor_name') or ''
    doctor_name = doctor_name.strip() if doctor_name else ''
    
    visit_date = results.get('visit_date') or ''
    medications = results.get('medications', [])
    
    # 1. 檢查是否為已知的記憶幻覺模式
    suspicious_clinics = ['佑民醫療社團法人佑民醫院', '佑民醫院']
    if clinic_name in suspicious_clinics:
        print(f"[驗證] 拒絕：檢測到疑似記憶幻覺 - {clinic_name}")
        return False
    
    # 2. 檢查是否完全沒有醫療相關資訊（方案 C）
    has_medical_info = any([
        clinic_name,      # 醫療機構名稱
        doctor_name,      # 醫師姓名  
        visit_date,       # 看診日期
        medications       # 藥物資訊
    ])
    
    if not has_medical_info:
        print("[驗證] 拒絕：完全沒有醫療相關資訊")
        return False
    
    print(f"[驗證] 通過：診所={clinic_name or '無'}, 醫師={doctor_name or '無'}, 藥物={len(medications)}種")
    return True

def handle_record_management(event, user_id, action, data):
    """處理藥歷記錄管理相關操作"""
    reply_token = event.reply_token
    
    if action == 'view_record_details':
        mm_id = int(data.get('mm_id', [0])[0])
        record = prescription_service.PrescriptionService.get_prescription_details(mm_id)
        if record:
            # 使用現有的分析報告生成函數來顯示藥歷詳情
            freq_map_list = DB.get_frequency_map()
            frequency_map = {item['frequency_code']: item for item in freq_map_list}
            liff_edit_id = current_app.config['LIFF_ID_EDIT']
            liff_reminder_id = current_app.config['LIFF_ID_PRESCRIPTION_REMINDER']
            member_name = record.get('member', '')
            
            messages = flex_prescription.generate_analysis_report_messages(
                record, frequency_map, liff_edit_id, liff_reminder_id, member_name, 
                is_direct_view=True, source=""
            )
            _reply_message(reply_token, messages)
        else:
            _reply_message(reply_token, TextSendMessage(text="❌ 找不到該筆記錄。"))
    
    elif action == 'confirm_delete_record':
        mm_id = data.get('mm_id', [None])[0]
        _reply_message(reply_token, flex_general.create_simple_confirmation(
            alt_text="確認刪除記錄", title="⚠️ 確定要刪除？", text="您確定要刪除這筆藥歷記錄嗎？此操作無法復原！",
            confirm_label="是，刪除", confirm_data=f"action=execute_delete_record&mm_id={mm_id}"
        ))
    
    elif action == 'execute_delete_record':
        mm_id = int(data.get('mm_id', [0])[0])
        if DB.delete_record_by_mm_id(user_id, mm_id):
            _reply_message(reply_token, TextSendMessage(text="✅ 記錄已成功刪除。"))
        else:
            _reply_message(reply_token, TextSendMessage(text="❌ 刪除失敗，找不到記錄或權限不足。"))
    
    elif action == 'load_record_as_draft':
        mm_id = int(data.get('mm_id', [0])[0])
        try:
            # 載入歷史記錄為草稿
            success = prescription_service.PrescriptionService.load_record_as_draft(user_id, mm_id)
            if success:
                # 載入成功後開啟編輯頁面
                liff_url = f"https://liff.line.me/{current_app.config['LIFF_ID_EDIT']}"
                from app.utils.flex.general import create_liff_button
                _reply_message(reply_token, create_liff_button("✏️ 開始編輯", liff_url, "歷史記錄已載入為草稿"))
            else:
                _reply_message(reply_token, TextSendMessage(text="❌ 載入記錄失敗，找不到記錄或權限不足。"))
        except Exception as e:
            current_app.logger.error(f"載入記錄為草稿時發生錯誤: {e}")
            _reply_message(reply_token, TextSendMessage(text="❌ 載入記錄時發生錯誤，請稍後再試。"))

def handle_image_message(event, user_id):
    """處理直接上傳的圖片訊息，進行藥單辨識"""
    from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, MessagingApiBlob
    from config import Config
    import io
    from PIL import Image
    
    reply_token = event.reply_token
    message_id = event.message.id
    
    try:
        # 啟動載入動畫
        start_loading_animation(user_id, 30)
        
        # 下載圖片
        configuration = Configuration(access_token=Config.LINE_CHANNEL_ACCESS_TOKEN)
        line_bot_blob_api = MessagingApiBlob(ApiClient(configuration))
        
        print(f"📷 [藥單辨識] 開始下載圖片 (Message ID: {message_id})")
        message_content = line_bot_blob_api.get_message_content(message_id=message_id)
        image_bytes = message_content if isinstance(message_content, bytes) else b"".join(message_content.iter_content())
        
        if not image_bytes:
            raise ValueError("下載的圖片內容為空")
        
        # 轉換為 PIL Image
        img_pil = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        print(f"📷 [藥單辨識] 圖片下載完成，大小: {img_pil.size}")
        
        # 調用 AI 分析
        from app.services.ai_processor import run_analysis
        
        db_config = {
            'host': Config.DB_HOST,
            'user': Config.DB_USER,
            'password': Config.DB_PASSWORD,
            'database': Config.DB_NAME,
            'port': Config.DB_PORT
        }
        
        print(f"🤖 [藥單辨識] 開始 AI 分析...")
        analysis_result, usage_info = run_analysis([image_bytes], db_config, Config.GEMINI_API_KEY)
        
        if not analysis_result:
            _reply_message(reply_token, TextSendMessage(text="❌ 藥單分析失敗，請確認圖片清晰度並重試。"))
            return
        
        print(f"✅ [藥單辨識] AI 分析完成")
        
        # 儲存分析結果到狀態中
        import time
        task_id = f"direct_{user_id[:8]}_{int(time.time())}"
        
        # 建立任務狀態
        task_info = {
            "task_id": task_id,
            "line_user_id": user_id,
            "member": "本人",  # 直接上傳預設為本人
            "status": "completed",
            "results": analysis_result,
            "image_bytes_list": [base64.b64encode(image_bytes).decode('utf-8')],
            "source": "direct_upload"
        }
        
        # 儲存到用戶狀態
        full_state = {
            "last_task": task_info
        }
        UserService.set_user_complex_state(user_id, full_state)
        
        # 生成預覽訊息
        medications = analysis_result.get('medications', [])
        clinic_name = analysis_result.get('clinic_name', '未知診所')
        visit_date = analysis_result.get('visit_date', '未知日期')
        
        # 獲取頻率對照表並轉換為字典格式
        frequency_list = DB.get_frequency_map()
        frequency_map = {item['frequency_code']: item for item in frequency_list} if frequency_list else {}
        
        # 使用現有的分析報告生成方法
        preview_messages = flex_prescription.generate_analysis_report_messages(
            analysis_result=analysis_result,
            frequency_map=frequency_map,
            liff_edit_id=Config.LIFF_ID_EDIT,
            liff_reminder_id=Config.LIFF_ID_PRESCRIPTION_REMINDER,
            member_name="本人",  # 直接上傳預設為本人
            is_direct_view=False,
            source=""
        )
        
        # 添加成功訊息
        success_message = TextSendMessage(
            text=f"🎉 藥單分析完成！\n\n📋 診所：{clinic_name}\n📅 日期：{visit_date}\n💊 識別到 {len(medications)} 種藥物"
        )
        
        # 合併所有訊息
        all_messages = [success_message] + preview_messages
        _reply_message(reply_token, all_messages)
        
        print(f"✅ [藥單辨識] 處理完成，任務ID: {task_id}")
        
    except Exception as e:
        current_app.logger.error(f"處理圖片訊息時發生錯誤: {e}")
        traceback.print_exc()
        _reply_message(reply_token, TextSendMessage(text="❌ 處理圖片時發生錯誤，請稍後再試。"))