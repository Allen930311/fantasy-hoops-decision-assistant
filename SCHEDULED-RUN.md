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

Roster changes in the repository are the first ownership authority. A later owner message explicitly confirming an already completed but not yet synced transaction can temporarily override the affected player identities, with citation and timestamp. A proposed/intent-only transaction never overrides the repository. Do not reconstruct prior roster membership from general chat memory.

## 3. Free-agent / available-player truth

Before Yahoo read-only reconciliation is complete:

- Treat every player listed in any team in `rosters.json` as rostered / unavailable.
- Build the candidate available-player pool from current NBA/Fantasy-eligible players and exclude every rostered player.
- Distinguish confirmed fantasy availability from inference when waiver/eligibility state cannot be verified.
- Do not recommend a player who appears on any of the 16 recorded rosters.
- Prefer players with enough current evidence to evaluate under the owner's scoring model; do not spam deep-bench names merely because they are technically unrostered.

The 2026-10-19 Yahoo API application denial means **no live Yahoo entitlement is available**. Do not scrape protected Yahoo data, rely on undocumented endpoints/cookies, or circumvent region/access restrictions. Until a separately authorized source is validated, treat roster-exclusion as *candidate discovery only*: waiver eligibility/availability must remain **UNKNOWN** unless current owner-supplied/authorized evidence confirms it. A future official provider transition requires new authorization and read-back, not a prompt assumption.

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

## 8. Daily report vs conditional alert (2026–27)

The scheduled **15:00 Asia/Taipei** daily battle report is a separate delivery obligation from the conditional notification gate in section 6. If one or more NBA games have completed by the data cutoff, produce the complete daily report even when there is no actionable ADD/DROP/TRADE alert. Section 6 governs only **extra GM action alerts**, not daily report delivery.

Daily reports cover every owner-roster player who played, curated highlights from other 15 teams, and selected truly unrostered free agents. Use fresh main rosters and season scoring. Explicitly confirmed but unsynced completed adds are temporary ownership exclusions; mere trade intentions are not.

**Read-only separation:** The monitor itself remains read-only with respect to rosters, Yahoo, waivers and trades. The independently tested report archival writer may only create immutable files beneath `seasons/<season>/report/daily/`, on a review branch/PR; it has no authority to change rosters, scoring, or transact. Owner explicitly waived the Fresh Agent comparison **for this daily-report archive integration only** on 2026-10-22. This is a WAIVER, not Fresh Agent PASS. After successful code CI, GitHub authorization/readback smoke test, and merge of the reviewed archive implementation, the existing daily scheduled task may invoke the independently scoped report archive flow. Treat a branch commit as PR_PENDING; report ARCHIVED only after a verified main readback. Failure to archive must not suppress the daily report. On writer failure, still deliver the report with an archive failure label; never claim archival success prematurely.

## 9. One-time acceptance decision for PR #9 (2026-10-22)

Owner: Fresh Agent A/B is **not required for this feature**; this does **not** repeal Fresh Agent requirements for any other workflow. Standard automated tests, complete provenance, write/readback verification, and fail-closed report publication remain required. The daily report remains a separate delivery from archiving. A successful draft PR alone is not proof that the report is already in main.
