# config-service (fixture)

A deliberately buggy fixture repository used to exercise CoTracer's
hypothesis-driven multi-agent debugging in a real runtime.

## Issue

A CLI override for `max_retries` never takes effect. Run:

```sh
python main.py --max-retries=10
```

Expected: `max_retries: 10` (CLI overrides the config-file value 5).
Actual: `max_retries: 5` — the highest-priority layer is silently ignored.

## Files

- `config_service.py` — layered config resolution: defaults → config.json →
  env → CLI overrides; keys are normalized (dash → underscore, lowercase).
- `config.json` — the file layer.
- `main.py` — CLI parsing and reporting.

## Notes for the debugger

- Do not modify source files. You may write temporary probe scripts into the
  system temp directory if you need them.
- The root cause is inside this repository; a single small change fixes it.
- The env layer works (`CONFIG_SERVICE_MAX_RETRIES=10 python main.py` prints
  10) — only the CLI layer is broken.