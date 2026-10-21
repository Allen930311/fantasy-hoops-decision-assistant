# STATUS

**Project:** Fantasy Hoops Decision Assistant  
**Status:** EXTERNAL_BLOCKER — Yahoo Fantasy API application declined; lawful offline/manual R0 is the next gate  
**Lifecycle:** Active (offline R0 and PR #6 still require review/qualification)  
**Repository:** `Allen930311/fantasy-hoops-decision-assistant`

## Current objective

Move the next useful decision-support milestone to a **lawful offline/manual workflow**: review the existing 2026–27 16-team model, score public/licensed player data using the owner's league rules, and reconcile owner-confirmed roster/waiver inputs with explicit timestamps and uncertainty. See [Issue #7](https://github.com/Allen930311/fantasy-hoops-decision-assistant/issues/7). [Issue #5](https://github.com/Allen930311/fantasy-hoops-decision-assistant/issues/5) and Draft [PR #6](https://github.com/Allen930311/fantasy-hoops-decision-assistant/pull/6) retain their independent ranking, validation and CI gates.

## API access: external blocker (new evidence)

- Application submitted on **2026-10-04**. The previous `AWAITING_REVIEW` wording was the historical state, **not current truth**.
- The Yahoo Fantasy API Team **declined this application** by official email dated **2026-10-19** (2026-10-20 Asia/Taipei). It stated that the proposed use case did not align with its current API Access and Use Agreement/policies and that the standard terms are for use in the United States and Canada only.
- **No authorization or live read-only connection has been granted.** This denial does not establish that every future application is impossible; any future integration would require fresh eligibility, provider permission and Owner approval.
- Do **not** circumvent Yahoo's access restrictions with scraped protected pages, undocumented APIs, session cookies, geographic workarounds, or unapproved credentials. Do not infer Yahoo write access.

## Season-scoped local bootstrap (not live league authority)

The repository stores the **2026–27** league under `seasons/2026-27/`:

- 16 teams, 13 recorded roster slots each, 208 unique rostered-player slots in the recorded bootstrap;
- `team_02` is the owner's team in that bootstrap;
- `league.json` provides the owner-defined scoring rules;
- `rosters.json` is a mutable, **as-of** owner-provided snapshot, not a verified current Yahoo roster, waiver pool, or transaction feed;
- the 2026-10-04 Marcus Smart → Pelle Larsson change is historical evidence, **not** proof that the October 2026 live roster remains identical.

Newer changes require an owner-confirmed input, dated `as_of`, provenance and integrity validation. If they have not been reconciled, explicitly label the roster state **STALE / UNCONFIRMED** rather than silently treating the last file as live state.

## Offline/manual R0 acceptance (not yet complete)

1. Validate season configuration (`league.json`), roster structure, unique ownership and explicit input `as_of` date.
2. Use publicly available data only where access, permitted use and attribution are verified. Record per-player statistic source, data cutoff, coverage, missingness and owner-defined fantasy point calculations; do not substitute Yahoo generic scoring.
3. Document the manual input/reconciliation SOP for league teams, adds/drops/trades and waiver/eligibility status (input, authority, provenance, side effects, failures). **Not on a stored roster ≠ confirmed available on Yahoo.**
4. Keep actual performance and forward projections separate and show uncertainty. Validate the 16-team ranking, independent Fresh Agent recalculation and CI for Issue #5 / Draft PR #6.
5. Publish decision recommendations only with an explicit source/uncertainty label; unsupported Yahoo-specific ownership or availability remains **UNKNOWN**.
6. Obtain the normal Owner merge gate before promoting any Draft work.

## Current boundary and next action

There is no authorized Yahoo API production integration. Offline scoring and owner-supplied snapshots are usable as *inputs*, not provider-certified live league truth. The next step is [Issue #7](https://github.com/Allen930311/fantasy-hoops-decision-assistant/issues/7) and PR #6 review, **not waiting indefinitely for Yahoo approval**. Reconsider an official integration only on new, legitimate provider authorization; never work around the denial.

_Last evidence reconciliation: 2026-10-21 (Asia/Taipei). Documentation update proposed; does not by itself qualify offline R0 or PR #6._
