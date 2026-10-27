# Player Scouting Fresh Agent A/B 驗收（未執行）

此流程**只屬球探 Skill**，不得沿用 2026-10-22 每日戰報功能的一次性 Fresh Agent 豁免。若不能取得兩個真正隔離、乾淨的 Agent runtime，輸出 `BLOCKED_FRESH_AGENT_RUNTIME` 而非 PASS。

## 真實案例與凍結原則
以 Owner 隊的 **Herbert Jones** 作真正研究樣本，另加：
- `Keon Ellis`：已確認 ADD／隊伍未知，不能被推薦為 FA。
- `Kentavious Caldwell-Pope`：已有較新 DROP，但當下 Yahoo waiver/FA 狀態未獲確認。
- 另一隊已持有球員（從固定 commit 的 rosters 選取；不得臨時改題）。
- 有 verified 當前 Yahoo FA 的候選若無證據則明確保持 UNKNOWN，不臆造成功案例。
記錄 exact main SHA、三個權威檔案 bytes/SHA-256 和球員身份、NBA/Yahoo/影片原始來源、檢索時間；兩組必須拿到**相同**的原始遊戲資料與資源限制。

## 隔離，尤其避免 control 偷讀 Skill
1. 控制組 A：獨立乾淨容器／全新 session，輸入是中性研究問題 + **相同內容的 league.json、rosters.json、ownership/current-state.json 和原始 NBA 資料**。不可掛載整個 repo；**不能**讓 A 讀取指向 Skill 的 `AGENT_CONTEXT.md`、`README.md`、`STATUS.md`、`.agents/`、`.claude/`、`scouting/`、PR、Issue、以前 Agent transcript 或 B 的任何輸出。A 不能透過 git/tool 搜索 repo 尋找 Skill。
2. 處理組 B：另一個乾淨的獨立 session，與 A 相同中性資料、工具、成本和任務；額外提供 `scouting/README.md`、兩個 Skill 入口之一、validator/template。
3. **比較嚴格度**：A/B 都須知道基本任務「籃球球探 + Owner Fantasy 聯盟比較」，不讓 B 拿到額外真實統計或更晚 Yahoo evidence。允許各自使用同樣限額的公開 research tool，但必須凍結資料截止並保存全部查詢。
4. **不可污染**：執行者不得向 A 發送 B 的 bug/guidance；兩組不得讀到彼此模型輸出。另請與 Writer 不同的 Reviewer 事後盲評；隱藏模型組別與產物檔名，解盲後再比較。
5. **原始紀錄**：為每組保存確切 prompt、可讀權限清單、輸入 SHA、完整 transcript、研究 URL/時間、所有工具呼叫、生成文章/JSON、成本/時間、失敗訊息、事後評分與可回放檔；禁止依敘述編造 Agent run、時間或 review。
6. **固定 rubric**：P0 hard gate 為完整當季 FP（缺欄不補零）、虛構來源 0、已持有/隊伍未知被當 FA 0、DROP 被當立即 FA 0、角色/影片事實有出處、結論不越權、差值可驗算；再比較合理 basketball insight、反證深度與 readability。B 必須全數通過硬 gate；A 是否通過如實記錄。通過靜態 CI 不代表 Fresh Agent PASS。

## 建議紀錄位置
`tests/fresh-agent/scouting/runs/<YYYY-MM-DD>-<run-id>/`，保存 `manifest.json`（IDs、hash、工具/隔離與時間）、`A-transcript.*`、`B-transcript.*`、`blind-review.md`、`scorecard.json`，以及原始可核對產物。若 GitHub 沒有隔離執行與保存原始產物能力，不應創建看似真的 runs；只回報 `BLOCKED_FRESH_AGENT_RUNTIME`。

目前狀態：`NOT_RUN`。此文件是 protocol，**不是** Fresh Agent 測試結果。
