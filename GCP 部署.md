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
set PROJECT_ID=gcp1-462701
docker build -t us-central1-docker.pkg.dev/sunlit-hook-461906-r1/njdg/pill_test:latest .
docker push us-central1-docker.pkg.dev/sunlit-hook-461906-r1/njdg/pill_test:latest
```

---

### 5️⃣ 部署到 Cloud Run（請先準備好你的 LINE_TOKEN）

假設：

- `LINE_CHANNEL_SECRET=你的LINE_CHANNEL_SECRET`
- `LINE_CHANNEL_ACCESS_TOKEN=你的LINE_CHANNEL_ACCESS_TOKEN`

請把以下指令中的兩個值替換成你自己的：

```
gcloud run deploy pilltest --image=us-central1-docker.pkg.dev/sunlit-hook-461906-r1/njdg/pill_test:latest --region=us-central1 --platform=managed --allow-unauthenticated --env-vars-file env.yaml

```

```python
gcloud run deploy line-bot \
  --image gcr.io/my-project-id/my-image:latest \
  --region asia-east1 \
  --platform managed \
  --allow-unauthenticated \
  --env-vars-file env.yaml

```

---

# 🎯 補充一點：

在 Windows CMD 裡：

- 環境變數用 `%VAR_NAME%`
- 參數都用單行執行，不要換行、不用 `\`