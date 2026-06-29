# Booth Game — 完整使用指南

## 目錄

1. [環境準備](#1-環境準備)
2. [啟動伺服器](#2-啟動伺服器)
3. [攤位遊戲流程](#3-攤位遊戲流程)
4. [海報設計與 QR 碼](#4-海報設計與-qr-碼)
5. [網路架構 (WiFi Egg)](#5-網路架構-wifi-egg)
6. [常見問題](#6-常見問題)
7. [檔案結構](#7-檔案結構)

---

## 1. 環境準備

### 需求
- Python 3.12+
- 一台筆電（執行伺服器）
- 一台平板（顯示 Booth 頁面，供觀眾操作）
- WiFi Egg（4G 行動路由器，提供區域網路 + 網際網路）

### 首次設定

```bash
# 1. 建立虛擬環境（僅第一次）
python -m venv venv

# 2. 啟動虛擬環境（每次都要）
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Windows CMD:
venv\Scripts\activate.bat

# 3. 安裝依賴套件（僅第一次）
pip install -r requirements.txt

# 4. 設定 DeepSeek API Key
# 複製 .env.example 為 .env
copy .env.example .env
# 編輯 .env，填入你的 DeepSeek API Key：
# DEEPSEEK_API_KEY=sk-your-key-here
```

---

## 2. 啟動伺服器

### 一般模式（HTTP，無 QR 掃描相機）

```bash
.\venv\Scripts\python main_api.py
```

輸出範例：
```
[START] Starting AI-HR Bridge Platform v4.0...
[BOOTH] http://<this-ip>:8000/booth/play.html  (Booth Game)
[SSL]  HTTPS not configured. Camera QR scan not available on LAN.
```

### HTTPS 模式（啟用相機 QR 掃描，適用於攤位 LAN 環境）

```bash
# 1. 產生 SSL 憑證（僅第一次）
.\venv\Scripts\python -c "
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import os, datetime
d = os.path.join(os.path.dirname(__file__), 'cert')
os.makedirs(d, exist_ok=True)
k = rsa.generate_private_key(65537, 2048, default_backend())
s = i = x509.Name([x509.NameAttribute(NameOID.COUNTRY_NAME, 'TW'), x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'Booth'), x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')])
c = x509.CertificateBuilder().subject_name(s).issuer_name(i).public_key(k.public_key()).serial_number(x509.random_serial_number()).not_valid_before(datetime.datetime.now(datetime.timezone.utc)).not_valid_after(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=1825)).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]), False).sign(k, hashes.SHA256(), default_backend())
open(os.path.join(d,'key.pem'),'wb').write(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
open(os.path.join(d,'cert.pem'),'wb').write(c.public_bytes(serialization.Encoding.PEM))
print('HTTPS cert generated in cert/')
"

# 2. 啟動伺服器（自動偵測憑證，啟用 HTTPS）
.\venv\Scripts\python main_api.py
```

輸出範例：
```
[START] Starting AI-HR Bridge Platform v4.0...
[BOOTH] https://<this-ip>:8443/booth/play.html  (Booth Game)
[SSL]  HTTPS enabled (camera QR scan works on LAN)
```

### 關閉伺服器
按 `Ctrl+C` 或關閉命令列視窗。

---

## 3. 攤位遊戲流程

### 步驟 ① — 填寫職缺描述

```
瀏覽器打開：http://<筆電IP>:8000/booth/play.html
          或 https://<筆電IP>:8443/booth/play.html  （HTTPS 模式）
```

- 畫面顯示一個文字框，已預填預設職缺描述
- 可按「📄 使用預設」恢復預設值
- 可自行修改成任意職缺需求
- 按「下一步 →」進入步驟②

---

### 步驟 ② — 挑選條件

在攤位海報上，觀眾從 **3 個分類**各選 1 個：

| 分類 | 選項 | 對應卡片 |
|------|------|----------|
| 🎓 學歷 | 博士 / 碩士 / 學士 / 中學 | 4 張 |
| 💼 經驗 | 7 年以上 / 3-5 年 / 1-3 年 / 1 年以下 | 4 張 |
| 🔧 技能 | 高 / 低 | 2 張 |

**操作方式（二選一）：**

**方式 A：觸控點選**
- 直接在平板上點選 3 個分類的對應按鈕
- 已選的按鈕會變成藍色
- 進度條顯示「3 / 3」時即可配對

**方式 B：掃描 QR Code**
- 用平板相機掃描海報卡片上的 QR code（僅 HTTPS 模式）
- 掃描後自動填入該選項
- 掃滿 3 個分類後進度條填滿

選完後按「🔍 尋找配對」→ 進入步驟③

---

### 步驟 ③ — AI 篩選

**配對結果顯示：**
- 頭像 + 候選人姓名（如「陳志明 (Chen Ming)」）
- 配對率徽章（🟢 高 / 🟡 中 / 🔴 低）
- 難度星級
- 3 格匹配明細（🎓 學歷 ✅/❌、💼 經驗 ✅/❌、🔧 技能 ✅/❌）
- 完整履歷（可捲動瀏覽）

**篩選操作：**
1. 按「🤖 Run AI Screening」
2. 等待 AI 分析（約 5-15 秒）
3. 顯示 5 維度評分條：
   - Core Competency（核心能力）
   - Experience（經驗匹配）
   - Education（學歷背景）
   - Culture Fit（文化契合）
   - Development（發展潛力）
4. 顯示總體評分 + 匹配合適度標籤
   - ≥80：Highly Suitable 🟢
   - ≥60：Partially Suitable 🟦
   - ≥40：Borderline 🟡
   - <40：Not Suitable 🔴
5. 6 區塊詳細分析：
   - ✅ Strengths（優勢）
   - ⚠️ Weaknesses（劣勢）
   - 🏢 Culture（文化適配度）
   - 🚀 Dev（發展建議）
   - 🚩 Risks（僱用風險）
   - 🎯 Interview（建議面試問題）

**高分時自動灑花 🎉**

---

## 4. 海報設計與 QR 碼

### 海報佈局建議

```
┌─────────────────────────────────────────────────┐
│         🎯 BUILD YOUR CANDIDATE                  │
│                                                   │
│  🎓 學歷                     💼 經驗              │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐  │
│  │ 高   │ │ 中   │ │ 低   │ │ 高   │ │ 中   │  │
│  │ [QR] │ │ [QR] │ │ [QR] │ │ [QR] │ │ [QR] │  │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘  │
│                                                   │
│  🔧 技能                                          │
│  ┌──────┐ ┌──────┐ ┌──────┐                      │
│  │ 高   │ │ 中   │ │ 低   │                      │
│  │ [QR] │ │ [QR] │ │ [QR] │                      │
│  └──────┘ └──────┘ └──────┘                      │
└─────────────────────────────────────────────────┘
```

### 自行產生 QR 碼

使用任何 QR code 產生器（如 https://qrcodemonkey.com），輸入以下網址：

| 卡片 | QR Code 內容 |
|------|-------------|
| 🎓 博士 | `https://192.168.1.100:8443/booth/play.html?edu=phd` |
| 🎓 碩士 | `https://192.168.1.100:8443/booth/play.html?edu=master` |
| 🎓 學士 | `https://192.168.1.100:8443/booth/play.html?edu=bachelor` |
| 🎓 中學 | `https://192.168.1.100:8443/booth/play.html?edu=highschool` |
| 💼 7 年以上 | `https://192.168.1.100:8443/booth/play.html?exp=7plus` |
| 💼 3-5 年 | `https://192.168.1.100:8443/booth/play.html?exp=3to5` |
| 💼 1-3 年 | `https://192.168.1.100:8443/booth/play.html?exp=1to3` |
| 💼 1 年以下 | `https://192.168.1.100:8443/booth/play.html?exp=under1` |
| 🔧 技能-高 | `https://192.168.1.100:8443/booth/play.html?skill=high` |
| 🔧 技能-低 | `https://192.168.1.100:8443/booth/play.html?skill=low` |

> **注意：** 將 `192.168.1.100:8443` 換成你的伺服器實際 IP 和 Port。
> HTTP 模式使用 port 8000，無 QR 掃描功能。
> HTTPS 模式使用 port 8443，支援 QR 掃描。

---

## 5. 網路架構 (WiFi Egg)

```
[DeepSeek API 伺服器]
       ↑ 網際網路
[WiFi Egg / 4G 路由器]     ← 建立 192.168.1.x/24 區域網路
       ↓ WiFi
[主筆電]                     [攤位平板]
IP: 192.168.1.100           IP: 192.168.1.101
執行：python main_api.py    瀏覽器打開：
Port: 8000 (HTTP)            http://192.168.1.100:8000/booth/play.html
Port: 8443 (HTTPS)           https://192.168.1.100:8443/booth/play.html
```

### WiFi Egg 設定步驟

1. 開啟 WiFi Egg，確保有 4G 訊號
2. 筆電連上 WiFi Egg 的 SSID
3. 平板連上同一個 WiFi Egg 的 SSID
4. 查詢筆電的區域網路 IP：
   ```bash
   ipconfig
   # 找到 Wireless LAN adapter 的 IPv4 位址，例如 192.168.1.100
   ```
5. 在平板上打開 `http://192.168.1.100:8000/booth/play.html`

---

## 6. 常見問題

### Q: 平板打不開網頁？
A: 確認筆電防火牆允許 Python/uvicorn 連入。檢查兩台裝置是否在同一個 WiFi 網路。

### Q: QR 掃描顯示「相機需 HTTPS 或 localhost」？
A: 相機 API 需要安全連線。請改用 HTTPS 模式啟動（見 [第 2 節](#2-啟動伺服器)），或在筆電本機測試時用 `http://localhost:8000`。

### Q: Run AI Screening 失敗？
A: 確認 `.env` 檔案中有正確的 `DEEPSEEK_API_KEY`。檢查網路連線是否正常。

### Q: 選項按鈕沒反應？
A: 檢查瀏覽器開發者工具（F12）的 Console 是否有錯誤。確認伺服器有正常執行。

### Q: 配對結果不對？
A: 32 份履歷對應 32 種 (edu×exp×skill) 組合。檢查你選的 3 個條件是否與預期候選人相符。

### Q: 如何重設遊戲？
A: 重新整理頁面即可。選擇會保存在 localStorage，如果沒被清除會保留。

---

## 7. 檔案結構

```
HRMS_ESG/
├── main_api.py               ← 伺服器主入口（含 5 個 Booth API）
├── booth/                    ← Booth 遊戲
│   ├── __init__.py           ←   套件標記
│   ├── manager.py            ←   配對引擎（27 候選人、配對演算法）
│   └── play.html             ←   單一前端頁面（全部 CSS+JS 內嵌）
├── sample_data/resumes/      ← 27 份候選人履歷
├── cert/                     ← HTTPS 憑證（執行 gen_cert 後產生）
├── .env                      ← API Key 設定
├── .env.example              ← 環境變數範本
├── PROMISING_BROCHURE.md     ← 產品說明書
├── index.html                ← 主要 Dashboard
├── task_router.py            ← AI 工作流程調度
├── model_provider.py         ← DeepSeek API 整合
├── embedding_mgr.py          ← 向量嵌入管理
└── hrms_manager.py           ← HR 核心邏輯
```
