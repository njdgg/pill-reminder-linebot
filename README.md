# 用藥提醒 LINE Bot 🏥💊

[![CI/CD Pipeline](https://github.com/your-username/your-repo/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/your-username/your-repo/actions/workflows/ci-cd.yml)
[![Deploy to GCP](https://github.com/your-username/your-repo/actions/workflows/deploy-gcp.yml/badge.svg)](https://github.com/your-username/your-repo/actions/workflows/deploy-gcp.yml)
[![Security Scan](https://github.com/your-username/your-repo/actions/workflows/security-scan.yml/badge.svg)](https://github.com/your-username/your-repo/actions/workflows/security-scan.yml)

一個智能的 LINE Bot 應用程式，幫助用戶管理藥物提醒、辨識藥品、記錄健康狀況，並支援家人綁定功能。

## ✨ 主要功能

- 📋 **藥單辨識**: 使用 AI 技術自動辨識藥單照片
- ⏰ **用藥提醒**: 智能提醒系統，支援多種提醒模式
- 👨‍👩‍👧‍👦 **家人綁定**: 家庭成員互相關心，共同管理健康
- 🗂️ **藥歷管理**: 完整的用藥記錄管理系統
- 📊 **健康記錄**: 記錄和追蹤健康狀況
- 🤖 **AI 助手**: 基於 Google Gemini 的智能對話

## 🏗️ 技術架構

- **後端框架**: Flask 3.1.1
- **資料庫**: MySQL
- **AI 服務**: Google Gemini API
- **訊息平台**: LINE Bot SDK
- **前端**: LIFF (LINE Front-end Framework)
- **部署**: Google Cloud Run
- **容器化**: Docker

## 🚀 快速開始

### 環境需求

- Python 3.11+
- MySQL 5.7+
- Docker (可選)

### 本地開發設置

1. **克隆專案**
   ```bash
   git clone https://github.com/your-username/your-repo.git
   cd your-repo
   ```

2. **安裝依賴**
   ```bash
   pip install -r requirements.txt
   ```

3. **設置環境變數**
   ```bash
   cp .env.example .env
   # 編輯 .env 檔案，填入您的配置
   ```

4. **啟動應用程式**
   ```bash
   python run.py
   ```

### Docker 部署

1. **建構映像**
   ```bash
   docker build -t pill-reminder-bot .
   ```

2. **運行容器**
   ```bash
   docker run -p 8080:8080 --env-file .env pill-reminder-bot
   ```

## 🔧 配置說明

### 必要環境變數

```bash
# LINE Bot API 設定
LINE_CHANNEL_ACCESS_TOKEN=your_access_token
LINE_CHANNEL_SECRET=your_channel_secret
YOUR_BOT_ID=@your_bot_id

# LIFF 應用程式設定
LIFF_CHANNEL_ID=your_liff_channel_id
LIFF_ID_CAMERA=your_camera_liff_id
LIFF_ID_EDIT=your_edit_liff_id
LIFF_ID_PRESCRIPTION_REMINDER=your_prescription_reminder_liff_id
LIFF_ID_MANUAL_REMINDER=your_manual_reminder_liff_id
LIFF_ID_HEALTH_FORM=your_health_form_liff_id

# LINE Login 設定
LINE_LOGIN_CHANNEL_ID=your_login_channel_id
LINE_LOGIN_CHANNEL_SECRET=your_login_channel_secret

# Google Gemini API 設定
GEMINI_API_KEY=your_gemini_api_key

# MySQL 資料庫設定
DB_HOST=your_db_host
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=your_db_name
DB_PORT=3306

# Flask 設定
SECRET_KEY=your_secret_key
```

## 📁 專案結構

```
.
├── app/                    # 主應用程式目錄
│   ├── routes/            # 路由處理
│   │   ├── handlers/      # 業務邏輯處理器
│   │   ├── auth.py        # 認證相關
│   │   ├── liff_views.py  # LIFF 視圖
│   │   └── line_webhook.py # LINE Webhook
│   ├── services/          # 業務服務層
│   ├── templates/         # HTML 模板
│   └── utils/             # 工具函數
├── .github/               # GitHub Actions 配置
│   ├── workflows/         # CI/CD 工作流程
│   └── ISSUE_TEMPLATE/    # Issue 模板
├── Dockerfile             # Docker 配置
├── requirements.txt       # Python 依賴
├── config.py             # 應用程式配置
└── run.py                # 應用程式入口點
```

## 🔄 CI/CD 流程

本專案使用 GitHub Actions 實現自動化 CI/CD：

### 主要工作流程

1. **CI/CD Pipeline** (`.github/workflows/ci-cd.yml`)
   - 程式碼品質檢查
   - 自動化測試
   - Docker 映像建構和推送
   - 自動部署到 staging/production

2. **GCP 部署** (`.github/workflows/deploy-gcp.yml`)
   - 部署到 Google Cloud Run
   - 環境變數管理
   - 健康檢查

3. **安全掃描** (`.github/workflows/security-scan.yml`)
   - 依賴漏洞掃描
   - 程式碼安全分析
   - Docker 映像安全檢查

### 部署環境

- **Staging**: `develop` 分支自動部署
- **Production**: `main` 分支自動部署

## 🔒 安全性

- 使用 GitHub Secrets 管理敏感資訊
- 定期進行安全掃描
- 依賴項目自動更新 (Dependabot)
- 容器映像漏洞檢測

## 🧪 測試

```bash
# 運行測試
python -m pytest

# 運行測試並生成覆蓋率報告
python -m pytest --cov=app

# 程式碼風格檢查
flake8 app/
```

## 📝 貢獻指南

1. Fork 此專案
2. 創建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交變更 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 開啟 Pull Request

請確保：
- 遵循程式碼風格指南
- 添加適當的測試
- 更新相關文檔

## 📄 授權

此專案採用 MIT 授權 - 詳見 [LICENSE](LICENSE) 檔案

## 🆘 支援

如果您遇到問題或有建議，請：

1. 查看 [Issues](https://github.com/your-username/your-repo/issues)
2. 創建新的 Issue
3. 聯繫維護者

## 🙏 致謝

- [LINE Developers](https://developers.line.biz/)
- [Google Gemini](https://ai.google.dev/)
- [Flask](https://flask.palletsprojects.com/)
- 所有貢獻者

---

**注意**: 請確保在生產環境中妥善保護您的 API 金鑰和敏感資訊。