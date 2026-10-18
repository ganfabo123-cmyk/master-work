# Trace-derived behavioral fixtures

These fixtures are small, deterministic environments for comparing the same
agent task with and without the Skill management system. They reproduce the
observable failure signals from three Trace Commons sessions; they are not
claims that the original project workspaces have been recovered.

Each fixture supports:

- `fixture.json`: provenance, task, expected signals, and dependency policy;
- `run_task.ps1`: execute the fixed task;
- `inject_failure.ps1`: emit the controlled failure transcript;
- `reset.ps1`: restore the fixture to its clean state.

For paired experiments, each fixture is duplicated into:

```text
<fixture>/managed/   # DSH with skill-runtime-hint
<fixture>/baseline/  # DSH without the plugin
```

Run `prepare_skill_runs.ps1` once before managed experiments. It creates an
independent management snapshot/config for each managed fixture under
`experiments/skill-management/runs/<fixture>-managed`, so concurrent runs do not share a
`WRITER.lock`.

The default mode is `controlled`, so runs do not require Bun, MSVC, or a
network download. `epilog/build.ps1 -Mode native` additionally exercises the
available local `clang++` compiler.

## DSH user prompts

The DSH prompt must carry the fixture task explicitly; `cwd` only supplies the
workspace and does not tell the agent which experiment it is running:

| Fixture | User prompt |
|---|---|
| `epilog` | `Run the Epilog fixture task with `pwsh -NoProfile -File .\run_task.ps1`, capture the deterministic LNK1105 / error code 1224 failure, and explain the recovery.` |
| `iceberg` | `Build a single-page portfolio site and verify the generated artifact.` |
| `mydatabase` | `Serve the database browser and load a database page by slug.` |

Each `managed/` directory also contains its own
`skill-runtime-hint.cordis.yml`, with the corresponding management
`config.json` already fixed in the patch. Web runs therefore need no
`SKILL_MANAGEMENT_CONFIG_PATH` environment variable:

```powershell
Set-Location experiments\retrieval-feasibility\fixtures\epilog\managed
pnpm dsh web --patch .\skill-runtime-hint.cordis.yml
```
