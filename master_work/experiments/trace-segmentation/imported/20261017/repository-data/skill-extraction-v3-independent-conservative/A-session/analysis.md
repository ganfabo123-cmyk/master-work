# A-session independent conservative extraction

Input: 30 complete original sessions, represented by 117 context-expanded segment files from `context-expanded-sessions/index.json`. This analysis was performed independently from the A input only; no slice or narrow-domain experiment result was used.

Six skills survived the strict gate. Each has a concrete trigger, observed action or decision, an observable result, a scope limit, and direct evidence from an original context-expanded trajectory. Near-duplicates were merged rather than split.

1. Reactive UI lifecycle repair: identify raw HTML injection that prevents Alpine initialization, move state into Alpine components/stores, and explicitly initialize inserted trees. Evidence: the trace reports the click fix and `Alpine.initTree` repair.
2. Idempotent window/process lifecycle: guard repeated opens and attach process cleanup to close. Evidence: the trace names the leak and reports `windows.isOpen()` and `onClose` cleanup.
3. Static deployment layout alignment: inspect the real root/dist layout and disable inferred build output only when the entry script has no imports. Evidence: deployment succeeded after `buildCommand: ""` and `outputDirectory: "."`.
4. Legacy plus GOP rendering: preserve MB1/VGA fallback while routing shared drawing through a capability-selected abstraction for MB2/GOP. Evidence: both headers and both rendering paths are reported, with direct VGA writes removed from snake.
5. Actionable selector diagnostics: include exact call, target type, rejection reason, and selectable alternatives. Evidence: the emitted exception and subsequent full suite results.
6. Complementary mobile review: combine static package inspection with install/interact evidence, verify false positives, and stop unsupported device claims. Evidence: tracker false-positive correction, successful app interaction, and on-device self-updater discovery.

Discarded candidates: 24. They were rejected because they were plans, generic read/edit/test routines, ordinary feature work, one-off project details, or duplicates of a stronger retained skill. The complete candidate/reason list is in `analysis.json`.

Self-check: all six retained entries have existing source files and non-empty direct evidence; no code was modified.
