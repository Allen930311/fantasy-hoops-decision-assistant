# Player Scouting — 2026–27 canonical SOP（繁體中文）

**唯一完整流程權威**是本文件；Codex `.agents/skills/player-scout/SKILL.md` 和 Claude Code `.claude/skills/player-scout/SKILL.md` 只作 Skill discovery/router，不得自訂另一套規則。研究個案不是 FA，研究歸檔不等於有交易權限。

## Input / Source authority
- Input：球員、研究問題、時間截點、可取得的原始 NBA box score / 影片／新聞及 Yahoo 證據。
- 每次重新從 GitHub main 釘住 commit，讀 `league.json`（本季唯一 scoring）、`rosters.json`（兩個持有集合 `players` 和 `additional_owned_players`）及 `ownership/README.md` + `ownership/current-state.json`。**不可**把歷史 ADD 截圖排除檔永久聯集。
- 未歸屬已確認 ADD 仍不是 FA；DROP 只證明釋出，**不保證目前 waiver/FA 可撿**；顯示隊名不是穩定 team ID。僅帶來源及時間的當前 Yahoo FA/waiver 查證可支持 `CONFIRMED_FA / CONFIRMED_WAIVER`。
- 所有真實數據須有 source URL、抓取時間、球員唯一身分、game ID；資料或影片不齊則標明而不填造。

## Steps — independent read-only scouting
1. **Read & pin**：取得 roster commit SHA 和 league/roster/ownership 各 Git blob SHA，確認 nba_id 或 yahoo_id、別名與研究截止時間。無法確認穩定 ID 可進 watchlist 或 PROVISIONAL，不可正式 VALIDATED。
2. **Ownership gate**：依 ownership SOP 決定 `OWNER_ROSTER / OTHER_TEAM_ROSTER / OWNED_TEAM_UNKNOWN / RELEASED_AVAILABILITY_UNVERIFIED / CONFIRMED_FA / CONFIRMED_WAIVER / UNKNOWN`。不確定可用性者不可直接建議立即 ADD。
3. **Basketball**：進攻、防守、戰術角色、球隊輪替、角色變化、優缺點及反證；影片應寫比賽日期、game ID、時間戳與正反案例，不能憑 highlights 推定全場能力。
4. **NBA stats & FP**：共用 `scripts/nba_data_adapter.py` 取得排程、Box Score、PBP、來源快照與逐欄品質；使用該模組的 `calculate_custom_fp` 對 `league.json.scoring` 計算全部欄位（含 FTA、OREB/DREB、TECH、EJCT、FF、DD、TD）。近 5／10／20 場及全季以真實樣本為準，樣本不足填 N/A；不可把缺值補零。逐場原始資料與 canonical `stats_sha256`、原始來源擷取位元組的 `raw_source_sha256` 寫入可驗證 sidecar，保留缺漏（無法取得 raw source digest 時不能標 VALIDATED）；DAILY 戰報與球探資料分離。
5. **Forecast/Compare**：保守／基準／樂觀 minutes、FP/G、每週預期出賽及可重算公式；短期兩週和長期；和 Owner 現有球員／替代人選比較差值。已被別隊持有者只能提出談判路徑，不能直接叫 ADD。
6. **Review**：執行 `python scripts/validate_scouting_report.py <report.json> seasons/2026-27`；再由與 Scout **不同**的 Reviewer 實際核對 URL 可開、box score 場次及影片說法，記錄審核時間與來源。Validator 是離線資料/算術/一致性 gate，使用共用 FP calculator，能重算 normalized stats digest；原始 `raw_source_sha256` 需由獨立 Reviewer 比對實際來源保存結果；不能僅靠格式證實 URL 真實性或 Yahoo 即時狀態。
7. **Publish**：只在專用 branch/PR 新增 watchlist 與 `reports/<slug>/YYYY-MM-DD.vN.md` 加同名 `.json`，版本不可靜默覆寫；不改 roster、ownership、scoring、Yahoo 或 15:00 報告。main 遠端讀回另立 receipt，不能報告自述完成。

## 狀態分離與寫入治理
- `content_status`：`BLOCKED | PROVISIONAL | VALIDATED`。
- `review_status`：`NOT_RUN | PASS | FAIL`。完整來源經獨立 Reviewer PASS 後可顯示**衍生標籤** `REVIEW_READY`。
- `archive_status`：`NOT_WRITTEN | PR_PENDING | ARCHIVE_BLOCKED | ARCHIVED`。三個維度獨立，**PROVISIONAL + ARCHIVED 可以成立**（僅表示檔案有存，不表示結論正確）。
- 不可變 dossier JSON **不得自稱 ARCHIVED**。成功合併之後另以獨立 `scouting/archive-receipts/` 紀錄實際 GitHub main 讀回的檔案路徑、內容 SHA、PR、commit 和驗證時間；目前並無自動 receipt writer，沒有實際讀回不得宣稱 ARCHIVED。

## Output, side effects, finish / fail states
- `watchlist.json` 為可變研究隊列，不是球員歸屬來源；附穩定 ID（尚未核實時明標 null／UNVERIFIED）。
- `report-template.md` 是給人讀的八段繁體中文報告；`reports/*.json` 是相同版本結構化原始證據，不能用空 Markdown 取代完成證明。
- Scout 撰文、Validator 核算、獨立 Reviewer 評估證據、Owner 審最後 GM 行動；Owner 不必逐筆核准程式開發。Side effects 限研究 PR，不碰 Yahoo / 名冊 / 排程。
- `BLOCKED`：讀不到 canonical scoring／ownership；`PROVISIONAL`：原始欄位/影片/可用性不足，保留缺漏、不編數字；`FAIL`：錯誤歸屬、精確 FP 造假、錯誤來源或無 evidence，禁止標 VALIDATED。
- CI 只能稱 `IMPLEMENTATION_TESTS_PASS`，不代表 `SCOUTING_E2E_PASS`。此功能沒有 Fresh Agent 豁免；隔離測試規則見 `tests/fresh-agent/scouting/README.md`，跑不到回報 `BLOCKED_FRESH_AGENT_RUNTIME`。

## V1 實作進度限制
V1 只建立獨立 SOP、watchlist、模板、deterministic validation 及 CI。真實球探與 Fresh Agent A/B 是另一道驗收：以 Herbert Jones 及 Keon Ellis（持有但隊伍未知）等固定案例做實際研究，核對 Owner 比較決策後才能聲稱 E2E PASS。不要在本功能尚未驗收時接入每天 15:00 監控。
