# STATUS — Fantasy Hoops Decision Assistant

**Lifecycle:** Active　｜　**Last reviewed:** 2026-10-25（Asia/Taipei）　｜　**Current season:** 2026–27

## Current truth / authority

- `seasons/2026-27/league.json`：當季唯一 Fantasy scoring，16 隊，每隊基準 13 位持有。
- `seasons/2026-27/rosters.json`：截至 2026-10-25 的手動驗證名冊；每隊 `players` 加上 `additional_owned_players` 才是完整持有集合。
- `seasons/2026-27/ownership/README.md` 與 `ownership/current-state.json`：有效持有排除層，未知隊伍的確定 ADD 仍非 FA，已 DROP 不自動變 FA；歷史日期檔不是現行狀態。
- 2026-10-25 main 已更新包括 team_09 的 Trevon Brazile / Mitchell Robinson 交易及 team_10 額外 ADD。**此 STATUS 不可作固定球員名單**；每次 fresh-read `main` 及來源的 `as_of`。
- `SCHEDULED-RUN.md`：15:00 每日戰報及通知權威，與球探 Skill 的獨立 SOP 不同。

## Yahoo 讀取整合

2026-10-04 已送出 Yahoo Fantasy Sports API 申請；目前**尚未找到已成功執行 authenticated read-only R0 與所有名冊、FA/waiver 對帳的 repo 證據**。不可把「已送出」當作已批准，亦不可宣稱 Yahoo live read 已可用。正式對帳前依 Owner 已確認名冊和近期截圖覆蓋，對 FA/waiver 未證實者保持 UNKNOWN。

R0 完成條件：OAuth 成功、確認聯盟、讀取 16 隊所有球員及額外格位、真實可撿池、正規化 stable IDs、與人工 bootstrap 對帳零未解釋差異。OAuth/私人 Yahoo 憑證不可進 repo；未授權任何 Yahoo 交易寫入。

## Scouting 目前狀態 / gates

- **Draft PR #16 / Issue #15**：正在補研究資料庫、Codex/Claude Skill 入口、報告 sidecar validator 與 Fresh Agent 治理。
- canonical SOP：`seasons/2026-27/scouting/README.md`；Skill 入口僅路由。Watchlist 的 `QUEUED` 不代表已完成球探。
- `IMPLEMENTATION_IN_REVIEW`；即使 GitHub CI 通過，只能是 `STRUCTURAL_TESTS_PASS`。
- `SCOUTING_E2E_NOT_RUN`、`FRESH_AGENT_NOT_RUN`；如果無法執行真正隔離的 Fresh Agent A/B，標 `BLOCKED_FRESH_AGENT_RUNTIME`，不冒稱 PASS。未完成 QA 前不得接 15:00 排程。

## Next gates

修復 PR #16 治理缺口 → GitHub CI/分支讀回 → 真實 NBA/影片/Yahoo 比較案例及獨立 Reviewer → 隔離 Fresh Agent A/B → 再由 Owner 判斷能否正式合併或串接。研究 PR 不得修改 Yahoo、roster、ownership、league 或每日戰報。
