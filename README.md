# 存股雷達（財報藏寶圖 v5 網頁版）

把 Excel 的「財報藏寶圖 v5」與「投資工作籃」做成**手機可看的免費網站**：

- **爬蟲**（Python）：每天收盤後自動抓富邦 eBroker DJ 的財報與股價、證交所的股票清單
- **計算**：沿用 v5 的規則——獲利矩陣積分、9 大指標、5 年級別與趨勢、預估 EPS、本益比價格帶、高登公式、買進訊號
- **網頁**（純靜態、免安裝、手機版面）：各產業優等生（積分 ≥ 13，依產業分組）、買點清單、全部股票搜尋、個股決策總覽
- **部署**：GitHub Actions 定時更新 + GitHub Pages 免費發布，不用自己的主機

> 網頁上**沒有**「更新」按鈕：GitHub Pages 只能放靜態檔案，瀏覽器也不能直接去爬富邦（會被跨網域限制擋下）。
> 更新由 GitHub 每天自動做；想立刻更新，在手機瀏覽器開 GitHub → Actions → 「更新資料並發布」→ Run workflow（見下方）。

---

## 一、部署步驟（約 15 分鐘 + 第一次完整更新 2~3 小時）

**1. 建立儲存庫**
1. 註冊／登入 [github.com](https://github.com)。
2. 右上角 `+` → **New repository**，名稱例如 `twstock-web`，選 **Public**（免費的 GitHub Pages 需要公開儲存庫），建立。

**2. 上傳檔案**
- 網頁方式：進入儲存庫 → **Add file → Upload files**，把本資料夾**裡面的所有內容**（含隱藏的 `.github` 資料夾）拖進去 → Commit。
  - 若拖曳時 `.github` 沒被帶上，改用下面的 git 指令。
- 或用 git：
  ```bash
  cd twstock-web
  git init -b main && git add -A && git commit -m "init"
  git remote add origin https://github.com/<你的帳號>/twstock-web.git
  git push -u origin main
  ```

**3. 開啟 GitHub Pages**
儲存庫 **Settings → Pages → Build and deployment → Source** 選 **GitHub Actions**。

**4. 先做小量測試（強烈建議）**
**Actions** 分頁 → 左側「更新資料並發布」→ **Run workflow**：
- `codes` 填 `1707,2330`，`deploy` 不勾 → Run。
- 跑完點進該次執行，在 **Summary** 會看到這兩檔的結果表（現價、積分、5 年級別、9 項通過數、訊號）。
- 葡萄王(1707)的數值應和你的 Excel 差不多。若表格是空的或全部「查無資料」，代表富邦頁面格式和預期不同，把執行記錄（log）貼給我，我來修爬蟲。

**5. 正式更新**
同一個地方 **Run workflow**，`codes` 留空 → Run。第一次要抓約 1,600 檔 × 12 個頁面，約 2~3 小時（程式刻意放慢，避免對來源網站造成負擔）。
完成後，`github-pages` 環境會出現網址：`https://<你的帳號>.github.io/twstock-web/`。

**6. 手機使用**
用手機瀏覽器開上面的網址 → 分享 / 選單 →「加入主畫面」，就像 App 一樣。

之後每個**週一到週五台灣時間 18:30** 會自動更新：股價每天更新，財報依 `fund_ttl_days`（預設 7 天）輪流重抓。

> 想立刻更新：手機開 GitHub 網站（或 GitHub App）→ 儲存庫 → Actions → 「更新資料並發布」→ Run workflow。
> 注意：公開儲存庫若 60 天沒有任何活動，GitHub 會自動停用排程；到 Actions 頁面按一下 Enable 即可。

---

## 二、設定

修改根目錄的 `config.json`（在 GitHub 網頁上直接編輯即可），下一次更新就會套用：

| 欄位 | 說明（對應 Excel 決策總覽的黃底儲存格） |
|---|---|
| `pe_low / pe_mid / pe_high` | 本益比價格帶：低估／合理／高估倍數（預設 10／15／18） |
| `market_pe_adjust` | 大盤本益比調整（大盤資金多 +1、公司體質轉差下調） |
| `risk_free_rate` | 無風險利率 %（預設 1.5，**只是假設，請自行更新**） |
| `min_score_elite` | 「各產業優等生」的積分門檻（預設 13） |
| `fund_ttl_days` | 財報幾天重抓一次（預設 7） |
| `thresholds` | 9 大指標的門檻值（預設同書中標準） |
| `cyclical_industries` | 會顯示「景氣循環股」警示的產業 |
| `request_delay_sec` | 每個請求的間隔秒數（預設 0.7，請勿調太小） |

公司「亮點」與「簡介」連結來自 `data_ref/highlights.json`（由「大家都在搞什麼鬼.xlsx」轉出），可自行新增：`"代號": {"hl": "一句話亮點", "url": "簡介網址"}`。

---

## 三、專案結構

```
crawler/
  fubon.py     下載與解析富邦頁面（Big5、oMainTable、科目名稱＋最後 8 欄數字）
  twse.py      證交所 ISIN 股票清單（上市＋上櫃，只取普通股）
  scoring.py   計算邏輯（逐項對照 Excel v5 公式）
  build.py     主流程：清單 → 股價 → 輪流更新財報 → 計算 → 輸出 JSON
docs/          手機網頁（index.html / app.js / style.css），demo/ 是尚無真實資料時的示範
tests/         單元測試：用葡萄王 1707 的 Excel 實際數據，檢查 Python 結果＝Excel 結果
.github/workflows/update.yml   排程更新 + 發布
config.json    估價參數
```

**狀態保存**：爬到的原始數字存在專案的 `data` 分支（每次覆蓋成單一 commit，不會讓儲存庫越來越大），網站內容則直接發布到 Pages。

**本機執行**（選用）：
```bash
pip install -r requirements.txt
python -m unittest discover -s tests            # 驗證計算邏輯
python -m crawler.build --state state --out site/data --codes 1707,2330   # 小量實測
cp -r docs/. site/ && cd site && python -m http.server                   # 開 http://localhost:8000
```

---

## 四、和 Excel 版的差異與限制

- **一致**：獲利矩陣分級與積分、9 大指標、5 年級別／趨勢、預估 EPS（保守／趨勢／折衷）、本益比價格帶、高登公式、品質檢查、警示、買進訊號。測試以葡萄王 1707 的 Excel 數值逐項比對，全部一致。
- **金融保險業**：與投資工作籃相同，第二指標用「每股淨值年增」、ROE 門檻 A≥10%／B≥7%；不抓現金流量表，9 大指標中的現金流項目與估價僅供參考。
- **巴菲特指標**：Excel 是手動輸入；網頁版預設不使用（`buffett_indicator` 可填數字顯示在結論卡）。
- **上市櫃年數**：以證交所清單的上市日計算。
- **最新財報 PDF 連結**：依法定申報期限推估期別（與 Excel 版相同），若該公司尚未公告或證交所改了檔名規則，連結可能打不開。
- **資料來源**：富邦 eBroker DJ 與證交所的公開頁面。請遵守其使用條款，維持預設的請求間隔，僅供個人研究，不要公開轉載資料。若來源改版，爬蟲需要跟著調整；程式在「連續失敗」或「可分析股票太少」時會中止並**保留上一次的網站內容**，不會用壞資料覆蓋。
- 本專案是依書中方法整理的自我檢視工具，**不構成投資建議**。
