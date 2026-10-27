---
name: player-scout
description: 研究 NBA 球員、建立觀察名單、用當季 Fantasy scoring 比較球員與交易取捨。
---

# Claude Code Player Scout — discovery only

此入口只提供路由，**唯一 canonical SOP** 為當季 `seasons/<season>/scouting/README.md`。讀 `AGENT_CONTEXT.md`、`STATUS.md`、當季 scoring、rosters 與現行 ownership，再執行 SOP：原始統計與 MD/JSON sidecar、嚴格 FP/FA gate、獨立 Reviewer、不可變報告與 main readback receipt。不得另訂權威或操作 Yahoo、名冊、15:00 排程。
