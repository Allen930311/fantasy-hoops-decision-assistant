# Yahoo Fantasy 交易歸屬與自由球員排除 SOP（2026–27）

## 目的與資料權威

此 SOP 依照 Owner 於 2026-10-25 確認的規則，從 Yahoo Fantasy 聊天室 ADD／DROP 截圖更新球員歸屬；**能確認隊伍就更新該隊，無法確認隊伍才放入未歸屬但非自由球員名單**。不以不穩定的隊伍暱稱取代 `team_id`。

輸入：當季 `rosters.json`、既有 `ownership/current-state.json`、前次具日期的證據與新 Yahoo 截圖。經驗證的即時 Yahoo ownership 是最終權威；在其接線完成前，以較新的已完成交易證據修正 repo snapshot；未證實的意向不得寫入。每筆保留來源、日期、ADD/DROP、配對方法和不確定性。

## 獨立可重跑的判定規則（順序不可顛倒）

1. **先去重與排序。** 同一交易在多張重疊截圖只算一次。截圖的「今天／昨天」依截圖取得日換成絕對日期；僅把可見的時間當作介面顯示時間，不虛構精確交易時間。以後取得的明確證據優先於舊紀錄。
2. **能確認的交易要歸隊。** 若 Yahoo 可驗證的穩定隊伍 ID 已知，直接映射；否則可用同批 DROP 的球員，從交易發生前的 16 隊名冊找到**唯一持有隊伍**，且不存在更新的矛盾轉隊證據，將這批交易歸到該隊 `team_id`。同一則／同批畫面中清楚出現的 ADD 也跟著歸隊；沒有確切相同交易脈絡就不可擴張推論。
3. **隊名不是永久 ID。** Yahoo 球隊顯示名稱可以改；同一畫面名稱可用來連結同批事件，**不可**單憑當天暱稱永久配對 repo `team_XX`，更不可用暱稱相似度、假設隊主或玩家實力猜隊伍。
4. **ADD-only 仍可能是有效持有。** 聯盟允許 IL；沒有 DROP 並不代表沒有 ADD，也不能推斷另一名球員被釋出。若同隊已經有 13 名基準球員，額外確認的 ADD 記在該隊 `additional_owned_players`，**格位未知**；這個欄位僅代表該隊確實持有，不代表該球員一定在 IL 或一定是第 14 位活躍名額。絕不可為了湊 13 人自行刪除他人。
5. **確定 ADD 但隊伍不明。** 加進 `ownership/current-state.json.unassigned_confirmed_owned_players`、`team_id=null`，從自由球員候選中排除；不修改 16 隊任一名冊。若同一未知隊同時有 ADD/DROP，也只能記錄該事件，不能冒稱已知道 repo 隊號。
6. **DROP 不等於即刻 FREE AGENT。** 確認釋出的球員應從已知歸屬/舊 ADD-only 排除移除，寫入 `released_availability_unverified`。必須再核對 Yahoo 即時 Waiver／FA 身分，才能建議撿入；不能因為截圖寫 DROP 就認定可直接撿。
7. **保留歷史，不做永久封鎖。** 日期型 `confirmed-add-fa-exclusions-YYYY-MM-DD.json` 是當時歷史證據；`current-state.json` 是目前有效覆蓋層，會以較新 DROP 解除舊「持有」判定。不要把所有歷史 ADD 無條件聯集成永久非 FA 名單。正式 Yahoo ownership 對帳後依最新真值更新它。
8. **實際讀取與衝突處理。** 目前 `owned = 各隊 players ∪ 各隊 additional_owned_players ∪ current-state.unassigned_confirmed_owned_players`；`released_availability_unverified` 是未知可撿狀態，不加入 owned，也不視為已確認 FA。任何跨集合重複或已釋出者仍在 owned，都必須 FAIL 並回頭查證。最後只在可重現的驗證通過後更新 main。

## 2026-10-24～25 截圖實例

- **唯一可歸隊：** 宏洋的顯示隊名在同批消息 DROP **Brayden Burries**；此人交易前僅存在 `team_10`，故本批 ADD **Mario Hezonja**、**Aaron Wiggins** 皆屬 `team_10`。以 Mario 取代基準 13 人名單中的 Brayden；Aaron 暫置 `additional_owned_players`，只是資料存放方式，**無法確認真實 IL 格位**。
- **無法可靠歸隊：** Tristan da Silva、Keon Ellis、Jock Landale、Sam Merrill、De'Anthony Melton 均列為已確認持有、隊伍未明；不因暱稱或其先後 ADD 而指定 `team_id`。
- **後續 DROP 解除歷史持有：** Kentavious Caldwell-Pope 在 2026-10-25 的截圖被 DROP，覆蓋 2026-10-24 舊 ADD 證據；Brayden 也已由 team_10 DROP。兩人都進「可撿狀態未驗證」名單，不直接判 FA。
- 目前 `team_10` 為 13 位基準持有 + 1 位格位未知的額外持有；全聯盟 208 個基準名額 + 1 位額外已確認歸隊；另有未歸屬已確認 ADD，不能列入自由市場。

## Output / 完成條件 / 失敗狀態

- **Output：** `rosters.json` 更新已可確認隊號的持有；`ownership/current-state.json` 更新未歸屬 ADD、已確認 DROP 與證據；`transaction_notes` 留下可稽核鏈；不要重寫歷史日期檔。
- **PASS：** 16 隊各 13 位基準名單、額外持有欄位合法、姓名跨隊唯一、已確認 ADD 不會被推薦為 FA、DROP 不會被誤認為可立刻撿、來源和邏輯可讀回。
- **FAIL/BLOCKED：** 出現互相矛盾的團隊歸屬、截圖缺必要 DROP/ADD 身分、重複姓名、無法取得 repo 或讀回不一致。保留未知狀態並揭露缺口，不編造隊伍或交易。
- **Side effects：** 只更動 Fantasy repo 的版本化資料與 SOP；不操作 Yahoo ADD／DROP、不改使用者自己的球員、更不靠遠端工具清理本機資料。

此 SOP 可單獨執行與驗證；排程只是讀取消費者，不可繞過本 SOP 自行覆寫歸屬。
