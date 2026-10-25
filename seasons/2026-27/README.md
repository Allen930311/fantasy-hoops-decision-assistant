# 2026–27 League State

This directory contains the owner-specific league state and scoring configuration for the **2026–2027 Fantasy Basketball season**.

## Files

- `league.json` — season metadata and the owner-defined scoring system.
- `rosters.json` — mutable 16-team roster snapshot; `teams[].additional_owned_players` records confirmed same-team ADDs with unknown active/IL slot, not an invented DROP.
- [`ownership/README.md`](ownership/README.md) — Yahoo transaction attribution SOP (known team vs unknown team, ADD-only, DROP precedence).
- [`ownership/current-state.json`](ownership/current-state.json) — effective unassigned-confirmed-ADD exclusions and releases awaiting Yahoo FA/waiver verification; newer evidence overrides historical dated overlays.
- `report/2026-10-05-preseason-model-v1.md` — frozen 16-team preseason power-ranking baseline, including model methodology, scoring formula, team ranking, owner-team interpretation, and limitations.
- `report/daily/README.md` — 每日 Fantasy 戰報獨立歸檔 SOP；離線驗證、暫定稿、版本控制、GitHub PR 和 main 讀回關卡。

## Reports

Reports under `report/` are dated analytical snapshots. They should **not** be silently rewritten when projections change; create a new dated report/model version so later season states can be compared against the earlier baseline.

Daily reports use immutable dated snapshots under `report/daily/`; `VALIDATED` is a content gate, not proof of GitHub `ARCHIVED`. The Fresh Agent trial for PR #9 was waived by the owner on 2026-10-22; CI, provenance, GitHub write/readback and correct status labeling remain requirements. Check deployment/automation state separately from existence of code.

Current baseline:

- [2026-10-05 Preseason Model V1](report/2026-10-05-preseason-model-v1.md)

## Update policy

- Treat roster membership as mutable. Apply `ownership/README.md` first: attributable transactions update `rosters.json` and `as_of`, while unassignable confirmed ADDs update only `ownership/current-state.json`. Reconcile any later DROP against historical ADD-only exclusions.
- Do not silently carry roster state or scoring rules into another season.
- For a new season, create a new sibling directory such as `seasons/2027-28/` with that season's own league settings and rosters.
- `team_02` is the owner's team for this snapshot.
- The original source workbook contained a display-only “14th slot vacancy”; the computational baseline remains **13 players per team**. A subsequent owner-confirmed ADD without a matching DROP may make the real number of owned players exceed that baseline. Store confirmed extra ownership in `additional_owned_players` without asserting an IL slot.
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
