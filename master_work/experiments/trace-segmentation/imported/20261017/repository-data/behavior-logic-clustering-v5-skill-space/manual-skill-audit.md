# V5 manual Skill audit

I read every D001–D008 `skill-candidates.json` member reference and the corresponding raw slice event JSON under `calibrated-confidence-length-banded-v3-slices`. The review used no LLM or embedding. The strict gate was: at least two independent sessions show the same concrete problem-solving experience, and that experience transfers beyond the source task. Shared Edit/Read/Compile, documentation updates, and generic planning were rejected. OpenCode availability was not used as a conclusion.

The 41 candidates produce 1 `extractable`, 5 `partial`, and 35 `not_extractable` reviews. The strict extractable rate is 1/41 = 2.44%. The broad usable rate (`extractable` + `partial`) is 6/41 = 14.63%.

| Domain | Candidates | Extractable | Partial | Not extractable |
|---|---:|---:|---:|---:|
| D001 | 3 | 0 | 0 | 3 |
| D002 | 3 | 1 | 0 | 2 |
| D003 | 10 | 0 | 2 | 8 |
| D004 | 2 | 0 | 0 | 2 |
| D005 | 6 | 0 | 1 | 5 |
| D006 | 6 | 0 | 2 | 4 |
| D007 | 10 | 0 | 0 | 10 |
| D008 | 1 | 0 | 0 | 1 |
| **Total** | **41** | **1** | **5** | **35** |

The only clearly extractable candidate is D002/skill-01: two independent low-level OS sessions repeatedly use runtime boot evidence (MB1/MB2, UEFI/GOP tags, GRUB/QEMU errors, framebuffer mapping) to repair compatibility and then re-test the application display path. Its draft Skill is: “When migrating a low-level boot or display path across boot protocols, keep legacy and new entry paths explicit; validate the actual boot tag and framebuffer mode at runtime, then fix build modules, memory mapping, and application display abstractions from that evidence before rerunning the image.”

The five partial candidates are typography/layout patterns. D003/skill-05, D003/skill-06, D005/skill-03, and D006/skill-03 repeatedly request professional font selection followed by shared typography, spacing, or icon refinement, but require human confirmation and splitting into precise design rules. D006/skill-05 repeatedly diagnoses an off-size or off-center grid across two sessions; it is potentially reusable as a layout-debugging procedure but mixes different responsive constraints and should be split before extraction. Drafts and slice-level evidence are recorded in `manual-skill-audit.json`.

The remaining candidates are dominated by unrelated product requirements, generic backend/frontend implementation, continuation state, staged milestone planning, compile/read/edit relations, or documentation/housekeeping. They do not meet the evidence and transferability gate. In particular, no OpenCode availability observation is used to label a candidate.

New artifact: `manual-skill-audit.json` contains the per-candidate label, session count, raw-event evidence summary, and drafts for extractable/partial candidates. This Markdown file provides the human-readable totals and domain rollup.
