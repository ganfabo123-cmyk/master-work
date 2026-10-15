# Experiment B — conservative Skill extraction from 97 slices

Scope: only `calibrated-confidence-length-banded-v3-slices`; A and C were not read or used.

Result: 97 slices read, 7 Skills retained, and 90 slices discarded. The JSON records 17 grouped discarded-candidate explanations; grouped records intentionally avoid fabricating one candidate per slice when the slice contained no independently supportable Skill.

Retained entries:

1. `B-001` — Diagnose fixed-size solver stack overflows by locating large automatic state/copies, then use static storage or references and rerun the complete suite. Strongest evidence: the explicit `0xC00000FD` diagnosis and final `10/10 suites, 144/144 tests pass`.
2. `B-002` — Keep request-backed route data alive until dispatch consumes it. Strongest evidence: the explicit `free_all`/freed `req.path` diagnosis and stated fix.
3. `B-003` — Expose a C++ engine through opaque `extern "C"` handles and validate the ABI with dedicated/regression tests.
4. `B-004` — When parser and VM separation is contradicted by the implementation, compile through a scratch runtime and serialize portable bytecode. The cited slice also has the Stage 1/2 test counts; the retained evidence does not claim more than those counts.
5. `B-005` — Preserve a shared transport seam for Android WebView, swap the native bridge calls, and verify install/logcat/screenshot plus release signing.
6. `B-006` — Resolve annotation semantics from configuration and the published schema before answering; keep the mapping tied to the cited dataset.
7. `B-007` — When device access is unavailable during F-Droid review, report static manifest/recipe/CI findings and state the runtime-test limitation explicitly.

The full structured records, direct evidence excerpts, scope limits, and discarded reasons are in [analysis.json](analysis.json).

Most valuable manual-review targets:

- `B-001`: useful general debugging pattern, but confirm that the static-storage recommendation is acceptable for the solver's non-reentrant contract.
- `B-002`: strong concrete lifetime diagnosis; verify that the source slice's later route test actually exercised the repaired endpoint.
- `B-004`: technically valuable architecture pivot; verify the bytecode evidence is from the same Stage 3 implementation rather than a summary-only projection.
- `B-005`: strongest end-to-end evidence among the UI/mobile slices, but live USB behavior remains outside the cited verification.

Self-check performed: every retained source path exists under the declared source root; every retained Skill has non-empty direct evidence; no retained entry duplicates the same slice experience as a separate near-identical Skill.
