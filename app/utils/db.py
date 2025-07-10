# app/utils/db.py

from datetime import datetime, timedelta, timezone, date
import json
import os
import pymysql
from flask import g
from zoneinfo import ZoneInfo
import random
import string
import time

# --- 資料庫連線管理 ---

def get_db_connection():
    """從 Flask 的 g 物件取得資料庫連線，若不存在則建立一個。"""
    try:
        if 'db' not in g:
            g.db = pymysql.connect(
                host=os.environ.get('DB_HOST'),
                user=os.environ.get('DB_USER'),
                password=os.environ.get('DB_PASS'),
                database=os.environ.get('DB_NAME'),
                port=int(os.environ.get('DB_PORT', 3306)),
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=10
            )
        return g.db
    except pymysql.MySQLError as e:
        print(f"資料庫連線錯誤: {e}")
        return None

def close_db_connection(e=None):
    """關閉 g 物件中儲存的資料庫連線。"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_app(app):
    """註冊資料庫關閉函式到 Flask app。"""
    app.teardown_appcontext(close_db_connection)

# --- 資料庫操作類別 (整合雙方邏輯) ---

class DB:
    """一個包含所有資料庫操作靜態方法的類別。"""

    # --- 狀態 (State) 相關方法 ---
    # 來自組員的簡單 Key-Value 狀態管理
    @staticmethod
    def save_simple_state(user_id, state_value, minutes_to_expire=5):
        db = get_db_connection()
        if not db: return
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=minutes_to_expire)
        with db.cursor() as cursor:
            query = "REPLACE INTO state (recorder_id, state, expires_at) VALUES (%s, %s, %s)"
            cursor.execute(query, (user_id, state_value, expires_at))
            db.commit()

    @staticmethod
    def get_simple_state(user_id):
        db = get_db_connection()
        if not db: return None
        with db.cursor() as cursor:
            query = "SELECT state FROM state WHERE recorder_id=%s AND expires_at > UTC_TIMESTAMP()"
            cursor.execute(query, (user_id,))
            row = cursor.fetchone()
            return row['state'] if row else None
    
    @staticmethod
    def delete_simple_state(user_id):
        db = get_db_connection()
        if not db: return
        with db.cursor() as cursor:
            cursor.execute("DELETE FROM state WHERE recorder_id=%s", (user_id,))
            db.commit()

    # 來自您的複雜 JSON 狀態管理 (用於藥單分析流程)
    @staticmethod
    def get_complex_state(user_id):
        db = get_db_connection()
        if not db: return {"state_info": {}, "last_task": {}}
        with db.cursor() as cursor:
            cursor.execute("SELECT state_data FROM user_temp_state WHERE recorder_id = %s", (user_id,))
            record = cursor.fetchone()
            if record and record['state_data']:
                try:
                    return json.loads(record['state_data'])
                except (json.JSONDecodeError, TypeError):
                    return {"state_info": {}, "last_task": {}}
            return {"state_info": {}, "last_task": {}}

    @staticmethod
    def set_complex_state(user_id, state_data):
        db = get_db_connection()
        if not db: return
        with db.cursor() as cursor:
            # 使用自定义的 JSON 编码器来处理 date 类型
            from app import CustomJSONEncoder
            json_data = json.dumps(state_data, cls=CustomJSONEncoder)
            sql = "INSERT INTO user_temp_state (recorder_id, state_data) VALUES (%s, %s) ON DUPLICATE KEY UPDATE state_data = VALUES(state_data)"
            cursor.execute(sql, (user_id, json_data))
            db.commit()

    @staticmethod
    def clear_complex_state(user_id):
        db = get_db_connection()
        if not db: return
        with db.cursor() as cursor:
            cursor.execute("DELETE FROM user_temp_state WHERE recorder_id = %s", (user_id,))
            db.commit()

    # --- 使用者與成員管理 (整合) ---
    @staticmethod
    def get_or_create_user(user_id, user_name):
        db = get_db_connection()
        if not db: return None
        with db.cursor() as cursor:
            cursor.execute("SELECT recorder_id FROM users WHERE recorder_id = %s", (user_id,))
            if cursor.fetchone():
                return user_id
            cursor.execute(
                "INSERT INTO users (recorder_id, user_name) VALUES (%s, %s) ON DUPLICATE KEY UPDATE user_name = %s",
                (user_id, user_name, user_name)
            )
            db.commit()
            # 同時為新用戶建立一個 "本人" 的成員
            DB.add_member(user_id, "本人")
            return user_id

    @staticmethod
    def add_member(recorder_id, member_name, is_self=False, bound_user_id=None):
        """通用新增成員方法"""
        db = get_db_connection()
        if not db: return
        with db.cursor() as cursor:
            sql = "INSERT INTO members (recorder_id, member) VALUES (%s, %s) ON DUPLICATE KEY UPDATE member=VALUES(member)"
            cursor.execute(sql, (recorder_id, member_name))
            db.commit()

    @staticmethod
    def get_members(user_id):
        db = get_db_connection()
        if not db: return []
        with db.cursor() as cursor:
            query = "SELECT * FROM members WHERE recorder_id = %s ORDER BY created_at ASC"
            cursor.execute(query, (user_id,))
            return cursor.fetchall()

    @staticmethod
    def delete_member_by_name(user_id, member_name):
        """删除指定用户的指定成员"""
        db = get_db_connection()
        if not db: return 0
        with db.cursor() as cursor:
            query = "DELETE FROM members WHERE recorder_id = %s AND member = %s"
            cursor.execute(query, (user_id, member_name))
            db.commit()
            return cursor.rowcount

    @staticmethod
    def rename_member(user_id, old_name, new_name):
        """
        【邏輯強化】重命名成員，並同步更新所有關聯表。
        此操作在一個事務中完成，確保資料一致性。
        """
        db = get_db_connection()
        if not db: return 0
        try:
            with db.cursor() as cursor:
                # 步驟 1: 更新藥歷主表
                q1 = "UPDATE medication_main SET member = %s WHERE recorder_id = %s AND member = %s"
                cursor.execute(q1, (new_name, user_id, old_name))

                # 步驟 2: 更新用藥提醒表
                q2 = "UPDATE medicine_schedule SET member = %s WHERE recorder_id = %s AND member = %s"
                cursor.execute(q2, (new_name, user_id, old_name))
                
                # 步驟 3: 更新家人綁定關係表
                q3 = "UPDATE invitation_recipients SET relation_type = %s WHERE recorder_id = %s AND relation_type = %s"
                cursor.execute(q3, (new_name, user_id, old_name))

                # 步驟 4: 最後更新成員主表
                q4 = "UPDATE members SET member = %s WHERE recorder_id = %s AND member = %s"
                cursor.execute(q4, (new_name, user_id, old_name))
                rows_affected = cursor.rowcount

            db.commit()
            return rows_affected
        except pymysql.Error as e:
            db.rollback()
            print(f"重命名成員時發生資料庫錯誤: {e}")
            return 0
    @staticmethod
    def get_deletable_members(user_id):
        """
        【新增】獲取可刪除的提醒對象（僅限使用者手動建立，且非綁定關係的成員）。
        """
        db = get_db_connection()
        if not db: return []
        with db.cursor() as cursor:
            query = """
                SELECT m.* 
                FROM members m
                LEFT JOIN invitation_recipients ir ON m.recorder_id = ir.recorder_id AND m.member = ir.relation_type
                WHERE m.recorder_id = %s 
                AND m.member != '本人'
                AND ir.recipient_line_id IS NULL
            """
            cursor.execute(query, (user_id,))
            return cursor.fetchall()
            
    # --- 家人綁定 (來自組員) ---
    @staticmethod
    def get_inviter_by_code(code):
        db = get_db_connection()
        if not db: return None
        with db.cursor() as cursor:
            query = "SELECT recorder_id FROM state WHERE state=%s AND expires_at > UTC_TIMESTAMP()"
            cursor.execute(query, (code,))
            row = cursor.fetchone()
            return row['recorder_id'] if row else None
            
    @staticmethod
    def check_binding_exists(user1_id, user2_id):
        db = get_db_connection()
        if not db: return False
        with db.cursor() as cursor:
            # 检查是否已经在 invitation_recipients 表中建立绑定关系
            query = """
            SELECT COUNT(*) as count FROM invitation_recipients 
            WHERE (recorder_id = %s AND recipient_line_id = %s) 
               OR (recorder_id = %s AND recipient_line_id = %s)
            """
            cursor.execute(query, (user1_id, user2_id, user2_id, user1_id))
            result = cursor.fetchone()
            return result['count'] > 0 if result else False

    @staticmethod
    def add_family_binding(inviter_id, binder_id, binder_name, relation_type):
        """
        【邏輯強化】在 invitation_recipients 表中建立家人綁定關係，並同步在 members 表中建立記錄。
        """
        db = get_db_connection()
        if not db: return False
        try:
            with db.cursor() as cursor:
                # 步驟 1: 新增或更新邀請記錄
                sql_invite = """
                INSERT INTO invitation_recipients (recorder_id, recipient_line_id, recipient_name, relation_type)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE recipient_name=%s, relation_type=%s;
                """
                cursor.execute(sql_invite, (inviter_id, binder_id, binder_name, relation_type, binder_name, relation_type))
                
                # 步驟 2: 在邀請者的成員列表中新增被綁定者
                sql_member = "INSERT INTO members (recorder_id, member) VALUES (%s, %s) ON DUPLICATE KEY UPDATE member=VALUES(member)"
                cursor.execute(sql_member, (inviter_id, relation_type))

            db.commit()
            return True
        except Exception as e:
            db.rollback()
            print(f"建立家人綁定關係失敗: {e}")
            return False

    @staticmethod
    def get_existing_binding_info(user1_id, user2_id):
        """
        【新增】獲取兩個使用者之間的現有綁定資訊，用於豐富錯誤提示。
        """
        db = get_db_connection()
        if not db: return None
        with db.cursor() as cursor:
            query = """
                SELECT recorder_id, recipient_line_id, recipient_name, relation_type 
                FROM invitation_recipients 
                WHERE (recorder_id = %s AND recipient_line_id = %s) 
                   OR (recorder_id = %s AND recipient_line_id = %s)
            """
            cursor.execute(query, (user1_id, user2_id, user2_id, user1_id))
            return cursor.fetchone()
    @staticmethod
    def get_family_bindings(user_id):
        """获取用户的家人绑定关系"""
        db = get_db_connection()
        if not db: return []
        with db.cursor() as cursor:
            query = """
            SELECT ir.*, u.user_name as bound_user_name 
            FROM invitation_recipients ir
            LEFT JOIN users u ON ir.recipient_line_id = u.recorder_id
            WHERE ir.recorder_id = %s
            """
            cursor.execute(query, (user_id,))
            return cursor.fetchall()

    @staticmethod
    def delete_family_binding(user_id, recipient_id):
        """删除家人绑定关系"""
        db = get_db_connection()
        if not db: return 0
        with db.cursor() as cursor:
            query = "DELETE FROM invitation_recipients WHERE recorder_id = %s AND recipient_line_id = %s"
            cursor.execute(query, (user_id, recipient_id))
            db.commit()
            return cursor.rowcount

    # --- 藥單與藥歷 (來自您) ---
    @staticmethod
    def save_or_update_prescription(analysis_data, task_info, line_user_id):
        db = get_db_connection()
        if not db: raise pymysql.MySQLError("資料庫連線失敗")
        
        mm_id = None
        with db.cursor() as cursor:
            medications = analysis_data.get('medications', [])
            for med in medications:
                if not med.get('matched_drug_id') and (med.get('drug_name_zh') or med.get('drug_name_en')):
                    # 對於新辨識的藥物，不需要 drug_id
                    # 直接使用藥物名稱保存在個人藥歷中
                    # 不寫入全域 drug_info 資料庫，避免污染
                    med['matched_drug_id'] = None  # 設為 None，表示沒有對應的全域藥物ID
            
            recorder_id, member, clinic_name = line_user_id, task_info.get('member'), analysis_data.get('clinic_name')
            visit_date = analysis_data.get('visit_date')
            doctor_name = analysis_data.get('doctor_name')
            
            mm_id_to_update = task_info.get("mm_id_to_update")
            is_update = bool(mm_id_to_update)

            if is_update:
                mm_id = mm_id_to_update
                cursor.execute("UPDATE medication_main SET visit_date = %s, clinic_name = %s, doctor_name = %s WHERE mm_id = %s", (visit_date, clinic_name, doctor_name, mm_id))
                cursor.execute("DELETE FROM record_details WHERE record_id IN (SELECT mr_id FROM medication_records WHERE mm_id = %s)", (mm_id,))
                cursor.execute("DELETE FROM medication_records WHERE mm_id = %s", (mm_id,))
            else:
                # 使用 ON DUPLICATE KEY UPDATE 来处理重复记录
                sql_main = """
                INSERT INTO medication_main (recorder_id, member, clinic_name, visit_date, doctor_name) 
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    clinic_name = VALUES(clinic_name),
                    doctor_name = VALUES(doctor_name),
                    updated_at = NOW()
                """
                cursor.execute(sql_main, (recorder_id, member, clinic_name, visit_date, doctor_name))
                
                # 如果是更新操作，需要获取现有的 mm_id
                if cursor.rowcount == 2:  # ON DUPLICATE KEY UPDATE 执行时 rowcount 为 2
                    cursor.execute("SELECT mm_id FROM medication_main WHERE recorder_id = %s AND member = %s AND clinic_name = %s AND visit_date = %s AND doctor_name = %s", 
                                 (recorder_id, member, clinic_name, visit_date, doctor_name))
                    result = cursor.fetchone()
                    mm_id = result['mm_id'] if result else cursor.lastrowid
                    is_update = True  # 标记为更新操作
                    # 删除旧的药物记录
                    cursor.execute("DELETE FROM record_details WHERE record_id IN (SELECT mr_id FROM medication_records WHERE mm_id = %s)", (mm_id,))
                    cursor.execute("DELETE FROM medication_records WHERE mm_id = %s", (mm_id,))
                else:
                    mm_id = cursor.lastrowid
            
            if medications:
                days = int(analysis_data.get('days_supply')) if str(analysis_data.get('days_supply')).isdigit() else None
                source = "手動" if "manual" in task_info.get("source", "") else "藥單"
                
                for med in medications:
                    sql_rec = "INSERT INTO medication_records (mm_id, recorder_id, member, drug_name_en, drug_name_zh, source_detail, dose_quantity, days, frequency_count_code, frequency_timing_code) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                    cursor.execute(sql_rec, (mm_id, recorder_id, member, med.get('drug_name_en'), med.get('drug_name_zh'), source, med.get('dose_quantity'), days, med.get('frequency_count_code'), med.get('frequency_timing_code')))
                    mr_id = cursor.lastrowid

                    dose_str = str(med.get('dose_quantity', '')).strip()
                    parts = dose_str.split()
                    val, unit = (parts[0], ' '.join(parts[1:])) if len(parts) > 1 else (parts[0] if parts else '', '')
                    
                    sql_det = "INSERT INTO record_details (record_id, drug_id, dosage_value, dosage_unit, frequency_text) VALUES (%s, %s, %s, %s, %s)"
                    cursor.execute(sql_det, (mr_id, med.get('matched_drug_id'), val, unit, (med.get('frequency_text') or '')[:10]))

            db.commit()
            return mm_id, is_update

    @staticmethod
    def get_prescription_by_mm_id(mm_id):
        db = get_db_connection()
        if not db: return None
        with db.cursor() as cursor:
            cursor.execute("SELECT * FROM medication_main WHERE mm_id = %s", (mm_id,))
            main_record = cursor.fetchone()
            if not main_record: return None
            
            cursor.execute("SELECT * FROM medication_records WHERE mm_id = %s", (mm_id,))
            med_details = cursor.fetchall()
            
            for med in med_details:
                cursor.execute("SELECT drug_id, dosage_value, dosage_unit, frequency_text FROM record_details WHERE record_id = %s", (med.get('mr_id'),))
                detail = cursor.fetchone()
                if detail:
                    med['matched_drug_id'] = detail.get('drug_id')
                    if not med.get('dose_quantity'):
                        med['dose_quantity'] = f"{detail.get('dosage_value', '')} {detail.get('dosage_unit', '')}".strip()
                    med['frequency_text'] = med.get('frequency_text') or detail.get('frequency_text')
            
            result = main_record.copy()
            result['medications'] = med_details
            if med_details: result['days_supply'] = med_details[0].get('days')
            return result

    # --- 提醒 (Reminder) 相關 (來自組員) ---
    @staticmethod
    def create_reminder(data):
        # 整合組員的 create 和 update 邏輯
        db = get_db_connection()
        if not db: return None
        with db.cursor() as cursor:
            sql = """
            INSERT INTO medicine_schedule (
                recorder_id, member, drug_name, dose_quantity, notes,
                frequency_name, time_slot_1, time_slot_2, time_slot_3, time_slot_4, time_slot_5
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                dose_quantity = VALUES(dose_quantity), notes = VALUES(notes),
                frequency_name = VALUES(frequency_name), time_slot_1 = VALUES(time_slot_1), 
                time_slot_2 = VALUES(time_slot_2), time_slot_3 = VALUES(time_slot_3),
                time_slot_4 = VALUES(time_slot_4), time_slot_5 = VALUES(time_slot_5), 
                updated_at = NOW()
            """
            params = (
                data['recorder_id'], data['member'], data.get('drug_name'), data.get('dose_quantity'), data.get('notes'),
                data.get('frequency_name'), data.get('time_slot_1'), data.get('time_slot_2'), 
                data.get('time_slot_3'), data.get('time_slot_4'), data.get('time_slot_5')
            )
            cursor.execute(sql, params)
            db.commit()
            return cursor.lastrowid

    @staticmethod
    def get_reminders(user_id, member_name):
        """获取特定成员的提醒"""
        db = get_db_connection()
        if not db: return []
        with db.cursor() as cursor:
            query = "SELECT * FROM medicine_schedule WHERE recorder_id = %s AND member = %s"
            cursor.execute(query, (user_id, member_name))
            return cursor.fetchall()

    @staticmethod
    def check_reminder_ownership(reminder_id, user_id):
        """检查提醒是否属于指定用户"""
        db = get_db_connection()
        if not db: return False
        with db.cursor() as cursor:
            query = "SELECT COUNT(*) as count FROM medicine_schedule WHERE id = %s AND recorder_id = %s"
            cursor.execute(query, (reminder_id, user_id))
            result = cursor.fetchone()
            return result['count'] > 0 if result else False

    @staticmethod
    def get_reminder_by_id(reminder_id):
        """根据ID获取提醒详情"""
        db = get_db_connection()
        if not db: return None
        with db.cursor() as cursor:
            query = "SELECT * FROM medicine_schedule WHERE id = %s"
            cursor.execute(query, (reminder_id,))
            return cursor.fetchone()

    @staticmethod
    def delete_reminder(reminder_id):
        """删除指定提醒"""
        db = get_db_connection()
        if not db: return 0
        with db.cursor() as cursor:
            query = "DELETE FROM medicine_schedule WHERE id = %s"
            cursor.execute(query, (reminder_id,))
            db.commit()
            return cursor.rowcount

    @staticmethod
    def get_member_by_id(member_id):
        """根据ID获取成员信息"""
        db = get_db_connection()
        if not db: return None
        with db.cursor() as cursor:
            query = "SELECT * FROM members WHERE id = %s"
            cursor.execute(query, (member_id,))
            return cursor.fetchone()

    @staticmethod
    def delete_reminders_for_member(user_id, member_name):
        """删除指定成员的所有提醒"""
        db = get_db_connection()
        if not db: return 0
        with db.cursor() as cursor:
            query = "DELETE FROM medicine_schedule WHERE recorder_id = %s AND member = %s"
            cursor.execute(query, (user_id, member_name))
            db.commit()
            return cursor.rowcount

    @staticmethod
    def get_prescription_for_liff(mm_id):
        """为LIFF页面获取处方信息"""
        return DB.get_prescription_by_mm_id(mm_id)

    @staticmethod
    def create_reminders_batch(reminders_data):
        """批量创建提醒"""
        db = get_db_connection()
        if not db: return False
        try:
            with db.cursor() as cursor:
                for reminder in reminders_data:
                    DB.create_reminder(reminder)
                db.commit()
                return True
        except Exception as e:
            print(f"批量创建提醒失败: {e}")
            return False

    @staticmethod
    def get_records_by_member(user_id, member_name):
        """获取指定成员的药单记录"""
        db = get_db_connection()
        if not db: return []
        with db.cursor() as cursor:
            query = "SELECT * FROM medication_main WHERE recorder_id = %s AND member = %s ORDER BY created_at DESC"
            cursor.execute(query, (user_id, member_name))
            return cursor.fetchall()

    @staticmethod
    def delete_record_by_mm_id(user_id, mm_id):
        """删除指定的药单记录"""
        db = get_db_connection()
        if not db: return 0
        with db.cursor() as cursor:
            # 先检查所有权
            query = "SELECT COUNT(*) as count FROM medication_main WHERE mm_id = %s AND recorder_id = %s"
            cursor.execute(query, (mm_id, user_id))
            result = cursor.fetchone()
            if not result or result['count'] == 0:
                return 0
            
            # 删除相关记录
            cursor.execute("DELETE FROM record_details WHERE record_id IN (SELECT mr_id FROM medication_records WHERE mm_id = %s)", (mm_id,))
            cursor.execute("DELETE FROM medication_records WHERE mm_id = %s", (mm_id,))
            cursor.execute("DELETE FROM medication_main WHERE mm_id = %s", (mm_id,))
            db.commit()
            return cursor.rowcount

    # --- 藥物資料庫相關 (來自您) ---
    @staticmethod
    def get_all_drug_info():
        db = get_db_connection()
        if not db: return []
        with db.cursor() as cursor:
            cursor.execute("SELECT drug_id, drug_name_zh, drug_name_en, main_use, side_effects FROM drug_info")
            return cursor.fetchall()

    @staticmethod
    def get_frequency_map():
        db = get_db_connection()
        if not db: return []
        with db.cursor() as cursor:
            cursor.execute("SELECT frequency_code, frequency_name, times_per_day, timing_description FROM frequency_code")
            return cursor.fetchall()
    
    # --- 药丸辨识相关 (集成0705功能) ---
    @staticmethod
    def get_pills_details_by_ids(drug_ids):
        """从数据库查询多个药丸的详细信息"""
        if not drug_ids:
            return []
        
        db = get_db_connection()
        if not db:
            return []
            
        try:
            with db.cursor() as cursor:
                # 构建 IN 查询
                placeholders = ', '.join(['%s'] * len(drug_ids))
                sql = f"""
                    SELECT drug_id, drug_name_en, drug_name_zh, main_use, side_effects, 
                           shape, color, food_drug_interactions, image_url 
                    FROM drug_info WHERE drug_id IN ({placeholders})
                """
                
                cursor.execute(sql, drug_ids)
                results = cursor.fetchall()
                
                # 转换字段名以匹配0705的格式
                details_list = []
                for row in results:
                    details_list.append({
                        'drug_id': row.get('drug_id'),
                        'drug_name_en': row.get('drug_name_en'),
                        'drug_name_zh': row.get('drug_name_zh'),
                        'uses': row.get('main_use'),  # 将 main_use 映射为 uses
                        'side_effects': row.get('side_effects'),
                        'shape': row.get('shape'),
                        'color': row.get('color'),
                        'interactions': row.get('food_drug_interactions'),  # 映射字段名
                        'image_url': row.get('image_url')
                    })
                
                return details_list
                
        except Exception as e:
            print(f"查询药品信息失败: {e}")
            return []
    
    @staticmethod
    def get_pills_details_by_prefix(prefix):
        """根據藥品ID前綴查詢藥品詳細資訊"""
        if not prefix:
            return []
        
        db = get_db_connection()
        if not db:
            return []
            
        try:
            with db.cursor() as cursor:
                sql = """
                    SELECT drug_id, drug_name_en, drug_name_zh, main_use, side_effects, 
                           shape, color, food_drug_interactions, image_url 
                    FROM drug_info WHERE drug_id LIKE %s
                """
                
                cursor.execute(sql, (f"{prefix}%",))
                results = cursor.fetchall()
                
                # 轉換字段名以匹配格式
                details_list = []
                for row in results:
                    details_list.append({
                        'drug_id': row.get('drug_id'),
                        'drug_name_en': row.get('drug_name_en'),
                        'drug_name_zh': row.get('drug_name_zh'),
                        'uses': row.get('main_use'),
                        'side_effects': row.get('side_effects'),
                        'shape': row.get('shape'),
                        'color': row.get('color'),
                        'interactions': row.get('food_drug_interactions'),
                        'image_url': row.get('image_url')
                    })
                
                return details_list
                
        except Exception as e:
            print(f"根據前綴查詢藥品信息失敗: {e}")
            return []

    @staticmethod
    def add_drug_info(drug_id, drug_name_en, drug_name_zh, main_use, side_effects, shape, color, interactions, image_url):
        """新增或更新药品信息到 drug_info 表"""
        db = get_db_connection()
        if not db:
            return False
            
        try:
            with db.cursor() as cursor:
                sql = """
                    INSERT INTO drug_info (
                        drug_id, drug_name_en, drug_name_zh, main_use, side_effects, 
                        shape, color, food_drug_interactions, image_url
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        drug_name_en = VALUES(drug_name_en),
                        drug_name_zh = VALUES(drug_name_zh),
                        main_use = VALUES(main_use),
                        side_effects = VALUES(side_effects),
                        shape = VALUES(shape),
                        color = VALUES(color),
                        food_drug_interactions = VALUES(food_drug_interactions),
                        image_url = VALUES(image_url)
                """
                
                cursor.execute(sql, (
                    drug_id, drug_name_en, drug_name_zh, main_use, side_effects,
                    shape, color, interactions, image_url
                ))
                db.commit()
                return True
                
        except Exception as e:
            print(f"新增/更新药品信息失败: {e}")
            return False
    
    # --- 排程器專用查詢 ---
    @staticmethod
    def get_reminders_for_scheduler(current_time_str):
        db = get_db_connection()
        if not db: return []
        with db.cursor() as cursor:
            sql = """
                SELECT ms.*, 
                       ir.recipient_line_id as bound_recipient_line_id
                FROM medicine_schedule ms
                LEFT JOIN invitation_recipients ir ON ms.recorder_id = ir.recorder_id AND ms.member = ir.relation_type
                WHERE %s IN (
                    DATE_FORMAT(ms.time_slot_1, '%%H:%%i'),
                    DATE_FORMAT(ms.time_slot_2, '%%H:%%i'),
                    DATE_FORMAT(ms.time_slot_3, '%%H:%%i'),
                    DATE_FORMAT(ms.time_slot_4, '%%H:%%i'),
                    DATE_FORMAT(ms.time_slot_5, '%%H:%%i')
                )
            """
            cursor.execute(sql, (current_time_str,))
            return cursor.fetchall()

    # --- 健康記錄相關方法 ---
    @staticmethod
    def add_health_log(log_data):
        """新增健康記錄"""
        db = get_db_connection()
        if not db: 
            print("資料庫連線失敗")
            return False
        
        try:
            with db.cursor() as cursor:
                print(f"開始處理健康記錄: {log_data}")
                
                # 確保使用者存在
                cursor.execute("SELECT recorder_id FROM users WHERE recorder_id = %s", (log_data['recorderId'],))
                user_exists = cursor.fetchone()
                print(f"使用者是否存在: {bool(user_exists)}")
                
                if not user_exists:
                    # 自動建立使用者
                    user_name = log_data.get('userName', f"User_{log_data['recorderId'][:8]}")
                    print(f"建立新使用者: {user_name}")
                    cursor.execute("INSERT INTO users (recorder_id, user_name) VALUES (%s, %s)", 
                                 (log_data['recorderId'], user_name))
                
                # 準備健康記錄資料
                fields = ['recorder_id', 'target_person', 'record_time']
                values = [log_data['recorderId'], log_data['targetPerson'], datetime.fromisoformat(log_data['record_time'].replace('Z', '+00:00'))]
                
                print(f"基本欄位: {fields}")
                print(f"基本數值: {values}")
                
                # 動態添加健康數值
                health_fields = ['blood_oxygen', 'systolic_pressure', 'diastolic_pressure', 'blood_sugar', 'temperature', 'weight']
                for field in health_fields:
                    if field in log_data and log_data[field] is not None and log_data[field] != '':
                        fields.append(field)
                        values.append(log_data[field])
                        print(f"添加健康欄位: {field} = {log_data[field]}")
                
                # 插入健康記錄
                placeholders = ', '.join(['%s'] * len(values))
                sql = f"INSERT INTO health_log ({', '.join(fields)}) VALUES ({placeholders})"
                print(f"執行 SQL: {sql}")
                print(f"參數: {values}")
                
                cursor.execute(sql, values)
                affected_rows = cursor.rowcount
                print(f"影響行數: {affected_rows}")
                
                db.commit()
                print("資料庫提交成功")
                return True
                
        except Exception as e:
            print(f"新增健康記錄失敗: {e}")
            import traceback
            print(f"錯誤詳情: {traceback.format_exc()}")
            return False

    @staticmethod
    def get_all_logs_by_recorder(recorder_id):
        """獲取指定用戶的所有健康記錄"""
        db = get_db_connection()
        if not db: return []
        
        try:
            with db.cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM health_log 
                    WHERE recorder_id = %s 
                    ORDER BY record_time DESC
                """, (recorder_id,))
                logs = cursor.fetchall()
                
                # 轉換時間格式並將 Decimal 轉為字串
                taipei_tz = ZoneInfo("Asia/Taipei")
                for log in logs:
                    for key, value in log.items():
                        if isinstance(value, datetime):
                            # 假設儲存的 datetime 是 UTC，並將其轉換為台北時間
                            # 然後格式化為 ISO 8601 字串，直接傳送給前端
                            if value.tzinfo is None:
                                # 如果沒有時區資訊，假設它是 UTC
                                utc_dt = value.replace(tzinfo=timezone.utc)
                            else:
                                utc_dt = value.astimezone(timezone.utc)
                            
                            taipei_dt = utc_dt.astimezone(taipei_tz)
                            log[key] = taipei_dt.isoformat()
                        elif hasattr(value, '__class__') and 'Decimal' in str(value.__class__):
                            # 將 Decimal 轉換為字串以避免 JSON 序列化問題
                            log[key] = str(value)
                        elif isinstance(value, date) and not isinstance(value, datetime):
                            log[key] = value.isoformat()
                
                return logs
        except Exception as e:
            print(f"查詢健康記錄失敗: {e}")
            return []

    @staticmethod
    def delete_health_log(log_id, recorder_id):
        """刪除健康記錄"""
        db = get_db_connection()
        if not db: return False
        
        try:
            with db.cursor() as cursor:
                # 驗證記錄所有者
                cursor.execute("SELECT recorder_id FROM health_log WHERE log_id = %s", (log_id,))
                result = cursor.fetchone()
                
                if not result:
                    return False
                
                if result['recorder_id'] != recorder_id:
                    return False
                
                # 刪除記錄
                cursor.execute("DELETE FROM health_log WHERE log_id = %s", (log_id,))
                db.commit()
                return True
                
        except Exception as e:
            print(f"刪除健康記錄失敗: {e}")
            return False