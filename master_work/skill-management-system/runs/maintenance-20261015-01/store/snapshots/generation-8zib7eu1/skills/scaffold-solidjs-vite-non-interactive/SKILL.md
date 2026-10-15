---
name: scaffold-solidjs-vite-non-interactive
description: Use when `npm create solid` (create-solid) stalls at an interactive prompt in a shell with no TTY but a SolidJS app is still required. Helps the agent write the minimal Vite + SolidJS project by hand, install dependencies, and prove it with a production build, optionally adding `@solidjs/router` for multi-page routing. Requires Node/npm, network access for installs, and write access to the project directory. Do not use when an interactive terminal is available for create-solid, or when SolidStart/SSR scaffolding is required (not covered by this evidence).
triggers:
  - "create-solid"
  - "npm create solid"
  - "What type of project would you like to create?"
---
# Hand-Scaffold a SolidJS + Vite App When create-solid Blocks on Prompts

## Goal
Produce a SolidJS + Vite application in a target directory without relying on the interactive create-solid CLI, verified by a successful `npm install` and a green `npm run build`, with optional `@solidjs/router` routing added on top.

## Scope
### In scope
- Recognizing that `create-solid` is blocked on an interactive prompt in a non-TTY shell and stopping that stalled task.
- Hand-writing the minimal SolidJS + Vite file set: `package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `src/index.tsx`, `src/App.tsx`, `src/index.css`.
- Installing dependencies and verifying with a production `vite build`.
- Optionally adding `@solidjs/router` with `/` and a second route, wiring `<A>` navigation, and re-verifying with another build.

### Out of scope
- SolidStart / SSR scaffolds and prerender configurations (never exercised in the evidence).
- Running or smoke-testing the dev server in a browser (only `npm install` and `npm run build` were verified).
- UI styling decisions, design-system work, or content authoring.
- Frameworks other than SolidJS, and package publishing.

## Inputs
- **Target directory**: path, from the user; required. Should hold only files the user wants kept (in the evidence the directory was cleared to two doc files at user direction before scaffolding). Default: 无.
- **Shell interactivity**: observation of the scaffolder's output; required. If the CLI prints `What type of project would you like to create?`, the shell has no usable TTY for it. Default: 无.
- **Package versions**: strings written into `package.json`; optional, verified installable in the evidence as `solid-js` `^1.9.5`, `vite` `^6.3.5`, `vite-plugin-solid` `^2.11.6`. Default: those trace-verified values.
- **npm registry access**: network condition; required for `npm install`. Default: 无.
- **Routing requirement**: boolean or route list, from the user; optional, whether a second page is needed (evidence used `/` and `/timelines`). Default: 无 (single page).

## Outputs
### Artifacts
- `package.json` (scripts `dev`/`build`/`preview` → `vite`, `vite build`, `vite preview`; deps `solid-js`; devDeps `vite`, `vite-plugin-solid`) at the project root.
- `vite.config.ts` registering `solidPlugin()`.
- `tsconfig.json` with `jsx: "preserve"`, `jsxImportSource: "solid-js"`, `moduleResolution: "bundler"`, `noEmit`, `include: ["src"]`.
- `index.html` mounting `<div id="root">` with `<script type="module" src="/src/index.tsx">`.
- `src/index.tsx` (render entry), `src/App.tsx` (root component), `src/index.css` (imported by the entry).
- Optional: `src/pages/*.tsx` plus router wiring in `src/index.tsx` and `<A>` links in the nav.

### Success criteria
- `npm install` reports added packages and `found 0 vulnerabilities` (observed: `added 73 packages, and audited 74 packages in 41s`).
- `npm run build` ends green (observed: `✓ built in 568ms`; after adding the router, `✓ built in 889ms` with `27 modules transformed`).
- `dist/` contains `index.html`, a CSS asset, and a JS asset as listed by the build output.

### Failure criteria
- `npm install` or `npm run build` exits non-zero or prints errors.
- The interactive scaffolder is left running or its prompts are treated as completed.
- A build was never run before reporting the scaffold as done.

## Preconditions
- Node.js and npm are installed and runnable (evidence environment: Node v22.20.0, npm 11.8.0). If missing, stop and report.
- The target directory is writable and its existing contents are ones the user permits to keep or remove; if other framework files would conflict (e.g. a previous scaffold), get user direction before deleting anything.
- npm registry access is available for `npm install`; if installs fail, stop — the build cannot be verified.
- It has been established that the interactive scaffolder cannot be driven (prompt visible with no TTY). If a real interactive terminal is available, prefer the official CLI instead of this skill.
- Write access to the project root and `src/` (and `src/pages/` when routing is requested).

## Procedure
### Step 1: Detect the interactive stall and stop it
- Actions: run the scaffolder once and inspect output; if it stops at `What type of project would you like to create?`, stop the background task (TaskStop) instead of waiting.
- Inputs: scaffolder output (evidence: `npm create solid@latest . -- --template bare --ssr false` → `create-solid@0.7.0`).
- Outputs: stopped task, no half-created files assumed.
- Cautions: exit-code/no-output reads are misleading — check the task output file before concluding success.
- Preserve: anything the user asked to keep in the directory.
- Next: task stopped / no TTY → Step 2; interactive TTY available → use the official CLI instead of this skill.

### Step 2: Write `package.json`
- Actions: define `scripts` (`dev`: `vite`, `build`: `vite build`, `preview`: `vite preview`), `dependencies` with `solid-js`, `devDependencies` with `vite` and `vite-plugin-solid`, `"type": "module"`.
- Inputs: trace-verified versions (defaults in Inputs).
- Outputs: `package.json`.
- Cautions: do not add SSR/meta-framework packages; keep it minimal.
- Preserve: pre-existing user files; no deletions in this step.
- Next: Step 3.

### Step 3: Write build and type configuration
- Actions: `vite.config.ts` = `defineConfig({ plugins: [solidPlugin()] })`; `tsconfig.json` = `target/module: ESNext`, `moduleResolution: bundler`, `jsx: "preserve"`, `jsxImportSource: "solid-js"`, `strict`, `noEmit`, `isolatedModules`, `include: ["src"]`.
- Inputs: none beyond conventions above.
- Outputs: `vite.config.ts`, `tsconfig.json`.
- Cautions: `jsxImportSource` must be `solid-js` or the JSX will not compile under the Solid plugin.
- Next: Step 4.

### Step 4: Write the entry and root component files
- Actions: `index.html` with `<div id="root">` and `<script type="module" src="/src/index.tsx">`; `src/index.tsx` calling `render(() => <App />, document.getElementById('root')!)` and importing `./index.css`; `src/App.tsx` with the app markup; `src/index.css` with styles.
- Inputs: app content from the user.
- Outputs: the four `src`/root files.
- Cautions: a `tsconfig` diagnostic about a missing `src` folder resolves once these files exist — do not chase it beforehand.
- Preserve: exact entry path agreement between `index.html` and `src/index.tsx`.
- Next: Step 5.

### Step 5: Install dependencies
- Actions: run `npm install` in the project root.
- Inputs: network + `package.json`.
- Outputs: install log (evidence: `added 73 packages, and audited 74 packages in 41s`, `found 0 vulnerabilities`).
- Cautions: treat npm's stderr wrapper noise as non-fatal only when the log also shows the added-packages line.
- Next: install green → Step 6; otherwise stop and fix.

### Step 6: Verify with a production build
- Actions: run `npm run build`.
- Inputs: scaffolded project.
- Outputs: build log listing `dist/index.html`, a CSS asset, and a JS asset, ending `✓ built in <time>` (evidence: `✓ built in 568ms`).
- Cautions: build success proves compilation/bundling only — it does not prove dev-server or browser behavior.
- Next: green → Step 7 if routing is needed, else done; red → fix and re-run Step 6 before reporting.

### Step 7 (optional): Add `@solidjs/router` for a second page
- Actions: `npm install @solidjs/router`; wrap the entry render in `<Router>` with `<Route path="/" component={App} />` and one route per additional page; import `A` and replace in-app `<a>` nav links with `<A href="/..." class="..." activeClass="..." end>` where exact-match highlighting is wanted; rebuild.
- Inputs: route list from the user.
- Outputs: updated `src/index.tsx`, updated nav in `src/App.tsx`, new page file (evidence: `src/pages/Timelines.tsx`).
- Cautions: plain `<a href="#">` links bypass the router — route links must be `<A>`; `end` is what keeps `/` from matching every path.
- Preserve: existing routes and styling; only wiring changes.
- Next: re-run `npm run build` (evidence: `✓ built in 889ms`, `27 modules transformed`) and report only after it is green.

## Decision Rules
### When the scaffolder prints `What type of project would you like to create?` in a non-TTY shell
Treat it as blocked regardless of flags passed (evidence: `--template bare --ssr false` did not prevent prompting); stop the task and hand-scaffold (Step 2).

### When a real interactive terminal is available
Do not use this skill — prefer the official create-solid CLI.

### When only a single page is needed
Stop after Step 6; do not add a router.

### When a second page or in-app navigation is required
Add `@solidjs/router` (Step 7) rather than hand-rolling history handling; the installed package plus `<Router>`/`<Route>`/`<A>` wiring was the verified pattern.

### When `npm install` or `npm run build` fails
Do not report the scaffold as done; fix and re-run until the build log is green.

### When SSR / SolidStart is required
This skill's evidence covers client-side Vite only — stop and choose a different approach.

## Invariants
- Only the files needed for the SolidJS + Vite scaffold are written; unrelated files in the directory are never removed without explicit user direction (in the evidence the wipe was user-requested).
- The stalled interactive scaffolder is stopped rather than left running or assumed finished.
- The framework stays minimal: `solid-js` + `vite` + `vite-plugin-solid`, no SSR/meta-framework packages added.
- Entry-path agreement between `index.html` and `src/index.tsx` is preserved on every edit.
- No success is claimed without a green `npm install` and a green `npm run build` in captured tool output.
- Build success is reported as build success only — dev-server or browser behavior is never asserted from it.

## Common Failures
### Failure: scaffolder hangs waiting for input
- Symptoms: task output stops at `What type of project would you like to create?` with no progress; the command must be killed.
- Causes: `create-solid@0.7.0` prompts interactively in this shell even when `--template bare --ssr false` are supplied; whether a non-interactive mode exists is 轨迹未提供.
- Recovery: stop the task (Step 1) and hand-scaffold (Steps 2–4).

### Failure: build fails after hand-scaffolding
- Symptoms: `npm run build` exits non-zero (not observed in the evidence — the hand-scaffold built green on the first attempt).
- Causes: 轨迹未提供 (no failing build occurred); the fields most critical to compilation are `jsxImportSource: "solid-js"` in `tsconfig.json` and the `src="/src/index.tsx"` entry path in `index.html`.
- Recovery: check those two values first, re-run `npm run build`, and only report success once the log is green.

### Failure: directory already contains another framework's files
- Symptoms: leftover config/route folders coexist with the new SolidJS files.
- Causes: a previous scaffold was run in the same directory.
- Recovery: obtain user direction before deleting anything (in the evidence the user explicitly asked to wipe the prior scaffold); then continue from Step 2.

### Failure: route links do not navigate / active states missing
- Symptoms: nav items are plain `<a href="#">` and never switch pages.
- Causes: router links were not used.
- Recovery: use `<A href=... activeClass=... end>` (Step 7) and rebuild.

## Verification
Observable checks (each requires tool output):

- Stalled CLI stopped: task-stop result confirms the interactive `create-solid` task is no longer running.
- Files present: reading back `package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `src/index.tsx`, `src/App.tsx`, `src/index.css` shows the expected contents (`plugins: [solidPlugin()]`, `jsxImportSource: "solid-js"`, `src="/src/index.tsx"`).
- Install: `npm install` log shows an added-packages line (evidence: `added 73 packages, and audited 74 packages in 41s`) and `found 0 vulnerabilities`.
- Build: `npm run build` log ends with `✓ built in <time>` (evidence: `✓ built in 568ms`) and lists `dist/index.html` plus CSS and JS assets.
- Router (when used): `@solidjs/router` appears in dependencies; entry contains `<Route path="/" ...>` and a second `<Route>`; nav uses `<A ... activeClass=... end>`; rebuild is green with a larger module count (evidence: `27 modules transformed`, `✓ built in 889ms`).
- Not verified by this skill: dev-server startup and rendered-page behavior in a browser — do not claim them from a build result.

## Examples
### Example 1: bare SolidJS + Vite app from an empty directory
- Input: writable directory; `npm create solid@latest . -- --template bare --ssr false` stalls at `What type of project would you like to create?`.
- Procedure: Step 1 (stop the stalled task) → Steps 2–4 (write `package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `src/index.tsx`, `src/App.tsx`, `src/index.css`) → Step 5 (`npm install`) → Step 6 (`npm run build`).
- Expected result: install logs `added 73 packages, and audited 74 packages in 41s` with `found 0 vulnerabilities`; build logs `✓ built in 568ms` and emits `dist/index.html`, `dist/assets/index-*.css`, `dist/assets/index-*.js`.
- Parameterized values: package name (`iceberg` in evidence — replace with the real project name), versions (`solid-js` `^1.9.5`, `vite` `^6.3.5`, `vite-plugin-solid` `^2.11.6`), Node/npm versions (v22.20.0 / 11.8.0 in evidence).

### Example 2: same app plus a second route
- Input: the working app from Example 1 and a user request for a `/timelines` page.
- Procedure: Step 7 (`npm install @solidjs/router`; `<Router>`/`<Route>` in `src/index.tsx`; new `src/pages/Timelines.tsx`; `<A href="/" class="nav-item" activeClass="is-active" end>` and `<A href="/timelines" ...>` in the nav) → rebuild.
- Expected result: `npm run build` green again — `✓ built in 889ms`, `27 modules transformed` (up from 7).
- Parameterized values: route paths (`/`, `/timelines`), page component names, nav labels.

## Evidence
- file_id: `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index: 199, source_part_index: 0
  quote: `What type of project would you like to create?`
  supports: problem/condition — `create-solid@0.7.0` blocks on an interactive prompt even when invoked as `npm create solid@latest . -- --template bare --ssr false`, which is the trigger for hand-scaffolding.

- file_id: `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index: 205, source_part_index: 0
  quote: `Successfully stopped task: bw7f05hh1`
  supports: action — the stalled scaffolder task was terminated before manual scaffolding began.

- file_id: `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index: 208, source_part_index: 0
  quote: `"vite-plugin-solid": "^2.11.6"`
  supports: action — the hand-written `package.json` dependency set (with `vite` `^6.3.5` and `solid-js` `^1.9.5`) that later installed cleanly.

- file_id: `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index: 211, source_part_index: 0
  quote: `plugins: [solidPlugin()]`
  supports: action — the minimal `vite.config.ts` content used for the scaffold.

- file_id: `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index: 213, source_part_index: 0
  quote: `"jsxImportSource": "solid-js"`
  supports: action — the critical `tsconfig.json` setting for compiling Solid JSX.

- file_id: `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index: 218, source_part_index: 0
  quote: `src="/src/index.tsx"`
  supports: action — `index.html` entry path that must match the written `src/index.tsx`.

- file_id: `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index: 236, source_part_index: 0
  quote: `added 73 packages, and audited 74 packages in 41s`
  supports: verification — `npm install` succeeded for the hand-written manifest (log also shows `found 0 vulnerabilities`).

- file_id: `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index: 238, source_part_index: 0
  quote: `✓ built in 568ms`
  supports: verification — the hand-scaffolded app compiled and bundled green (`7 modules transformed`, `dist/` assets listed), establishing the scaffold as working.

- file_id: `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index: 327, source_part_index: 0
  quote: `<Route path="/timelines" component={Timelines} />`
  supports: action — router wiring in `src/index.tsx` (`<Router>` + `<Route>` per page) for the optional multi-page step.

- file_id: `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index: 363, source_part_index: 0
  quote: `<A href="/timelines" class="nav-item" activeClass="is-active">Timelines</A>`
  supports: action — router link pattern with active-state highlighting used instead of plain `<a>`.

- file_id: `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index: 368, source_part_index: 0
  quote: `✓ built in 889ms`
  supports: verification — rebuild after adding `@solidjs/router` and the second page stayed green (`27 modules transformed`), verifying the routing step.
