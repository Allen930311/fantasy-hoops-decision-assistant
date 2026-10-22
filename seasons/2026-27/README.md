# 2026–27 League State

This directory contains the owner-specific league state and scoring configuration for the **2026–2027 Fantasy Basketball season**.

## Files

- `league.json` — season metadata and the owner-defined scoring system.
- `rosters.json` — mutable 16-team roster snapshot.
- `report/2026-10-05-preseason-model-v1.md` — frozen 16-team preseason power-ranking baseline, including model methodology, scoring formula, team ranking, owner-team interpretation, and limitations.
- `report/daily/README.md` — 每日 Fantasy 戰報獨立歸檔 SOP；離線驗證、暫定稿、版本控制、GitHub PR 和 main 讀回關卡。

## Reports

Reports under `report/` are dated analytical snapshots. They should **not** be silently rewritten when projections change; create a new dated report/model version so later season states can be compared against the earlier baseline.

Daily reports use immutable dated snapshots under `report/daily/`; `VALIDATED` is a content gate, not proof of GitHub `ARCHIVED`. The Fresh Agent trial for PR #9 was waived by the owner on 2026-10-22; CI, provenance, GitHub write/readback and correct status labeling remain requirements. Check deployment/automation state separately from existence of code.

Current baseline:

- [2026-10-05 Preseason Model V1](report/2026-10-05-preseason-model-v1.md)

## Update policy

- Treat roster membership as mutable. When a player is added, dropped, traded, or reassigned, update `rosters.json` and advance its `as_of` date.
- Do not silently carry roster state or scoring rules into another season.
- For a new season, create a new sibling directory such as `seasons/2027-28/` with that season's own league settings and rosters.
- `team_02` is the owner's team for this snapshot.
- The source workbook contained a display-only “14th slot vacancy”; it is intentionally excluded. The recorded roster size is **13 players per team**.
- Until Yahoo read-only integration is validated, this snapshot is the bootstrap ownership-state source. After reconciliation, Yahoo becomes league-state truth while owner-defined scoring remains decision truth.

## Integrity snapshot

- Teams: **16**
- Players per team: **13**
- Total rostered players: **208**
- Duplicate rostered players in the imported snapshot: **0**

## Validation

Run the season integrity check after roster or scoring edits:

```bash
python scripts/validate_season_state.py seasons/2026-27
```

The validator checks team count, roster size, unique rostered players, exactly one owner team, season alignment, and scoring presence.
