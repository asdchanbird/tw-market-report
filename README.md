# 台股盤後日報 📈

每個交易日晚上自動抓取證交所與期交所的盤後資料，整理成一封 HTML 郵件寄到信箱，並由 Claude 產生一段盤勢摘要。整個流程跑在 GitHub Actions 上，不需要自己的伺服器。

## 報告內容

| 區塊 | 資料 | 來源 |
|---|---|---|
| 大盤 | 加權指數收盤、漲跌、成交金額與量能變化 | 證交所 FMTQIK |
| 三大法人 | 外資／投信／自營商現貨買賣超（億元） | 證交所 BFI82U |
| 台指期籌碼 | 三大法人多空未平倉淨額與較前日增減 | 期交所 |
| 選擇權 | Put/Call Ratio（成交量、未平倉） | 期交所 |
| 信用交易 | 融資餘額、融券餘額與增減 | 證交所 MI_MARGN |
| 新台幣匯率 | 新台幣兌美元（臺銀即期買賣中價）與升貶 | 臺灣銀行牌告匯率 |
| 近 5 日趨勢圖 | 加權指數、成交金額、外資現貨買賣超、外資台指期未平倉淨額、新台幣匯率 | 同上 |
| 近期新聞整理 | 台股、國際財經各 6 則重點新聞（標題、時間、關鍵字、連結） | 鉅亨網 |
| AI 摘要 | 3～5 句盤勢解讀，不含買賣建議 | Claude API |

## 架構

```
GitHub Actions (cron 週一至五 21:30)
        │
        ▼
  report/fetchers.py ──► TWSE JSON API / TAIFEX CSV / 臺銀牌告 CSV
  report/news.py     ──► 鉅亨網新聞 API（關鍵字評分挑選）
        │  （fetch 與 parse 分離，parse 為純函式可單元測試）
        ▼
  report/models.py   ──► DailyReport dataclass（統一換算單位）
        │
        ├──► report/ai_summary.py ──► Claude API
        ├──► report/chart.py      ──► matplotlib 近 5 日趨勢圖（PNG）
        ▼
  report/render.py   ──► Jinja2 HTML 郵件模板
        ▼
  report/mailer.py   ──► Gmail SMTP
```

## 設計重點

- **非交易日自動略過**：以大盤成交資料判斷當天是否開市，假日、颱風假不會寄出空報告。
- **部分失敗不影響整體**：某個資料源抓取失敗時，報告仍會寄出，並在信末註記缺少哪些資料；AI 摘要失敗也只會省略該區塊。
- **可測試性**：HTTP 與解析邏輯分開，`tests/` 使用真實回應樣本驗證單位換算、跨月前一交易日、未平倉增減等邊界情況。
- **郵件相容性**：郵件軟體普遍不支援 `<style>`，因此模板全部使用 inline CSS；配色依台股慣例紅漲綠跌。
- **郵件內嵌圖表**：Gmail 等郵件軟體不支援 SVG 與 JavaScript，趨勢圖以 matplotlib 輸出 PNG，用 `cid:` 內嵌在信中。四張小圖各用獨立 y 軸、上下排列，方便手機閱讀；買賣超沿用紅買綠賣，並以零軸上下位置與正負號標籤作為第二重編碼，色覺辨識障礙者也能判讀。
- **新聞挑選不靠 AI**：抓取「前一交易日 21:30 至今」的新聞（週一自動涵蓋週末），排除個股盤中快訊與重複標題，再以總經／權值股關鍵字與盤勢專欄標記評分，挑出各組前 6 則。
- **網路穩定性**：requests 搭配指數退避重試，應付官方網站偶發的 5xx 錯誤；對證交所的連續請求間隔 1.5 秒，避免觸發 IP 封鎖。

## 快速開始

### 1. 本機執行

```bash
python -m venv .venv
.venv/Scripts/activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

python -m pytest                             # 單元測試
python -m report --date 2026-09-24 --dry-run --no-ai   # 產生 output/report-2026-09-24.html
```

參數：

| 參數 | 說明 |
|---|---|
| `--date YYYY-MM-DD` | 指定日期，預設為台北時間今天 |
| `--dry-run` | 不寄信，只輸出 HTML 到 `output/` |
| `--no-ai` | 不呼叫 Claude |

### 2. 準備 Gmail 應用程式密碼

1. Google 帳戶需先開啟「兩步驟驗證」
2. 前往 <https://myaccount.google.com/apppasswords> 建立應用程式密碼（16 碼）

### 3. 部署到 GitHub Actions

在 repo 的 **Settings → Secrets and variables → Actions** 新增：

| Secret | 說明 |
|---|---|
| `GMAIL_USER` | 寄件 Gmail 地址 |
| `GMAIL_APP_PASSWORD` | 上一步的應用程式密碼 |
| `MAIL_TO` | 收件人，多位以逗號分隔（可省略，預設寄給自己） |
| `ANTHROPIC_API_KEY` | Claude API 金鑰（可省略，省略則不產生 AI 摘要） |

設定後可在 **Actions → 台股盤後日報 → Run workflow** 手動執行測試；勾選 dry run 時，產生的 HTML 可從該次執行的 Artifacts 下載。

## 注意事項

- 融資融券資料通常於晚間公布，所以排程設在 21:30；GitHub 排程在尖峰時段可能延遲數十分鐘。
- GitHub 會停用 60 天內沒有任何 commit 的 repo 的排程 workflow，需要定期推送或手動重新啟用。
- 本專案僅供學習與資訊整理，不構成任何投資建議。

## 可以再延伸的方向

- 把每日數據存成 CSV／SQLite，拉長趨勢圖的期間
- 加入外資期貨未平倉的歷史分位數，判斷目前部位是否極端
- 支援 Telegram／Discord 推送
