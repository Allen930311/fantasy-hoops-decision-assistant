# 每日 Fantasy 戰報保存 SOP（2026–27）

## 目的與邊界
每天台灣時間 15:00 的既有排程先交付戰報，通過資料驗證後另存為可追溯、不可靜默覆寫的 Markdown 快照。不得建立重複排程；目前尚未有本次修復後的 scheduled-production 執行證據。僅處理報告，**不得**修改 `rosters.json`、`league.json`、Yahoo 或進行交易。

## Input / Authority
1. 每次執行重新讀取 `main:seasons/2026-27/rosters.json`（16 隊已確認歸屬；**含 `additional_owned_players`**）、`main:seasons/2026-27/ownership/current-state.json`（未歸屬 ADD 排除與 DROP 釋出狀態）與 `main:seasons/2026-27/league.json`（唯一計分規則），記錄來源 SHA、讀取時間與各 `as_of`。日期型舊 ADD 名單不得直接聯集成永久持有。
2. 使用者在較新對話**明確確認已完成**但 repo 尚未同步的交易，可作暫時 ownership 覆蓋；逐筆列出來源、日期、ADD/DROP 與未確認欄位。意向不是交易；不推測 DROP。
3. 僅使用服務條款允許本用途的 NBA 結構化數據來源；標示台灣日期、NBA 當地日期、賽事結束狀態、來源與擷取時間。公開網址或 HTTP 200 不等於自動取得/使用許可。禁止杜撰。

## Output
- `seasons/2026-27/report/daily/YYYY-MM-DD.md`：驗證通過的正式戰報。
- 如缺 OREB、PF、紀律罰分或其他計分欄位，僅可標為 `PROVISIONAL`，版本 1 為 `YYYY-MM-DD.provisional.md`，修訂版用 `YYYY-MM-DD.provisional.v2.md`；不得以基礎 FP 冒充完整 FP。
- 報告 front matter 至少包含：`season`、`report_date_taipei`、`generated_at_taipei`、`status`、`roster_commit_sha`、`rosters_blob_sha`、`league_blob_sha`、`roster_as_of`、`data_cutoff_taipei`、`source_urls`、`validation_summary`。
- 正文：NBA 今日焦點；**使用者所有當日出賽球員逐人 MIN、PTS、3PTM、OREB、DREB、AST、STL、BLK、TO、FTA、PF、TECH、EJCT、FF、DD、TD 與完整 FP 或逐欄缺口**；其他 15 隊僅精選爆發/角色異動球員；真正 FA 候選；有證據的 GM 建議。未出賽/DNP 不可混淆。
- 檔名權威為 `scripts/report_archive_naming.py`：正式版用 `YYYY-MM-DD.md` / `YYYY-MM-DD.v2.md`，暫定版用 `YYYY-MM-DD.provisional.md` / `YYYY-MM-DD.provisional.v2.md`；歷史 `YYYY-MM-DD.v2.provisional.md` 仍可讀取。若報告已存在，產生下一個版本並說明差異，不直接覆寫。

## 執行流程
1. **Read**：讀取最新 main、賽程與 Box Score；依 `ownership/README.md` 合併基本名冊 + 同隊額外持有 + 未歸屬確認 ADD，再依較新 DROP 消解舊持有，建立 ownership set 與今日出賽交集。DROP 若尚未核實 Yahoo 當前 FA/waiver，不得直接列為推薦自由球員。
2. **Calculate**：逐項按 league.json 計算 FP，保留每項加扣分明細；未有欄位就記缺口，不補零。
3. **Review**：確認我的出賽球員 100% 覆蓋；其他隊僅精選；FA 不在 16 隊或已確認未同步 ADD；比賽皆已結束；來源可追溯；文字敘事不超出證據。
4. **Deliver**：先在既有 15:00 任務結果交付完整可讀戰報。Runtime、存檔或公開發布失敗都不得抑制交付；逐欄保留未知值，並把內容狀態標為 `PROVISIONAL`。
5. **Store / publish separately**：只在實際存在且授權的 Owner-accessible 持久目的地寫入不可覆寫版本，讀回完整 UTF-8 內容並核對 SHA-256。Public GitHub 發布是獨立選擇；NBA 衍生內容的來源/再發布權未確認前，不建立公開分支、檔案或 PR。

## 獨立狀態 / Fail State
- `content_status=VALIDATED|PROVISIONAL`：只代表身份、欄位品質與 FP 計算狀態。
- `runtime_status=EXECUTED_CANONICAL|RUNTIME_INTEGRATION_BLOCKED|NOT_EXECUTED`：只有正式任務實際呼叫最新 main 才能標 `EXECUTED_CANONICAL`。
- `delivery_status=DELIVERED|FAILED`：完整報告確實出現在 Owner-facing 任務結果才是 `DELIVERED`。
- `storage_status=STORED|STORAGE_BLOCKED`：需實際持久目的地、未截斷讀回、位元組相同及 SHA-256 相同；無權限或無讀回證據則為 `STORAGE_BLOCKED`。
- `publication_rights_status=AUTHORIZED|UNVERIFIED|BLOCKED` 與來源使用權分開記錄；`publication_status=PUBLISHED|PR_PENDING|PUBLICATION_BLOCKED|NOT_REQUESTED`：受限來源或再發布權尚未核實時公開發布為 `PUBLICATION_BLOCKED`，但不影響交付或允許的私有保存。
- 真實資料缺漏標 `PROVISIONAL`，不得補零。任何來源、Runtime、保存或發布失敗都要列明，不以記憶代替。
- 收據必須另記 `execution_mode=SCHEDULED_PRODUCTION|MANUAL_REPLAY|CI|SYNTHETIC|UNKNOWN`。正式排程須有既有任務 ID 與自動化平台可讀回的 run ID / 時間；程式欄位或手動 replay 不能自我證明為排程執行。
- `scripts/daily_report_run_receipt.py` 只組合呼叫者提供的證據與雜湊；不呼叫執行器、不驗證外部帳號權限，也不是平台簽章。單元測試全部是 synthetic，不等於真人可存取的持久保存或 Scheduled E2E。

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
- NBA Live box score 的 `played` 可能是布林、數字或字串；字串 `"0"` 必須是 DNP，不是 True 或 VERIFIED_ZERO。未知 `played` 值令該來源 schema 失敗並觸發合法 fallback，不可當作出賽、DNP 或零 FP。
- Adapter 技術上提供多來源 fallback，但不能因此推定來源授權。只有在取得方式與本 Fantasy 用途均獲來源條款允許時才可呼叫備援；ESPN public JSON 也須先核實自動化使用條款。第三方玩家 ID 沒有明確 NBA ID crosswalk 時不得冒認為官方 ID，資料保持 `PARTIAL_FP`。
- 報告中的單場統計事實、依 `league.json` 算出的 Fantasy Points、原創評論、原始供應商回應屬不同資料類別，但任何一類都不得預設已取得來源授權。既有公開報告清冊與 NBA 條款查核見 `docs/data-publication-audit-2026-10-27.md`；舊檔標記待權利複核，新報告在書面授權或合約確認前保持私有。
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
- `scripts/daily_report_run_receipt.py` 將 Runtime、交付、持久保存、公開發布分開記錄；它只核對提供的報告與 readback，不會自行呼叫 Runtime、寫 Drive 或發布 GitHub。
- 既有 15:00 task 必須以真實收據證明 Runtime、Owner 交付與保存讀回。手動 replay/CI 不等於 Scheduled E2E；不新增第二套排程。
- Fresh Agent：本功能 Owner 豁免，不需執行。GitHub 公開發布被阻擋時仍需正常交付報告，並標記 `PUBLICATION_BLOCKED`。
