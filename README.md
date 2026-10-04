# Fantasy Hoops Decision Assistant

Personal Yahoo Fantasy Basketball analytics and decision-support project.

## Purpose

This project is intended to use Yahoo Fantasy Sports data as the live source of league state, then combine it with an owner-defined fantasy scoring model, player projections, role analysis, injury/risk context, and transaction analysis.

The goal is decision support for a private Fantasy Basketball league: identify meaningful free-agent, waiver, roster, and trade opportunities without treating Yahoo's own rankings as the decision authority.

## Initial scope

The first milestone is a read-only Yahoo Fantasy integration that can:

- identify the authenticated user's Fantasy Basketball league;
- read league settings and teams;
- reconstruct current team rosters;
- identify available / waiver players;
- read standings, matchups, player statistics, and completed transactions;
- normalize that state for downstream scoring and recommendation workflows.

Roster changes, waiver claims, and trades remain manual owner actions.

## Decision model

Yahoo Fantasy data is the **league-state truth**.

Owner-defined scoring, projections, role/health adjustments, free-agent ranking, and trade valuation are the **decision truth**.

```text
Yahoo Fantasy league state
        ↓
Normalized league state
        ↓
Custom scoring + projections
        ↓
FA / waiver / trade analysis
        ↓
Actionable recommendation
```

## Season-scoped league data

League configuration is versioned by season because rosters and scoring rules can change every year.

The current bootstrap snapshot lives under:

- [`seasons/2026-27/league.json`](seasons/2026-27/league.json) — **2026–2027** scoring rules and league metadata.
- [`seasons/2026-27/rosters.json`](seasons/2026-27/rosters.json) — mutable 16-team roster state.
- [`seasons/2026-27/README.md`](seasons/2026-27/README.md) — update and season-boundary policy.

Do not overwrite an old season to represent a new one. Create a new season directory and explicitly define that season's rosters and scoring rules.

Until Yahoo read-only reconciliation is complete, the owner-provided season snapshot is the bootstrap ownership-state source. Once validated, Yahoo becomes league-state truth; the season-scoped owner scoring configuration remains decision truth.

## Status

Repository initialized. Yahoo Fantasy API access is being requested before implementation begins.

A season-scoped **2026–2027** 16-team bootstrap roster and custom scoring configuration are now available for decision-support work before live Yahoo ingestion is validated.

See [STATUS.md](STATUS.md) for current operational state.

## Security

Do not commit Yahoo OAuth client secrets, refresh tokens, access tokens, cookies, or personal league credentials to this repository. Local secrets must stay outside version control.
