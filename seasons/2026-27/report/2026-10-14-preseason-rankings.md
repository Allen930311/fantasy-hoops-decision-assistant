# 2026–27 Preseason Actual and Regular-Season Rankings

> **Status:** Official ranking — post-validation
> **Data cutoff (UTC):** 2026-10-14T04:32:24Z
> **Retrieved:** 2026-10-14T04:32:27Z to 2026-10-14T04:33:24Z
> **Owner team:** `team_02` / 第2隊

## Scope and authority

Fantasy ownership comes from this season's owner-confirmed `rosters.json`; current NBA franchise and player identity come from NBA Stats API `CommonAllPlayers`. The report uses the custom weights in `league.json`. It does not use Yahoo or ESPN Fantasy Points.

- Roster: 16 teams × 13 players = 208 names.
- Completed preseason games in the captured snapshot: 44; scheduled or in-progress games by cutoff: 2.
- Current NBA roster matches: 208/208.
- Prior-season special-stat name matches (ESPN): 193/208 for 2025–26 and 184/208 for 2024–25; unique suffix-only aliases: 1 and 1 respectively. Ambiguous suffix aliases are not matched (0 and 0 roster names).

## Scoring and field definitions

Every game is recomputed from the season's configured scoring fields:

```text
FP = (-0.25)×FTA + 2×3PTM + 1×PTS + 2.5×OREB + 1.5×DREB + 2×AST + 3×STL + 3×BLK + (-2)×TO + (-1)×PF + (-1)×TECH + (-10)×EJCT + (-5)×FF + 7×DD + 6×TD
```

The game-level source fields are `PTS`, three-point makes, free-throw attempts, offensive and defensive rebounds, assists, steals, blocks, turnovers, personal fouls, technical fouls, ejections, flagrant fouls, double-doubles, and triple-doubles. `DD` means at least two of points/rebounds/assists/steals/blocks reach 10; `TD` means at least three. A triple-double also receives the configured `DD` bonus because `league.json` treats the two bonuses cumulatively. Technical/Flagrant/Ejection counts are taken from NBA Stats play-by-play for preseason and ESPN's per-athlete special-stat fields for the historical baseline; all other fields come from NBA Stats API. Preseason `TECH` counts each `Foul` action labeled technical, including double technicals, hanging technicals, and flopping technicals; the associated technical free-throw attempt is not counted as another foul.

## 2026 preseason actual sample ranking

This table ranks the sum of each fantasy roster's ten highest observed 2026 preseason custom FP/G values. Players with no completed appearance are excluded from this sample and are not assigned zero. Coverage and sample size appear beside each team.

| Rank | Team | Top-10 actual FP/G | Players with sample | Coverage |
|---:|---|---:|---:|---:|
| 1 | 第2隊 | 302.6 | 11/13 | 84.6% |
| 2 | 第3隊 | 295.0 | 12/13 | 92.3% |
| 3 | 第14隊 | 274.5 | 12/13 | 92.3% |
| 4 | 第16隊 | 272.1 | 12/13 | 92.3% |
| 5 | 第12隊 | 268.2 | 13/13 | 100.0% |
| 6 | 第1隊 | 266.3 | 13/13 | 100.0% |
| 7 | 第10隊 | 244.6 | 13/13 | 100.0% |
| 8 | 第13隊 | 244.1 | 13/13 | 100.0% |
| 9 | 第5隊 | 244.0 | 11/13 | 84.6% |
| 10 | 第4隊 | 237.9 | 12/13 | 92.3% |
| 11 | 第15隊 | 234.1 | 11/13 | 84.6% |
| 12 | 第6隊 | 231.7 | 12/13 | 92.3% |
| 13 | 第11隊 | 225.3 | 11/13 | 84.6% |
| 14 | 第9隊 | 218.5 | 12/13 | 92.3% |
| 15 | 第8隊 | 215.8 | 11/13 | 84.6% |
| 16 | 第7隊 | 211.6 | 10/13 | 76.9% |

## 2026–27 regular-season projection ranking

The primary projection score is the sum of the ten highest players' expected custom FP per fantasy-team game. Player expected FP/G equals the projected active-game rate multiplied by an availability rate. Availability starts from prior-season GP/82 and is shrunk toward the 2025–26 league mean (0.6888, 452 players with at least 20 GP and complete stats) using a 20-game prior. Preseason samples update per-36 production and role minutes with fixed shrinkage; they cannot dominate a full prior season. The scenario range is a heuristic sensitivity band, not a calibrated confidence interval.

For a player with a full historical baseline, preseason production weight is `min(0.35, preseason_minutes / (preseason_minutes + 720))`; the projected FP/36 is the historical FP/36 and preseason FP/36 weighted by that share. Projected minutes use `min(0.25, preseason_minutes / (preseason_minutes + 360))` against historical minutes per game. Players who need a cohort-only rate prior use 2025–26 rookie-cohort medians, with preseason rate/minute weights capped at 0.60/0.50 and denominators 360/240 minutes; uncertainty is wider. Expected FP/team game is `(projected FP/36 × projected minutes / 36) × availability`; availability is `(2025–26 GP + 20 × league 2025–26 GP/82 mean) / 102`, except 2026 rookies use the rookie-cohort availability median. A player with zero 2025–26 games is explicitly risk-flagged even when the production baseline must fall back to 2024–25.

The player scenario half-width is `min(0.75, 0.12 + 0.35/sqrt(baseline GP + 10) + 0.20/sqrt(preseason GP + 1) + applicable risk add-ons)`. Risk add-ons are +0.15 for a cohort-only production prior, +0.08 for a 2024–25 production baseline, +0.10 for zero 2025–26 GP, and +0.05 per explicit preseason injury/illness DNP up to +0.15. Team scenario bounds sum the selected ten players' corresponding low/high expected FP/G; they are sensitivity ranges, not probabilities.

| Rank | Team | Top-10 expected FP/team game | Top-10 active FP/G | Scenario range | Low-confidence players |
|---:|---|---:|---:|---:|---:|
| 1 | 第15隊 | 298.0 | 355.2 | 210.7–385.2 | 0 |
| 2 | 第5隊 | 295.0 | 365.9 | 210.4–379.7 | 1 |
| 3 | 第2隊 | 278.5 | 344.8 | 198.2–358.8 | 0 |
| 4 | 第13隊 | 278.4 | 346.2 | 204.7–352.1 | 2 |
| 5 | 第11隊 | 277.8 | 367.3 | 196.1–359.6 | 0 |
| 6 | 第14隊 | 277.1 | 362.8 | 190.7–363.6 | 0 |
| 7 | 第9隊 | 272.0 | 367.3 | 194.6–349.5 | 1 |
| 8 | 第4隊 | 269.7 | 355.8 | 193.3–346.0 | 0 |
| 9 | 第7隊 | 267.4 | 366.9 | 188.5–346.3 | 0 |
| 10 | 第1隊 | 260.7 | 375.3 | 189.7–331.7 | 1 |
| 11 | 第12隊 | 260.0 | 326.6 | 189.6–330.4 | 0 |
| 12 | 第8隊 | 250.4 | 313.1 | 180.9–320.0 | 0 |
| 13 | 第6隊 | 250.3 | 347.7 | 177.8–322.9 | 1 |
| 14 | 第10隊 | 249.8 | 342.9 | 180.1–319.5 | 2 |
| 15 | 第16隊 | 249.6 | 338.8 | 177.3–321.9 | 0 |
| 16 | 第3隊 | 238.7 | 314.4 | 167.5–309.8 | 5 |

## Team_02 detail and risk

Team_02 projected rank: **3**. It has 11/13 players with a completed preseason sample and 1 player(s) with an explicit injury/illness DNP note.
Team_02 projects 278.5 expected FP/team game, 19.5 behind the current leader and +0.08 relative to the fourth-place cutoff.

| Player | NBA team / position | Preseason status | Preseason GP | Actual FP/G | Baseline season | Projected active FP/G | Availability | Expected FP/team game | Risk |
|---|---|---|---:|---:|---|---:|---:|---:|---|
| Stephon Castle | SAS / G | played | 2 | 31.0 | 2025-26 | 37.8 | 80% | 30.3 | — |
| Andrew Wiggins | MIA / F | played | 2 | 20.1 | 2025-26 | 33.4 | 80% | 26.8 | — |
| De'Aaron Fox | SAS / G | did_not_play | 0 | — | 2025-26 | 38.4 | 84% | 32.3 | no_completed_preseason_minutes |
| Scottie Barnes | TOR / F-G | played | 3 | 32.9 | 2025-26 | 45.3 | 92% | 41.6 | — |
| Alperen Sengun | HOU / C | played | 1 | 60.8 | 2025-26 | 49.7 | 84% | 41.8 | — |
| Herbert Jones | NOP / F | played | 2 | 12.1 | 2025-26 | 22.1 | 68% | 15.1 | — |
| Aaron Gordon | DEN / F | played | 3 | 25.9 | 2025-26 | 32.3 | 49% | 15.8 | — |
| Walker Kessler | LAL / C | did_not_play | 0 | — | 2025-26 | 44.2 | 18% | 8.1 | no_completed_preseason_minutes |
| RJ Barrett | TOR / F-G | played | 3 | 31.2 | 2025-26 | 33.2 | 69% | 23.0 | — |
| Jrue Holiday | POR / G | played | 2 | 24.0 | 2025-26 | 37.7 | 65% | 24.7 | — |
| Max Christie | DAL / G | played | 2 | 28.0 | 2025-26 | 24.6 | 89% | 21.9 | — |
| Zaccharie Risacher | DAL / F | played | 2 | 28.2 | 2025-26 | 21.9 | 79% | 17.4 | — |
| Pelle Larsson | MIA / G | played | 2 | 20.5 | 2025-26 | 22.9 | 82% | 18.8 | preseason_injury_or_illness_dnp |

**Lowest per-player output:** NBA primary F players average 23.3 expected FP/team game across 6 roster spots, 0% below the league average for that NBA label. This describes the roster mix, not a Yahoo position slot.
NBA-label center depth is the clearest roster-count gap: 2 center-primary players versus a league median of 3; their average projection is 24.9 expected FP/team game, so the gap is depth rather than below-average per-player output.

**Ownership-legal optional 1-for-1 proposal:** offer RJ Barrett (team_02; 23.0 expected FP/team game) to 第9隊 for Alex Sarr (23.0). The other roster has 3 NBA center-primary players; team_02 would move from 2 to 3. The model's point estimate changes by -0.1 FP/team game, so this is a depth-for-near-equal-value option, not a top-four shortcut. Confirm current Yahoo ownership and eligibility before any transaction; the analysis uses the roster snapshot only.

## All-roster player detail

The full 208-player table, including game-level sample counts, missing fields, rate-shrink weights, availability, risk flags, and source game IDs, is in `2026-10-14-preseason-player-model.csv`. Per-game source rows for rostered players are in `2026-10-14-preseason-player-games.csv`.

## Data quality, uncertainty, and limitations

- The ranking uses NBA Stats `boxscoretraditionalv3` as the canonical preseason stat source. The separate NBA `PlayerGameLogs` feed differs in 56 stat/minute cells across 433 rostered player-game rows; those values were not mixed into the ranking. Sample differences: Pelle Larsson 0012600002 AST: boxscore 5.0, PlayerGameLogs 4.0, Pelle Larsson 0012600002 MIN: boxscore 24.9, PlayerGameLogs 22.7, Jrue Holiday 0012600033 PTS: boxscore 5.0, PlayerGameLogs 0.0.
- Historical baseline reconciliation against NBA LeagueDashPlayerStats: 0 per-game mismatch(es) outside a 0.16 stat-per-game tolerance.
- Projection-only rookie prior: 2025-26 rookie cohort median; 71 player(s) in its 2025-26 source cohort. No-history players are visibly flagged and receive wider scenario bands rather than zero.
- No 2026-27 official injury report was available in the captured source set. Availability uses prior-season attendance; current preseason DNP injury/illness notes are surfaced as risks and widen the range but are not extrapolated into a season-long injury absence.
- Top-10 actual preseason FP/G is a tiny-sample observation, not a regular-season forecast. Team schedules differ and preseason rotations are not representative of regular-season minutes.
- Per-game projections are conditional on the owner-confirmed roster snapshot; Yahoo read-only reconciliation remains pending, so current waiver eligibility and Yahoo position eligibility are not claimed.
- The projection model uses a 2025-26 baseline, per-36 rate shrinkage, role-minute shrinkage, a historical availability prior, and observed preseason participation. The published central value is a model output; low/high values are sensitivity bands, not probabilities.

## Reproduction and validation

```bash
python scripts/collect_preseason_snapshot.py --cutoff-utc 2026-10-14T04:32:24Z
python scripts/build_preseason_rankings.py --snapshot seasons/2026-27/data/preseason-2026-10-14
python scripts/validate_preseason_rankings.py --snapshot seasons/2026-27/data/preseason-2026-10-14 --allow-draft
# Preserve the fresh independent review in 2026-10-14-independent-validation.json
python scripts/build_preseason_rankings.py --snapshot seasons/2026-27/data/preseason-2026-10-14 --official
python scripts/validate_preseason_rankings.py --snapshot seasons/2026-27/data/preseason-2026-10-14
```

The collection command writes exact source responses and their retrieval timestamps and SHA-256 hashes to `source_manifest.json`. The frozen manifest is the reproduction source for the rankings above.

## Sources and definitions

- [NBA Stats API](https://stats.nba.com/stats/) — scoreboard, player game logs, traditional box scores, play-by-play, current rosters, and prior-season player statistics.
- [NBA Stats glossary](https://www.nba.com/stats/help/glossary) — DD2/TD3 field definitions.
- [NBA Rule No. 12: Fouls and Penalties](https://official.nba.com/rule-no-12-fouls-and-penalties/) — technical, flagrant, and ejection rules used to interpret preseason play-by-play.
- [ESPN player statistics API](https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/statistics/byathlete?season=2026&seasontype=2) — historical TECH/FLAG/EJECT only; those rare stats are not in NBA base player game logs.
