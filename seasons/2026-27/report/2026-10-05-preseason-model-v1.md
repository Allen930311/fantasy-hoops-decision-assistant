# 2026–27 Preseason Model V1 — 16-Team Power Ranking

> **Status:** Frozen baseline snapshot  
> **Model date:** 2026-10-05  
> **League-state date:** 2026-10-04  
> **Owner team:** `team_02` / 第2隊  
> **Purpose:** Preserve the accepted preseason model so future live-season, Yahoo-reconciled, or simulation models can be compared against a stable baseline.

## 1. What this report answers

This model estimates the relative 2026–27 season-long fantasy strength of all 16 teams under this league's custom scoring.

It is intentionally a **preseason valuation / power-ranking model**, not a daily lineup optimizer and not a claim that these values are Yahoo's exact live totals.

The main ranking signal is **Top-10 adjusted FP/G**: the sum of each roster's 10 highest projected adjusted fantasy-points-per-game values. This is used as a rough proxy for the league's 10 active lineup slots.

## 2. Inputs and source authority

The snapshot combines:

1. `league.json` — season-specific scoring rules.
2. `rosters.json` — the current 16-team, 13-player roster snapshot.
3. The prior 16-team projection workbook `fantasy_16teams_2026_27_projection(1).xlsx` — 2025–26 box-score baselines plus player-level role and health factors.
4. The owner-confirmed 2026-10-04 roster change for `team_02`: **Marcus Smart OUT → Pelle Larsson IN**.

Until Yahoo read-only integration is validated, roster state in this repo remains the bootstrap league-state authority. This report is a frozen analytical snapshot, not a mutable source of roster truth.

## 3. Fantasy-points calculation

The 2025–26 baseline fantasy-points-per-game formula is:

```text
FP/G =
  PTS
  + 2 × 3PTM
  + 2.5 × OREB
  + 1.5 × DREB
  + 2 × AST
  + 3 × STL
  + 3 × BLK
  - 2 × TO
  - 1 × PF
  - 0.25 × FTA
  - 1 × TECH
  - 10 × EJCT
  - 5 × FF
  + 7 × DD
  + 6 × TD
```

DD and TD bonuses are treated as cumulative unless live Yahoo settings later prove otherwise.

### 3.1 2026–27 player adjustment

For players with a usable 2025–26 NBA sample:

```text
2026–27 Adjusted FP/G
= 2025–26 Base FP/G
× Role Factor
× Health / Availability Factor
```

**Role Factor**

- `1.00` = role is expected to remain broadly similar.
- `> 1.00` = expected increase in minutes, usage, creation, or fantasy-relevant opportunity.
- `< 1.00` = expected decline in role, touches, minutes, or rotation priority.

**Health / Availability Factor**

- `1.00` = no additional season-long availability discount.
- Lower values apply a season-equivalent discount for surgery recovery, load management, injury recurrence, or expected missed time.
- This is **not** the player's ability while healthy; it is an availability-adjusted season valuation.

### 3.2 Projection-only players

Players without a usable 2025–26 NBA regular-season sample are not assigned a fabricated historical FP/G.

Instead:

```text
Adjusted FP/G
= Projection-only baseline
× Role Factor
× Health / Availability Factor
```

This lane is mainly for incoming rookies and players returning without a representative prior-season sample.

## 4. Team aggregation

Three team-level values are retained:

- **13-player adjusted FP/G total** — complete roster depth.
- **Top-10 adjusted FP/G** — sum of the 10 highest adjusted player values; the primary ranking signal.
- **13-player average** — supporting depth indicator.

The model ranks teams by **Top-10 adjusted FP/G**, because the full 13-player sum can over-reward deep benches that cannot all occupy active slots simultaneously.

This still does **not** optimize daily schedule density or position eligibility.

## 5. 16-team result — frozen 2026-10-05 snapshot

| Rank | Team | Top-10 Adjusted FP/G | 13-player Total | 13-player Avg | Model read |
|---:|---|---:|---:|---:|---|
| 1 | 第1隊 | **378.9** | 452.0 | 34.77 | S |
| 2 | 第13隊 | **371.2** | 438.1 | 33.70 | S |
| 3 | 第4隊 | **363.9** | 429.0 | 33.00 | A+ |
| **4** | **第2隊 (Owner)** | **362.7** | **429.0** | **33.00** | **A+** |
| 5 | 第11隊 | 361.9 | 429.1 | 33.01 | A+ |
| 6 | 第9隊 | 361.9 | 425.6 | 32.74 | A+ |
| 7 | 第5隊 | 361.7 | 427.6 | 32.90 | A+ |
| 8 | 第3隊 | 357.2 | 425.0 | 32.69 | A |
| 9 | 第7隊 | 351.9 | 419.0 | 32.23 | A |
| 10 | 第15隊 | 350.9 | 411.1 | 31.62 | A |
| 11 | 第14隊 | 347.1 | 416.6 | 32.05 | B+ |
| 12 | 第6隊 | 346.4 | 403.5 | 31.04 | B+ |
| 13 | 第10隊 | 340.4 | 405.1 | 31.16 | B |
| 14 | 第16隊 | 329.4 | 391.1 | 30.09 | C+ |
| 15 | 第8隊 | 322.1 | 384.6 | 29.58 | C |
| 16 | 第12隊 | 320.3 | 375.6 | 28.89 | C |

## 6. Owner-team result

The accepted V1 model places **team_02 at No. 4 of 16** with:

- **Top-10 adjusted FP/G: 362.7**
- **13-player adjusted FP/G total: 429.0**
- **13-player average: 33.00**
- **Projection-only players: 0**

The main projected engines are:

| Player | Approx. Adjusted FP/G |
|---|---:|
| Alperen Sengun | 48.7 |
| Scottie Barnes | 46.9 |
| Walker Kessler | 40.8 |
| De'Aaron Fox | 37.2 |
| Stephon Castle | 37.0 |

This gives the roster a relatively high-confidence core because the current 13-player owner roster does not depend on projection-only rookies to reach its ranking.

### 6.1 Smart → Larsson effect

The owner-confirmed change is modeled approximately as:

- Marcus Smart old adjusted value: **18.1 FP/G**
- Pelle Larsson new adjusted value: **24.6 FP/G**
- Full-roster depth change: approximately **+6.5 FP/G**
- Top-10 impact: only about **+0.5 FP/G**, because the move primarily improves the bottom of the rotation rather than the top-end core.

The move therefore improves **roster floor and depth** more than championship ceiling.

## 7. Competitive interpretation

The model currently shows two broad patterns:

**Front pair**

- 第1隊: 378.9
- 第13隊: 371.2

**Dense contender pack**

- 第4隊: 363.9
- 第2隊: 362.7
- 第11隊: 361.9
- 第9隊: 361.9
- 第5隊: 361.7

For the owner team:

- Gap to No. 3: about **1.2 FP/G**
- Gap to No. 2: about **8.5 FP/G**
- Gap to No. 1: about **16.2 FP/G**
- Spread from No. 3 through No. 7: only about **2.2 FP/G**

The practical conclusion is that team_02 should be treated as a **championship contender**, not a fringe playoff roster. Small role changes, a breakout, one successful waiver upgrade, or an injury can reorder the entire No. 3–No. 7 cluster.

## 8. Known limitations

This V1 model deliberately does not attempt to solve all fantasy-basketball uncertainty.

1. **No daily schedule simulation.** Top-10 is a roster-strength proxy, not a calendar-aware lineup optimizer.
2. **No position-eligibility optimization.** It does not test whether the theoretical best 10 can all be started together under Yahoo positional rules.
3. **No Monte Carlo injury variance.** Health is represented by a deterministic availability factor.
4. **Role factors are forward-looking assumptions.** They are intentionally separated from historical box-score evidence and may change rapidly during preseason.
5. **Disciplinary-event history is incomplete.** TECH is incorporated where reliably available; FF/EJCT are not fully replayed from Yahoo game logs.
6. **No live Yahoo reconciliation yet.** Once the read-only Yahoo integration is validated, Yahoo should become league-state truth while this repo's scoring configuration remains decision truth.
7. **This report is a snapshot.** Do not silently rewrite it when projections change.

## 9. Next model versions

Future work should create a new dated report rather than overwrite this V1 baseline.

Likely next steps:

- Yahoo read-only roster reconciliation.
- Updated player roles after the opening regular-season rotation stabilizes.
- Position-eligibility and daily schedule optimization.
- Monte Carlo season / head-to-head simulation.
- Playoff probability, Top-3 probability, and championship probability.
- Waiver and trade marginal-value analysis relative to the owner's weakest active slots.

This file remains the comparison baseline for those later models.
