# STATUS — Fantasy Hoops Decision Assistant

**Lifecycle:** Active　｜　**Last reviewed:** 2026-10-28 (Asia/Taipei)　｜　**Current season:** 2026–27

## Current authority

- `seasons/2026-27/league.json` is the sole custom Fantasy scoring authority.
- `rosters.json` (`players` and `additional_owned_players`) plus `ownership/current-state.json` are the current owner-confirmed bootstrap and effective overlay. They are not live Yahoo reads.
- Yahoo API application submitted 2026-10-04 was denied 2026-10-19. No current authenticated read-only Yahoo integration is validated; uncertain FA/waiver status remains `UNKNOWN`.
- `SCHEDULED-RUN.md` is the authority for the existing 15:00 Asia/Taipei report task. Do not create another schedule.

## Daily report implementation and acceptance

- PR #23 merged to main as `2be255188ab186e0934c6b12fd4225a4e749592b`. The shared NBA adapter, `league.json` FP calculator, generator, validator, and rights-gated publisher are in main.
- Offline tests: 89/89 pass; three-date official-source replay was completed before merge. This is not proof of the scheduled task invoking Python.
- Issue #11's 2026-10-28 revision separates source/use permission, runtime/numerical validation, delivery/storage, and public publication. The existing 15:00 task remains the only schedule; its prompt now requires report delivery independent of save/publication and prohibits unverified public GitHub writes.
- No supported Python runner or GitHub Actions dispatch is exposed to the scheduled task. The last recorded run was scheduled for 15:00 on 2026-10-27 but started at 14:38 and ended at 14:41 Taipei. `SCHEDULED_PRODUCTION_E2E_PENDING`.
- NBA endpoint use for this Fantasy workflow remains `UNVERIFIED`; do not infer permission from public HTTP endpoints, `nba_api`, or League Pass. Public release remains blocked separately. See `docs/data-publication-audit-2026-10-27.md`.
- Google Drive write was denied with `ACCESS_TOKEN_SCOPE_INSUFFICIENT`. Task result history can be checked as a private delivery/readback surface, but only mark storage `STORED` after complete, untruncated exact readback and SHA-256 comparison. A workspace file is not a scheduled persistent save.
- Current engineering work adds a run-receipt contract for independent `content_status`, `runtime_status`, `execution_mode`, `delivery_status`, `storage_status`, `source_use_status`, and `publication_rights_status` / `publication_status`; its tests are synthetic and do not prove production execution or source rights.

## Next gates

1. Configure an authorized current-season provider that permits automated private Fantasy analytics, then verify real schema, IDs, rate limits, and required fields.
2. Obtain a platform-supported Python runner or authenticated dispatch plus result return channel for the existing task.
3. Demonstrate a genuine scheduled run, Owner delivery, and retrievable private report readback with matching SHA-256.

Keep Issue #11 open until the scheduled-run acceptance criteria pass. Keep Scouting Issue #15 and Yahoo roster transactions outside this gate.
