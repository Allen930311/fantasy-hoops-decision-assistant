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

- **PR #16 / Issue #15**：PR 已同步最新 main；只保留 Scouting SOP、Codex/Claude Skill 入口、報告 sidecar validator 與 Scouting CI。Daily NBA adapter / FP calculator 已由 main 的 PR #23 提供，Scouting 共用它而不複製。PR 仍須 CI、獨立審查與產品驗收。
- canonical SOP：`seasons/2026-27/scouting/README.md`；Skill 入口僅路由。Watchlist 的 `QUEUED` 不代表已完成球探。
- `IMPLEMENTATION_IN_REVIEW`；本地 unit/integration 與手動真實資料取得不等於 GitHub CI、production 或 scheduled E2E。
- 每日報告：官方 NBA 真實資料的三日 replay 已完成；來源公開再發布權未證實，故 GitHub report archive 仍 `ARCHIVE_BLOCKED`，不可將本機 `VALIDATED` 稱為 `ARCHIVED`。
- 15:00 排程：沿用既有 Asia/Taipei task，尚無本次修復後的正式排程執行證據，狀態 `SCHEDULED_PRODUCTION_PENDING`。
- `SCOUTING_E2E_NOT_RUN`、`FRESH_AGENT_NOT_RUN`；如果無法執行真正隔離的 Fresh Agent A/B，標 `BLOCKED_FRESH_AGENT_RUNTIME`，不冒稱 PASS。未完成 QA 前不得接 15:00 排程。

## Next gates

Daily Report：取得來源可公開再發布的書面許可或授權來源 → PR/CI/review → existing 15:00 task 真實執行與 main readback。Scouting：真實球員資料、影片/Yahoo 比較、獨立 Reviewer 與隔離 Fresh Agent A/B → Owner 產品驗收；研究 PR 不得修改 Yahoo、roster、ownership、league 或每日戰報排程。
