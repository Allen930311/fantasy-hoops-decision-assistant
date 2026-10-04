# Scheduled Fantasy Monitor

This file is the canonical bootstrap for the scheduled Fantasy Basketball monitor.

The scheduled task must not hard-code roster membership, free-agent names, season scoring, or owner-team players in its own prompt. Every run must fresh-read this repository and resolve current truth from the files below.

## 1. Resolve current season and project state

Read, in order:

1. `STATUS.md`
2. root `README.md`
3. the current season directory identified by project status / active season metadata

For the current 2026–27 season, read:

- `seasons/2026-27/README.md`
- `seasons/2026-27/league.json`
- `seasons/2026-27/rosters.json`

If the repository later changes the active season or authority path, follow the repository's newest canonical state instead of this historical example.

## 2. League and owner-team truth

`league.json` is the season-specific league/scoring configuration.

`rosters.json` is the current bootstrap ownership state until the repository explicitly promotes a validated Yahoo read-only source.

Resolve the owner's team from `owner_team_id`; do not hard-code player names in the scheduled task.

Roster changes are authoritative only when they are present in the repository's current state. Do not reconstruct old roster membership from chat memory or from an older scheduled prompt.

## 3. Free-agent / available-player truth

Before Yahoo read-only reconciliation is complete:

- Treat every player listed in any team in `rosters.json` as rostered / unavailable.
- Build the candidate available-player pool from current NBA/Fantasy-eligible players and exclude every rostered player.
- Distinguish confirmed fantasy availability from inference when waiver/eligibility state cannot be verified.
- Do not recommend a player who appears on any of the 16 recorded rosters.
- Prefer players with enough current evidence to evaluate under the owner's scoring model; do not spam deep-bench names merely because they are technically unrostered.

After the repository records a validated Yahoo availability/ownership authority, use that source instead of roster-exclusion inference. The scheduled prompt must not need to change for this transition.

## 4. Scoring authority

Read scoring directly from the current season's `league.json` on every run.

Never hard-code or substitute Yahoo generic rankings, category rankings, or another site's fantasy points formula.

Use external rankings only as supporting context.

## 5. Monitoring job

Using the fresh repository state, monitor:

- the owner's current roster;
- meaningful free-agent / waiver candidates;
- injuries and return timelines;
- starting/bench role and rotation changes;
- minutes, usage, ball-handling and depth-chart changes;
- NBA transactions;
- preseason and regular-season performance;
- realistic 1-for-1 and 2-for-1 consolidation trade opportunities.

Re-evaluate relevant players using the owner-defined scoring model from the repository.

## 6. Notification gate

Notify only when there is a **new, decision-relevant change** such as:

- an owner-roster player materially rises or falls in value;
- a current roster player becomes a credible HOLD / TRADE / DROP decision;
- an actually available player becomes a credible ADD;
- a meaningful waiver target appears;
- a realistic trade package becomes newly actionable.

When notifying, include:

- the player(s) affected;
- what changed;
- the impact under the repo-defined scoring;
- a concrete ADD / DROP / TRADE / HOLD recommendation;
- for trades, a specific negotiable package.

Do not repeat previously reported information without new evidence.

If nothing materially changes, do not notify.

## 7. Failure-safe behavior

If the current repository authority cannot be read, fail closed and report the exact missing source instead of falling back to an old hard-coded roster or scoring prompt.

This scheduled monitor is read-only. It must not edit the repository, execute Yahoo roster actions, submit waivers, or make trades.
