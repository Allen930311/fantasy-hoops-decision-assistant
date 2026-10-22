# Daily Fantasy archive — Fresh Agent acceptance (NOT YET EXECUTED)

## Purpose
The offline unit/CLI test suite cannot substitute for an independent **Fresh Agent** trial. Do not label Fresh Agent PASS until two separate, clean agent sessions and their untouched raw transcripts are attached here.

## Fixed case inputs
1. Read main `seasons/2026-27/rosters.json` and `league.json` using an explicitly pinned GitHub commit and record both blob SHAs; report ownership using that snapshot, not an old message.
2. Historical real game regression: `tests/fixtures/historical-nba-finals-2025-06-23-partial.json`. The mini roster is **synthetic and test-only**; player box scores for Shai Gilgeous-Alexander and Jalen Williams are from the 2025 NBA Finals G7. Verify original sources at https://www.nba.com/game/ind-vs-okc-0042400407/box-score and https://www.basketball-reference.com/boxscores/202506220OKC.html . The deliberately unasserted TECH/EJCT/FF fields MUST cause PROVISIONAL.
3. Season-real example: 2026-10-22 Taipei report date, Lakers vs Warriors 2026-10-21 US game, and the owner's rostered Walker Kessler. Freeze official score and per-player source before agents start. If an entire daily schedule is not frozen, this is a **player-level test only**, not a full daily-report PASS.
4. Adversarial test conditions: OREB != 0 and DREB separately; DD and TD cumulative scoring; confirmed but unsynced completed ADD with proof; unconfirmed ADD intent; DNP; missing discipline fields; other-team roster mistaken for FA; rerun identical input; revised provisional report; mismatched Taipei game-date; completed schedule game missing from box-score feed; accent-name alias (Alperen Sengun / Alperen Şengün).

## Trial
- **A / control:** brand-new clean agent with identical sources and report request but no repository SOP or archive writer guidance.
- **B / treatment:** another brand-new clean agent with identical sources, requirements, tools/budget, plus `seasons/2026-27/report/daily/README.md` and the archive validator instructions.
- Both must independently generate a report and structured audit evidence. Sessions may not read each other's outputs, this PR discussion, or prior transcripts before completion.
- Save untouched transcripts, exact prompts, run/source timestamps, commits, input bytes/SHA-256, output SHA-256, check results and errors under a new run-specific `tests/fresh-agent/runs/<date>-<runid>/` directory. Redact secrets only; never invent timestamps or results.
- In a separate audit pass, score each agent using the same rubric: owner played coverage (100% required), FP field and value accuracy (100%), no rostered FA (0 errors), explicit provisional vs validated, mandatory daily battle report when games end, no fabricated transaction, correct source SHA, immutable archive rerun and branch/main state distinction.

## Gates
- Unit/CLI CI PASS alone = `IMPLEMENTATION_TESTS_PASS`, not Fresh Agent PASS.
- Treatment agent must pass **all hard gates**. Control is a baseline comparison; record it accurately even if it also passes.
- Manual scoring must be supported by independent evidence. The story's prose quality is assessed separately from numeric/ownership safety gates.
- Only after complete trial + independent review + PR merge/main readback may the scheduled 15:00 workflow be updated to invoke the archive writer. Schedule remains unchanged until then.
- If an independent agent runtime is unavailable, record `BLOCKED_FRESH_AGENT_RUNTIME`; do not substitute ordinary unit tests or imply completion.
