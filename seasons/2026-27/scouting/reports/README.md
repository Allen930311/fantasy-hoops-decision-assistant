# 球探成果保存與不可變版本

一份球探報告由 `reports/<player-slug>/YYYY-MM-DD.vN.md`（完整繁體中文文章）加同版本 `YYYY-MM-DD.vN.json`（原始資料/provenance/scoring sidecar）組成；不能只寫一份空 Markdown 就標完成。v1 寫入後不得靜默覆寫，修正請新增 v2，保留修正理由。

**三個維度分開**：`content_status` = BLOCKED / PROVISIONAL / VALIDATED；`review_status` = NOT_RUN / PASS / FAIL；`archive_status` = NOT_WRITTEN / PR_PENDING / ARCHIVE_BLOCKED / ARCHIVED。從 VALIDATED + Reviewer PASS 衍生 REVIEW_READY。PROVISIONAL 報告也可以 ARCHIVED，僅表示已保存。

**歸檔循環不可自證**：JSON 是不可變快照，不得自行填 ARCHIVED。需要從 GitHub PR branch 讀回才可稱 PR_PENDING；PR 合併後再從 main 讀回並比對檔案雜湊，才可另外追加不可變的 `scouting/archive-receipts/<date>-<report-id>.json`，記錄 `report_path`、`sha256`、`pr_url`、`merge_commit`、`main_readback_time`、`main_blob_sha`、`archive_status=ARCHIVED`。事後收據不得回頭覆寫原報告。現階段**沒有** publisher / receipt writer，不能只因 PR 建立就宣稱 ARCHIVED。

資料來源 URL 的真實性與正確性，必須由獨立 Reviewer 查證；離線 Validator 只驗格式、數值與當前 checkout 的檔案 blob，而非即時網路存在性或實際 Yahoo FA 狀態。
