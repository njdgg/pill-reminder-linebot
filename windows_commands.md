# Windows 命令修正版本

## 查看 Cloud Run 日誌（Windows 版本）

```cmd
gcloud logging read "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"linebot0711\"" --limit=10
```

或者使用更簡單的版本：

```cmd
gcloud logging read "resource.type=cloud_run_revision" --limit=10
```

## 查看 Cloud Scheduler 日誌

```cmd
gcloud logging read "resource.type=cloud_scheduler_job" --limit=5
```

## 查看最近的所有日誌

```cmd
gcloud logging read "timestamp>=2025-07-11T04:30:00Z" --limit=20
```

## 檢查 Cloud Scheduler 任務狀態

```cmd
gcloud scheduler jobs list --location=us-central1
```

## 手動觸發排程任務

```cmd
gcloud scheduler jobs run reminder-check-job --location=us-central1
```

## 檢查 Cloud Run 服務狀態

```cmd
gcloud run services describe linebot0711 --region=us-central1
```