# STATUS — Fantasy Hoops Decision Assistant

**Lifecycle:** Active　｜　**Last reviewed:** 2026-10-27（Asia/Taipei）　｜　**Current season:** 2026–27

## Current truth / authority

- `seasons/2026-27/league.json`：當季唯一 Fantasy scoring，16 隊，每隊基準 13 位持有。
- `seasons/2026-27/rosters.json`：截至 2026-10-25 的手動驗證名冊；每隊 `players` 加上 `additional_owned_players` 才是完整持有集合。
- `seasons/2026-27/ownership/README.md` 與 `ownership/current-state.json`：有效持有排除層，未知隊伍的確定 ADD 仍非 FA，已 DROP 不自動變 FA；歷史日期檔不是現行狀態。
- 2026-10-25 main 已更新包括 team_09 的 Trevon Brazile / Mitchell Robinson 交易及 team_10 額外 ADD。**此 STATUS 不可作固定球員名單**；每次 fresh-read `main` 及來源的 `as_of`。
- `SCHEDULED-RUN.md`：15:00 每日戰報及通知權威，與球探 Skill 的獨立 SOP 不同。

## Yahoo 讀取整合 / 外部限制

2026-10-04 送出的 Yahoo Fantasy Sports API 申請已於 **2026-10-19 遭拒**。此結果只代表該次申請未獲准，不代表未來申請必然遭拒；目前沒有授權憑證，也沒有 authenticated read-only R0 與名冊／FA／waiver 對帳成功的 repo 證據。不得描述為「等待審核」或宣稱 Yahoo live read 可用。

未來若有新的明確授權，再依 OAuth 成功、確認聯盟、讀取 16 隊所有球員及額外格位、真實可撿池、stable IDs 正規化及人工 bootstrap 零未解釋差異完成 R0。OAuth／私人 Yahoo 憑證不可進 repo；未授權任何 Yahoo 交易寫入。現行決策須繼續使用 owner 確認名冊與 ownership overlay，未查證的 waiver／FA 保持 UNKNOWN。

## Scouting 目前狀態 / gates

- **Draft PR #16 / Issue #15**：保留未驗收的球探資料庫、Skill 入口、報告 validator 與產品工作；Daily 共用 NBA adapter / FP calculator 已拆到獨立工程 PR，PR #16 仍須獨立球探與產品驗收。
- canonical SOP：`seasons/2026-27/scouting/README.md`；Skill 入口僅路由。Watchlist 的 `QUEUED` 不代表已完成球探。
- `IMPLEMENTATION_IN_REVIEW`；本地 unit/integration 與手動真實資料取得不等於 GitHub CI、production 或 scheduled E2E。
- 每日報告：原始 NBA 回應於 2026-10-27 實際取得，之後用正確 `played` parser 重播：三日 24/24 場完賽、657 個 box-score roster rows，其中 539 `PLAYED`、118 `DNP`；上場者有 531 `VERIFIED_FP`、8 `PARTIAL_FP`（TECH 衝突）。逐日：10/24 170 上場 / 49 DNP / 166 VERIFIED / 4 PARTIAL；10/25 157 / 36 / 154 / 3；10/26 212 / 33 / 211 / 1。修正前把字串 `"0"` 當 True 的 649/657 統計已撤銷，不可引用。修復後 E2E receipt SHA-256 `69b44baf0514c54c10502bf01465ce7935283d197b22254e66545bd7e6c9a82c` 保存在私人工作區。來源權利盤點見 `docs/data-publication-audit-2026-10-27.md`；既有公開報告標 `HISTORICAL_PUBLIC_REVIEW_REQUIRED`，新增公開發布維持 `ARCHIVE_BLOCKED`。
- 2026-10-27 私人更正報告 SHA-256：`63acbf5774ec1ec04e4488cda0849d225ae9a64d7a7f80d1bc6e42819d6c1723`。PR #21 兩版舊報告標記 `SUPERSEDED`；更正報告目前只在私人工作區，不能稱為 GitHub 歸檔。
- 15:00 排程：保留既有 Asia/Taipei task，不建立重複排程。尚無證據證明它已呼叫 `generate_daily_report.py` 並交付檔案內容；本次工作階段沒有排程控制工具，Cloud Environment 回報的可用 runtime capabilities 為空。狀態 `SCHEDULED_PRODUCTION_PENDING`。
- `SCOUTING_E2E_NOT_RUN`、`FRESH_AGENT_NOT_RUN`；如果無法執行真正隔離的 Fresh Agent A/B，標 `BLOCKED_FRESH_AGENT_RUNTIME`，不冒稱 PASS。未完成 QA 前不得接 15:00 排程。

## Next gates

Daily Report：先完成既有公開報告權利對帳；取得來源可公開再發布的書面許可或授權來源 → 獨立工程 PR / CI / review → 把既有 15:00 task 綁定到支援的 Python runtime → 正式執行、交付報告本文、歸檔並 main 精確讀回。Scouting：真實球員資料、影片/Yahoo 比較、獨立 Reviewer 與隔離 Fresh Agent A/B → Owner 產品驗收；研究 PR 不得修改 Yahoo、roster、ownership、league 或每日戰報排程。
