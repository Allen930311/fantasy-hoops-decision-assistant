---
name: player-scout
description: 研究 NBA 球員、建立球探觀察名單、結合 2026–27 或目前賽季的 Fantasy 自訂計分與隊伍歸屬，產生 ADD/HOLD/DROP/TRADE 比較報告；球探或球員替換任務使用。
---

# Player Scout — Claude Code 入口

此為跨 Agent 相容入口，**不得自行發展另一套規則**。

1. 讀取 repo 根目錄 `.agents/skills/player-scout/SKILL.md`（唯一 Skill 流程權威）。
2. 再讀當季 `seasons/<season>/scouting/README.md` 和 `report-template.md`。
3. 完全依同一份流程處理 watchlist 或正式球探報告；任何 source、ownership、Fantasy FP 缺口仍需 fail-closed。
