# Fantasy Hoops Decision Assistant

Personal Fantasy Basketball analytics and decision-support project.

## Purpose

Personal Fantasy Basketball analysis and decision support using owner-defined scoring, publicly sourced/licensed NBA performance information and **owner-confirmed, date-stamped manual league-state inputs**. Yahoo Fantasy league state would be the live provider authority **only if** an official API integration is separately authorized, implemented and reconciled.

Yahoo declined this project's API application (official notice dated 2026-10-19). Do not scrape protected Yahoo surfaces, reuse cookies or undocumented endpoints, or work around provider restrictions. See [STATUS.md](STATUS.md) and [Issue #7](https://github.com/Allen930311/fantasy-hoops-decision-assistant/issues/7).

## Active offline/manual scope

- Apply the owner's 2026–27 `league.json` scoring configuration to sourced, date-stamped player statistics, recording coverage, rights and missing data.
- Reconcile the 16-team `rosters.json` bootstrap against **newer owner-confirmed manual updates** (adds/drops/trades) with input timestamps and integrity checks.
- Build provisional free-agent, waiver and trade analyses; do **not** label an unrostered player as confirmed Yahoo-available without separate current evidence.
- Evaluate PR #6 for Issue #5: actual vs projected rankings, independent calculation, validation, Fresh Agent and CI evidence.
- Keep every Yahoo-specific league state/eligibility/transaction claim **UNKNOWN** unless a permitted, authoritative source is supplied.

## Decision authority

- `league.json`: owner-approved season scoring rules.
- `rosters.json`: owner-provided bootstrap ownership **as of its recorded update**, not a live Yahoo feed.
- Owner-confirmed manual league/waiver/transaction snapshots: explicit `as_of` and provenance; no inferred Yahoo permission or live status.
- Public/licensed NBA player data: raw basketball statistics, not league ownership.
- Custom scoring, projections, role/risk adjustments and recommendations: derived decision analysis with uncertainty.

```text
Owner-confirmed league snapshot (timestamped) + permitted public stats
                   ↓
       Validation + source / staleness labels
                   ↓
       Custom scoring + projections
                   ↓
       Provisional FA / waiver / trade analysis
                   ↓
       Owner-controlled action (not automated)
```

A future official Yahoo read-only connection is a **conditional option**, not an active milestone or granted entitlement.

## Season-scoped league data

League configuration is versioned by season because rosters and scoring rules can change every year.

The current bootstrap snapshot lives under:

- [`seasons/2026-27/league.json`](seasons/2026-27/league.json) — **2026–2027** scoring rules and league metadata.
- [`seasons/2026-27/rosters.json`](seasons/2026-27/rosters.json) — mutable 16-team roster state.
- [`seasons/2026-27/README.md`](seasons/2026-27/README.md) — update and season-boundary policy.

Do not overwrite an old season to represent a new one. Create a new season directory and explicitly define that season's rosters and scoring rules.

Until a newly authorized provider source is genuinely validated, the season snapshot is only an **as-of manual bootstrap**. It may be stale; future official Yahoo state cannot be promoted without new authorization and read-back evidence. The owner scoring configuration remains the scoring authority.

## Status

Yahoo API application was declined by official notice dated 2026-10-19. Active next gate: offline/manual R0 and review of Draft PR #6; no provider read entitlement has been established.

A season-scoped **2026–2027** 16-team bootstrap roster and custom scoring configuration are now available for provisional decision support while authorized live provider ingestion is unavailable.

See [STATUS.md](STATUS.md) for current operational state.

## Security

Do not commit Yahoo OAuth client secrets, refresh tokens, access tokens, cookies, or personal league credentials to this repository. No use of cookies, protected-page scraping, geographic bypasses, or undocumented endpoints to circumvent the denial. Do not commit private owner-provided snapshots without appropriate confidentiality review.


## Scheduled monitor

The recurring Fantasy monitor is repository-driven. Its stable bootstrap is [SCHEDULED-RUN.md](SCHEDULED-RUN.md).

The schedule itself must not contain a hard-coded roster or scoring model. Update the repository's current season state instead, and the next run will read the new truth.
