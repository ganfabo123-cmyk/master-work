# 行为归一化 LLM 输入

该文件只保留候选簇的短语义证据和统计摘要，不包含 slice 成员 ID；LLM 输出应按照 `llm-behavior-normalization-prompt-v1.md` 的 JSON 格式保存，再交给 `apply_llm_behavior_normalization.py` 回填成员。
