# Full-message trajectory segmentation research log

> This document records the current experiment as research material. It
> distinguishes measured observations from hypotheses and does not treat an
> automatically generated slice as a validated atomic task.

## 1. Research question

The target is an atomic trajectory with a task-like closed loop:

```text
task/request text
    -> tool-assisted execution
    -> verification, correction, or result text
```

The first tool-only representation was useful for finding changes in tool
behavior, but it often cut through the middle of one user task. The trajectory
was therefore expanded to include ordinary text messages and other trace
message parts.

The current dataset contains 30 public sessions and 18,100 extracted message
events. The output is an exploratory baseline; it is not ground-truth task
annotation.

## 2. Frozen mathematical model

The formula was frozen as `full-message-boundary-v1` so that later experiments
change parameters rather than silently changing the algorithm.

For a candidate boundary `t`:

```text
score(t) =
    0.65 * normalized_mean_js(t)
  + 0.20 * multiscale_stability(t)
  + 0.10 * text_boundary_signal(t)
  + 0.05 * closure_signal(t)
```

The components are:

- `normalized_mean_js`: Jensen-Shannon divergence between weighted message
  category distributions to the left and right of `t`, averaged over several
  windows;
- `multiscale_stability`: the fraction of configured windows for which the
  local JS value is above that window's per-session quantile;
- `text_boundary_signal`: a prior for `user_text` or `assistant_text` near a
  boundary;
- `closure_signal`: a small prior for completion/verification language in
  assistant text.

The selection procedure is fixed as:

1. compute the score at eligible event positions;
2. keep local maxima above the per-session score quantile;
3. apply non-maximum suppression with a minimum gap;
4. reject boundaries too close to the session edge or a short segment.

`tool_result` has weight `0.0`. It remains in the exported trajectory and
materialized slices, but does not contribute to the distribution-based score,
because it is a return value coupled to a tool call rather than an independent
behavior decision.

The canonical implementation is:

[`frozen_message_segmentation.py`](frozen_message_segmentation.py)

## 3. Baselines

### Frozen v1

Parameters:

```text
weights: tool_result=0, other categories=1
windows: [7, 13, 19]
threshold quantile: 0.85
minimum gap: 15 events
minimum segment: 15 events
```

Measured output:

| Metric | Value |
|---|---:|
| Sessions | 30 |
| Message events | 18,100 |
| Selected boundaries | 453 |
| Segments | 483 |
| Mean segment length | 37.47 |
| Segments <= 20 events | 150 |
| Segments <= 30 events | 276 |
| Segments with text at both ends | 46 / 483 = 9.5% |
| `user_text -> assistant_text` segments | 6 |
| Segments with closure language | 189 |
| Metadata/tool-result boundary involvement | 298 |

Interpretation: v1 has high temporal resolution but is strongly over-segmented.

### Recommended v2 baseline

The first conservative parameter group was:

```text
weights: tool_result=0, record:*=0, assistant_thinking=0.25
windows: [11, 19, 31]
threshold quantile: 0.90
minimum gap: 25 events
minimum segment: 25 events
```

Measured output:

| Metric | Value |
|---|---:|
| Selected boundaries | 233 |
| Segments | 263 |
| Mean segment length | 68.82 |
| Segments <= 20 events | 2 |
| Segments <= 30 events | 37 |
| Segments with text at both ends | 30 / 263 = 11.4% |
| `user_text -> assistant_text` segments | 5 |
| Segments with closure language | 140 |
| Metadata/tool-result boundary involvement | 154 |

Interpretation: v2 substantially reduces short fragments and metadata noise,
but it may merge multiple internal task phases. Its average dominant-category
share decreased from 25.8% to 24.6%, while its average number of categories per
segment increased from 9.76 to 11.65. This is evidence against claiming that
v2 is simply “more atomic”.

## 4. Parameter sweep 2026-10-10

The formula and feature definitions were held fixed. Only the configured
parameters changed.

| Experiment | Windows | Quantile | Gap | Min segment | Segments | Mean length | <=20 | <=30 | Both-end text | User->assistant | Metadata boundary |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| grid-a-sensitive | 9,17,25 | .88 | 20 | 20 | 336 | 53.87 | 17 | 112 | 39 / 11.6% | 8 | 188 |
| grid-b-current | 11,19,31 | .90 | 25 | 25 | 263 | 68.82 | 2 | 37 | 30 / 11.4% | 5 | 154 |
| grid-c-conservative | 13,25,37 | .92 | 30 | 30 | 195 | 92.82 | 2 | 7 | 21 / 10.8% | 10 | 106 |
| grid-d-long-high | 11,19,31 | .92 | 25 | 25 | 227 | 79.74 | 2 | 25 | 24 / 10.6% | 5 | 144 |

Additional closed-loop proxy:

| Experiment | Both-end-text segments containing closure language |
|---|---:|
| grid-a-sensitive | 25 / 39 = 64.1% |
| grid-b-current | 21 / 30 = 70.0% |
| grid-c-conservative | 17 / 21 = 81.0% |
| grid-d-long-high | 16 / 24 = 66.7% |

## 5. Current interpretation

There is no single winner under the current proxy metrics.

- `grid-a-sensitive` has the best recall-like behavior: it preserves more
  candidate boundaries and has the highest count of text-ended segments, but
  it still produces many short pieces.
- `grid-c-conservative` has the strongest closed-loop proxy ratio and the most
  `user_text -> assistant_text` segments, but it may under-segment because its
  mean segment length is 92.82 events.
- `grid-b-current` is the most balanced operating point so far: it removes
  most very short fragments without being as aggressive as grid-c.
- `grid-d-long-high` is more conservative than grid-b, but its proxy evidence
  is not better than grid-c and it still does not improve the user-to-assistant
  closure count.

The important trade-off is:

```text
more sensitivity  -> more boundary recall, more over-segmentation
more conservatism  -> fewer fragments, higher risk of merging tasks
```

The present metrics are not sufficient to decide which side is correct,
because there is no human-labeled atomic-boundary reference set.

## 6. What should be tuned next

The next experiments should remain parameter-only:

1. Keep `tool_result=0`, `record:*=0`, and `assistant_thinking=0.25`.
2. Compare `grid-a-sensitive`, `grid-b-current`, and `grid-c-conservative` on
   the same manually reviewed subset.
3. Label a small set of boundaries as `keep`, `move`, or `remove` for several
   representative sessions. The labels need not cover every event.
4. Use those labels to select the operating point, not the raw number of
   segments.

The most useful acceptance signals are expected to be:

- text-start alignment;
- assistant-result/end alignment;
- one coherent user intent per segment;
- presence of execution and verification;
- low continuation leakage across a boundary;
- a penalty for short or metadata-only fragments.

Until a small labeled reference exists, “fewer segments” must not be treated
as proof of better atomicity.

## 7. Reproduction

The experiments were generated with the canonical script. Example:

```powershell
python frozen_message_segmentation.py `
  --profile recommended-v2 `
  --windows 13,25,37 `
  --quantile 0.92 `
  --min-gap 30 `
  --min-segment 30 `
  --output parameter-experiments/grid-c-conservative/full-message-segments.json `
  --output-dir parameter-experiments/grid-c-conservative/plots
```

The formula specification is also recorded in
[`frozen-segmentation-formula.md`](frozen-segmentation-formula.md).

## 8. Recall-first segmentation test

The downstream requirement is recall-first: a slice may contain extra context,
but it must not omit the content needed to understand the task. This is
different from claiming that every slice is already one atomic closed loop.

The first implementation is in `frozen_message_segmentation.py` and keeps the
frozen score formula unchanged. It adds a post-selection safety layer:

- `--safe-boundary` keeps a cut only when the left event is `assistant_text` or
  the right event is `user_text`;
- `--safe-radius` permits projection to a nearby safe text boundary;
- `--overlap-events` expands each materialized slice on both sides, allowing
  duplicated context but no coverage gap.

The generated output is:
`parameter-experiments/recall-first-grid-c-overlap25/`.

Run parameters:

```powershell
python frozen_message_segmentation.py `
  --profile recommended-v2 `
  --windows 13,25,37 `
  --quantile 0.92 `
  --min-gap 30 `
  --min-segment 30 `
  --safe-boundary `
  --safe-radius 25 `
  --overlap-events 25 `
  --output parameter-experiments/recall-first-grid-c-overlap25/full-message-segments.json `
  --output-dir parameter-experiments/recall-first-grid-c-overlap25/plots
```

Observed on the 30-session dataset:

- 18,100 message events;
- 161 retained safe boundaries and 191 slices;
- 183/191 slices have non-zero overlap;
- average core length: 94.8 events;
- average materialized length: 136.9 events;
- all retained boundaries were already safe in this run; no unsafe boundary
  remained and no non-zero projection distance was needed;
- the core partition covers every original event, while overlap duplicates
  context around boundaries.

Direct text inspection shows that this improves boundary recall/context
preservation, but long slices can still combine multiple work phases. The
current evidence therefore supports “recall-first and gap-resistant”, not
“atomicity guaranteed”. The next mathematical tuning target should be a
boundary-risk/continuation-leakage measure, not simply fewer slices.

## 9. Recursive binary segmentation test

`recursive_recall_segmentation.py` adds a recursive split experiment. It does
not split at the numeric midpoint. For each current interval it finds the
strongest local maximum of the frozen boundary score, requires a safe text
boundary, and accepts the split only when both children contain user text,
assistant text, and tool-call evidence. Accepted children are then visited
recursively. The materialized slices retain 25 events of context overlap.

Output:
`parameter-experiments/recursive-recall-v1/`.

Observed result:

- 30 sessions and 18,100 events;
- 49 recursive boundaries and 79 slices;
- average materialized length: 260.1 events;
- only 2 slices are at most 30 events;
- 67/79 slices contain overlap context.

Direct inspection shows the recursive completeness gate is conservative: it
reduces risky cuts but leaves several multi-phase work blocks intact. For
example, the first core segment of session `07b57159-218e-4330-a64e-0ec4b4355056`
contains 285 events and spans multiple CFML milestones. Therefore this version
is useful as a high-confidence coarse segmentation baseline, not as evidence
that recursion alone solves atomic-task segmentation.

## 10. Best-first confidence-gated segmentation

`best_first_confidence_segmentation.py` implements the next hypothesis: at
each iteration it evaluates the strongest safe candidate in every active
interval, accepts the globally highest-confidence candidate, splits that
interval, and repeats. It stops when the global best confidence falls below
the configured threshold.

The current confidence is explicitly a proxy, not a calibrated probability:

```text
confidence =
    0.50 * boundary_score
  + 0.25 * min(left_completeness, right_completeness)
  + 0.15 * safe_text_boundary_signal
  + 0.10 * margin_signal
```

The output records the confidence, score margin, left/right completeness,
acceptance decision, and stopping reason for every decision. With threshold
`0.72`, the output is in
`parameter-experiments/best-first-confidence-v1/`.

Observed result:

- 30 sessions and 18,100 events;
- 111 accepted boundaries and 141 materialized slices;
- 122 decisions were evaluated, including 11 explicit below-threshold stops;
- accepted confidence range: 0.724–0.921, average 0.815;
- rejected stop confidence average: 0.668;
- average materialized length: 167.7 events.

This is an adaptive middle point between the one-pass recall-first version
(191 slices) and the conservative recursive version (79 slices). The
confidence values should not yet be described as statistical probabilities;
calibration requires manually labeled accepted/rejected boundaries or a
task-completeness reference set.

## 11. First manual boundary-review pilot

`build_annotation_set.py` creates a review set from the union of the
best-first and recall-first candidate boundaries. Each item stores a small
left/right event context and has the labels `keep`, `move`, or `remove`.
`annotate_pilot.py` records the first manual review batch in
`boundary-review-pilot.json`.

The pilot reviewed 60 candidate boundaries distributed across three groups:
both algorithms proposed the boundary, best-first only proposed it, or
recall-first only proposed it. The labels were:

- `keep`: 16;
- `move`: 2;
- `remove`: 42.

Counting `keep` or `move` as a usable boundary, the reviewed subset accepted
13/40 best-first candidates and 13/40 recall-first candidates. This is a
stratified pilot, not an unbiased estimate of whole-dataset precision; it is
mainly evidence that the current confidence proxy is not calibrated as a
probability. Several high-scoring boundaries are still ordinary continuation
steps such as read/edit/build sequences. The next calibration step should add
negative samples at non-candidate positions and expand review across sessions.

## 12. Label-informed confidence optimization

The first optimization attempt exposed an implementation issue: adding new
features only to the final confidence after selecting the score-best local
candidate did not let those features choose the candidate. The optimized
profile now computes goal-change and closure signals for every local maximum,
then ranks local candidates by the optimized confidence before the global
best-first step. The original `best-first-v1` path remains available.

The optimized confidence proxy is:

```text
confidence_v2 =
    0.30 * boundary_score
  + 0.20 * min_child_completeness
  + 0.20 * nearby_goal_change
  + 0.20 * nearby_closure
  + 0.10 * margin_signal
```

The first threshold `0.72` was too strict after the feature change and left
only 19 boundaries. A threshold scan showed that the recall-first constraint
favours a lower threshold. The selected current experiment is
`parameter-experiments/best-first-v2-fixed-t0.55/`:

- 111 boundaries and 141 slices;
- 30 sessions and 18,100 events;
- 18 of the manually reviewed pilot items were covered;
- among those covered items: 10 `keep`, 1 `move`, 7 `remove`.

The 18-item coverage is not directly comparable to the v1 40-item coverage,
because the optimized algorithm moved many candidate positions. Therefore the
apparent improvement is encouraging but not a final precision estimate. The
next evaluation must compare both algorithms against the same expanded gold
boundary set, including positions neither algorithm proposed.

## 13. Unsupervised PELT baseline

`pelt_segmentation.py` implements an unlabeled penalized segmentation baseline.
Each segment uses a weighted multinomial negative-log-likelihood/entropy cost
over message categories. `tool_result` and metadata records have zero weight,
and `assistant_thinking` has weight 0.25. Candidate changepoints are restricted
to safe text boundaries, and materialized slices receive 25 events of overlap.

The objective is:

```text
sum(segment_cost) + penalty * number_of_segments
```

The first implementation attempted PELT pruning, but the custom entropy cost
was not proven to satisfy the pruning inequality. It therefore produced an
incorrectly over-pruned result. The current implementation uses exact dynamic
programming for the same penalized objective and explicitly records that
pruning is disabled.

On the 30-session dataset, the useful penalty scan produced:

- penalty 0.05: 83 boundaries, 113 segments;
- penalty 0.10: 83 boundaries, 113 segments;
- penalty 0.25: 80 boundaries, 110 segments;
- penalty 1.00: 73 boundaries, 103 segments;
- penalty 5.00: 39 boundaries, 69 segments;
- penalty 100: 0 boundaries, 30 segments.

Direct inspection shows a limitation of this first cost model: even at low
penalties it prefers broad global distribution changes. For example, the
CFML session `07b57159-218e-4330-a64e-0ec4b4355056` is mostly split into
events 1–83 and 84–682, leaving many task phases merged. This is not a PELT
failure; it indicates that category-entropy alone is too weak a segment cost
for task-level boundaries. The next PELT version should add local transition
costs, user-goal/closure features, or a kernel cost over event-window
representations.

## 14. Structured-cost PELT experiment

`structured_pelt_segmentation.py` keeps the event representation fixed but
replaces the first entropy-only cost with:

```text
segment_cost =
    0.65 * category negative log-likelihood
  + 0.35 * event-family transition negative log-likelihood
```

The objective also gives a configurable reward to safe boundaries near a new
user goal or assistant closure. This is still fully unlabeled. Exact dynamic
programming is used because pruning for this custom cost is not yet justified.

The useful middle setting tested was penalty `0.5`, boundary reward `5`,
minimum segment length `30`, and overlap `25`, producing:

- 177 boundaries;
- 207 slices;
- 30 sessions and 18,100 events;
- 30 generated plots.

Output:
`parameter-experiments/structured-pelt-p0.5-r5/`.

Direct inspection shows the richer cost changes the global solution but does
not yet improve task atomicity: in the CFML example, the first segment spans
events 1–190 and still combines multiple milestones. The structured PELT
baseline is therefore useful as an unsupervised comparison, but the current
cost still rewards broad phase distribution more than complete task closure.
The existing recall-first and best-first outputs remain the better practical
baselines for now.

## 15. Pure message embedding representation

The next representation experiment removes the hand-written event-category to
scalar mapping. Every complete event in `message-trajectories.json` is
serialized and embedded directly; no category weight or event-type number is
used as the segmentation input. Source-position fields are retained as output
metadata but excluded from the text sent to the embedding model so the model
does not learn event numbering.

The API run used DashScope `qwen3.7-text-embedding` with 1024-dimensional
vectors. It produced:

- 18,100 event vectors;
- 30 sessions;
- no duplicate `(session_id, event_index)` positions;
- no invalid JSONL records;
- output size about 402 MB in `message-embeddings.jsonl`.

The API was initially run with a resumable JSONL writer. A transient
`IncompleteRead` response exposed a missing retry case; the embedding script
now retries `IncompleteRead` and connection errors, and completed batches are
flushed before the next request.

This representation captures semantic content such as completion phrases,
goal changes, retries, and summaries without requiring the algorithm to know
that a message is a `tool_call` or `assistant_text`. It also has a known risk:
semantic similarity can make two stages of the same task look close even when
one is the start and the other is the completion.

## 16. Embedding-space visualization

`plot_embedding_distribution.py` projects all 1024-dimensional vectors into a
single two-dimensional PCA space only for inspection. The first two principal
components explain 14.59% and 9.35% of variance, 23.93% combined. The global
plot shows a dense shared core and several excursions; sessions do not form
isolated clusters. Individual session plots show repeated movement between a
dense semantic region and outlying regions.

This result is evidence that the vectors contain structured variation, but PCA
is not used as the segmentation representation. The original 1024-dimensional
vectors and chronological order remain the algorithm input.

Outputs are under `embedding-visualizations/`:

- `global-pca-by-session.png`;
- `session-trajectory-grid.png`;
- one plot per session under `sessions/`;
- `pca-summary.json`.

## 17. Multiscale semantic-change signal

`plot_embedding_change_scores.py` computes, for each event position `t`, the
cosine distance between the mean embedding in the left and right windows:

```text
D_w(t) = 1 - cosine(mean(x[t-w+1:t]), mean(x[t+1:t+w]))
```

The tested windows are `5`, `15`, `30`, and `60` events. A robustly
standardized average of the four signals is plotted as a visual composite;
this stage does not select cut points.

The curves show that the short window is noisy, while the 30/60-event windows
reveal broader semantic shifts. Several peaks persist across multiple scales,
which motivates using scale persistence instead of treating every local spike
as a boundary. Outputs are under `embedding-change-score-plots/`.

## 18. Persistent peak candidates

`find_persistent_embedding_peaks.py` turns the multiscale signal into
candidates without performing segmentation. A candidate is a local maximum of
a smoothed composite and must be supported by multiple scale-specific robust
z-scores. The initial permissive setting used:

```text
support >= 2 scales
z-score >= 1.0
minimum distance = 15 events
```

It produced 523 candidates. A stricter setting was then used for the first DP
experiment:

```text
support >= 3 scales
z-score >= 1.5
minimum distance = 30 events
```

It produced 202 candidates across the 30 sessions, averaging 6.7 candidates
per session. These are semantic-change candidates, not calibrated
probabilities and not yet proof of complete task boundaries. The strict result
is stored in `persistent-embedding-peaks-strict/`.

## 19. Candidate-constrained embedding dynamic programming

`embedding_dp_segmentation.py` implements the first actual segmentation pass.
It restricts possible internal boundaries to the strict persistent peaks and
uses exact dynamic programming. For a candidate segment `(s, t)`, the current
within-segment cost is:

```text
C(s,t) = length(s,t) - ||sum(normalized_embeddings[s:t])||
```

The global objective is:

```text
sum(C(segment))
+ penalty * number_of_internal_boundaries
- boundary_reward * candidate_peak_score
```

The implementation also enforces a minimum core segment length and materializes
25 events of overlap on both sides of selected boundaries. The output keeps
core ranges separate from materialized ranges so overlap does not change the
mathematical segmentation.

The penalty scan was:

| Penalty | Segments | Boundaries | Interpretation |
|---:|---:|---:|---|
| 0.25 | 225 | 195 | too fine |
| 0.50 | 223 | 193 | too fine |
| 1.00 | 220 | 190 | fine |
| 2.00 | 170 | 140 | intermediate/finer |
| 3.00 | 119 | 89 | selected first middle setting |
| 5.00 | 54 | 24 | too coarse |
| 10.00 | 31 | 1 | nearly no split |

The selected first output is
`embedding-dp-penalty-3/embedding-dp-segments.json`, with materialized event
records under `embedding-dp-penalty-3/sliced-sessions/`. It contains 119
segments across 30 sessions; core segments average 152.1 events and
materialized segments average 189.5 events.

This is a valid unsupervised embedding-based baseline, not yet an atomicity
claim. The next required evaluation is direct reading of representative
materialized slices, checking whether they preserve complete task loops and
whether the 25-event overlap is sufficient at candidate boundaries.
# 20. 统计校准版置信度优先切分（2026-10-10）

## 20.1 本轮问题

旧版置信度优先方法的两个主要超参数仍然不够科学：

1. 底层事件类别曾通过人工数值/类别权重进入边界分数；
2. 最终置信度阈值是经验阈值，不是真正校准过的概率。

本轮保留 best-first/递归切分框架，但替换边界证据和阈值机制。

## 20.2 新公式

对事件 embedding 先做单位化。对于候选边界 `t` 和窗口 `w`，计算左右窗口均值向量的余弦距离：

```text
D(t, w) = 1 - cosine(mean(E[t-w:t]), mean(E[t:t+w]))
D(t) = mean_w D(t, w)
```

不再使用 category-to-number 距离。每条 session 内部用 `D(t)` 的 median 和 MAD 估计背景分布，得到 robust z-score 和上尾 p-value；随后对同一 session 的全部候选边界执行 Benjamini-Hochberg 多重检验，得到 q-value。

最终审计分数为：

```text
confidence(t) = (1 - q_value(t)) * (0.5 + 0.5 * multiscale_stability(t))
```

其中 `multiscale_stability` 表示多个窗口中有多少比例同时呈现显著变化。切分接受条件为：

```text
safe text boundary
q_value <= 0.10
multiscale_stability >= 2/3
```

`q_value` 是局部 robust-normal null 假设下的统计证据，不宣称等于“语义正确概率”。

## 20.3 实现与结果

新增：

- `calibrated_confidence_segmentation.py`
- `calibrated-confidence-v1-segments.json`
- `calibrated-confidence-v1-slices/`

输入仍为 30 条 session、18,100 个事件和已有 1024 维 message embedding。运行结果：

| 指标 | 旧置信度优先版 | 统计校准版 |
|---|---:|---:|
| session 数 | 30 | 30 |
| 事件数 | 18,100 | 18,100 |
| 边界数 | 111 | 62 |
| 切片数 | 141 | 92 |
| 边界附近有文本（±3事件） | 未在本轮重算 | 62/62 |

统计校准版的切片核心长度为最小 11、平均 196.7、最大 856。少于 30 的核心片段来自短 session 本身，而非算法在长 session 中违反最小长度约束。

## 20.4 初步判断

这版解决了“人为类别数值 + 固定阈值”的理论问题，且仍然保留了原始轨迹完整性和可审计性。但它目前更保守：边界从 111 降到 62，不能仅凭切片数量判断质量变好。

对长 session 的人工文本抽查显示，统计校准版可以减少明显的过碎切分，但也可能把多个连续开发阶段合并到同一片段。因此当前结论是：

```text
统计校准版 = 更科学的边界证据与阈值机制
置信度优先旧版 = 更激进的边界召回基线
```

下一步应比较两版的“内容完整率、任务合并率、任务碎片率和切片可理解性”，而不是继续直接调一个固定 confidence threshold。

# 21. 长度自适应阈值实验（2026-10-10）

## 21.1 动机

人工检查发现统计校准版仍有多个 500～800 事件的长片段，因此加入长度相关的递归切分阈值：区间越长，允许的 FDR 阈值越宽松；区间较短时仍保持严格阈值。

## 21.2 参数化公式

```text
length_factor = max(0, log2(interval_length / 300))
effective_fdr = min(0.30, 0.10 + 0.08 * length_factor)
```

这不是更换算法，而是给同一统计检验增加长度相关的超参数。阈值最多放宽到 0.30，避免超长 session 产生无控制的过切。

## 21.3 运行结果

新增：

- `calibrated-confidence-length-adaptive-v1-segments.json`
- `calibrated-confidence-length-adaptive-v1-slices/`

结果：

| 指标 | 固定 FDR 版 | 长度自适应版 |
|---|---:|---:|
| 边界数 | 62 | 64 |
| 切片数 | 92 | 94 |
| 核心片段平均长度 | 196.7 | 192.6 |
| 核心片段中位长度 | 120 | 120 |
| 超过 300 事件片段 | 20 | 19 |
| 超过 500 事件片段 | 8 | 8 |
| 最大核心片段 | 856 | 856 |

新增边界主要出现在 `6a7964...` 和 `da5d...`，另有一个边界在 `07b...` 向前移动了 3 个事件。由于候选还受到文本边界、局部峰值和多尺度稳定性约束，单独放宽 FDR 的效果有限。

## 21.4 结论

长度自适应阈值方向合理，但本组参数只带来轻微切分增加，没有解决长片段过度合并问题。后续如果继续优化，应优先对超长片段使用更小窗口重新计算局部变化，而不是无限提高最大 FDR。

# 22. 更激进的长度阈值公式（2026-10-10）

## 22.1 公式调整

上一版长度自适应只把 FDR 从 `0.10` 小幅增加到 `0.30`，实际只新增 2 个边界。因此本轮把线性对数放宽改为有上限的指数饱和放宽：

```text
excess = max(0, interval_length - 300)
factor = 1 - exp(-excess / 400)
effective_fdr = 0.10 + (0.45 - 0.10) * factor
```

特点：

- 300 事件以内仍保持 FDR=0.10；
- 超过 300 后逐渐放宽；
- 极长区间最多接近 0.45，不会无限放宽。

## 22.2 结果

新增：

- `calibrated-confidence-length-aggressive-v2-segments.json`
- `calibrated-confidence-length-aggressive-v2-slices/`

| 指标 | 固定 FDR 版 | 上一版长度自适应 | 本版 |
|---|---:|---:|---:|
| 边界数 | 62 | 64 | 72 |
| 切片数 | 92 | 94 | 102 |
| 平均核心长度 | 196.7 | 192.6 | 177.5 |
| 超过 500 事件片段 | 8 | 8 | 3 |
| 超过 700 事件片段 | 5 | 5 | 0 |
| 最大核心片段 | 856 | 856 | 694 |

## 22.3 结论

本轮公式确实增强了长片段的切分倾向，并显著减少了极长片段。代价是 FDR 放宽到约 0.45 后，可能引入更多统计上不够强的边界，因此需要对新增边界进行文本质量抽查，不能直接把“切得更多”当成质量提升。

# 23. 分段长度阈值实验（2026-10-10）

## 23.1 规则

将连续的长度函数改为显式的长度档位，默认参数为：

```text
0–499 事件：FDR 0.10
500–799 事件：FDR 0.30
800+ 事件：FDR 0.45
```

实现通过 `--length-bands` 配置，例如：

```text
--length-bands 0:0.10,500:0.30,800:0.45
```

这样普通片段沿用基础阈值，只有 500 事件以上的长区间才进入更积极的切分档位。

## 23.2 结果

新增：

- `calibrated-confidence-length-banded-v3-segments.json`
- `calibrated-confidence-length-banded-v3-slices/`

| 指标 | 统计校准版 | 激进连续版 | 分段版 |
|---|---:|---:|---:|
| 边界数 | 62 | 72 | 67 |
| 切片数 | 92 | 102 | 97 |
| 平均核心长度 | 196.7 | 177.5 | 186.6 |
| 超过 500 事件片段 | 8 | 3 | 4 |
| 超过 700 事件片段 | 5 | 0 | 1 |
| 最大核心片段 | 856 | 694 | 788 |

## 23.3 判断

分段版符合“保持普通片段基础行为，只增强 500+ 长片段”的目标。它比激进连续版保守，边界数量也更容易解释和调参；但仍需对 500+ 区间新增边界做文本质量抽查。

# 24. 海量轨迹的低成本最终方案（2026-10-10）

## 24.1 设计决策

后续面向海量 Vibecoding/LLM Agent session，采用局部 embedding 校准，而不是默认对全部历史轨迹重复做 embedding：

```text
约 1% 的代表性轨迹
→ embedding
→ 学习事件原型、相对语义关系、置信度校准和长度阈值

海量新轨迹
→ 复用原型、关系和切分参数
→ 重复事件使用缓存
→ 只有无法匹配或新颖度高的事件才增量 embedding
→ 置信度优先切分
→ 长度分段阈值处理长片段
```

## 24.2 表示方式

不把事件强行压成一维固定数字，例如 `write=1`、`edit=1.1`，而是从局部 embedding 样本中建立：

- 事件原型；
- 工具/消息之间的相对距离；
- 常见事件组合和阶段模式；
- 新事件到已知原型的距离；
- 边界变化分数和置信度分布。

同一个 embedding 模型的坐标空间是全局一致的，因此局部样本学习到的 `write`、`edit` 等事件关系可以迁移；但局部样本不能保证覆盖海量轨迹中的全部新语义。

## 24.3 当前最终切分链路

```text
局部代表性 embedding 校准
→ 原型/相对关系复用与新颖事件增量 embedding
→ 多尺度语义变化检测
→ 置信度优先选择边界
→ 500+ 事件使用更宽松的长度分段阈值
→ overlap 保证轨迹内容不缺失
→ 切片 embedding / 聚类 / LLM 分析
```

## 24.4 预期创新点

当前拟定的论文创新表述不是“发明了一个全新的变化点公式”，而是：

> 面向海量 LLM Agent 原始轨迹的低成本结构化方法：仅使用小比例代表性轨迹学习事件语义关系和置信度参数，再通过原型复用、按需增量 embedding、置信度优先切分和长度感知阈值，将海量 session 转换为内容完整、可聚类的任务轨迹切片。

核心价值是降低全量 embedding 和全量语义判断成本，同时保留足够的轨迹语义结构。

## 24.5 当前仍属于假设的部分

以下结论目前是设计假设，不是已证明事实：

1. 约 1% 代表性轨迹足以覆盖同一 Vibecoding 场景的主要事件关系；
2. 局部原型关系能够稳定迁移到海量 session；
3. 新颖事件增量 embedding 能够控制局部校准误差；
4. 低成本切分不会显著损害后续聚类质量。

因此“海量低成本切分”是当前最终研究方向和创新假设，不能在尚未完成大规模验证前表述为已经证明的结论。
