# LINE Bot 藥物管理系統開發指南 🏥💊

## 📋 目錄
- [系統概述](#系統概述)
- [技術架構](#技術架構)
- [核心功能模組](#核心功能模組)
- [開發環境設置](#開發環境設置)
- [API 設計](#api-設計)
- [資料庫設計](#資料庫設計)
- [部署指南](#部署指南)
- [開發最佳實踐](#開發最佳實踐)

## 系統概述

### 🎯 專案目標
開發一個智能的 LINE Bot 應用程式，提供藥物管理、健康記錄追蹤、家人綁定等功能，幫助用戶更好地管理個人和家庭的健康狀況。

### ✨ 核心功能
1. **📋 藥單辨識** - AI 驅動的藥單照片識別
2. **⏰ 用藥提醒** - 智能提醒系統
3. **👨‍👩‍👧‍👦 家人綁定** - 家庭成員健康管理
4. **🗂️ 藥歷管理** - 完整的用藥記錄系統
5. **📊 健康記錄** - 健康數據追蹤
6. **🤖 AI 助手** - 基於 Google Gemini 的智能對話

## 技術架構

### 🏗️ 系統架構圖
```
📱 LINE 用戶端
    ↕️ (Webhook/LIFF)
🌐 Flask 應用伺服器
    ↕️ (SQL)
🗄️ MySQL 資料庫
    ↕️ (API)
🤖 Google Gemini AI
```

### 🛠️ 技術棧

#### 後端框架
- **Flask 3.1.1** - 輕量級 Web 框架
- **Werkzeug 3.1.3** - WSGI 工具庫
- **Gunicorn 21.2.0** - WSGI HTTP 伺服器

#### LINE Bot SDK
- **line-bot-sdk 3.17.1** - LINE Bot 官方 SDK
- **LIFF (LINE Front-end Framework)** - 前端整合

#### AI 服務
- **google-genai 1.24.0** - Google Gemini AI API
- **google-auth 2.40.3** - Google 認證
- **google-cloud-storage** - 雲端儲存

#### 資料庫
- **PyMySQL 1.1.1** - MySQL 連接器
- **MySQL** - 關聯式資料庫

#### 其他依賴
- **Pillow 11.3.0** - 圖像處理
- **requests 2.32.4** - HTTP 請求
- **schedule 1.2.2** - 任務排程
- **pydantic 2.11.7** - 資料驗證
- **python-dotenv 1.1.1** - 環境變數管理

## 核心功能模組

### 1. 📋 藥單辨識系統

#### 技術實現
```python
# 核心處理流程
def process_prescription_images(image_bytes_list, processing_mode="smart_filter_parallel"):
    """
    藥單圖片處理主函數
    
    Args:
        image_bytes_list: 圖片二進制數據列表
        processing_mode: 處理模式 (smart_filter_parallel)
    
    Returns:
        analysis_result: 分析結果包含藥物清單和統計資訊
    """
```

#### AI 辨識流程
1. **圖片預處理** - 使用 Pillow 進行圖片優化
2. **OCR 文字提取** - Google Gemini Vision API
3. **藥物名稱匹配** - 智能篩選算法
4. **結果驗證** - 數學驗證和信心度評估

#### 智能匹配算法
```python
def smart_filter_drugs(all_drugs, keywords):
    """
    多層次藥物匹配算法
    
    匹配策略：
    1. 直接匹配 (1.0分)
    2. 標準化匹配 (0.9分) 
    3. 組件匹配 (0.8分)
    4. 相似度匹配 (0.6分)
    5. 部分詞匹配 (0.4-0.7分)
    6. 超級寬鬆匹配 (0.3分)
    """
```

#### 特殊處理規則
- **Spalytic HS** - 處理下劃線和連字符變體
- **摩舒益多** - 多種中英文變體匹配
- **瓦斯康錠** - OCR 誤識修正 (卡斯康→瓦斯康)

### 2. ⏰ 用藥提醒系統

#### 架構設計
```python
# 提醒資料結構
medicine_schedule = {
    'schedule_id': 'UUID',
    'recorder_id': 'LINE_USER_ID',
    'member': '成員名稱',
    'drug_name': '藥物名稱',
    'time_slots': ['08:00', '12:00', '18:00'],
    'is_active': True
}
```

#### 提醒邏輯
1. **時間檢查** - 每分鐘掃描待發送提醒
2. **成員匹配** - 支援家人綁定提醒
3. **訊息發送** - 使用 LINE Push Message API
4. **狀態追蹤** - 記錄發送狀態和用戶回應

#### 排程系統
```python
import schedule
import time

def check_reminders():
    """檢查並發送用藥提醒"""
    current_time = datetime.now().strftime('%H:%M')
    # 查詢需要發送的提醒
    # 發送 LINE 訊息
    
# 每分鐘執行一次
schedule.every().minute.do(check_reminders)
```

### 3. 👨‍👩‍👧‍👦 家人綁定系統

#### 綁定流程
1. **邀請碼生成** - 6位隨機數字
2. **邀請分享** - 透過 LINE 分享邀請碼
3. **關係確認** - 選擇家庭關係 (父母/子女/配偶等)
4. **雙向通知** - 綁定成功通知雙方

#### 資料結構
```sql
CREATE TABLE invitation_recipients (
    id INT PRIMARY KEY AUTO_INCREMENT,
    recorder_id VARCHAR(50),      -- 邀請者 LINE ID
    recipient_line_id VARCHAR(50), -- 被邀請者 LINE ID
    relation_type VARCHAR(20),     -- 關係類型
    created_at TIMESTAMP
);
```

#### 權限管理
- **雙向查看** - 家人可查看彼此的藥歷和健康記錄
- **建立者標註** - 顯示記錄建立者資訊
- **刪除權限** - 建立者和記錄對象都可刪除

### 4. 🗂️ 藥歷管理系統

#### 查詢邏輯
```python
def get_records_by_member(user_id, member_name):
    """
    獲取成員藥歷記錄
    
    查詢策略：
    - 查看"本人"：只返回關於自己的記錄
    - 查看特定成員：返回自己建立的 + 該成員自建的記錄
    """
```

#### FLEX 訊息顯示
```python
def create_prescription_list(records):
    """
    生成藥歷列表的 FLEX 訊息
    
    Features:
    - 藥物資訊卡片
    - 建立者標註
    - 操作按鈕 (查看/編輯/刪除)
    """
```

### 5. 📊 健康記錄系統

#### LIFF 整合
```javascript
// 前端 LIFF 應用
async function loadAllHealthData(recorderId) {
    const targetPerson = getSelectedPerson();
    let apiUrl;
    
    if (targetPerson === '本人') {
        apiUrl = `/api/health_logs/${recorderId}`;
    } else {
        apiUrl = `/api/health_logs/${recorderId}/member/${memberId}`;
    }
    
    const response = await fetch(apiUrl);
    // 處理回應資料
}
```

#### 雙向共享 API
```python
# 查看本人記錄
@app.route('/api/health_logs/<user_id>')
def get_health_logs_api(user_id):
    logs = DB.get_all_logs_by_recorder(user_id)
    return jsonify(logs)

# 查看特定成員記錄
@app.route('/api/health_logs/<user_id>/member/<member_id>')
def get_member_health_logs_api(user_id, member_id):
    logs = DB.get_logs_for_specific_member(user_id, member_id)
    return jsonify(logs)
```

## API 設計

### LINE Webhook 處理
```python
@webhook_bp.route("/callback", methods=['POST'])
def callback():
    """LINE Webhook 回調處理"""
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    
    return 'OK'
```

### 訊息分派系統
```python
def handle_message_dispatcher(event):
    """
    訊息分派邏輯
    
    優先級：
    1. 全局指令 (選單、主選單等)
    2. 特定流程文字觸發
    3. 狀態相關處理
    4. 成員名稱匹配
    """
```

### Postback 事件處理
```python
@handler.add(PostbackEvent)
def handle_postback_dispatcher(event):
    """
    Postback 事件分派
    
    Actions:
    - prescription_actions: 藥單相關
    - family_actions: 家人綁定相關
    - reminder_actions: 提醒相關
    - pill_actions: 藥丸辨識相關
    """
```

## 資料庫設計

### 核心資料表

#### 用戶表
```sql
CREATE TABLE users (
    recorder_id VARCHAR(50) PRIMARY KEY,
    user_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 藥歷主表
```sql
CREATE TABLE medication_main (
    mm_id INT PRIMARY KEY AUTO_INCREMENT,
    recorder_id VARCHAR(50),
    member VARCHAR(50),
    clinic_name VARCHAR(100),
    doctor_name VARCHAR(100),
    visit_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 藥物記錄表
```sql
CREATE TABLE medication_records (
    mr_id INT PRIMARY KEY AUTO_INCREMENT,
    mm_id INT,
    drug_name_zh VARCHAR(200),
    drug_name_en VARCHAR(200),
    dose_quantity VARCHAR(100),
    frequency_text VARCHAR(100),
    main_use TEXT,
    side_effects TEXT
);
```

#### 健康記錄表
```sql
CREATE TABLE health_log (
    log_id INT PRIMARY KEY AUTO_INCREMENT,
    recorder_id VARCHAR(50),
    target_person VARCHAR(50),
    record_time DATETIME,
    systolic_pressure INT,
    diastolic_pressure INT,
    blood_sugar DECIMAL(5,2),
    temperature DECIMAL(4,2),
    weight DECIMAL(5,2)
);
```

#### 用藥提醒表
```sql
CREATE TABLE medicine_schedule (
    schedule_id VARCHAR(36) PRIMARY KEY,
    recorder_id VARCHAR(50),
    member VARCHAR(50),
    drug_name VARCHAR(200),
    time_slots JSON,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 資料關聯設計

#### 雙向共享邏輯
```sql
-- 查看特定成員的完整記錄
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

## 開發環境設置

### 環境變數配置
```bash
# .env 檔案
LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token
LINE_CHANNEL_SECRET=your_channel_secret
GOOGLE_API_KEY=your_gemini_api_key

# LIFF 應用 ID
LIFF_ID_CAMERA=your_camera_liff_id
LIFF_ID_EDIT_RECORD=your_edit_liff_id
LIFF_ID_HEALTH_FORM=your_health_liff_id
LIFF_ID_PRESCRIPTION_REMINDER=your_reminder_liff_id

# 資料庫配置
DB_HOST=localhost
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=your_db_name
```

### 本地開發啟動
```bash
# 安裝依賴
pip install -r requirements.txt

# 設置環境變數
cp .env.example .env
# 編輯 .env 檔案

# 啟動開發伺服器
python run.py
```

### Docker 部署
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "run:app"]
```

## 部署指南

### Google Cloud Platform 部署

#### Cloud Run 配置
```yaml
# cloudbuild.yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/linebot-app', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/linebot-app']
  - name: 'gcr.io/cloud-builders/gcloud'
    args: ['run', 'deploy', 'linebot-app', 
           '--image', 'gcr.io/$PROJECT_ID/linebot-app',
           '--platform', 'managed',
           '--region', 'asia-east1']
```

#### Cloud Scheduler 設置
```bash
# 用藥提醒排程
gcloud scheduler jobs create http reminder-job \
    --schedule="* * * * *" \
    --uri="https://your-app.run.app/api/check-reminders" \
    --http-method=POST
```

### CI/CD Pipeline
```yaml
# .github/workflows/deploy-gcp.yml
name: Deploy to GCP
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Cloud SDK
        uses: google-github-actions/setup-gcloud@v1
      - name: Deploy to Cloud Run
        run: gcloud builds submit --config cloudbuild.yaml
```

## 開發最佳實踐

### 程式碼結構
```
app/
├── routes/           # 路由處理
│   ├── line_webhook.py    # LINE Webhook
│   ├── liff_views.py      # LIFF 頁面
│   └── handlers/          # 功能處理器
├── services/         # 業務邏輯
│   ├── ai_processor.py    # AI 處理
│   ├── user_service.py    # 用戶服務
│   └── reminder_service.py # 提醒服務
├── utils/           # 工具函數
│   ├── db.py             # 資料庫操作
│   ├── helpers.py        # 輔助函數
│   └── flex/             # FLEX 訊息模板
└── templates/       # LIFF 頁面模板
```

### 錯誤處理
```python
def safe_api_call(func):
    """API 調用安全包裝器"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            current_app.logger.error(f"API 調用錯誤: {e}")
            return {"error": "服務暫時無法使用"}
    return wrapper
```

### 日誌記錄
```python
import logging

# 設置日誌格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 使用日誌
current_app.logger.info(f"處理用戶請求: {user_id}")
current_app.logger.error(f"處理錯誤: {error}")
```

### 安全性考量
1. **API 金鑰保護** - 使用環境變數
2. **簽名驗證** - LINE Webhook 簽名檢查
3. **輸入驗證** - 使用 Pydantic 進行資料驗證
4. **SQL 注入防護** - 使用參數化查詢
5. **HTTPS 強制** - 生產環境必須使用 HTTPS

### 效能優化
1. **資料庫索引** - 為常用查詢欄位建立索引
2. **圖片壓縮** - 使用 Pillow 優化圖片大小
3. **快取策略** - 對頻繁查詢的資料進行快取
4. **並行處理** - 使用 asyncio 處理多圖片分析

## 監控與維護

### 健康檢查
```python
@app.route('/health')
def health_check():
    """系統健康檢查"""
    try:
        # 檢查資料庫連接
        db = get_db_connection()
        if db:
            return {"status": "healthy", "timestamp": datetime.now()}
        else:
            return {"status": "unhealthy", "error": "database"}, 500
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}, 500
```

### 效能監控
```python
import time

def monitor_performance(func):
    """效能監控裝飾器"""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        
        current_app.logger.info(f"{func.__name__} 執行時間: {execution_time:.2f}秒")
        return result
    return wrapper
```

### 錯誤追蹤
```python
import traceback

def log_error(error, context=None):
    """統一錯誤記錄"""
    error_info = {
        "error": str(error),
        "traceback": traceback.format_exc(),
        "context": context,
        "timestamp": datetime.now()
    }
    current_app.logger.error(f"系統錯誤: {error_info}")
```

## 結語

這個 LINE Bot 藥物管理系統展示了現代 Web 應用開發的最佳實踐，整合了 AI 技術、雲端服務和用戶體驗設計。通過模組化的架構設計和完善的錯誤處理機制，系統能夠穩定地為用戶提供智能的健康管理服務。

### 技術亮點
- **AI 驅動的藥單識別** - 使用 Google Gemini 實現高準確度的 OCR
- **智能匹配算法** - 多層次的藥物名稱匹配策略
- **雙向資料共享** - 家人間的健康資料互通
- **LIFF 整合** - 無縫的 LINE 內 Web 應用體驗
- **雲端部署** - 基於 Google Cloud Platform 的可擴展架構

### 未來發展方向
1. **機器學習優化** - 持續改進藥物識別準確度
2. **多語言支援** - 支援更多語言的藥單識別
3. **健康分析** - 基於歷史資料的健康趨勢分析
4. **醫療整合** - 與醫療機構系統的整合
5. **穿戴設備** - 整合智能手錶等穿戴設備資料

---

*本文檔基於實際開發經驗編寫，涵蓋了從系統設計到部署維護的完整開發流程。*