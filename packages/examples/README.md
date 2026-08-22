# examples/ — ready-to-run demo bundles

English | [中文](README.zh.md)

This directory contains **demo / reference** packages: pre-composed plugin bundles that a thin leaf `cordis.yml` loads, plus `plugin-reference`, a small ordinary plugin used as the generated-plugin template. The `-demo` npm suffix marks the bundles as non-product surface. The runnable leaves under the repo-root [`examples/`](../../examples/AGENTS.md) and the [Python SDK runtime](../../python/sdk-runtime/README.md) are the bundle consumers.

| Package | npm name | Role |
|---|---|---|
| [`agent-spine-demo/`](agent-spine-demo/README.md) | `@deepseek-ai/dsh-agent-spine-demo` | Reusable agent-spine bundle |
| [`acp-demo/`](acp-demo/README.md) | `@deepseek-ai/dsh-acp-demo` | ACP automation application bundle |
| [`jsonrpc-demo/`](jsonrpc-demo/README.md) | `@deepseek-ai/dsh-sdk-jsonrpc-demo` | External-config JSON-RPC runtime |
| [`plugin-reference/`](plugin-reference/README.md) | `@deepseek-ai/dsh-plugin-reference` | Ordinary generated-plugin reference |

`agent-spine-demo` is the shared bundle; `acp-demo` adds its automation entry point, while `jsonrpc-demo` boots a deployment-owned plugin tree. Product one-shot execution belongs to `dsh --profile headless`; no package in this directory provides it.

These packages are not product API. Product seams and entry points remain in their owning groups; demo bundles select concrete compositions.

Do not confuse this group with the repo-root [`examples/`](../../examples/AGENTS.md): that directory holds the runnable `cordis.yml` **leaves**; this group holds the **bundles** those leaves load.
