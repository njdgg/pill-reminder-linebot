# LINE Bot 核心功能開發指南 🏥

## 📋 核心功能概述

本系統包含三個核心功能模組：
1. **📋 藥單辨識** - AI 驅動的處方箋識別
2. **🗂️ 藥歷功能** - 藥物記錄查詢與管理
3. **⏰ 藥單提醒設置** - 智能用藥提醒系統

## 🎯 應用場景與技術價值

### 家庭照護解決方案
利用LINE Bot的家人綁定機制，實現**跨世代健康管理**：
- **年輕人協助長輩** - 子女可代替不熟悉智慧手機的父母進行藥單記錄
- **雙向資料共享** - 長輩可查看子女為其建立的藥歷記錄
- **統一管理平台** - 一個帳號管理全家人的健康資訊

### 技術創新亮點
- **多圖處理突破** - 解決LINE原生不支援多圖上傳的限制
- **即時AI辨識** - 結合Google Gemini實現高準確度藥物識別
- **智能資料庫匹配** - 六層匹配策略確保藥物資訊準確性
- **無縫用戶體驗** - 從拍照到記錄完成的一站式流程

---

## 1. 📋 藥單辨識功能

### 技術架構
```
📱 LINE用戶 → 🌐 LIFF網頁 → 📸 多圖上傳 → 🤖 AI辨識 → 🔍 資料庫匹配 → 📋 FLEX展示
```

### 應用流程設計

#### 1. 多圖上傳解決方案
**技術挑戰：** LINE Bot 原生不支援多圖片同時上傳
**解決方案：** 設計專用的 LIFF (LINE Front-end Framework) 網頁

```javascript
// 多圖上傳核心邏輯
function handleMultipleImages(files) {
    const imagePromises = Array.from(files).map(file => {
        return new Promise((resolve) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.readAsDataURL(file);
        });
    });
    
    Promise.all(imagePromises).then(images => {
        sendImagesToAI(images);
    });
}
```

#### 2. 即時回應機制
**用戶體驗設計：** 辨識過程中提供即時反饋
```python
# 發送等待訊息
def send_processing_message(user_id):
    waiting_message = TextSendMessage(
        text="🔍 正在分析您的藥單，請稍候...\n⏳ 預計需要 10-30 秒"
    )
    line_bot_api.push_message(user_id, waiting_message)

# 辨識完成後發送結果
def send_analysis_result(user_id, analysis_result):
    flex_message = create_prescription_flex(analysis_result)
    line_bot_api.push_message(user_id, flex_message)
```

### 核心實現

#### AI 處理流程
```python
def process_prescription_images(image_bytes_list, processing_mode="smart_filter_parallel"):
    """
    藥單圖片處理主函數
    
    處理流程：
    1. 圖片預處理與壓縮
    2. OCR 文字提取 (Google Gemini Vision)
    3. 關鍵字提取與清理
    4. 智能藥物匹配
    5. 數學驗證與信心度評估
    6. 結果格式化與存儲
    """
```

#### 智能匹配算法
```python
def smart_filter_drugs(all_drugs, keywords):
    """
    六層匹配策略：
    
    1. 直接匹配 (1.0分) - 完全相同
    2. 標準化匹配 (0.9分) - 移除特殊字符後匹配
    3. 組件匹配 (0.8分) - 拆分組件匹配
    4. 相似度匹配 (0.6分) - 模糊匹配
    5. 部分詞匹配 (0.4-0.7分) - 關鍵詞部分匹配
    6. 超級寬鬆匹配 (0.3分) - 最後兜底
    """
```

#### 特殊處理規則
```python
# 針對常見 OCR 誤識的特殊處理
special_cases = {
    'spalytic_hs': ['spalytic', 'hs'],           # 下劃線處理
    'mosapride': ['摩舒益多', 'mosapride', '摩舒'], # 中英文變體
    'gascon': ['卡斯康', '瓦斯康', '加斯康']        # OCR 誤識修正
}
```

#### 數學驗證機制
```python
def calculate_frequency_from_math(total_dose, single_dose, days):
    """
    頻率計算公式：總劑量 ÷ 單次劑量 ÷ 天數 = 每日服用次數
    
    用途：
    - 驗證 AI 判斷的用藥頻率
    - 修正明顯錯誤（如 Gascon 40mg 被誤判為一日四次）
    - 提供信心度評估
    """
```

### 關鍵技術點

#### 1. 並行處理優化
- **批次 OCR**：多張圖片同時處理
- **智能篩選**：先篩選候選藥物再詳細分析
- **Token 優化**：減少 API 調用成本

#### 2. 錯誤處理機制
- **多重保障**：5層獨立匹配邏輯
- **自動降級**：API 失敗時的備用方案
- **詳細日誌**：完整的處理過程記錄

#### 3. 準確度提升策略
- **特殊藥物處理**：針對難識別藥物的專門邏輯
- **信心度評估**：基於多種因素的可靠性評分
- **人工驗證接口**：支援人工確認和修正

---

## 2. 🗂️ 藥歷功能

### 功能架構
```
📱 LINE 指令 → 🔍 資料庫查詢 → 📋 FLEX 訊息 → 👀 用戶查看
```

### 核心實現

#### 查詢邏輯
```python
def get_records_by_member(user_id, member_name):
    """
    藥歷查詢邏輯
    
    查看"本人"：
    - 自己建立的關於自己的記錄
    - 別人為自己建立的記錄
    
    查看特定成員（如"10"）：
    - 自己為該成員建立的記錄
    - 該成員自己建立的記錄（雙向共享）
    """
```

#### 雙向共享實現
```sql
-- 查看特定成員的完整藥歷
SELECT DISTINCT mm.*, u.user_name as creator_name
FROM medication_main mm
LEFT JOIN users u ON mm.recorder_id = u.recorder_id
WHERE (
    -- 自己為該成員建立的記錄
    (mm.recorder_id = ? AND mm.member = ?)
    OR
    -- 該成員自己建立的記錄
    (mm.recorder_id = ? AND mm.member = '本人')
)
ORDER BY mm.created_at DESC;
```

#### FLEX 訊息生成
```python
def create_prescription_list(records):
    """
    生成藥歷列表的 FLEX 訊息
    
    Features:
    - 藥物資訊卡片展示
    - 建立者標註（"由 XXX 建立"）
    - 操作按鈕（查看詳情/編輯/刪除）
    - 分頁處理（避免訊息過長）
    """
```

### 資料結構

#### 主要資料表
```sql
-- 藥歷主表
CREATE TABLE medication_main (
    mm_id INT PRIMARY KEY AUTO_INCREMENT,
    recorder_id VARCHAR(50),    -- 建立者 LINE ID
    member VARCHAR(50),         -- 記錄對象（"本人"或關係名稱）
    clinic_name VARCHAR(100),   -- 診所名稱
    doctor_name VARCHAR(100),   -- 醫師姓名
    visit_date DATE,           -- 看診日期
    created_at TIMESTAMP
);

-- 藥物詳細記錄
CREATE TABLE medication_records (
    mr_id INT PRIMARY KEY AUTO_INCREMENT,
    mm_id INT,                 -- 關聯主表
    drug_name_zh VARCHAR(200), -- 中文藥名
    drug_name_en VARCHAR(200), -- 英文藥名
    dose_quantity VARCHAR(100), -- 劑量
    frequency_text VARCHAR(100), -- 頻率
    main_use TEXT,             -- 主要用途
    side_effects TEXT          -- 副作用
);

-- 家人綁定關係
CREATE TABLE invitation_recipients (
    recorder_id VARCHAR(50),      -- 邀請者 ID
    recipient_line_id VARCHAR(50), -- 被邀請者 ID
    relation_type VARCHAR(20)      -- 關係類型（如"10"）
);
```

### 權限管理

#### 查看權限
- **本人記錄**：只顯示關於自己的記錄
- **家人記錄**：顯示雙向記錄（自己建立的 + 對方自建的）
- **建立者標註**：清楚標示記錄建立者

#### 操作權限
- **刪除權限**：建立者和記錄對象都可刪除
- **編輯權限**：目前僅建立者可編輯
- **隱私保護**：解除綁定時自動清理相關資料

---

## 3. ⏰ 藥單提醒設置

### 功能架構
```
📋 藥歷資料 → ⚙️ LIFF 設定頁面 → 💾 提醒排程 → ⏰ 定時發送
```

### 核心實現

#### LIFF 設定頁面
```javascript
// prescription_reminder_form.html
function getSafeFrequencyDisplay(med) {
    """
    安全的頻率顯示邏輯
    
    優先級：
    1. frequency_name (如"一日三次")
    2. frequency_code 翻譯 (TID → "一日三次")
    3. frequency_text (原始識別文字)
    4. 預設值 ("頻率請諮詢醫師")
    """
}

// 頻率代碼翻譯
const codeMap = {
    'QD': '一日一次',
    'BID': '一日兩次', 
    'TID': '一日三次',
    'QID': '一日四次',
    'PRN': '需要時使用',
    'HS': '睡前服用'
};
```

#### 提醒資料結構
```sql
CREATE TABLE medicine_schedule (
    schedule_id VARCHAR(36) PRIMARY KEY,
    recorder_id VARCHAR(50),     -- 設定者 LINE ID
    member VARCHAR(50),          -- 提醒對象
    drug_name VARCHAR(200),      -- 藥物名稱
    time_slots JSON,             -- 提醒時間 ["08:00", "12:00", "18:00"]
    notes TEXT,                  -- 備註（如"飯後服用"）
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP
);
```

#### 排程檢查邏輯
```python
def check_and_send_reminders():
    """
    提醒檢查與發送
    
    流程：
    1. 獲取當前時間（HH:MM 格式）
    2. 查詢需要發送的提醒
    3. 根據成員關係確定接收者
    4. 發送 LINE Push Message
    5. 記錄發送狀態
    """
    
    current_time = datetime.now().strftime('%H:%M')
    
    # 查詢需要發送的提醒
    reminders = get_active_reminders_by_time(current_time)
    
    for reminder in reminders:
        # 確定接收者
        recipient_id = get_reminder_recipient(reminder)
        
        # 發送提醒訊息
        send_reminder_message(recipient_id, reminder)
```

#### 接收者確定邏輯
```python
def get_reminder_recipient(reminder):
    """
    確定提醒接收者
    
    邏輯：
    - 如果 member = "本人"：發送給設定者
    - 如果 member = 其他：發送給對應的綁定成員
    """
    if reminder['member'] == '本人':
        return reminder['recorder_id']
    else:
        # 查詢綁定關係
        binding = get_family_binding(reminder['recorder_id'], reminder['member'])
        return binding['recipient_line_id'] if binding else None
```

### 用戶體驗設計

#### 智能提醒設定流程
**技術創新：** 從手動新增優化為智能批次設定

```javascript
// 批次提醒設定邏輯
function setupBatchReminders(prescriptionData) {
    // 1. 讀取藥歷資訊
    const medications = loadPrescriptionHistory(prescriptionData.mm_id);
    
    // 2. 智能分組（按頻率分組）
    const groupedMeds = groupMedicationsByFrequency(medications);
    
    // 3. 批次時間設定
    Object.keys(groupedMeds).forEach(frequency => {
        const timeSlots = generateTimeSlots(frequency);
        groupedMeds[frequency].forEach(med => {
            createReminderSchedule(med, timeSlots);
        });
    });
}
```

#### 完整設定流程
1. **選擇藥歷記錄** → 點擊「設定提醒」
2. **LIFF 頁面開啟** → 自動讀取藥歷資訊並顯示
3. **智能頻率顯示** → 系統自動解析並顯示建議頻率
4. **批次時間設定** → 用戶可一次設定多個藥物的提醒時間
5. **儲存確認** → 發送 LIFF 訊息確認，自動關閉頁面
6. **提醒啟動** → 系統按設定時間發送個人化提醒

#### 提醒訊息格式
```python
reminder_message = f"""
💊 用藥提醒

藥物：{drug_name}
時間：{current_time}
備註：{notes}

請按時服藥，注意用藥安全 🏥
"""
```

#### 安全機制
- **重複發送防護**：避免同一時間重複發送
- **錯誤處理**：API 失敗時的重試機制
- **用戶隱私**：只發送給有權限的用戶

---

## 🏥 家庭照護技術實現

### 跨世代協助機制
```python
def enable_family_assistance(elder_id, helper_id, relation_type):
    """
    建立家人協助關係
    
    技術實現：
    1. 創建綁定關係記錄
    2. 設定雙向資料存取權限
    3. 建立代理操作機制
    """
    
    # 建立綁定關係
    create_family_binding(helper_id, elder_id, relation_type)
    
    # 設定協助權限
    grant_assistance_permissions(helper_id, elder_id)
    
    # 通知雙方綁定成功
    notify_binding_success(helper_id, elder_id)
```

### LINE Bot 技術限制突破

#### 多圖上傳解決方案
**原生限制：** LINE Bot 一次只能接收一張圖片
**技術突破：** 使用 LIFF 網頁技術

```html
<!-- LIFF 多圖上傳頁面 -->
<input type="file" 
       id="imageInput" 
       multiple 
       accept="image/*"
       onchange="handleImageUpload(this.files)">

<script>
function handleImageUpload(files) {
    if (files.length > 5) {
        alert('最多只能上傳5張圖片');
        return;
    }
    
    // 壓縮並上傳圖片
    compressAndUploadImages(files);
}
</script>
```

#### FLEX 訊息動態生成
```python
def create_dynamic_prescription_flex(medications, user_context):
    """
    根據用戶情境動態生成 FLEX 訊息
    
    Features:
    - 根據藥物數量調整卡片佈局
    - 顯示建立者資訊（家人協助標記）
    - 提供個人化操作按鈕
    """
    
    flex_contents = []
    
    for med in medications:
        card = {
            "type": "bubble",
            "body": create_medication_body(med),
            "footer": create_action_buttons(med, user_context)
        }
        
        # 添加家人協助標記
        if med.get('recorder_id') != user_context['user_id']:
            card['body']['contents'].append({
                "type": "text",
                "text": f"📝 由 {med.get('recorder_name')} 記錄",
                "size": "xs",
                "color": "#999999"
            })
        
        flex_contents.append(card)
    
    return FlexSendMessage(
        alt_text="藥單辨識結果",
        contents={"type": "carousel", "contents": flex_contents}
    )
```

---

## 🔧 技術整合要點

### 1. 資料流整合
```
藥單辨識 → 藥歷存儲 → 提醒設定 → 定時發送
    ↓           ↓          ↓         ↓
  AI分析     FLEX顯示   LIFF設定   Push訊息
```

### 2. 權限一致性
- **查看權限**：三個功能使用相同的家人綁定邏輯
- **操作權限**：統一的建立者和對象權限管理
- **隱私保護**：一致的資料清理和隱私設定

### 3. 錯誤處理
```python
# 統一的錯誤處理模式
try:
    result = core_function()
    return success_response(result)
except SpecificError as e:
    logger.error(f"特定錯誤: {e}")
    return error_response("具體錯誤訊息")
except Exception as e:
    logger.error(f"未預期錯誤: {e}")
    return error_response("系統暫時無法使用")
```

### 4. 效能優化
- **資料庫索引**：為常用查詢欄位建立索引
- **快取策略**：藥物資料庫的記憶體快取
- **批次處理**：多圖片並行處理
- **API 限制**：合理的請求頻率控制

---

## 📊 系統監控

### 關鍵指標
- **辨識準確率**：藥物匹配成功率
- **提醒送達率**：提醒訊息發送成功率
- **用戶活躍度**：功能使用頻率統計
- **錯誤率**：各功能模組的錯誤發生率

### 日誌記錄
```python
# 關鍵操作日誌
logger.info(f"藥單辨識: 用戶={user_id}, 圖片數={image_count}, 識別藥物數={drug_count}")
logger.info(f"藥歷查詢: 用戶={user_id}, 查詢對象={member}, 記錄數={record_count}")
logger.info(f"提醒發送: 接收者={recipient_id}, 藥物={drug_name}, 時間={time}")
```

---

## 🚀 部署與維護

### 環境配置
```bash
# 核心環境變數
LINE_CHANNEL_ACCESS_TOKEN=your_token
GOOGLE_API_KEY=your_gemini_key
LIFF_ID_PRESCRIPTION_REMINDER=your_liff_id

# 資料庫配置
DB_HOST=your_db_host
DB_NAME=your_db_name
```

### 定時任務
```bash
# Cloud Scheduler 設定
gcloud scheduler jobs create http reminder-checker \
    --schedule="* * * * *" \
    --uri="https://your-app.run.app/api/check-reminders" \
    --http-method=POST
```

### 健康檢查
```python
@app.route('/health')
def health_check():
    """檢查三個核心功能的健康狀態"""
    return {
        "ai_service": check_gemini_api(),
        "database": check_db_connection(),
        "line_api": check_line_api(),
        "status": "healthy"
    }
```

---

這三個核心功能構成了完整的藥物管理生態系統，從智能識別到記錄管理再到提醒服務，為用戶提供了全方位的健康管理支援。