# LLM 归一化后的原始 session 与切片领域一致性

## normalized_session_to_slice_fine

| 原始归一化领域 | 最佳切片领域 | 原始 session 数 | 切片 session 数 | 交集 | 原始→切片 | 切片→原始 | Jaccard |
|---|---|---:|---:|---:|---:|---:|---:|
| domain-ui-web UI web layout and interaction | D001 D001 | 28 | 25 | 25 | 0.893 | 1.000 | 0.893 |
| domain-kernel-boot kernel boot and machine environment | D002 D002 | 10 | 20 | 10 | 1.000 | 0.500 | 0.500 |
| domain-cpp-parser-build C++ parser and build diagnostics | D001 D001 | 23 | 25 | 21 | 0.913 | 0.840 | 0.778 |
| domain-device-runtime device runtime and process environment | D001 D001 | 27 | 25 | 25 | 0.926 | 1.000 | 0.926 |
| domain-code-debugging code debugging and failure repair | D001 D001 | 23 | 25 | 21 | 0.913 | 0.840 | 0.778 |

## normalized_session_to_slice_broad

| 原始归一化领域 | 最佳切片领域 | 原始 session 数 | 切片 session 数 | 交集 | 原始→切片 | 切片→原始 | Jaccard |
|---|---|---:|---:|---:|---:|---:|---:|
| domain-ui-web UI web layout and interaction | domain-web-ui web UI | 28 | 24 | 24 | 0.857 | 1.000 | 0.857 |
| domain-kernel-boot kernel boot and machine environment | domain-kernel-boot kernel boot GOP framebuffer | 10 | 20 | 10 | 1.000 | 0.500 | 0.500 |
| domain-cpp-parser-build C++ parser and build diagnostics | domain-web-ui web UI | 23 | 24 | 22 | 0.957 | 0.917 | 0.880 |
| domain-device-runtime device runtime and process environment | domain-web-ui web UI | 27 | 24 | 23 | 0.852 | 0.958 | 0.821 |
| domain-code-debugging code debugging and failure repair | domain-web-ui web UI | 23 | 24 | 23 | 1.000 | 0.958 | 0.958 |
