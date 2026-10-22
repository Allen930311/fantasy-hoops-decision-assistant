# 每日 Fantasy 戰報保存 SOP（2026–27）

## 目的與邊界
每天台灣時間 15:00 的戰報先在聊天中交付，通過資料驗證後，另存為可追溯、不可靜默覆寫的 Markdown 快照。這是獨立 SOP；排程接線屬後續步驟。僅處理報告，**不得**修改 `rosters.json`、`league.json`、Yahoo 或進行交易。

## Input / Authority
1. 每次執行重新讀取 `main:seasons/2026-27/rosters.json`（16 隊 ownership 第一順位）與 `main:seasons/2026-27/league.json`（唯一計分規則），記錄 commit SHA、檔案 blob SHA、讀取時間與 roster `as_of`。
2. 使用者在較新對話**明確確認已完成**但 repo 尚未同步的交易，可作暫時 ownership 覆蓋；逐筆列出來源、日期、ADD/DROP 與未確認欄位。意向不是交易；不推測 DROP。
3. 取 NBA 官方或可核對逐人 Box Score，標示台灣日期、NBA 當地日期、賽事結束狀態、數據來源與擷取時間。禁止杜撰。

## Output
- `seasons/2026-27/report/daily/YYYY-MM-DD.md`：驗證通過的正式戰報。
- 如缺 OREB、PF、紀律罰分或其他計分欄位，僅可標為 `PROVISIONAL`，存 `YYYY-MM-DD.provisional.md`；不得以基礎 FP 冒充完整 FP。
- 報告 front matter 至少包含：`season`、`report_date_taipei`、`generated_at_taipei`、`status`、`roster_commit_sha`、`rosters_blob_sha`、`league_blob_sha`、`roster_as_of`、`data_cutoff_taipei`、`source_urls`、`validation_summary`。
- 正文：NBA 今日焦點；**使用者所有當日出賽球員逐人完整數據、完整 FP 與文字戰報**；其他 15 隊僅精選爆發/角色異動球員；真正 FA 精選；有證據的 GM 建議。未出賽/DNP 不可混淆。
- 若報告已存在，建立 `YYYY-MM-DD.v2.md` 或更高版並說明差異，不直接覆寫；保留舊版。

## 執行流程
1. **Read**：讀取最新 main、賽程與 Box Score，建立 ownership set 與今日出賽交集。
2. **Calculate**：逐項按 league.json 計算 FP，保留每項加扣分明細；未有欄位就記缺口，不補零。
3. **Review**：確認我的出賽球員 100% 覆蓋；其他隊僅精選；FA 不在 16 隊或已確認未同步 ADD；比賽皆已結束；來源可追溯；文字敘事不超出證據。
4. **Publish**：只在全部 gate PASS 時寫正式報告。未通過只可寫清楚標記的 provisional 草稿，不能宣稱正式完成。寫入專用 branch/PR，通過讀回後才合併；若無 GitHub 寫入權限，輸出可供提交的檔案並報 BLOCKED。
5. **Read-back**：從 GitHub 重新抓取報告，確認路徑、內容、版本與 SHA；在聊天中提供報告與連結。單獨存檔 SOP 必須可手動重跑。

## 完成條件 / Fail State
- `PASS`：官方賽事核對、完整自訂 FP、出賽覆蓋、ownership/FA 核對、GitHub 寫入與遠端讀回均通過。
- `PROVISIONAL`：可提供參考文章，但數據缺失或 FP 不完整；不得當成已驗收正式戰報。
- `BLOCKED`：GitHub、數據或 authority 無法取得；不以記憶代替。
- `FAIL`：任一球員歸屬錯誤、缺少使用者出賽球員、計分冒充完整或證據造假；不得發布正式版。

## Fresh Agent 驗收
使用無歷史對話的 Fresh Agent，分別測試『不使用 SOP』與『使用 SOP』對同一份固定真實 NBA 比賽/roster/scoring 樣本的結果；驗證覆蓋率、FP 精確度、FA ownership、provisional gate、重跑去重、版本保留與遠端讀回。保留原始 transcript 與比較結果。驗收前不得宣稱排程已具備自動回存能力。
