---
name: player-scout
description: 研究 NBA 球員並撰寫可追溯的繁體中文球探報告，結合 Fantasy 聯盟當季自訂計分、最新 16 隊歸屬、球員角色、影片證據與 ADD/HOLD/DROP/TRADE 決策。當使用者要求球探、觀察球員、替換球員、比較自由球員或撰寫正式球探報告時使用。
---

# Player Scouting Skill — 單一權威流程

**先閱讀**本 repo 的 `AGENT_CONTEXT.md`、`STATUS.md` 與當季 `seasons/<season>/scouting/README.md`。該 README 是完整的 workflow/驗收合約；此 Skill 是可發現的執行入口，不另立相衝突的權威。

## 任務路由
- 「觀察某球員、放入球探名單」：只維護當季 `scouting/watchlist.json`，標示研究問題，不把候選寫成 FA；如資料不足，保持 `QUEUED`。
- 「分析某球員」：完整完成 `Read → Ownership → NBA scout → Fantasy → Compare → Review → Publish`，以 `report-template.md` 產生新版本球探報告。
- 「取代某位球員／交易」：必須比較**現有持有球員**、替代者與真實可用性；提供 long-term / next 2 weeks 兩個視角，不把所有候選都叫自由球員。

## 權限與證據
1. 讀最新 `main` 的當季 `league.json`、`rosters.json`、`ownership/README.md`、`ownership/current-state.json`；不能用歷史截圖清單直接聯集成永久 owned。
2. Owned = 所有 `teams[].players` + `teams[].additional_owned_players` + `unassigned_confirmed_owned_players`。未知隊伍依然 **NOT_FA**。已 DROP 但在 `released_availability_unverified` 中的球員為 **AVAILABILITY_UNVERIFIED**，不是確認 FA。只有可追溯的最新 Yahoo FA/waiver 來源能確認 AVAILABLE。
3. NBA 表現、角色、交易、健康狀態必須有來源 URL、`as_of`、樣本數；影片觀察寫時間戳/正反案例，不把精彩剪輯誤當全場。
4. 自訂 Fantasy 計分只能讀 `league.json.scoring`。要區分 FTA vs FTM、OREB vs DREB、DD+TD 累計規則；缺少 TECH/EJCT/FF/PF 等欄位不得默認 0。缺資料請標 `PROVISIONAL` 並列缺口，禁止填造 FP/投影。
5. 投影寫明 minutes × per-minute rates、近 5/10/20 場與全季 sample，role / injury / game volume 可能改變的理由；給出保守/基準/樂觀情境和可觸發重新評估的條件；與 Owner 現有球員比較替換後淨差（delta）。
6. 報告正文一律繁體中文，可保留英文專有名詞；將 observation、inference、projection 分開。給結論的同時列反證與信心度。
7. 不得執行 Yahoo ADD/DROP/Trade、不擅改 `rosters.json` / `ownership` / `league.json` / 每日戰報或定時排程。寫入研究成果只可經專用 PR；未合併不可稱 main 已收錄。

## 交付
- 一名研究對象一份日期版 `seasons/<season>/scouting/reports/<player-slug>/YYYY-MM-DD.v1.md`；修正使用 `v2`，不可靜默覆寫。
- 回覆應含：目前歸屬/FA 可用性、Basketball scout、當季 FP 與未知欄位、相對 Owner 球員的差距、ADD/HOLD/DROP/TRADE/WATCH 判斷、來源/信心、下次追蹤觸發。
- 缺來源：`BLOCKED`；來源不完整：`PROVISIONAL`；完整審核只算 `REVIEW_READY`，main 讀回成功後才能稱 `ARCHIVED`。
- Fresh Agent 驗收依 `scouting/README.md`；沒有獨立 clean-agent runtime 不得宣稱 PASS。
