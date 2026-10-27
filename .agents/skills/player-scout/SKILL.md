---
name: player-scout
description: NBA 球探研究、Fantasy 球員比較或替換、ADD/HOLD/DROP/TRADE 決策分析、建立觀察名單。
---

# Codex Player Scout — discovery only

**唯一完整 SOP 是 `seasons/<active-season>/scouting/README.md`**。先 fresh-read `AGENT_CONTEXT.md`、`STATUS.md`、當季 `league.json`、`rosters.json`、`ownership/README.md`、`ownership/current-state.json` 再執行，不能用本入口自行發展第二套規則。

依 canonical SOP 獨立 Read → Ownership → Basketball → Stats/FP → Compare → Review → Publish。報告要配對同名 `.md + .json`，執行 `scripts/validate_scouting_report.py` 並由獨立 Reviewer 審證。不能把未確認 Yahoo FA 當可撿球員，缺少 FTA/OREB/DREB/TECH/EJCT/FF 等分數欄位不得補零。

`content_status`、`review_status`、`archive_status` 彼此獨立，報告不能自宣稱 ARCHIVED。不得修改 roster/ownership/scoring、Yahoo ADD/DROP/交易、15:00 戰報與排程；寫入研究只走專用 PR。Fresh Agent 未跑不得宣稱 PASS。
