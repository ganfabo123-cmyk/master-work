# APP_DESIGN

```yaml
document_version: 1
design_status: APPROVED
review_status: PASS
app_id: jubensha_haishanxianguan
app_name: 海山仙馆之寻
execution_stage: stage_one_synchronous
```

## 1. Product goal

依据《海山仙馆之寻》的角色剧本、规则书和线索材料，让六名由模型控制的角色在各自只掌握授权私密材料的前提下，完成两轮搜证与公开讨论、最终投票、真相复盘和任务计分。游戏的核心问题是找出最后调包道光皇帝画像的人，并判断画像最终所在位置。

## 2. Source index

| Source ID | Material | Location | Purpose |
|---|---|---|---|
| SRC-00 | 规则书 | `data/jubensha/00_海山仙馆之寻规则书.md` 第 4-7 页 | 角色选择、两轮搜证、讨论、投票、复盘与计分顺序 |
| SRC-01 | 潘仕成剧本 | `data/jubensha/01_潘仕成剧本.md` 第 4-11 页 | 潘仕成私密背景、时间线与任务 |
| SRC-02 | 伊凡剧本 | `data/jubensha/02_伊凡剧本.md` 第 4-14 页 | 伊凡私密背景、时间线与任务 |
| SRC-03 | 李夫人剧本 | `data/jubensha/03_李夫人剧本.md` 第 4-9 页 | 李夫人私密背景、时间线与任务 |
| SRC-04 | 侍女剧本 | `data/jubensha/04_侍女剧本.md` 第 4-10 页 | 侍女私密背景、时间线与任务 |
| SRC-05 | 管家剧本 | `data/jubensha/05_管家剧本.md` 第 4-10 页 | 管家私密背景、时间线与任务 |
| SRC-06 | 何绍基剧本 | `data/jubensha/06_何绍基剧本.md` 第 4-10 页 | 何绍基私密背景、时间线与任务 |
| SRC-07 | 六个角色人物卡 | `data/jubensha/07_6个角色人物卡.md` 第 1-6 页 | 公开角色身份简介 |
| SRC-08 | 十二个人物线索 | `data/jubensha/08_12个人物线索.md` 第 1-6 页 | 第一轮人物线索内容及归属 |
| SRC-09 | 十四个场景线索 | `data/jubensha/09_14个场景线索.md` 第 1-8 页 | 第二轮场景线索内容及掉落位置 |
| SRC-10 | 复盘剧本 | `data/jubensha/10_复盘剧本.md` 第 3-6 页 | 真凶、最终藏画地点和完整移动时间线 |

## 3. Confirmed domain facts

- `RULE-01`：固定参与角色为潘仕成、伊凡、李夫人、侍女、管家、何绍基，共六人。
- `RULE-02`：每名角色只可直接获知自己的完整角色剧本；人物卡中的简短身份介绍可以公开。
- `RULE-03`：流程依次包含角色阅读与自我介绍、第一轮人物线索搜证与自由讨论、第二轮场景线索搜证与自由讨论、最终投票、真相复盘与计分。
- `RULE-04`：搜得线索后，持有者可选择公开或不公开；未公开线索不得被其他角色看到。
- `RULE-05`：每名角色最终投一票，票的目标是六名角色之一；材料没有给出平票处理方式。
- `RULE-06`：最后调包画像的人是侍女；画像最终藏于贮韵楼旁、用于水路往返的小舟上。
- `RULE-07`：主线任务围绕判断自己是否为真凶、非真凶时找出真凶；各角色另有隐瞒事实、判断动机或找出画像位置等支线任务。
- `RULE-08`：真相复盘必须在最终投票完成后才公开，不能提前进入角色可见信息或讨论内容。
- `RULE-09`：材料中的人物剧本、线索和复盘均来自 PDF 解析，存在 OCR 缺字与错字；原文引用应保留来源，不能据乱码创造新规则。
- `RULE-10`：固定角色顺序为潘仕成、伊凡、李夫人、侍女、管家、何绍基；人物线索每人 2 条，场景线索依次为 3、3、2、2、2、2 条。
- `RULE-11`：角色任务原权重保持为：潘仕成、伊凡、管家 6+2+2；何绍基 8+2；李夫人 6+1+1+2；侍女 8+2。可机械验证的真凶判断、画像最终位置和标准动机计分；隐瞒、协助隐瞒、逃脱问责标记 `NOT_SCORED`。胜者按“已得可评分分数 / 可评分总分”的得分率确定，同率并列。

## 4. Participants

| Agent ID | Name | Responsibility | LLM controlled | Private materials |
|---|---|---|---|---|
| AGENT-PAN | 潘仕成 | 以园主身份介绍、讨论、决定线索公开策略并投票 | yes | SRC-01 完整正文、自己的任务、自己持有的未公开线索 |
| AGENT-IVAN | 伊凡 | 以法国公使随员身份介绍、讨论、决定线索公开策略并投票 | yes | SRC-02 完整正文、自己的任务、自己持有的未公开线索 |
| AGENT-LI | 李夫人 | 以园主正妻身份介绍、讨论、决定线索公开策略并投票 | yes | SRC-03 完整正文、自己的任务、自己持有的未公开线索 |
| AGENT-MAID | 侍女 | 以贴身侍女身份介绍、讨论、决定线索公开策略并投票 | yes | SRC-04 完整正文、自己的任务、自己持有的未公开线索 |
| AGENT-BUTLER | 管家 | 以总管家身份介绍、讨论、决定线索公开策略并投票 | yes | SRC-05 完整正文、自己的任务、自己持有的未公开线索 |
| AGENT-HE | 何绍基 | 以诗人书画家身份介绍、讨论、决定线索公开策略并投票 | yes | SRC-06 完整正文、自己的任务、自己持有的未公开线索 |

## 5. Domain information and visibility

| Info ID | Content or source reference | Visible to | Becomes visible when |
|---|---|---|---|
| INFO-PUBLIC-ROLES | SRC-07 六张人物卡 | 全部角色 | 游戏开始 |
| INFO-PAN-SCRIPT | SRC-01 | AGENT-PAN | 游戏开始 |
| INFO-IVAN-SCRIPT | SRC-02 | AGENT-IVAN | 游戏开始 |
| INFO-LI-SCRIPT | SRC-03 | AGENT-LI | 游戏开始 |
| INFO-MAID-SCRIPT | SRC-04 | AGENT-MAID | 游戏开始 |
| INFO-BUTLER-SCRIPT | SRC-05 | AGENT-BUTLER | 游戏开始 |
| INFO-HE-SCRIPT | SRC-06 | AGENT-HE | 游戏开始 |
| INFO-PERSON-CLUES | SRC-08 中的十二条人物线索 | 获得该线索的角色；公开后为全部角色 | 第一轮搜证分配后；公开时间由持有者决定 |
| INFO-SCENE-CLUES | SRC-09 中的十四条场景线索 | 获得该线索的角色；公开后为全部角色 | 第二轮搜证分配后；公开时间由持有者决定 |
| INFO-PUBLIC-SPEECH | 自我介绍及两轮讨论中的公开发言 | 全部角色 | 发言提交后 |
| INFO-VOTES | 每名角色的最终投票 | 提交后仅本人；全部收齐后为全部角色 | 六票全部收齐后一次性公开 |
| INFO-TRUTH | SRC-10 中真凶、动机、画像移动与最终地点 | 全部角色 | 所有最终投票收齐后 |
| INFO-SCORES | 每名角色任务得分及胜者 | 全部角色 | 真相公开并完成计分后 |

## 6. Domain workflow

| Phase ID | Domain purpose | Participants | User-visible completion |
|---|---|---|---|
| PHASE-INTRO | 各角色阅读授权材料并作简短自我介绍 | 六名角色 | 六份公开自我介绍均已发布 |
| PHASE-PERSON-SEARCH | 分配第一轮人物线索，持有者决定公开或保密 | 六名角色 | 每名角色完成本轮线索处理 |
| PHASE-PERSON-DISCUSS | 根据角色材料与已公开人物线索进行第一轮讨论 | 六名角色 | 按 `Q-02` 的确定性讨论规则完成 |
| PHASE-SCENE-SEARCH | 分配第二轮场景线索，持有者决定公开或保密 | 六名角色 | 每名角色完成本轮线索处理 |
| PHASE-SCENE-DISCUSS | 根据此前材料与已公开场景线索进行第二轮讨论 | 六名角色 | 按 `Q-02` 的确定性讨论规则完成 |
| PHASE-VOTE | 每名角色判断最后调包者并提交一票 | 六名角色 | 六票全部收齐且完成平票处理 |
| PHASE-REVEAL | 公开真相、画像移动过程和最终位置 | 自动流程 | 完整复盘进入公开结果 |
| PHASE-SCORE | 按任务答案计算各角色得分并确定胜者 | 自动流程 | 每名角色分数、依据及胜者公开，游戏终止 |

### Domain actions

| Action ID | Actor | Intent | Parameters | Domain preconditions | Domain effect |
|---|---|---|---|---|---|
| ACTION-INTRODUCE | 六名角色 | 作不泄露私密材料的公开自我介绍 | `content` | PHASE-INTRO 且本人尚未介绍 | 发布公开介绍并记录完成 |
| ACTION-HANDLE-CLUE | 六名角色 | 领取本轮分配线索并决定是否公开 | `clue_id`, `reveal`, `public_summary` | 对应搜证阶段、线索属于本人且尚未处理 | 将线索记入本人私有信息；选择公开时发布完整可审计线索内容 |
| ACTION-DISCUSS | 六名角色 | 在当前讨论轮公开陈述、质疑或回应 | `content` | 对应讨论阶段且轮到本人 | 发布完整公开发言并记录本轮发言完成 |
| ACTION-VOTE | 六名角色 | 投票认定最后调包者并提交任务答案 | `suspect_id`, `image_location`, `motive`, `task_claims` | PHASE-VOTE 且本人尚未投票 | 私下/公开记录投票及任务答案，待全部收齐后结算 |

### Rules and edge cases

| Rule ID | Condition | Required behavior | Source or user decision |
|---|---|---|---|
| RULE-12 | 角色尝试读取他人剧本或未公开线索 | 拒绝访问且不得泄露内容 | RULE-02, RULE-04 |
| RULE-13 | 角色提交不属于当前阶段的行为 | 拒绝并给出当前允许行为 | 由固定流程推导 |
| RULE-14 | 同一角色重复提交已完成行为 | 拒绝重复提交，不产生第二次公开内容或计分影响 | 确定性与恢复要求 |
| RULE-15 | 搜证线索分配 | 按 RULE-10 固定分配，不使用随机数 | Q-01 用户确认 |
| RULE-16 | 最终投票平票 | 判定未成功找出唯一真凶，仍继续复盘与个人计分 | Q-03 用户确认 |
| RULE-17 | 投票尚未收齐 | 已提交投票仅本人可见；全部收齐后一次公开 | Q-04 用户确认 |
| RULE-18 | 任务计分 | 真凶标准答案为侍女；位置标准答案为贮韵楼旁水路小舟；动机标准答案枚举为 `FAMILY_MEDICAL_COST_AND_FREEDOM`；其余语义任务 `NOT_SCORED`；按得分率确定胜者 | Q-05、Q-07、Q-08 用户确认 |

## 7. Architecture blueprint

### State schema

| Field | Type | Initial value/source | Updated by transition | Persisted reason |
|---|---|---|---|---|
| `task_id` | string | 启动任务 | 不更新 | 公共协议与恢复标识 |
| `session_id` | string | 会话创建 | 不更新 | 会话、ROOM、Trace 与存储关联 |
| `phase` | enum | `PHASE-INTRO` | 每个阶段转换 | 恢复时确定下一步 |
| `role_order` | tuple[Agent ID] | RULE-10 固定顺序 | 不更新 | 确定发言、分配与结算顺序 |
| `script_refs` | map[Agent ID, Info ID] | INFO-*-SCRIPT 引用 | 不更新 | 重建私有观察而不复制大段原文 |
| `person_clue_assignments` | map[Agent ID, tuple[clue ID]] | 按 SRC-08 原顺序每人 2 条 | 不更新 | 私密归属和确定性恢复 |
| `scene_clue_assignments` | map[Agent ID, tuple[clue ID]] | 按 SRC-09 原顺序分配 3、3、2、2、2、2 | 不更新 | 私密归属和确定性恢复 |
| `handled_clues` | map[Agent ID, set[clue ID]] | 空 | TRANS-SEARCH-* | 判断搜证收集完成并防重复 |
| `revealed_clues` | set[clue ID] | 空 | TRANS-SEARCH-* | 构造公开观察与 ROOM 内容 |
| `introductions` | map[Agent ID, string] | 空 | TRANS-INTRO | 保存完整公开自我介绍 |
| `discussion_rounds` | map[Phase ID, map[Agent ID, string]] | 两轮空映射 | TRANS-DISCUSS-* | 保存完整公开讨论与恢复进度 |
| `votes` | map[Agent ID, vote payload] | 空 | TRANS-VOTE | 保存保密投票和任务答案 |
| `vote_tally` | map[Agent ID, integer] | 空 | TRANS-VOTE-COMPLETE | 公开票数与平票判断 |
| `collective_result` | object/null | null | TRANS-VOTE-COMPLETE | 保存是否唯一找出真凶及理由 |
| `truth_revealed` | bool | false | TRANS-REVEAL | 防止恢复时重复公开真相 |
| `scores` | map[Agent ID, score breakdown] | 空 | TRANS-SCORE | 保存逐任务状态（CORRECT/INCORRECT/NOT_SCORED）、分值、可评分总分和得分率 |
| `winner_ids` | tuple[Agent ID] | 空 | TRANS-SCORE | 支持最高分并列胜者 |
| `consumed_action_ids` | set[string] | 空 | 每个角色行动转换 | 幂等拒绝重复 Action |
| `emitted_event_ids` | set[string] | 空 | 事件投递成功边界 | 恢复时避免重复业务投影 |
| `terminal_result` | object/null | null | TRANS-SCORE | 终局摘要与 `is_terminal` 判断 |

### Phase contracts

| Phase ID | Selected Agent IDs | Observation view IDs | Available Action IDs | Collection condition | Resolution | Transition | Next phase |
|---|---|---|---|---|---|---|---|
| PHASE-INTRO | 固定顺序中尚未介绍的下一名角色 | VIEW-ROLE | ACTION-INTRODUCE | 当前选中角色提交 1 个合法介绍；六人均完成时阶段完成 | 保留完整介绍正文 | TRANS-INTRO | 未完成则 PHASE-INTRO；完成则 PHASE-PERSON-SEARCH |
| PHASE-PERSON-SEARCH | 固定顺序中尚未处理全部人物线索的下一名角色 | VIEW-PERSON-SEARCH | ACTION-HANDLE-CLUE | 当前角色一次处理本人所有未处理人物线索；六人均完成时阶段完成 | 校验归属，逐条登记公开选择 | TRANS-SEARCH-PERSON | 未完成则本阶段；完成则 PHASE-PERSON-DISCUSS |
| PHASE-PERSON-DISCUSS | 固定顺序中本轮尚未发言的下一名角色 | VIEW-DISCUSS-1 | ACTION-DISCUSS | 当前角色提交 1 个合法发言；六人均完成时阶段完成 | 保留完整发言正文 | TRANS-DISCUSS-1 | 未完成则本阶段；完成则 PHASE-SCENE-SEARCH |
| PHASE-SCENE-SEARCH | 固定顺序中尚未处理全部场景线索的下一名角色 | VIEW-SCENE-SEARCH | ACTION-HANDLE-CLUE | 当前角色一次处理本人所有未处理场景线索；六人均完成时阶段完成 | 校验归属，逐条登记公开选择 | TRANS-SEARCH-SCENE | 未完成则本阶段；完成则 PHASE-SCENE-DISCUSS |
| PHASE-SCENE-DISCUSS | 固定顺序中本轮尚未发言的下一名角色 | VIEW-DISCUSS-2 | ACTION-DISCUSS | 当前角色提交 1 个合法发言；六人均完成时阶段完成 | 保留完整发言正文 | TRANS-DISCUSS-2 | 未完成则本阶段；完成则 PHASE-VOTE |
| PHASE-VOTE | 固定顺序中尚未投票的下一名角色 | VIEW-VOTE | ACTION-VOTE | 当前角色提交 1 票；六票收齐时阶段完成 | 确定性计票；唯一最高票与侍女相同则成功，平票或唯一最高票错误则失败 | TRANS-VOTE、TRANS-VOTE-COMPLETE | 未完成则 PHASE-VOTE；完成则 PHASE-REVEAL |
| PHASE-REVEAL | 无，由自动 hook 处理 | 无 | 无 | 进入阶段且 `truth_revealed=false` | 从 SRC-10 加载完整真相正文 | TRANS-REVEAL | PHASE-SCORE |
| PHASE-SCORE | 无，由自动 hook 处理 | 无 | 无 | 进入阶段且尚无 `terminal_result` | 按 RULE-18 比较结构化答案；不可机械验证项标记 NOT_SCORED；按得分率选出可并列胜者 | TRANS-SCORE | 终止 |

### Observation projections

| View ID | Agent IDs | Included State/info IDs | Excluded private info | Available Action IDs |
|---|---|---|---|---|
| VIEW-ROLE | 全部角色（按当前 actor 投影） | 本人 script ref 对应完整剧本、INFO-PUBLIC-ROLES、已发布介绍、当前进度 | 他人完整剧本、全部线索、INFO-TRUTH、他人未提交内容 | ACTION-INTRODUCE |
| VIEW-PERSON-SEARCH | 全部角色 | 本人完整剧本、本人获配人物线索正文、本人处理状态、已公开内容 | 他人未公开人物线索、全部场景线索、INFO-TRUTH | ACTION-HANDLE-CLUE |
| VIEW-DISCUSS-1 | 全部角色 | 本人完整剧本、本人持有线索、全部已公开人物线索、介绍与已发生公开发言 | 他人未公开线索、场景线索、INFO-TRUTH | ACTION-DISCUSS |
| VIEW-SCENE-SEARCH | 全部角色 | 本人完整剧本、本人全部已获配线索、公开历史、本人场景线索正文 | 他人未公开线索、INFO-TRUTH | ACTION-HANDLE-CLUE |
| VIEW-DISCUSS-2 | 全部角色 | 本人完整剧本、本人持有线索、全部公开线索、全部公开发言 | 他人未公开线索、INFO-TRUTH | ACTION-DISCUSS |
| VIEW-VOTE | 全部角色 | 本人完整剧本与持有线索、全部公开线索与讨论、本人任务定义、本人已提交票（若有） | 他人剧本、他人未公开线索、他人投票、INFO-TRUTH | ACTION-VOTE |

### Action schemas

| Action ID | Tool name | Actor IDs | JSON-like parameters | Available when | Validation failures and reasons | Payload fields |
|---|---|---|---|---|---|---|
| ACTION-INTRODUCE | `introduce_character` | 全部角色 | `{content: string}` | PHASE-INTRO 且 actor 是当前选中角色 | 错误阶段：“当前不是自我介绍阶段”；错误 actor：“尚未轮到该角色”；空内容：“介绍不能为空”；重复：“该角色已经完成介绍”；重复 ID：“该 Action 已消费” | `content` |
| ACTION-HANDLE-CLUE | `handle_clues` | 全部角色 | `{decisions: [{clue_id: string, reveal: bool}]}` | 两个搜证阶段且 actor 是当前选中角色 | 错误阶段；错误 actor；缺少/多出本人本轮未处理线索；线索不属于 actor；重复 clue；重复 ID。原因必须指出具体 clue ID | `decisions`；公开正文由授权数据加载器按 clue ID 读取，模型不得改写 |
| ACTION-DISCUSS | `discuss_publicly` | 全部角色 | `{content: string}` | 两个讨论阶段且 actor 是当前选中角色 | 错误阶段；错误 actor；空内容；本轮已经发言；重复 ID | `content`, `discussion_phase` |
| ACTION-VOTE | `submit_vote` | 全部角色 | `{suspect_id, image_location: enum, motive: enum, self_is_culprit: bool, task_claims: object}` | PHASE-VOTE 且 actor 是当前选中角色 | 错误阶段；错误 actor；嫌疑人不在六角色中；位置/动机不是声明枚举；缺少本人可评分任务键；重复投票；重复 ID | 完整参数、actor 专属任务答案及不可评分任务的复盘陈述 |

### Transition rules

| Transition ID | From phase | Collected Actions | State updates | Consumed IDs | To phase |
|---|---|---|---|---|---|
| TRANS-INTRO | PHASE-INTRO | 当前 actor 的 ACTION-INTRODUCE | 在复制 State 中写入完整介绍 | 加入 action_id | PHASE-INTRO 或 PHASE-PERSON-SEARCH |
| TRANS-SEARCH-PERSON | PHASE-PERSON-SEARCH | 当前 actor 的 ACTION-HANDLE-CLUE | 记录本人全部人物线索已处理及公开集合 | 加入 action_id | PHASE-PERSON-SEARCH 或 PHASE-PERSON-DISCUSS |
| TRANS-DISCUSS-1 | PHASE-PERSON-DISCUSS | 当前 actor 的 ACTION-DISCUSS | 写入第一轮完整发言 | 加入 action_id | PHASE-PERSON-DISCUSS 或 PHASE-SCENE-SEARCH |
| TRANS-SEARCH-SCENE | PHASE-SCENE-SEARCH | 当前 actor 的 ACTION-HANDLE-CLUE | 记录本人全部场景线索已处理及公开集合 | 加入 action_id | PHASE-SCENE-SEARCH 或 PHASE-SCENE-DISCUSS |
| TRANS-DISCUSS-2 | PHASE-SCENE-DISCUSS | 当前 actor 的 ACTION-DISCUSS | 写入第二轮完整发言 | 加入 action_id | PHASE-SCENE-DISCUSS 或 PHASE-VOTE |
| TRANS-VOTE | PHASE-VOTE | 当前 actor 的 ACTION-VOTE | 私密写入本人完整投票 payload | 加入 action_id | PHASE-VOTE 或 PHASE-REVEAL |
| TRANS-VOTE-COMPLETE | PHASE-VOTE | 六个 ACTION-VOTE 已收齐 | 计算 `vote_tally` 和 `collective_result`，不修改原票 | 已由逐票转换加入 | PHASE-REVEAL |
| TRANS-REVEAL | PHASE-REVEAL | 无（自动） | `truth_revealed=true` | 无 | PHASE-SCORE |
| TRANS-SCORE | PHASE-SCORE | 无（自动） | 按 RULE-18 写入逐项状态、可评分总分、得分率、winner_ids、terminal_result | 无 | 终止 |

### Recovery

每次成功转换并完成该转换对应的事件投递后保存完整 State，形成安全阶段边界。恢复需要 `session_id`、State、六个 Agent 配置、各 Agent 增量上下文、公共 ROOM、六个角色私密 ROOM，以及 SRC-00 至 SRC-10 数据引用。恢复后依据 `phase` 和各收集映射选择尚未行动的下一角色；`consumed_action_ids` 拒绝重复 Action，稳定事件 ID 与 `emitted_event_ids` 防止已投递内容重复出现。若在投递完成但持久化前中断，重新构建同一事件 ID，由投递层幂等去重后再保存。

## 8. ROOM and event projection

| Event ID/type | Trigger | Complete content | Room key | Recipients | Private | Release time |
|---|---|---|---|---|---|---|
| EVT-SESSION-OPENED | 初始 State 创建 | App 名称、六个公开人物卡、固定角色顺序、阶段流程与公开计分规则 | `public` | all | false | 会话开始 |
| EVT-PRIVATE-SCRIPT | 会话创建/恢复资源重建 | 对应角色完整剧本、任务与来源引用 | `private:<agent_id>` | 对应角色 | true | 会话开始；恢复时使用稳定 ID 不重复 |
| EVT-INTRODUCTION | TRANS-INTRO | actor、完整介绍正文 | `public` | all | false | 每次合法介绍后 |
| EVT-PRIVATE-CLUES | 角色进入搜证阶段 | 本轮获配 clue ID、完整原始线索正文、来源 | `private:<agent_id>` | 对应角色 | true | 该角色首次进入本轮搜证时 |
| EVT-CLUE-DECISION-PRIVATE | TRANS-SEARCH-* | actor、每条 clue ID、公开/保密选择 | `private:<agent_id>` | 对应角色 | true | 合法处理后 |
| EVT-CLUE-REVEALED | TRANS-SEARCH-* 且 `reveal=true` | actor、clue ID、完整原始线索正文、来源，不以摘要替代 | `public` | all | false | 合法处理后 |
| EVT-DISCUSSION | TRANS-DISCUSS-* | 轮次、actor、完整公开发言 | `public` | all | false | 每次合法发言后 |
| EVT-VOTE-RECEIPT | TRANS-VOTE 且未收齐 | actor、本人完整投票与任务答案 | `private:<agent_id>` | 对应角色 | true | 本人投票后 |
| EVT-VOTES-REVEALED | TRANS-VOTE-COMPLETE | 六名 actor 各自完整投票、任务答案、完整计票及集体判断 | `public` | all | false | 六票全部收齐后一次性发布 |
| EVT-TRUTH-REVEALED | TRANS-REVEAL | 真凶侍女、动机、画像逐次移动的完整复盘、最终小舟位置及 SRC-10 引用 | `public` | all | false | 投票公开后 |
| EVT-SCORES | TRANS-SCORE | 每名角色每项任务的答案、CORRECT/INCORRECT/NOT_SCORED 状态、可评分分值、得分率、胜者与并列情况 | `public` | all | false | 真相公开后 |
| EVT-TERMINAL | TRANS-SCORE | 集体是否找对真凶、最终真相、最终分数与 winner_ids 的完整终局结果 | `public` | all | false | 终止时 |

## 9. Acceptance scenarios

| AC ID | Initial facts | Actions | Expected state | Expected visibility |
|---|---|---|---|---|
| AC-NORMAL-01 | 初始六角色、固定线索顺序 | 六人依次介绍；两轮均按分配处理线索并各讨论一次；六人投票；自动复盘计分 | 按八个阶段顺序到 terminal；侍女与小舟真相落入 terminal_result；consumed IDs 完整 | 私密剧本/保密线索只在对应私密 ROOM；公开正文完整；票收齐后才公开；复盘与分数进入公共 ROOM |
| AC-INVALID-01 | PHASE-PERSON-SEARCH，轮到潘仕成 | 潘仕成提交属于伊凡的 clue ID | State 不变；返回包含具体 clue ID 和归属错误的拒绝原因 | 拒绝及 Tool Result 仅追加到潘仕成同一上下文，不发布线索 |
| AC-INVALID-02 | PHASE-VOTE，轮到李夫人 | 提交不存在的 suspect ID 或缺失 task_claims | State 不变；返回具体参数错误并允许纠正 | 无公开投票；ToolCall/ToolResult 在李夫人同一上下文成对 |
| AC-PRIVACY-01 | 第一轮人物线索已分配，侍女选择保密一条 | 其他角色进入讨论观察 | 保密 clue 不在其他角色 Observation | clue 完整正文只在侍女私密 ROOM；公共 ROOM 不存在该正文 |
| AC-VOTE-PRIVACY-01 | 前五名已投票，第六名尚未投票 | 构建第六名 VIEW-VOTE | 第六名看不到前五票；第六票后确定计票 | 前五票只有各自私密回执；收齐后单一公共事件完整公开六票 |
| AC-DUPLICATE-01 | 任一合法 Action 已转换并消费 | 重放同 action_id | State、分数和阶段不变；返回“该 Action 已消费” | 不重复发布介绍、线索、发言、投票或结算事件 |
| AC-TIE-01 | 六票将形成最高票平票 | 提交最后一票 | collective_result 为未找出唯一真凶；仍进入复盘计分并终止 | 公共 ROOM 完整显示票数、平票原因、真相与个人分数 |
| AC-TERMINAL-01 | PHASE-SCORE，已公开真相 | 自动计分 | 可验证答案按 RULE-18；语义任务 NOT_SCORED；winner_ids 包含全部最高得分率角色；is_terminal=true | 完整逐项状态、得分率和终局结果进入公共 ROOM |
| AC-RECOVERY-01 | 在第一轮讨论完成三人后持久化并终止进程 | 恢复同 session，后三人行动至下一阶段 | 前三人发言不重放；从第四人继续；最终可终止 | 已有 ROOM 内容不重复，后续内容按原可见性追加 |
| AC-RECOVERY-02 | EVT-TRUTH-REVEALED 已投递但转换后持久化尚未确认 | 恢复并继续 | 稳定事件 ID 保证真相只投影一次，随后计分终止 | 公共 ROOM 只有一份完整真相事件 |
| AC-PAIRING-01 | 任一角色产生合法或非法 Tool Call | Environment 处理 Action | 合法调用执行 acknowledgement 后改变 State；非法调用只反馈原因 | assistant Tool Call 后紧邻匹配 Tool Result，二者在同一 Agent 上下文 |

## 10. Assumptions and unresolved decisions

| ID | Type | Statement | Consequence | Status |
|---|---|---|---|---|
| Q-01 | confirmed | 固定角色顺序为潘仕成、伊凡、李夫人、侍女、管家、何绍基；人物线索每人 2 条；场景线索按顺序分配为 3、3、2、2、2、2 条。 | 角色可见信息与分配可复现 | CONFIRMED_BY_USER |
| Q-02 | confirmed | 每轮自由讨论中六名角色按固定顺序各公开发言 1 次，每轮共 6 次。 | 阶段无需外部等待即可完成 | CONFIRMED_BY_USER |
| Q-03 | confirmed | 最终投票平票时判定未成功找出唯一真凶，但仍进入复盘与个人任务计分。 | 主线集体结果确定 | CONFIRMED_BY_USER |
| Q-04 | confirmed | 所有投票在全部收齐前保密，收齐后一次性公开。 | 后投角色不会看到先投结果 | CONFIRMED_BY_USER |
| Q-05 | confirmed | 采用角色任务页的具体分值体系，不采用规则书中“主线 3 分、支线 1 分（待平衡）”；OCR 缺失值由 Q-07 补全。 | 角色任务权重确定 | CONFIRMED_BY_USER |
| Q-06 | confirmed | 六名角色全部由 LLM 控制，不设置真人角色或主持人等待。 | 保持第一阶段同步可执行 | CONFIRMED_BY_USER |
| Q-07 | confirmed | 潘仕成、伊凡、管家采用 6+2+2，何绍基采用 8+2，使每名角色总分统一为 10。 | 四名角色计分及最终胜者可确定 | CONFIRMED_BY_USER |
| Q-08 | confirmed | 第一阶段只对真凶、最终位置和标准动机自动计分；隐瞒、协助隐瞒和逃脱问责展示为 NOT_SCORED；按可评分得分率确定胜者。 | 计分可确定性执行 | CONFIRMED_BY_USER |

## 11. Approval

```yaml
requirements_confirmed: true
blueprint_approved: true
approved_revision: haishanxianguan-blueprint-r1
implementation_status: GENERATED
verification_status: PASS_MOCK_ONLY
```
