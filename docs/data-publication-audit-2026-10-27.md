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
read from `main` at `d07c194e` and PR #21's public branch at
`ec5f896987b1c17fbb09ac433586bef6a89e9a22`.

| Location | Content found | SHA-256 | Audit state |
|---|---|---|---|
| `main:seasons/2026-27/report/daily/2026-10-24.provisional.md` | Player/game stats, custom FP, commentary, source links | `1335f05e0c738e72fd238afa9a3b397079dd5df34a0c221b978cea18b6bb4b8f` | Historical public; review required |
| `main:seasons/2026-27/report/daily/2026-10-25.provisional.md` | Player/game stats, custom FP, commentary, source links | `637c4682ccebbf70fac782e6428edd2e33ddec262b365aa10ceee61b232589bd` | Historical public; review required |
| `main:seasons/2026-27/report/daily/2026-10-26.provisional.md` | Player/game stats, custom FP, commentary, source links | `b5d826ac5122b74b9614cc41f92dbcf2a012a8a86bc5cf949b253b6373b723ad` | Historical public; review required |
| `PR #21:.../2026-10-27.provisional.md` | Player/game stats, custom FP, commentary, source links | `04d6c5f1c348d232118ef42a21dbb5570949ca4e7a20196ec6007d6faf781794` | Public draft; superseded |
| `PR #21:.../2026-10-27.v2.provisional.md` | Player/game stats, custom FP, commentary, source links | `572d0fd3375315163dd051e28432948d513b201eb25ebe59cdd9a2e2711269b5` | Public draft; superseded |

The inspected Markdown files contain report-level values and citations, but no
complete raw NBA API response payload was found embedded in those files. Raw
response snapshots for the new adapter's private E2E are stored outside this
public repository. A source URL, a hash, or an official-looking endpoint is
provenance evidence; none of them is a redistribution grant.

The corrected private 2026-10-27 report is identified by SHA-256
`91c34382a48ebb6db172983903597c53ca869eb3f1eb0455e659ed0573ee90ae`. It is not
published in this repository. PR #21's two report versions must be treated as
`SUPERSEDED`; the private report hash is a traceable correction reference, not a
public archive location.

## Rights evidence reviewed

Fetched 2026-10-27 13:27 UTC (21:27 Asia/Taipei):

- [NBA.com Terms of Use](https://www.nba.com/termsofuse), HTTP 200, page states
  last updated 2026-07-13. Retrieved-response SHA-256:
  `bcf618ed7a46177b9d9036ec6f173d54236b794d60f0a3ea4f5483ff32ff309b`. Its
  definition of “Basketball Content” includes statistics and updated scores and
  its use section restricts reproduction, republication and related reuse absent
  written permission. It also describes only limited personal, noncommercial
  downloading where a download function is provided.
- [NBA Subscriber Agreement](https://www.nba.com/subscriberagreement), HTTP 200,
  page states last updated June 2023. Retrieved-response SHA-256:
  `11c9495025bcfad9cbdd5dac19c1e33b40ccc7a74427cf8f90418f14857a605a`. Its
  content section limits use/viewing to personal, noncommercial use and
  restricts copying, distribution, publishing and circulation without express
  prior written consent.

These are the general website and subscriber terms reviewed for this audit. No
separate license for automated access to the NBA Live Data / Stats endpoints, or
for public republication of their outputs, was found in this review. The Terms of
Use do not resolve the legal status of a standalone factual statistic, an
independently calculated FP value, or original commentary in every jurisdiction.
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
