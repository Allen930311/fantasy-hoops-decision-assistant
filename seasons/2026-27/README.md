# 2026–27 League State

This directory contains the owner-specific league state and scoring configuration for the **2026–2027 Fantasy Basketball season**.

## Files

- `league.json` — season metadata and the owner-defined scoring system.
- `rosters.json` — mutable 16-team roster snapshot.

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
