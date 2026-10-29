# STATUS — Fantasy Hoops Decision Assistant

**Lifecycle:** Active　｜　**Last reviewed:** 2026-10-29 (Asia/Taipei)　｜　**Current season:** 2026–27

## Current authority

- `seasons/2026-27/league.json` is the sole custom Fantasy scoring authority.
- `rosters.json` (`players` and `additional_owned_players`) plus `ownership/current-state.json` are the current owner-confirmed bootstrap and effective overlay. They are not live Yahoo reads.
- Yahoo API application submitted 2026-10-04 was denied 2026-10-19. No current authenticated read-only Yahoo integration is validated; uncertain FA/waiver status remains `UNKNOWN`.
- `SCHEDULED-RUN.md` is the authority for the existing 15:00 Asia/Taipei report task. Do not create another schedule.

## Daily report implementation and acceptance

- PR #23 merged to main as `2be255188ab186e0934c6b12fd4225a4e749592b`. The shared NBA adapter, `league.json` FP calculator, generator, validator, and rights-gated publisher are in main.
- Offline tests: 89/89 pass; three-date official-source replay was completed before merge. This is not proof of the scheduled task invoking Python.
- **Owner's latest Issue #11 decision is authoritative for the daily report:** the existing 15:00 ChatGPT task directly searches lawful public web sources for the actual games/box scores, calculates FP from `league.json`, labels missing fields `PARTIAL`, and **delivers the private report first**. Python runner, Actions dispatch, provider API subscription, public-redistribution approval, GitHub archive, and further architecture work are **not prerequisites for delivering the report**. Separately check every owner player's injury/availability status; official NBA injury reports are the primary reference. Do not publish third-party content without applicable rights.
- The 2026-10-28 scheduled task ran at 15:03–15:07 Taipei and delivered a `PROVISIONAL` report: 4/4 Final games, 4/4 owner participants identified, 2/4 numeric partial FP bases, 0/4 fully verified custom FP. No verified GitHub archive. Python runner / Actions dispatch have not been demonstrated, but these are optional engineering capabilities and do not block Owner-facing delivery.
- NBA endpoint use for this Fantasy workflow remains `UNVERIFIED`; do not infer permission from public HTTP endpoints, `nba_api`, or League Pass. Public release remains blocked separately. See `docs/data-publication-audit-2026-10-27.md`.
- GitHub archiving and persistent storage are independent of the report: only mark `STORED` / `ARCHIVED` after actual durable write and complete readback. Previous Google Drive write returned `ACCESS_TOKEN_SCOPE_INSUFFICIENT`; do not reopen Drive/Python integration merely to deliver the report.
- Current engineering work adds a run-receipt contract for independent `content_status`, `runtime_status`, `execution_mode`, `delivery_status`, `storage_status`, `source_use_status`, and `publication_rights_status` / `publication_status`; its tests are synthetic and do not prove production execution or source rights.

## Immediate operating priorities (Owner's simplified flow)

1. Every 15:00 report: newest main roster/ownership/league → current web search → every Final owner player's box score → custom FP, with `PARTIAL` for unresolved fields → **deliver report regardless of archive**.
2. Include every owner-rostered player's latest injury / game-availability status, source and update time, changed risk, and GM implication; never assume a player absent from a game-specific injury report is definitively healthy. A separate injury-only alert may run without creating another daily-report task.
3. Try GitHub archival only when content, rights, and write surface permit it; report actual result without treating failure as a delivery failure. Never declare complete FP or archive without supporting evidence.

Issue #11 stays open while factual owner-coverage/FP and scheduled delivery are being improved; do not substitute optional runner engineering or public-release research for daily delivery. Scouting Issue #15 and Yahoo transaction work remain separate.
