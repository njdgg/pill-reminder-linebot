# 🚀 快速修復用藥提醒時區問題

## 問題分析
從您的日誌可以看出：
- Cloud Scheduler 正常運行 ✅
- 提醒資料已寫入資料庫 ✅  
- **問題**: 時區不匹配 ❌
  - 系統使用 UTC 時間 `[04:33]`
  - 您在台北/香港時間 `12:33` 設定提醒
  - 時差 8 小時導致無法匹配

## 修復內容
我已經修改了以下文件，讓系統使用台北時區：
1. `app/services/reminder_service.py` - 使用台北時區檢查提醒
2. `app/routes/scheduler_api.py` - 測試端點也使用台北時區

## 立即部署修復
```bash
# 1. 重新構建映像
docker build -t us-central1-docker.pkg.dev/gcp1-462701/pill-test/0711:latest .

# 2. 推送映像
docker push us-central1-docker.pkg.dev/gcp1-462701/pill-test/0711:latest

# 3. 部署到 Cloud Run
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

## 測試修復結果
部署完成後，等待 1-2 分鐘，然後檢查日誌：
```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="linebot0711"' --limit=10
```

您應該會看到類似這樣的日誌：
```
[12:35] 開始檢查提醒（台北時間）...
UTC時間: 04:35
[12:35] 找到 X 筆到期提醒
```

## 手動測試（可選）
```bash
curl -X POST "https://linebot0711-712800774423.us-central1.run.app/api/test-reminder" \
  -H "Authorization: Bearer pill-reminder-scheduler-token-2025-secure" \
  -H "Content-Type: application/json"
```

## 預期結果
修復後，當您設定的提醒時間到達時（例如 12:35），系統應該會：
1. 正確匹配台北時間
2. 找到對應的提醒
3. 發送 LINE 訊息給您

## 如果還有問題
請提供最新的日誌，我會進一步協助診斷。