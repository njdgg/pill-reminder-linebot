# 🔧 修復用藥提醒系統 - 診斷指南

## 問題診斷步驟

### 1. 檢查 Cloud Scheduler 是否已設定
```bash
gcloud scheduler jobs list --location=us-central1
```

如果沒有看到 `reminder-check-job`，請執行以下命令創建：

```bash
# 啟用 Cloud Scheduler API
gcloud services enable cloudscheduler.googleapis.com

# 創建 App Engine 應用（如果需要）
gcloud app create --region=us-central1

# 創建排程任務
gcloud scheduler jobs create http reminder-check-job \
  --location=us-central1 \
  --schedule="* * * * *" \
  --uri="https://linebot0711-712800774423.us-central1.run.app/api/check-reminders" \
  --http-method=POST \
  --headers="Content-Type=application/json,Authorization=Bearer pill-reminder-scheduler-token-2025-secure" \
  --description="每分鐘檢查並發送用藥提醒" \
  --time-zone="Asia/Taipei"
```

### 2. 測試服務健康狀態
```bash
curl -X GET "https://linebot0711-712800774423.us-central1.run.app/api/health-detailed"
```

### 3. 手動測試提醒檢查
```bash
curl -X POST "https://linebot0711-712800774423.us-central1.run.app/api/check-reminders" \
  -H "Authorization: Bearer pill-reminder-scheduler-token-2025-secure" \
  -H "Content-Type: application/json"
```

### 4. 測試提醒功能
```bash
curl -X POST "https://linebot0711-712800774423.us-central1.run.app/api/test-reminder" \
  -H "Authorization: Bearer pill-reminder-scheduler-token-2025-secure" \
  -H "Content-Type: application/json"
```

### 5. 檢查 Cloud Run 日誌
```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="linebot0711"' --limit=20
```

### 6. 檢查 Cloud Scheduler 日誌
```bash
gcloud logging read 'resource.type="cloud_scheduler_job"' --limit=10
```

## 常見問題和解決方案

### 問題 1: Cloud Scheduler 任務不存在
**解決方案**: 執行上面的創建排程任務命令

### 問題 2: 401 Unauthorized 錯誤
**原因**: SECRET_TOKEN 不匹配
**解決方案**: 確認 env.yaml 中的 REMINDER_SECRET_TOKEN 與 Scheduler 中的一致

### 問題 3: 服務無法訪問
**原因**: Cloud Run 服務可能沒有正確部署
**解決方案**: 重新部署服務
```bash
gcloud run deploy linebot0711 \
  --image=us-central1-docker.pkg.dev/gcp1-462701/pill-test/0711:latest \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --env-vars-file=env.yaml \
  --min-instances=1 \
  --cpu-allocation=always \
  --memory=1Gi \
  --timeout=300s
```

### 問題 4: 資料庫連線失敗
**檢查**: 確認 env.yaml 中的資料庫設定正確
**解決方案**: 檢查 DB_HOST, DB_USER, DB_PASS, DB_NAME 是否正確

### 問題 5: 沒有提醒資料
**檢查**: 確認資料庫中有設定的提醒
**解決方案**: 
1. 檢查 `medicine_schedule` 表是否有資料
2. 確認時間格式正確（HH:MM）
3. 檢查 `get_reminders_for_scheduler` 函數

## 手動觸發測試

### 立即執行排程任務
```bash
gcloud scheduler jobs run reminder-check-job --location=us-central1
```

### 檢查任務執行結果
```bash
gcloud scheduler jobs describe reminder-check-job --location=us-central1
```

## 除錯提示

1. **檢查時間**: 確認您設定的提醒時間與當前時間匹配
2. **檢查時區**: 系統使用 Asia/Taipei 時區
3. **檢查資料**: 確認資料庫中有有效的提醒記錄
4. **檢查權限**: 確認 Cloud Run 服務有訪問資料庫的權限

## 如果問題持續存在

請執行以下命令收集詳細資訊：
```bash
# 檢查服務狀態
gcloud run services describe linebot0711 --region=us-central1

# 檢查最近的日誌
gcloud logging read 'resource.type="cloud_run_revision"' --limit=50 --format="table(timestamp,severity,textPayload)"

# 檢查環境變數
gcloud run services describe linebot0711 --region=us-central1 --format="value(spec.template.spec.template.spec.containers[0].env[].name)"
```