# 球員球探資料庫 / Player Scouting（2026–27）

這是**當季專屬**、可單獨執行的球探研究流程，並非每日 15:00 戰報。研究對象可包含本人隊伍、其他 15 隊、確認可撿自由球員、waiver 未確認球員或純 NBA 研究對象。記錄在 watchlist **不會**改變球員歸屬，也**不代表已確認自由球員**。

## 目錄
- `watchlist.json`：持續更新的研究隊列（`QUEUED / RESEARCHING / REVIEW_PENDING / SCOUTED / BLOCKED`）。只記錄研究問題、優先順序與進度。
- `report-template.md`：正式的雙層球探報告：Basketball + Fantasy。
- `reports/<player-slug>/YYYY-MM-DD.v1.md`：已形成文字的不可靜默覆寫快照；修訂建 v2，保留差異與原因。
- `reports/README.md`：歸檔、版號、溯源及 gate。
- `.agents/skills/player-scout/SKILL.md`（repo 根目錄）：Codex 工作入口；`.claude/skills/player-scout/SKILL.md` 是 Claude Code 轉接入口。

## SOP 合約（可以不靠排程單獨啟動）

**Input**：研究球員身分、研究問題、當季資訊、可用的最新 NBA/影片/新聞/Yahoo 證據。可由 Owner 提供球員名字，或從 watchlist 領取 `QUEUED` 的個案。

**Authority（每一次都 fresh read）**：
1. `STATUS.md`、`AGENT_CONTEXT.md`、當季 `league.json`（唯一計分權威）。
2. 當季 `rosters.json` 的 `teams[].players` **及** `teams[].additional_owned_players`，`ownership/README.md` 和 `ownership/current-state.json`（有效現行歸屬覆蓋，勿拿歷史日期檔永久聯集）。
3. NBA 官方球員/比賽/box score 為原始數據優先來源；各方報導僅支持明確可追溯說法。新證據優於過時報導，但不能直接把傳聞變交易事實。
4. 未對帳的 Yahoo / 截圖/隊名顯示狀態，不可冒充目前已驗證的 Yahoo 即時 FA/waiver 身分。

**Steps**：
1. **Read & pin**：讀最新 main，記下 `scoring/roster/ownership` 來源 SHA、`roster.as_of` 與研究截點（Asia/Taipei），確認球員別名與唯一身分。
2. **Ownership gate**：查 16 隊兩類名單及現行 ownership overlay。依歸屬 SOP 將球員定為 `OWNER_ROSTER`、`OTHER_TEAM_ROSTER`、`OWNED_TEAM_UNKNOWN`、`RELEASED_AVAILABILITY_UNVERIFIED`、`CONFIRMED_FA`、`CONFIRMED_WAIVER` 或 `UNKNOWN`。查無在 owned 集合中**不足以證實** `CONFIRMED_FA`。
3. **Basketball scout**：研究位置/身體條件、進攻/防守技能、實際角色、輪替對手、影片證據（對手/比賽日期/時間戳、正反案例）、最近角色或傷病變化。要看比賽脈絡，不得由精華片段推定防守可靠性。
4. **Stats & Fantasy scout**：列近 5／10／20 場與賽季（若樣本未滿，標 N/A 並列樣本數），上場時間、每 36 分鐘/每分鐘率、USG%、TS%、失誤、犯規、抄截、火鍋、OREB/DREB、3PTM、FTA、DD/TD 的真實樣本。以 `league.json.scoring` **動態**計算，保留各項完整欄位與 `missing`；不得用 Yahoo 預設分數或缺欄補零。
5. **Model & Compare**：說清保守／基準／樂觀三情境的 minutes、角色和數據假設、每場 FP 及每週出賽預估；比較 Owner 現有球員與其他可達的替代者（有明確 waiver/FA 才能直接建議 ADD）。
6. **Independent review**：檢查來源、歸屬、得分明細/缺項、觀察 vs 推估、反證、不確定性、球員身分、版本與可執行性。無法驗證時降級 `PROVISIONAL` 或 `BLOCKED`。
7. **Publish & readback**：僅將研究隊列/報告文件放進專用 branch/PR，不改隊伍名冊、ownership 或每日報告。branch 與 main 的讀回是不同完成狀態；main 有真實回讀才 `ARCHIVED`。

**Output**：填完的正式 report、來源與缺口摘要、`ADD/HOLD/DROP/TRADE/WATCH` 的行動理由、下一個觸發日/事件；必要時更新 watchlist 對應進度。

**Side effects**：僅版本化研究檔案；禁止 Yahoo transaction、名冊或聯盟設定變動；不接觸 15:00 排程。

**Fail state**：
- `BLOCKED`：讀不到 scoring/ownership 真值、無球員身分或研究要求的關鍵來源無法取得；不能用記憶代替。
- `PROVISIONAL`：已有可讀的初稿但樣本、影片、官方欄位、即時 FA 或投影依據不足；未驗證的估計需標示，**不可冒稱精準 FP**。
- `REVIEW_READY`：完整來源、計分、情境、對照、交易可行性、QA 均通過，適合 Owner 審閱，但尚未等於 main 歸檔。
- `ARCHIVED`：PR 合併且 GitHub main 回讀路徑、內容版本一致。

## Fresh Agent 驗收（本 Skill **沒有**豁免）

以真實 2026–27 `Herbert Jones` 替換研究作為一組固定案，同時納入其他隊持有、已確認 ADD 但隊伍未知（例如 `Keon Ellis`）、已 DROP 但 waiver 未確認（例如 `Kentavious Caldwell-Pope`）等 adversarial 案。實驗前釘住同一 commit 與真實數據截點。

兩個全新、互不見到彼此輸出的 Agent：A 不取得 Skill/SOP，B 取得 Skill/SOP；使用一致工具、資料、預算與要求。各自保存完整 prompt、資料 SHA、來源、原始報告、審核紀錄與成果。獨立比對：歸屬/FA 誤判 0、來源虛構 0、FP 缺項冒充完整 0，且情境與對照可讀。控制組表現須忠實列出。未能執行則 `BLOCKED_FRESH_AGENT_RUNTIME`，不得以文件編寫或單元測試冒充 PASS。

## 實作階段

V1 建立 Skill/隊列/模板與保存合約；**尚未**宣稱接好自動抓 NBA、每日推送、全量預測引擎、驗證器或 Fresh Agent E2E。先確保手動觸發能完整跑一份可核對的球探報告，再擴展自動追蹤。
