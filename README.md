# 台股短線技術分析工具 (tw_ta)

用 Python 抓台股資料,做技術指標、籌碼面、基本面分析、條件選股、實戰回測與
風險試算,並提供網頁介面操作。偏短線/技術操作取向。

> ⚠️ **免責聲明**:本工具所有輸出僅為技術/籌碼/基本面資料的客觀計算與整理,
> **不是投資建議**,不保證準確或獲利。股價來自 yfinance(免費、約 15 分鐘延遲、
> 日線收盤),不適合當沖即時下單。回測為歷史統計,不代表未來。
> 實際買賣請自行判斷並承擔風險。

## 安裝(只需一次)

```powershell
python -m pip install -r requirements.txt
```

## ⭐ 最簡單:用網頁介面

雙擊 **`開啟介面.bat`**,瀏覽器自動開啟操作介面。頂部顯示**大盤總覽**(加權指數、0050、櫃買指數),
可勾選顯示**大盤多空**(三大法人台指期淨未平倉口數);下方分頁:

| 分頁 | 功能 |
|------|------|
| ⚡ **當沖看盤** | 即時報價看板(每5秒更新、依漲跌排序、創高/漲停近**異動標記**)+ 分鐘K線+VWAP + **即時五檔買賣盤**(內外盤比/距漲跌停)+ **當沖損益試算** |
| 🔍 **清單掃描** | 一鍵掃觀察清單,表格列出每檔短線訊號、漲跌(紅綠標色)、可加查三大法人、一鍵匯出 Excel |
| 🎯 **條件篩選** | 勾選技術+籌碼+基本面條件(如均線多頭+外資連買+本益比<20),從股池篩出符合的股票 |
| 📊 **個股分析(短線)** | **即時報價**、綜合評分+雷達圖、**進階K線**(日/週/月K、訊號箭頭、量價分佈、支撐壓力、型態、十字游標、畫線工具)、**基本面**(EPS/毛利率/ROE/營收趨勢/本益比評價/配息)、**籌碼面**(三大法人+外資持股+累計買賣超+融資券趨勢+券資比+券商分點)、實戰回測、部位計算、**個股新聞** |
| 📈 **中線分析** | 波段角度:季線/年線排列、週KD、波段突破,個股趨勢體檢 + 批次掃中線偏多股 |
| 🆚 **比較** | 同業比較 + 多股 PK(走勢正規化)+ **類股強弱**(各產業近N日平均報酬) |
| 🌡️ **盤勢/資金** | 大盤技術狀態+研判、全市場三大法人買賣超、**本週資金流入族群** |
| ⚙️ **自選股管理** | **健診排行**(自選股全部評分排序)+ 新增/刪除觀察股 |

> 體驗優化:個股分析頁的細節改用「分段選擇器」**延遲載入**(點哪塊才抓資料,首屏更快);
> 掃描/篩選結果可**選一檔直接帶入「個股分析」**分頁。

關閉介面:在跳出的黑色視窗按 `Ctrl+C` 或直接關掉。第一次啟動若問 email,按 Enter 跳過。

## 🌐 讓朋友也能用(部署到 Streamlit Cloud)

把這個資料夾放到 GitHub,再用免費的 Streamlit Community Cloud 一鍵部署,
就會得到一個公開網址,朋友點連結隨時能用(你電腦不用開)。

**步驟:**
1. 註冊/登入 GitHub(https://github.com)。
2. 在 GitHub 點右上角 **+ → New repository**,取個名字(例如 `tw-ta`),
   可選 Private(私人),按 **Create repository**。
3. 在本資料夾把程式推上去(本地 git 已幫你 commit 好,只差設定遠端):
   ```powershell
   git remote add origin https://github.com/<你的帳號>/<庫名>.git
   git push -u origin main
   ```
   (第一次 push 會跳出 GitHub 登入授權,照著登入即可)
4. 到 https://share.streamlit.io 用 GitHub 登入 → **Create app** →
   選剛剛的 repo、分支 `main`、主檔案填 `app.py` → **Deploy**。
5. 等一兩分鐘安裝套件,就會得到網址 `https://<你的app>.streamlit.app`,
   把這個網址傳給朋友即可。

**進階(選用):** 想讓籌碼/基本面更穩定,到 Streamlit Cloud 的
**App → Settings → Secrets** 貼上:
```toml
FINMIND_TOKEN = "你的FinMind token"
```
程式會自動讀取(到 https://finmindtrade.com 免費註冊可拿 token)。

> ⚠ 雲端版說明:**每日排程掃描 + Email 通知是你本機的功能,雲端不會跑**
> (雲端沒有你的 Windows 排程器)。但互動分析、掃描、篩選、回測、中線分析等
> 核心功能都正常。另外雲端的觀察清單編輯不會永久保存(重新部署會還原)。

### 部署後要更新網站

Streamlit Cloud 會**自動**偵測 GitHub 有新版本並重新部署,你不用碰 Streamlit 後台。
本機改完東西後,只要把修改推上 GitHub 即可:

**最簡單:雙擊 `更新網站.bat`** — 它會自動 commit、同步遠端、push,
網站約 1 分鐘後自動更新。

手動指令版(等同批次檔內容):
```powershell
git add -A
git commit -m "更新說明"
git pull --rebase origin main   # 先同步遠端,避免被擋
git push origin main
```

小提醒:
- 黑視窗顯示 `nothing to commit` = 沒有新變更,正常。
- 出現 `CONFLICT` = 本機與遠端改到同處衝突,需手動解決(可求助)。
- `cache/`、`reports/` 等暫存已被 `.gitignore` 排除,不會上傳。

## 功能與命令列用法

### 清單掃描
```powershell
python scan.py                 # 掃 watchlist.txt
python scan.py 2330 2454       # 指定代號
python scan.py --bullish-only  # 只看有看多訊號
```

### 條件篩選器
```powershell
python screener.py             # 跑範例條件(可在檔案 __main__ 改條件)
```
從股池 `universe.txt`(約60檔中大型股,可自行擴充)篩選。支援條件:RSI 範圍、
KD 金叉、均線多頭、MACD 翻紅、布林突破、站上月線、乖離上限、法人連買天數、
法人合計、本益比上限、殖利率下限、營收年增率下限。

### 中線(波段)分析
```powershell
python swing.py 2330           # 2330 中線趨勢體檢(多頭/偏多/盤整/偏空/空頭)
```
與短線不同,看的是趨勢:月線/季線/半年線/年線排列、站上年線與否、季線翻揚、
週 KD、波段突破(創近季新高)。用 2 年資料計算。

中線訊號也可回測(在 UI 中線分頁,或程式呼叫 `swing.backtest_swing(df)`),
用 5 年資料、較長持有(預設20日)、較寬停損(預設8%/停利20%)。

### 實戰回測
```powershell
python backtest.py 2330 5      # 2330,持有5日,含停損停利+手續費,並與0050比較
```
事件式回測:隔日進場、停損/停利、扣手續費(0.1425%×2)+證交稅(0.3%)、
最大回撤、權益曲線、與大盤 0050 買進持有比較。

### 籌碼/基本面/新聞/評分
```powershell
python chips.py 2330           # 三大法人、外資持股比率、券資比
python fundamentals.py 2330    # 本益比/殖利率/EPS/毛利率/ROE/連續配息/本益比評價
python news.py 2330            # 個股最新新聞(標題/來源/連結)
python score.py 2330           # 技術+基本+籌碼 綜合評分
python broker.py 2330 5        # 券商分點買賣超(近5日;第2參數為交易日數)
```

> 券商分點(`broker.py`)資料來自 HiStock 網頁爬蟲,**非官方 API**,
> 網站改版或反爬時可能失效;分點不等於特定人、含借券/避險雜訊,僅供參考。

### 部位計算 + ATR 停損
```powershell
python risk.py 2330 500000 2   # 本金50萬、單筆風險2%,算可買張數與停損價
```
固定風險法:每筆最多賠「本金×風險%」,反推張數;停損用 ATR×倍數。

### 每日自動掃描 + Email 通知
```powershell
python daily_scan.py           # 掃描、存報告到 reports\,設定後寄 Email
```
**排程已設定好** ✅:Windows 工作排程器已建立任務「**台股每日掃描**」,
每週一~週五 14:30(台股收盤後)自動執行,報告存到 `reports\YYYY-MM-DD.txt`。
報告含**短線當日訊號**與**中線波段趨勢**兩部分。

管理排程(PowerShell):
```powershell
Get-ScheduledTaskInfo -TaskName "台股每日掃描"   # 看下次/上次執行
Start-ScheduledTask     -TaskName "台股每日掃描"   # 立刻手動跑一次
Disable-ScheduledTask   -TaskName "台股每日掃描"   # 暫停
Unregister-ScheduledTask -TaskName "台股每日掃描"  # 移除
```
也可在「工作排程器」GUI 裡找到同名任務調整時間。

**Email 設定**(選用):設系統環境變數 `TWTA_SMTP_USER`(Gmail)、`TWTA_SMTP_PASS`
(Gmail 應用程式密碼,非登入密碼)、`TWTA_MAIL_TO`(收件信箱),排程跑完就會寄信。
詳見 `notify.py`。未設定時只存報告檔。

### 個股技術圖(存 PNG)
```powershell
python plot.py 2330
```

## 技術訊號一覽

**看多**:KD 黃金交叉、MACD 翻紅、均線多頭排列、帶量突破月線、RSI 超賣回升、
突破布林上軌、量價同步(OBV)、爆量。
**警示**:KD 死亡交叉、RSI 過熱(>80)、乖離過大(>12%)。

**中線訊號**:季線黃金交叉(MA60上穿MA120)、站上年線、週KD黃金交叉、波段突破
(創近季新高)、季線翻揚且站穩;趨勢分級為 多頭/偏多/盤整/偏空/空頭。

指標:MA(5/10/20/60/120/240)、KD、週KD、MACD、週MACD、RSI、布林通道、
乖離率 BIAS、OBV、ATR。

## 資料來源
- **即時報價**:證交所 MIS(`mis.twse.com.tw`)官方即時行情。**交易時間(平日09:00–13:30)**
  才會跳動,盤後顯示最後成交;屬近即時(數秒~十數秒),非逐筆。雲端(Streamlit Cloud)
  可能被擋,本機通常正常。
- **股價(歷史/技術分析)**:yfinance(免費,約15分鐘延遲日線)。本地快取在 `cache\`,當日重用、隔日自動清除。
- **籌碼/基本面/新聞**:FinMind 免費 API。所有 FinMind 請求都經過 `finmind.py`
  的**本地快取**(`cache/finmind/`,當日重用、隔日自動清),同一查詢一天只打一次,
  且綜合評分與各區塊共用快取,大幅降低請求數。

### 遇到流量限制怎麼辦

FinMind 免費版有流量上限(匿名最嚴,且跟同 IP 的人共用)。兩招解決:

1. **拿免費 token(最有效)**:到 https://finmindtrade.com 免費註冊 → 會員中心複製
   API token。額度比匿名大很多。設定方式:
   - **本機**:設環境變數 `FINMIND_TOKEN`(PowerShell 永久設定:
     `setx FINMIND_TOKEN "你的token"`,設完重開終端機/程式)。
   - **雲端(Streamlit Cloud)**:App → Settings → Secrets 貼上
     `FINMIND_TOKEN = "你的token"`,程式會自動讀取。
2. **靠本地快取**:同一檔當天重複看不會再打 API;掃描/篩選也會重用股價與籌碼快取。

> 即使沒 token,程式遇到流量上限也只會該區塊顯示「抓取中/流量上限」,不會整個壞掉,
> 稍等(額度每小時恢復)或設 token 即可。

## 檔案結構
| 檔案 | 用途 |
|------|------|
| `app.py` | ⭐ Streamlit 網頁介面(主要入口、分頁邏輯) |
| `ui_common.py` | UI 共用層:快取包裝、輔助函式、常數、即時報價、共用圖表 |
| `tw_time.py` | 台北時區工具(避免雲端 UTC 差一天) |
| `data.py` | yfinance 股價抓取 + 批次下載 + 本地快取 |
| `indicators.py` | 技術指標計算 |
| `signals.py` | 短線訊號判斷 |
| `backtest.py` | 實戰回測引擎 |
| `swing.py` | 中線(波段)趨勢分析 |
| `screener.py` | 自訂條件選股 |
| `chips.py` | 三大法人/外資持股/累計買賣超/券資比 |
| `fundamentals.py` | 股名/估值/EPS/毛利率/ROE/配息/本益比評價 |
| `news.py` | 個股新聞(Google News RSS,即時) |
| `score.py` | 技術+基本+籌碼 綜合評分 |
| `broker.py` | 券商分點進出(HiStock 爬蟲,當日/3日/5日) |
| `sector.py` | 類股強弱(各產業平均報酬) |
| `futures.py` | 大盤多空(三大法人台指期淨未平倉口數) |
| `market.py` | 盤勢(大盤技術狀態/研判、全市場法人買賣超) |
| `realtime.py` | 個股即時報價(證交所 MIS,交易時間每3秒更新) |
| `charting.py` | 進階看盤:K線週期/訊號標記/量價分佈/支撐壓力/型態辨識 |
| `finmind.py` | FinMind 共用抓取層 + 本地快取 + 自動重試 |
| `test_smoke.py` | 離線煙霧測試(`測試.bat` 或 `pytest`) |
| `risk.py` | 部位計算 + ATR 停損 |
| `daily_scan.py` | 每日自動掃描 + 報告 |
| `notify.py` | Email 通知 |
| `scan.py` / `plot.py` | 命令列掃描 / 技術圖 |
| `watchlist.txt` / `universe.txt` | 觀察清單 / 篩選股池 |
| `開啟介面.bat` 等 | Windows 一鍵啟動 |

## 🔐 安全建議(重要)

進站密碼預設為 `1524`,**但此預設值寫在(公開的)程式碼裡,等於沒保護**。
若部署給他人用,**務必**到 Streamlit Cloud **Settings → Secrets** 設一組自己的密碼:
```toml
APP_PASSWORD = "你的新密碼"
```
設定後預設的 `1524` 即失效(Secrets 優先),且建議用較長、非純數字的密碼。
已內建:錯誤嘗試 5 次鎖定、安全比對(`hmac.compare_digest`)。
> 提醒:此為「簡單進站密碼」,適合朋友間分享,非高強度帳號系統。

## 穩定性 / 測試

- **自動重試**:yfinance / FinMind / HiStock 的請求失敗或限流時會自動重試,
  雲端給朋友用更穩;某個資料源壞掉只會該區塊降級,不會整個 app 崩掉。
- **煙霧測試**:改完程式後雙擊 `測試.bat`(或 `python -m pytest test_smoke.py`),
  用離線合成資料快速驗證核心計算(指標/訊號/回測/評分)沒被改壞。需先 `pip install pytest`。

## 想自訂?
- **改訊號門檻 / 加指標**:編輯 `signals.py` / `indicators.py`(在 `enrich()` 接上)。
- **改篩選股池**:編輯 `universe.txt`。
- **換資料源**(即時報價、更完整籌碼):替換 `data.py` 的 `fetch()` 即可,其餘不受影響。
