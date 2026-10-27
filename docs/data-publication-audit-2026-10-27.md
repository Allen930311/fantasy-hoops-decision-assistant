# NBA report publication audit — 2026-10-27

## Decision

`HISTORICAL_PUBLIC_REVIEW_REQUIRED`; `NEW_PUBLIC_RELEASE_BLOCKED`.

The repository is public. Existing report files are mixed artifacts: linked source
references, game/player identifiers and statistical facts, custom Fantasy Point
calculations, and original commentary. They are not all the same rights object.
This inventory does not conclude that historical publication was unlawful, and
does not establish that every standalone statistic is protected. It records that
the source and publication rights for the reports have not been documented well
enough to authorize another public upload. Do not delete or rewrite historical
reports as part of this audit. Keep new generated reports and raw source snapshots
private until a written grant or a provider contract covers the intended use.

## Public artifact inventory

Repository visibility was confirmed as public on 2026-10-27. The source tree was
read from `main` at `23595f69fbbfa904c9b1a1236a8a5061a43f21d1` and PR #21's public branch at
`a767aa3d7311cb557dbcc19f73c85fa4cd1bf248`.

| Location | Content found | SHA-256 | Audit state |
|---|---|---|---|
| `main:seasons/2026-27/report/daily/2026-10-24.provisional.md` | Player/game stats, custom FP, commentary, source links | `1335f05e0c738e72fd238afa9a3b397079dd5df34a0c221b978cea18b6bb4b8f` | Historical public; review required |
| `main:seasons/2026-27/report/daily/2026-10-25.provisional.md` | Player/game stats, custom FP, commentary, source links | `637c4682ccebbf70fac782e6428edd2e33ddec262b365aa10ceee61b232589bd` | Historical public; review required |
| `main:seasons/2026-27/report/daily/2026-10-26.provisional.md` | Player/game stats, custom FP, commentary, source links | `b5d826ac5122b74b9614cc41f92dbcf2a012a8a86bc5cf949b253b6373b723ad` | Historical public; review required |
| `PR #21:.../2026-10-27.provisional.md` | Player/game stats, custom FP, commentary, source links | `04d6c5f1c348d232118ef42a21dbb5570949ca4e7a20196ec6007d6faf781794` | Public draft; superseded |
| `PR #21:.../2026-10-27.v2.provisional.md` | Player/game stats, custom FP, commentary, source links | `572d0fd3375315163dd051e28432948d513b201eb25ebe59cdd9a2e2711269b5` | Public draft; superseded |
| `main:tests/fixtures/historical-nba-finals-2025-06-23-partial.json` | Partial player box-score facts used by a historical scoring test; not a raw API response | `12362a1f2b363c823fb288261a455291645462ce527c2811aabbf239a8b8894e` | Pre-existing public fixture; rights review required |

The inspected Markdown files contain report-level values and citations, but no
complete raw NBA API response payload was found embedded in those files. Raw
response snapshots for the new adapter's private E2E are stored outside this
public repository. A source URL, a hash, or an official-looking endpoint is
provenance evidence; none of them is a redistribution grant.

The three main-branch report blobs also occur byte-for-byte on public refs:
2026-10-24 appears on the 10/24–10/27 `fantasy-report` branches, `feat/player-scout-2026-27`,
`feature/daily-fa-exclusion-overlay-20261024`, the three 10/25 ownership branches,
and `roster/owner-champagnie-20261025`; 2026-10-25 appears on the 10/25–10/27
`fantasy-report` branches, `feat/player-scout-2026-27`, and the owner-Champagnie
roster branch; 2026-10-26 appears on the 10/26–10/27 `fantasy-report` branches
and `feat/player-scout-2026-27`. These are duplicate public refs, not additional
unique report content. PR #21 also carries inherited copies of the 10/24–10/26
files in addition to its two unique 10/27 draft reports and supersession note.
The audit therefore counts five unique report versions plus one metadata note,
not one publication per duplicate ref. The separate historical unit-test fixture
is not counted as a report; it already exists on main and is unchanged by this PR.
The current Daily tests use synthetic fixtures for quality-gate behavior, and
the real-data E2E snapshots remain private.

The three distinct main-branch report files entered main through merged PR #12
(10/24), #18 (10/25), and #20 (10/26). Their branch copies remain publicly
reachable after those merges.

The older reports link NBA.com in some source lists, but a quick scan did not
establish consistent prominent attribution in connection with each use.
Attribution compliance remains unverified.

The corrected private 2026-10-27 report is identified by SHA-256
`8e00f711b7715368d8c1ce49a4d08334576e94e72d94e7cb40806b0c456a74c3`. It is not
published in this repository. PR #21's two report versions must be treated as
`SUPERSEDED`; the private report hash is a traceable correction reference, not a
public archive location.

The private report was regenerated against main commit
`23595f69fbbfa904c9b1a1236a8a5061a43f21d1` using the current shared adapter.
Its SHA-256 is `8e00f711b7715368d8c1ce49a4d08334576e94e72d94e7cb40806b0c456a74c3`;
the canonical validator rendered byte-identical content. The publisher returned
`ARCHIVE_BLOCKED` with `github_request_made=false`, so this report was not sent to
GitHub. The source receipt records a three-day replay of 24 official NBA games
(539 played rows, 118 DNP, 531 VERIFIED_FP, 8 PARTIAL_FP due to TECH conflicts,
0 blocked rows and 0 fetch errors). The receipt applies the current ownership
snapshot only to matching Taipei game dates: the 10/26 ET slate (Taipei 10/27)
has six owner players, all VERIFIED_FP; 12 earlier rows matching the current
roster are excluded from historical ownership claims. One non-owner slate quality
gap remains on 10/26. Receipt SHA-256:
`3535580e0155cb2bbb6a46d46cfd557457f3d17dde1eb71742beee723ed9f959`; adapter
SHA-256: `e53f4e2943eaa1a9bde4ac73605446e8b53812220702b4a96b2b353e8dabd52e`.
Raw snapshots remain outside the public repository.

## Rights evidence reviewed

Fetched 2026-10-27 13:27 UTC (21:27 Asia/Taipei):

- [NBA.com Terms of Use](https://www.nba.com/termsofuse), HTTP 200, page states
  last updated 2026-07-13. Section 1 defines “Basketball Content” to include
  statistics and updated scores and restricts reproduction/republication absent
  written permission. Section 9, “NBA Statistics,” says use/display/publication
  must include prominent NBA.com attribution and may only be for legitimate news
  reporting or private, noncommercial purposes; it also says NBA Statistics may
  not be used in connection with any fantasy game or other commercial product or
  service. The project's personal Fantasy decision-support use intersects with
  that specific restriction; the personal-noncommercial wording does not
  unambiguously resolve it. Keep access/publication rights `UNVERIFIED` pending
  permission or a licensed source. The rendered page's whole-response hash
  changed between same-day reads, so no unstable HTML hash is treated as a
  stable terms-version fingerprint.
- [NBA Subscriber Agreement](https://www.nba.com/subscriberagreement), HTTP 200,
  page states last updated June 2023. Its content section limits use/viewing to
  personal, noncommercial use and restricts copying, distribution, publishing
  and circulation without express prior written consent. A League Pass
  subscription is not evidence of a programmatic statistics license or a public
  report republication grant.

No separate license for automated access to the NBA Live Data / Stats endpoints,
or for public republication of their outputs, was found in this review. This
audit distinguishes source responses, single-game statistical facts, custom FP
derived from those facts, and original commentary; it does not conclude that
these categories have identical legal status. Section 9's fantasy-game language
means this specific use remains unresolved even though the project is personal.
This is an operational rights gate, not a legal determination.

## Handling rule

1. Keep raw NBA responses and unapproved generated reports in the private cache.
2. Mark every dataset's access and publication grant separately; do not infer
   permission from HTTP 200, League Pass Premium, or an ESPN JSON endpoint.
3. Keep GitHub publication blocked unless written permission or a licensed
   provider contract covers automated access and the intended public output.
4. Preserve existing public reports for now, make the review state visible, and
   decide retention or removal only after the rights review resolves it.
5. Keep the corrected 2026-10-27 private report linked to PR #21 as a
   `SUPERSEDED_BY` reference without uploading its report body or raw data.
