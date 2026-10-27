# AGENT_CONTEXT — fantasy-hoops-decision-assistant

> Fresh-agent entrypoint for the 2026–2027 Fantasy Basketball decision system.

## What this repo is

Personal Fantasy Basketball decision support using the owner's season-scoped scoring
rules, permissioned/public NBA information, and explicitly dated manual league inputs.
The project's Yahoo API application was declined on 2026-10-19; no live Yahoo
read entitlement or provider-certified roster/waiver state exists.

## Authority

| Concern | Authority |
|---|---|
| Current project status and next gate | `STATUS.md` |
| Project purpose and boundaries | `README.md` |
| 2026–2027 owner-approved scoring rules | `seasons/2026-27/league.json` |
| Last recorded manual roster bootstrap, with its own `as_of` | `seasons/2026-27/rosters.json` |
| Validated Owner-provided ADD/DROP screenshots | Timestamped provenance; ownership exclusion even when adding team is unknown |
| Scheduled monitor instructions | `SCHEDULED-RUN.md` |

`league.json` governs scoring. `rosters.json` is only an **as-of snapshot**;
never assume it describes Yahoo live roster status. Read the actual `as_of` on
every run rather than copying a date from this entrypoint. A future official Yahoo
provider source may become league-state authority only with new permission,
successful integration and independent readback.

## Current gate

Read `STATUS.md` freshly. Yahoo's 2026-10-19 rejection replaces the stale
"awaiting review" description. The active work is lawful offline/manual scoring,
roster reconciliation and uncertainty-labeled recommendations, including the
independent reviews required by Issue #7 and Draft PR #6.

For transactions and free agents:
- A completed ADD evidenced by an Owner-supplied Yahoo screenshot is **owned**;
  exclude that player from FA suggestions, even when the adding team is unknown.
- A screenshot showing an ADD but no DROP does **not** establish free-agent
  availability or an invalid transaction: the league permits IL.
- Preserve `unknown_team` when attribution is unclear. Do not infer team identity
  from mutable team display names, and do not treat old screenshots as current
  without checking subsequent changes.
- Not listed on the manual roster is **not** proof a player is currently
  available in Yahoo. Waiver eligibility/availability stays `UNKNOWN`
  without new authoritative evidence.
- Roster changes and league transactions are Owner-controlled; the monitor
  cannot execute ADD, DROP or trade actions.

Do not scrape protected Yahoo pages, use private cookies/undocumented routes,
or bypass provider restrictions. Source NBA statistics only through permissible
sources and attach cutoff, completeness and attribution.

## Remote vs local truth

Remote `main` is shared project state, not an automatic live provider feed.
Credentials, private authenticated responses and other local secrets must not
be committed. If a source is missing or stale, report `UNKNOWN` or
`BLOCKED` rather than guessing from prior conversations.

## Season boundary

Never overwrite an earlier season. Roster membership, scoring rules and
recorded provenance must be evaluated for the active season.

## Safe start

1. Read `STATUS.md` and the current season's `league.json`.
2. Read `rosters.json`, its `as_of` and later verified Owner transaction/exclusion evidence.
3. Validate that player ownership is not inferred solely from roster absence.
4. Check fresh, licensed NBA player/role/injury evidence where relevant.
5. Report the exact current source cutoff and confidence before making a recommendation.
