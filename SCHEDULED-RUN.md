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
- `seasons/2026-27/ownership/README.md` (transaction matching policy)
- `seasons/2026-27/ownership/current-state.json` (current effective overlay; do **not** union all historical dated ADD lists)

If the repository later changes the active season or authority path, follow the repository's newest canonical state instead of this historical example.

## 2. League and owner-team truth

`league.json` is the season-specific league/scoring configuration.

`rosters.json` is the current bootstrap ownership state until the repository explicitly promotes a validated Yahoo read-only source. Owned players include **both** `teams[].players` and `teams[].additional_owned_players` (extra confirmed team ownership, actual active/IL slot unknown); do not assume 13 baseline slots exhaust ownership.

Resolve the owner's team from `owner_team_id`; do not hard-code player names in the scheduled task.

Apply the current-season `ownership/README.md` when reconciling screenshots: a uniquely rostered DROP can identify a stable team_id for that entire clear transaction batch; a nickname alone cannot, and ADD without DROP does not imply anyone else was released (IL allowed). `ownership/current-state.json` holds confirmed ADDs with no provable team_id; later explicit DROP releases historical ADD evidence, but waiver/FA eligibility remains unknown.

Roster changes in the repository are the first ownership authority. A later owner message explicitly confirming an already completed but not yet synced transaction can temporarily override the affected player identities, with citation and timestamp. A proposed/intent-only transaction never overrides the repository. Do not reconstruct prior roster membership from general chat memory.

## 3. Free-agent / available-player truth

Before Yahoo read-only reconciliation is complete:

- Treat every player in any team's `players` **or** `additional_owned_players` in `rosters.json` as rostered / unavailable.
- Exclude `ownership/current-state.json.unassigned_confirmed_owned_players` from FA recommendations, even though `team_id` is null.
- Players in `released_availability_unverified` are no longer treated as confirmed owned but must not be called immediately available without a newer Yahoo FA/waiver check.
- A newer confirmed screenshot overrides older ADD-only exclusions: never union historical `confirmed-add-fa-exclusions-YYYY-MM-DD.json` files as permanent ownership.
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

## 8. Daily report vs conditional alert (2026–27)

The **15:00 Asia/Taipei** daily report is unconditional and separate from the section 6 notification gate. Deliver the report even when there are no GM alerts or no completed games. State an empty slate, Live/Scheduled games, data gaps, and unavailable sources accurately; Live or Scheduled is never DNP.

Use current main's `rosters.json` (both player lists), `ownership/current-state.json`, and `league.json`. Cover every Owner player actually found in Final games; if schedule/box-score acquisition is incomplete, disclose unknown coverage rather than claiming 100%. Other teams are curated. FA candidates exclude rostered and confirmed unsynced ADD players; without current Yahoo evidence, claimability is `UNKNOWN`.

Report delivery must not wait for storage or public publication. Do not change Yahoo, roster, ownership, scoring, or schedule. An inability to invoke the Python runtime must be reported while still delivering the fullest report supported by authorized data.

## 9. One-time acceptance decision for PR #9 (2026-10-22)

Owner: Fresh Agent A/B is **not required for this feature**; this does **not** repeal Fresh Agent requirements for any other workflow. Standard automated tests, complete provenance, write/readback verification, and fail-closed report publication remain required. The daily report remains a separate delivery from archiving. A successful draft PR alone is not proof that the report is already in main.

## 10. Issue #11 run status and persistence contract (Owner-approved 2026-10-28)

Every run records independent fields:

- `content_status=VALIDATED|PROVISIONAL` — numerical/identity quality only.
- `runtime_status=EXECUTED_CANONICAL|RUNTIME_INTEGRATION_BLOCKED|NOT_EXECUTED` — only say `EXECUTED_CANONICAL` when the actual task invoked the latest main runtime.
- `execution_mode=SCHEDULED_PRODUCTION|MANUAL_REPLAY|CI|SYNTHETIC|UNKNOWN` — record the actual trigger. Scheduled acceptance also needs the existing task ID and a recorded run ID/time corroborated from automation history; caller-supplied fields or a shell/CI replay are not proof. Record early/on-time/late start against 15:00 Asia/Taipei; an early result is not a 15:00 report.
- `delivery_status=DELIVERED|FAILED` — only say `DELIVERED` when the readable report is present in the Owner-facing task result.
- `storage_status=STORED|STORAGE_BLOCKED` — `STORED` requires an Owner-accessible persistent destination, complete readback, exact UTF-8 equality, and SHA-256 match. Do not assume Drive write scopes or workspace durability. The task result history may count only when the full, untruncated result is read back and hashed.
- `publication_rights_status=AUTHORIZED|UNVERIFIED|BLOCKED` is independent of source-use permission. `publication_status=PUBLISHED|PR_PENDING|PUBLICATION_BLOCKED|NOT_REQUESTED` — public GitHub writes remain blocked for NBA-derived artifacts until both source/use and publication rights are established. This status never blocks report delivery or permitted private storage.

`scripts/daily_report_run_receipt.py` assembles these fields from caller-provided evidence. Its unit tests are synthetic; its assertions are not a platform signature or an independent verification of a storage account. A real receipt must be checked against the corresponding task history, runtime commit, storage adapter, full readback, and hashes.

The canonical scripts are in main after PR #23. The current scheduled-task tool surface has not demonstrated a Python invocation or GitHub Actions dispatch path. Do not use `run_now`, a hand replay, or CI as scheduled-production evidence; preserve the existing schedule and leave Issue #11 open until a genuine scheduled result, delivery, authorized save/readback, and complete receipt exist.

Source acquisition/use permission is separate from private storage and public redistribution. Use only sources whose terms cover the intended automated Fantasy research. Do not bypass provider controls. If no authorized source is available, report the exact data gap and still deliver whatever can be substantiated without those fields.
