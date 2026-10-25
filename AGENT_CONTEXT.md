# AGENT_CONTEXT — fantasy-hoops-decision-assistant

> Fresh-agent entrypoint for the 2026–2027 Fantasy Basketball decision system.

## What this repo is

Personal Yahoo Fantasy Basketball analytics and decision support. It combines
league state with Allen's season-scoped scoring model and basketball analysis.

## Authority

| Concern | Authority |
|---|---|
| What is true now / next gate | `STATUS.md` |
| Project purpose / decision model | `README.md` |
| Current 2026–2027 scoring rules | `seasons/2026-27/league.json` |
| Bootstrap roster state before Yahoo reconciliation | `seasons/2026-27/rosters.json` |
| Scheduled monitor bootstrap | `SCHEDULED-RUN.md` |

Yahoo becomes live league-state truth only after the planned read-only R0 is
successfully reconciled. Until then, the season roster file is a manual
owner-confirmed bootstrap snapshot, not live Yahoo truth.

Owner-defined scoring remains decision truth even after Yahoo ingestion.

## Current gate

Read `STATUS.md` fresh.

As of the current remote status, Yahoo Fantasy API access has been submitted
and is awaiting review. No production integration exists yet.

Legal next action before approval:
- maintain/reconcile owner-confirmed bootstrap state when Allen supplies a real
  roster transaction;
- research players/current NBA context for recommendations;
- do not pretend Yahoo live state was read.

After access is granted:
- configure OAuth locally without committing secrets;
- implement/validate **read-only** league-state ingestion first;
- reconcile Yahoo state against the season bootstrap before treating it as live
  authority.

Roster/waiver/trade actions remain manual owner actions unless a future
explicit contract changes that boundary.

## Remote vs local truth

Remote `main` is shared Project state. OAuth credentials, access tokens and
live authenticated Yahoo responses are external/local runtime facts and must
never be committed.

If live Yahoo access is unavailable, report it rather than guessing league
state from memory.

## Season boundary

Never overwrite an old season to represent a new season. Roster composition and
scoring rules are season-scoped.

## Safe start

1. Read `STATUS.md`.
2. Read `seasons/2026-27/league.json` before ranking players.
3. Read current roster/bootstrap state before recommending adds/drops/trades.
4. Check fresh NBA player/news evidence when a recommendation depends on current
   roles, injuries or transactions.

## Player scouting (independent SOP)

When asked to scout a player, track research candidates, or compare a long-term replacement, use `.agents/skills/player-scout/SKILL.md` and active-season `scouting/README.md`. Claude Code can discover the equivalent `.claude/skills/player-scout/SKILL.md` entrance. This is separate from the scheduled daily battle report. Never label a candidate CONFIRMED_FA solely because the name is absent from `rosters.json`; read the season ownership SOP and current effective overlay.
