# 每日 Fantasy 戰報保存 SOP（2026–27）

## 目的與邊界
每天台灣時間 15:00 的既有排程先交付戰報，通過資料驗證後另存為可追溯、不可靜默覆寫的 Markdown 快照。不得建立重複排程；目前尚未有本次修復後的 scheduled-production 執行證據。僅處理報告，**不得**修改 `rosters.json`、`league.json`、Yahoo 或進行交易。

## Input / Authority
1. 每次執行重新讀取 `main:seasons/2026-27/rosters.json`（16 隊已確認歸屬；**含 `additional_owned_players`**）、`main:seasons/2026-27/ownership/current-state.json`（未歸屬 ADD 排除與 DROP 釋出狀態）與 `main:seasons/2026-27/league.json`（唯一計分規則），記錄來源 SHA、讀取時間與各 `as_of`。日期型舊 ADD 名單不得直接聯集成永久持有。
2. 使用者在較新對話**明確確認已完成**但 repo 尚未同步的交易，可作暫時 ownership 覆蓋；逐筆列出來源、日期、ADD/DROP 與未確認欄位。意向不是交易；不推測 DROP。
3. 取 NBA 官方或可核對逐人 Box Score，標示台灣日期、NBA 當地日期、賽事結束狀態、數據來源與擷取時間。禁止杜撰。

## Output
- `seasons/2026-27/report/daily/YYYY-MM-DD.md`：驗證通過的正式戰報。
- 如缺 OREB、PF、紀律罰分或其他計分欄位，僅可標為 `PROVISIONAL`，版本 1 為 `YYYY-MM-DD.provisional.md`，修訂版用 `YYYY-MM-DD.provisional.v2.md`；不得以基礎 FP 冒充完整 FP。
- 報告 front matter 至少包含：`season`、`report_date_taipei`、`generated_at_taipei`、`status`、`roster_commit_sha`、`rosters_blob_sha`、`league_blob_sha`、`roster_as_of`、`data_cutoff_taipei`、`source_urls`、`validation_summary`。
- 正文：NBA 今日焦點；**使用者所有當日出賽球員逐人完整數據、完整 FP 與文字戰報**；其他 15 隊僅精選爆發/角色異動球員；真正 FA 精選；有證據的 GM 建議。未出賽/DNP 不可混淆。
- 檔名權威為 `scripts/report_archive_naming.py`：正式版用 `YYYY-MM-DD.md` / `YYYY-MM-DD.v2.md`，暫定版用 `YYYY-MM-DD.provisional.md` / `YYYY-MM-DD.provisional.v2.md`；歷史 `YYYY-MM-DD.v2.provisional.md` 仍可讀取。若報告已存在，產生下一個版本並說明差異，不直接覆寫。

## 執行流程
1. **Read**：讀取最新 main、賽程與 Box Score；依 `ownership/README.md` 合併基本名冊 + 同隊額外持有 + 未歸屬確認 ADD，再依較新 DROP 消解舊持有，建立 ownership set 與今日出賽交集。DROP 若尚未核實 Yahoo 當前 FA/waiver，不得直接列為推薦自由球員。
2. **Calculate**：逐項按 league.json 計算 FP，保留每項加扣分明細；未有欄位就記缺口，不補零。
3. **Review**：確認我的出賽球員 100% 覆蓋；其他隊僅精選；FA 不在 16 隊或已確認未同步 ADD；比賽皆已結束；來源可追溯；文字敘事不超出證據。
4. **Publish**：只在全部 gate PASS 時寫正式報告。未通過只可寫清楚標記的 provisional 草稿，不能宣稱正式完成。寫入專用 branch/PR，通過讀回後才合併；若無 GitHub 寫入權限，輸出可供提交的檔案並報 BLOCKED。
5. **Read-back**：從 GitHub 重新抓取報告，確認路徑、內容、版本與 SHA；在聊天中提供報告與連結。單獨存檔 SOP 必須可手動重跑。

## 完成條件 / Fail State
- `PASS`：官方賽事核對、完整自訂 FP、出賽覆蓋、ownership/FA 核對、GitHub 寫入與遠端讀回均通過。
- `PROVISIONAL`：可提供參考文章，但數據缺失或 FP 不完整；不得當成已驗收正式戰報。
- `BLOCKED`：GitHub、數據或 authority 無法取得；不以記憶代替。
- `FAIL`：任一球員歸屬錯誤、缺少使用者出賽球員、計分冒充完整或證據造假；不得發布正式版。

## 本功能 Fresh Agent 驗收豁免（Owner 決定，2026-10-22）
使用者明確表示「這個不需要 fresh agent，可以收尾了」。本次 PR #9 的 Fresh Agent A/B 狀態為 `WAIVED_BY_OWNER`，**不是 PASS，也沒有執行**。豁免只限本每日戰報歸檔功能；自動化計分／歸屬測試、GitHub 寫入／讀回、驗證資料缺口與真實排程執行安全性仍需保留。其他工作流程的 Fresh Agent 驗收規則不因此改變。

## 計分與狀態補充（P0 修正）
- FP 僅依 `league.json.scoring` 各項逐項計算：`PTS,3PTM,OREB,DREB,AST,STL,BLK,TO,FTA,PF,TECH,EJCT,FF,DD,TD`；OREB/DREB 必須分開，REB 不能直接代替。DD 與 TD 依 league.json 註記可累加，獎勵資格須由官方數據核對。
- `null`、欄位缺失、未知紀律罰分與真實零值嚴格區分；未知則 `PROVISIONAL`，不能產生標記為完整的 FP。單場完整欄位的 `FP` 可精確計算，否則僅展示已知部分並列缺口。
- **內容 gate**（數據、球員與計分）、**branch commit gate**（PR branch 寫入讀回）、**merge gate**（PR 審查合併）、**main readback gate**（正式歸檔）分別記錄；只有最後一關通過才稱為 `ARCHIVED`。
- 重跑同一資料/版本的報告須 idempotent（不重複 commit）；provisional 修正、轉正或正式報告更新均新增版本，保留原檔與差異說明。保存來源 URL、取得時間與報告內容 SHA-256。
- 每日戰報是否發布與是否出現重大 GM 操作警報是兩個獨立決策；有完賽就提供每日戰報，無新操作訊號仍要發布。

## NBA Data Adapter 與計分

- 共用版本化入口為 `scripts/nba_data_adapter.py`；Daily 與 Scouting 共用同一 `calculate_custom_fp` 實作和 `league.json`。排程優先使用 NBA 官方 dated `scoreboardv3`，失敗改用 NBA 官方靜態賽程 CDN，再以嚴格條件嘗試 ESPN；比賽資料使用官方 NBA Live Data box score 與 PBP。逐筆保存 URL、provider、取得時間、schema 版本、HTTP 狀態、原始 / 正規化 SHA-256、快照與錯誤歷程；`GAME_ID` / `PLAYER_ID` 不以姓名或日期推測。
- NBA 官方來源失敗後可用 ESPN public JSON 做具明確 GAME_ID、兩隊 tricodes 和 tipoff 的交叉比對；ESPN 玩家 ID 沒有明確 NBA ID crosswalk 時不得冒認為官方 ID，資料保持 `PARTIAL_FP`。資料可讀不等於授權；未取得公開 GitHub 再發布權時，標記 `PRIVATE_RESEARCH_ONLY`。
- FP 唯一規則仍讀當季 `league.json`。逐欄品質為 `VERIFIED_VALUE` / `VERIFIED_ZERO` / `THIRD_PARTY_RECONSTRUCTED` / `CONFLICTING` / `UNKNOWN`；每場輸出 `VERIFIED_FP` / `PARTIAL_FP` / `BLOCKED`。`FTA` 使用罰球出手數；OREB + DREB 對帳 REB；TECH / EJCT / FF 用穩定事件 ID 去重；DD / TD 由官方統計導出並依季規則累加。計算採 Decimal，`ROUND_HALF_UP` 至 0.01。
- Daily validator 同時讀 `rosters.json` 的 `players` 和 `additional_owned_players`、目前 `ownership/current-state.json` overlay；未歸屬 ADD 排除 FA，DROP 仍不代表已可領取。每項 FA 推薦必須有 Claimability Confidence。

## CLI 驗證器（離線可獨立執行）

- 指令：`python scripts/daily_report_archive.py INPUT.json --output-dir seasons/2026-27/report/daily`。Input 由共用 adapter 取得；validator 本身不發網路請求。
- INPUT 的 `league`／`rosters` 是固定來源快照；`schedule_games` 為獨立完賽清單，`schedule_source_url` 為其來源；`games` 的每個 final 場次須有 `id/date_taipei/source_url/players`。
- `ownership` 必須是當前 `ownership/current-state.json`；`report` 至少提供 `date/owner_players/other_players/free_agents/free_agent_claimability/body/source_urls/provenance`；provenance 必須含 `roster_commit_sha/rosters_blob_sha/league_blob_sha/ownership_blob_sha/data_rights_status/data_cutoff_taipei/generated_at_taipei`。如有已確認未同步交易，使用有 `status=completed,team_id,add,confirmed_at,source` 的 `confirmed_transactions`，有 DROP 才填 `drop`。
- 名稱差異可用 `identity_aliases` 明確映射 `box_name/roster_name/source`；禁止只用模糊姓名比對。程式只接受賽程顯示已結束的比賽，且若有已完賽但沒 box score 則 fail closed。
- 每位出賽球員必須帶同場 `game_id`、`player_id`；`VERIFIED_FP` 還要求明確來源的官方 NBA Player ID、所有計分欄位皆為官方已核實值 / 零。即使欄位有數值但來源第三方或衝突，只可 `PARTIAL_FP`。
- CLI 輸出 JSON `{path,sha256,created,status,missing}`。`VALIDATED` 只表示內容與數值通過驗證，**不等於有公開再發布權或 GitHub ARCHIVED**。publisher 僅接受 `data_rights_status=AUTHORIZED_FOR_GITHUB`；遠端 branch 讀回是 `PR_PENDING`，只有 GitHub main 逐位元讀回才是 `ARCHIVED`。
- 缺少欄位時只輸出 `PROVISIONAL`，不會把缺少的欄位補零。已驗證表格由程式產生，正文維持懂球球迷敘事；正文的事實與選材仍需要獨立 review。
- 本機測試：`python -m unittest discover -s tests -p 'test_*archive.py' -v` 與 `python -m unittest discover -s tests -p 'test_nba_data_adapter.py' -v`。真實資料命令為 `python scripts/verify_nba_live_e2e.py --dates YYYYMMDD YYYYMMDD YYYYMMDD --snapshot-dir <private-cache> --output <private-receipt>`；它不宣稱 scheduled production，也不把資料權利假定為已授權。Fresh Agent 驗收操作書在 `tests/fresh-agent/README.md`；本功能 Owner 豁免 Fresh Agent。

## 發布器與完成狀態
- 已有 `scripts/publish_daily_report_github.py`，建立 Draft PR 並從 PR branch 讀回；僅在另外呼叫 `--verify-main` 且內容與 main 一致時回報 `ARCHIVED`。
- 完整真實 2026–27 當日賽程、逐人資料及發報的 E2E，應以**第一次實際排程執行結果**判定，不得因歷史測試通過而冒稱已驗收。官方缺欄必須保留 `PROVISIONAL`。
- Fresh Agent：本功能 Owner 豁免，不需執行。若 GitHub 無寫入權限或建立 PR 失敗，正常傳送文章並回報 `ARCHIVE_BLOCKED`，不得冒稱已進 main。
