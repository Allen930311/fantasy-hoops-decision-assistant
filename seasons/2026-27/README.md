# 2026–27 League State

This directory contains the owner-specific league state and scoring configuration for the **2026–2027 Fantasy Basketball season**.

## Files

- `league.json` — season metadata and the owner-defined scoring system.
- `rosters.json` — mutable 16-team roster snapshot.
- `report/2026-10-05-preseason-model-v1.md` — frozen 16-team preseason power-ranking baseline, including model methodology, scoring formula, team ranking, owner-team interpretation, and limitations.
- `report/2026-10-14-preseason-rankings.md` — post-validation actual preseason ranking and 2026–27 regular-season projection, with full-roster player detail and methodology.
- `data/preseason-2026-10-14/` — frozen NBA Stats/ESPN source responses, retrieval timestamps, and SHA-256 manifest used for the October 14 ranking.

## Reports

Reports under `report/` are dated analytical snapshots. They should **not** be silently rewritten when projections change; create a new dated report/model version so later season states can be compared against the earlier baseline.

Current baseline:

- [2026-10-05 Preseason Model V1](report/2026-10-05-preseason-model-v1.md)
- [2026-10-14 Validated Preseason Rankings](report/2026-10-14-preseason-rankings.md)

The October 14 report is reproduced from its frozen source snapshot with `scripts/build_preseason_rankings.py` and checked with `scripts/validate_preseason_rankings.py`. Its signoff file records the independent sample recalculation.

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
