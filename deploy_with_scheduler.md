# 🚀 用藥提醒系統 Cloud Run + Cloud Scheduler 部署指南

## 問題說明
您的用藥提醒在 GCP Cloud Run 上無法正常運作，主要原因是：
- Cloud Run 是無狀態服務，當沒有請求時會自動縮放到零
- 背景排程器線程會被終止，導致提醒無法發送

## 解決方案
使用 **Google Cloud Scheduler** 每分鐘調用您的 Cloud Run 服務來檢查和發送提醒。

## 部署步驟

### 1. 更新代碼
已經為您修改了以下文件：
- `run.py` - 在 Cloud Run 環境中禁用背景排程器
- `app/__init__.py` - 註冊新的 scheduler API 藍圖
- `app/routes/scheduler_api.py` - 新增提醒檢查 API 端點

### 2. 設定環境變數
在您的 Cloud Run 服務中添加以下環境變數：
```bash
REMINDER_SECRET_TOKEN=your-secure-random-token-here
```

### 3. 重新部署 Cloud Run 服務
```bash
# 構建並推送新的 Docker 映像
docker build -t us-central1-docker.pkg.dev/gcp1-462701/pill-test/0711:latest .
docker push us-central1-docker.pkg.dev/gcp1-462701/pill-test/0711:latest

# 更新 Cloud Run 服務
gcloud run deploy linebot0711 \
  --image=us-central1-docker.pkg.dev/gcp1-462701/pill-test/0711:latest \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="REMINDER_SECRET_TOKEN=your-secure-random-token-here" \
  --min-instances=1 \
  --cpu-allocation=always
```

### 4. 設定 Cloud Scheduler
```bash
# 啟用 Cloud Scheduler API
gcloud services enable cloudscheduler.googleapis.com

# 創建 App Engine 應用（如果尚未創建）
gcloud app create --region=us-central1

# 創建排程任務
gcloud scheduler jobs create http reminder-check-job \
  --location=us-central1 \
  --schedule="* * * * *" \
  --uri="https://your-cloud-run-service-url.run.app/api/check-reminders" \
  --http-method=POST \
  --headers="Content-Type=application/json,Authorization=Bearer your-secure-random-token-here" \
  --description="每分鐘檢查並發送用藥提醒" \
  --time-zone="Asia/Taipei"
```

### 5. 測試系統
```bash
# 測試健康檢查
curl https://your-service-url.run.app/api/health-detailed

# 手動觸發排程任務
gcloud scheduler jobs run reminder-check-job --location=us-central1

# 測試提醒功能
curl -X POST https://your-service-url.run.app/api/test-reminder \
  -H "Authorization: Bearer your-secure-random-token-here"
```

## 監控和除錯

### 查看 Cloud Scheduler 日誌
```bash
gcloud logging read 'resource.type="cloud_scheduler_job"' --limit=10
```

### 查看 Cloud Run 日誌
```bash
gcloud logging read 'resource.type="cloud_run_revision"' --limit=20
```

### 檢查排程任務狀態
```bash
gcloud scheduler jobs describe reminder-check-job --location=us-central1
```

## 重要配置說明

### Cloud Run 配置
- `--min-instances=1`: 確保至少有一個實例運行
- `--cpu-allocation=always`: 確保 CPU 始終分配給容器
- 這些設定確保您的服務能夠快速響應 Scheduler 的請求

### 安全性
- 使用 `REMINDER_SECRET_TOKEN` 驗證來自 Scheduler 的請求
- 建議使用強隨機字符串作為 token

### 時區設定
- Scheduler 設定為 `Asia/Taipei` 時區
- 確保提醒時間與台灣時間一致

## 故障排除

1. **提醒沒有發送**
   - 檢查 Cloud Scheduler 是否正常運行
   - 查看 Cloud Run 日誌是否有錯誤
   - 確認資料庫連線正常

2. **Scheduler 調用失敗**
   - 確認 Cloud Run 服務 URL 正確
   - 檢查 SECRET_TOKEN 是否匹配
   - 確認服務允許未經身份驗證的請求

3. **資料庫連線問題**
   - 檢查環境變數是否正確設定
   - 確認資料庫服務正常運行
   - 查看詳細健康檢查端點的回應

完成這些步驟後，您的用藥提醒系統應該能在 Cloud Run 上正常運作！