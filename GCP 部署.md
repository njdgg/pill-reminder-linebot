# GCP 部署

### 1️⃣ 啟用 API（直接一行執行）

```
gcloud services enable run.googleapis.com artifactregistry.googleapis.com
```

---

### 2️⃣ 建立 Artifact Registry

```
gcloud artifacts repositories create njdg --repository-format=docker --location=us-central1
```

> ⚠️ 如果你已經建立過，可以略過此步驟。會出現 ALREADY_EXISTS 也沒關係。
> 

---

### 3️⃣ 設定 Docker 認證

```
gcloud auth configure-docker us-central1-docker.pkg.dev
```

---

### 4️⃣ 建立 Docker Image 並推送

```
docker build -t us-central1-docker.pkg.dev/sunlit-hook-461906-r1/njdg/pill_test:latest .
docker push us-central1-docker.pkg.dev/sunlit-hook-461906-r1/njdg/pill_test:latest
```

---

### 5️⃣ 部署到 Cloud Run

```
gcloud run deploy linebot0711 --image=us-central1-docker.pkg.dev/sunlit-hook-461906-r1/njdg/pill_test:latest --region=us-central1 --platform=managed --allow-unauthenticated --env-vars-file=env.yaml --min-instances=1 --memory=1Gi --timeout=300s
```

---

### 6️⃣ 設定 Cloud Scheduler

```
gcloud services enable cloudscheduler.googleapis.com
```

```
gcloud app create --region=us-central1
```

```
gcloud scheduler jobs create http reminder-check-job --location=us-central1 --schedule="* * * * *" --uri="https://linebot0711-712800774423.us-central1.run.app/api/check-reminders" --http-method=POST --headers="Content-Type=application/json,Authorization=Bearer pill-reminder-scheduler-token-2025-secure" --description="每分鐘檢查並發送用藥提醒" --time-zone="Asia/Taipei"
```


