# 球員球探報告模板（reports/<player-slug>/YYYY-MM-DD.vN.md）

> 同版本必須保存 `YYYY-MM-DD.vN.json` 原始資料 sidecar（schema 及規則以 `scripts/validate_scouting_report.py` 為準）；Markdown 不能代替結構化來源。

> 所有 `[待填]` 需填實際資料或 `N/A/UNKNOWN`，不得擅填零。嚴格區分球探觀察、原始統計、推論、模型預測。

## 0. 檔案與決策摘要
- `season`：[待填]｜`player_id/name/aliases`：[待填]
- `report_date_taipei`：[待填]｜`data_cutoff_taipei`：[待填]｜`researcher`：[待填]
- `content_status`：BLOCKED / PROVISIONAL / VALIDATED
- `review_status`：NOT_RUN / PASS / FAIL
- `archive_status`：NOT_WRITTEN / PR_PENDING / ARCHIVE_BLOCKED / ARCHIVED（需獨立 GitHub 存檔 receipt；不可在此自證 ARCHIVED）
- `roster_commit_sha`、`league_blob_sha`、`rosters_blob_sha`、`ownership_blob_sha`：[待填]
- `roster_as_of`：[待填]｜`NBA_source_time`：[待填]｜`Yahoo_availability_checked_at`：[待填或 UNKNOWN]
- 一句話結論：[待填]｜建議：ADD / HOLD / DROP / TRADE / WATCH｜信心：高 / 中 / 低
- 給 Owner 的具體行動、期限、另一人需 DROP/交易的代價：[待填]

## 1. 身分、體能與 NBA 球隊脈絡
- 球隊、年齡、身高/臂展（無可信來源填未知）、慣用手、出賽位置：[待填]
- 目前先發/第幾輪替、上場時間趨勢、球隊戰術定位：[待填]
- 競爭者、傷病與可核對復出資訊、交易傳聞 vs 已確認事實：[待填]

## 2. Basketball scouting（觀察不要和統計混寫）
| 面向 | 已看到的優勢 | 缺點/反例 | 證據 |
|---|---|---|---|
| 進攻：接球投射/出手選擇 | [待填] | [待填] | [比賽/時間戳] |
| 進攻：自主創造/切入終結 | [待填] | [待填] | [比賽/時間戳] |
| 進攻：擋拆/傳球/失誤 | [待填] | [待填] | [比賽/時間戳] |
| 防守：單防/協防/換防 | [待填] | [待填] | [比賽/時間戳] |
| 防守：抄截/護框/籃板卡位 | [待填] | [待填] | [比賽/時間戳] |
| 無球跑動/犯規/紀律/球商 | [待填] | [待填] | [比賽/時間戳] |

- 影片樣本：至少列對手、比賽日期、完整觀看範圍與時間戳；不足則標 `PROVISIONAL`。
- Player archetype、可轉移技能（相同位置不同體系是否有效）、合理上限/下限：[待填]
- 不把官方病史、未證實傳聞、單場 highlights 或個人感覺寫成客觀事實。

## 3. NBA 近況與數據（樣本數必填）
| 指標 | 近 5 場 | 近 10 場 | 近 20 場 | 本賽季 |
|---|---:|---:|---:|---:|
| 實際場數 GP | [N] | [N] | [N] | [N] |
| MIN | | | | |
| PTS / 3PTM | | | | |
| OREB / DREB | | | | |
| AST / STL / BLK | | | | |
| TO / FTA / PF | | | | |
| USG% / TS% | | | | |
| DD / TD 頻率 | | | | |
| 依本 repo 當季權重重新計算的 FP/G（完整才可填） | | | | |

- 上場/未上場、因傷缺賽是否納入 denominator、對手強弱、垃圾時間、樣本小的偏誤：[待填]
- 數據來源 URL / 原始 period / 資料擷取時間：[待填]

## 4. Fantasy scoring 與預測（必須讀當季 league.json）
- 完整計分項：`PTS, 3PTM, OREB, DREB, AST, STL, BLK, TO, FTA, PF, TECH, EJCT, FF, DD, TD`。
- 各項 raw input、對應權重、貢獻值、總分及缺漏欄位：[待填]
- **禁止**把總 REB 當 OREB+DREB、把 FTM 當 FTA，或缺少 TECH/EJCT/FF 就當 0；DD/TD 須依 league.json 註記計入。
- 模型假設：預測 MPG、usage/每分鐘率、先發機率、預期可出賽場數、主客場/背靠背相關證據：[待填]

| 情境 | 上場時間與角色假設 | 預測 FP/G | 預測每週 FP | 機率/信心與假設 |
|---|---|---:|---:|---|
| 保守 | [待填] | [或 N/A] | [或 N/A] | [待填] |
| 基準 | [待填] | [或 N/A] | [或 N/A] | [待填] |
| 樂觀 | [待填] | [或 N/A] | [或 N/A] | [待填] |

- 預測不等於事實；若依據不足，保留空值與理由，不製造精確小數點。

## 5. 本聯盟歸屬、可取得性與替換對照
- 查證來源：本季 `rosters.json` 的 16 隊 `players` + `additional_owned_players`、`ownership/current-state.json`：[待填]
- 身分：OWNER_ROSTER / OTHER_TEAM_ROSTER（team_id）/ OWNED_TEAM_UNKNOWN / RELEASED_AVAILABILITY_UNVERIFIED / CONFIRMED_FA / CONFIRMED_WAIVER / UNKNOWN：[待填]
- 若稱 `CONFIRMED_FA` 或 `CONFIRMED_WAIVER`，必須提供 Yahoo 當前證據與時間；沒有就不能直接推薦 ADD。
- 比較 Owner 可能被替換球員：[待填]；短期及長期 baseline FP/G、預計出賽、差值與 roster slot/IL 限制：[待填]
- 替代者 A/B/C（最多三個；每人皆需歸屬與 evidence）：[待填]
- 真正可執行的是立即 ADD、等 waiver、提出交易條件、持續 WATCH 還是 HOLD？[待填]

## 6. 風險、反證、追蹤觸發與最終決策
- 下行風險（傷病、教練換輪替、犯規、角色不穩、真實上場時間）：[待填]
- 看多/看空兩面的強證據、何種反證會改變結論：[待填]
- 重新觀察觸發：連續 N 場上場時間、先發改變、隊友復出、有效 Yahoo ownership/FA 更新：[待填]
- 決策：ADD / HOLD / DROP / TRADE / WATCH；**為什麼是此刻、換掉誰、成本與失敗退出條件**：[待填]

## 7. Provenance / QA / 版本
| 主張/資料欄位 | 來源 URL / 影片時間戳 | 觀測時間 | Fact / Observation / Inference / Projection |
|---|---|---|---|
| [待填] | [待填] | [待填] | [待填] |

- missing data / unsupported claim 清單：[待填]
- ownership gate / full custom FP / film / comparison / no fabricated FA gate：[PASS/PROVISIONAL/BLOCKED + 佐證]
- 獨立 review（Reviewer 身分與時間，不可虛構）：[待填或 NOT_RUN]
- 報告前版路徑及本版差異：[首次 v1 填 N/A]
- GitHub branch/PR/commit/main readback： [待填或 NOT_RUN；報告內容與歸檔狀態分開]
- JSON sidecar：每場完整 raw stats、由 canonical JSON 產生的 stats_sha256、原始抓取回應 raw_source_sha256、league 權重、source_url/擷取時間、roster/ownership snapshot blob SHA、影片正反案例、球員 NBA/Yahoo ID、三情境及獨立 Reviewer 證據；缺欄不能以 0 填入。
- 外部來源的 URL 是否真實存在、是否實際支持報告主張，必須由獨立 Reviewer 逐筆核對；離線 validator 不會上網查證。
