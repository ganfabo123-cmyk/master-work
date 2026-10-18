---
name: scaffold-solidjs-vite-noninteractive
description: Use when `npm create solid` / `create-solid` stalls at an interactive prompt in a non-TTY agent shell even after passing flags. Helps the agent write the minimal Vite + SolidJS + TypeScript project files by hand, install dependencies, and verify with a production build. Requires npm registry access and Node (trajectory used Node v22.20.0, npm 11.8.0). Do not use when the scaffolder completes non-interactively, when SolidStart is required, or when only a build is impossible to run.
---
# Manually Scaffold a Vite + SolidJS App When create-solid Is Interactive-Only

## Goal
Create a working Vite + SolidJS + TypeScript project by hand when the `create-solid` scaffolder blocks on an interactive prompt in a non-TTY agent shell, and prove it works with a successful `npm install` plus `vite build`.

## Scope
### In scope
- Detecting that `create-solid` is stalled at an interactive prompt (even with `--template` / `--ssr` flags) and stopping the background task.
- Writing the minimal file set by hand: `package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `src/index.tsx`, `src/index.css`, `src/App.tsx`.
- Installing dependencies and verifying with a production build; re-verifying after later additions such as `@solidjs/router` and extra pages.

### Out of scope
- SolidStart (server) projects and other `create-solid` templates.
- Bypassing the scaffolder with different flag combinations — flags did not remove the prompt in the trajectory.
- Runtime/dev-server behavior: only `npm install` and `vite build` were verified; no `npm run dev` run for this app appears in the trajectory.
- Styling frameworks (Tailwind etc.), deployment, and publishing.

## Inputs
- Target project directory — path — task environment — required — must exist and be writable; in the trajectory a previous framework's files were removed first while keeping `DESIGN.MD` and `CLAUDE.MD`; default: 无
- Dependency versions — strings — agent-authored `package.json` — not required — trajectory used `solid-js` `^1.9.5`, `vite` `^6.3.5`, `vite-plugin-solid` `^2.11.6`; default: the trajectory versions
- Node and npm — runtime — host environment — required — observed: Node v22.20.0, npm 11.8.0; default: 无
- npm registry access — network — host environment — required for install and build; default: 无
- App entry content (`src/App.tsx`, `src/index.css`) — strings — task design requirements — required — the page content itself is project-specific; default: 无
- Optional router package — string — task requirement — not required — `@solidjs/router` when more than one page is needed; default: 无

## Outputs
### Artifacts
- `<project>/package.json` — scripts `dev: vite`, `build: vite build`, `preview: vite preview`; deps `solid-js`; devDeps `vite`, `vite-plugin-solid`.
- `<project>/vite.config.ts` — `defineConfig({ plugins: [solidPlugin()] })`.
- `<project>/tsconfig.json` — `jsx: "preserve"`, `jsxImportSource: "solid-js"`, `moduleResolution: "bundler"`, `strict`, `noEmit`, `include: ["src"]`.
- `<project>/index.html` — `<div id="root">` plus `<script type="module" src="/src/index.tsx">`.
- `<project>/src/index.tsx`, `<project>/src/index.css`, `<project>/src/App.tsx` (later optionally `<project>/src/pages/*.tsx`).
- `<project>/node_modules/` after install; `<project>/dist/` after build.

### Success criteria
- `npm install` reports added packages and `found 0 vulnerabilities`.
- `npm run build` completes with `modules transformed` and `built in <ms>ms` and emits `dist/index.html`.
- Re-running the build after later page/router additions still succeeds.

### Failure criteria
- The scaffolder prompt reappears or the stalled task is left running.
- `npm install` fails (registry/auth/network).
- `npm run build` reports transform or TypeScript-adjacent errors.

## Preconditions
- The shell is non-interactive: confirm the scaffolder actually stalls (background output stops at the project-type question) before abandoning it; if it completes on its own, use its output instead of this skill.
- Node and npm are installed and `npm` can reach the registry (the trajectory install added 73 packages without authentication issues).
- The project directory is writable and its contents may be created/overwritten; unrelated files that must be preserved are identified first.
- Permission to stop the stalled background task (TaskStop or equivalent) so two creators never run concurrently.

## Procedure
### Step 1: Confirm the scaffolder is interactive-only and stop it
- Actions: run `npm create solid@latest <project> -- --template bare --ssr false`, let it start in the background, read its interim output; when the output stops at the project-type question, stop the task with the task-stop tool.
- Inputs: project path, flag set.
- Outputs: confirmation that even with `--template` and `--ssr` flags the prompt `What type of project would you like to create?` appears and no files are produced.
- Cautions: npm may wrap the warning `npm warn exec The following package was not found and will be installed: create-solid@0.7.0` in a PowerShell `NativeCommandError` — that noise is not the failure; the prompt stall is. Never leave the stalled creator running alongside manual writes.
- Preserve: existing files in the directory (identify what must be kept before Step 2).
- Next condition: task stopped, directory state known → Step 2.

### Step 2: Write `package.json`
- Actions: create `package.json` with `name`, `private: true`, `version`, `"type": "module"`, scripts `dev` → `vite`, `build` → `vite build`, `preview` → `vite preview`, dependency `solid-js`, devDependencies `vite` and `vite-plugin-solid`.
- Inputs: project path, version pins.
- Outputs: `<project>/package.json`.
- Cautions: `"type": "module"` is required by the ESM-style config and entry files; keep versions consistent with what will be installed.
- Preserve: nothing else in the file beyond the scaffold needs.
- Next condition: file written → Step 3.

### Step 3: Write `vite.config.ts`
- Actions: `import { defineConfig } from 'vite'` and `import solidPlugin from 'vite-plugin-solid'`, export `defineConfig({ plugins: [solidPlugin()] })`.
- Inputs: none beyond project path.
- Outputs: `<project>/vite.config.ts`.
- Cautions: without `vite-plugin-solid`, JSX files are not compiled as Solid.
- Preserve: no extra config (no SSR/server options needed for a client-only page).
- Next condition: file written → Step 4.

### Step 4: Write `tsconfig.json`
- Actions: set `target`/`module` `ESNext`, `moduleResolution` `bundler`, `jsx` `preserve`, `jsxImportSource` `solid-js`, `strict` true, `noEmit` true, `isolatedModules` true, `include` `["src"]`.
- Inputs: none.
- Outputs: `<project>/tsconfig.json`.
- Cautions: `jsxImportSource` must be `solid-js` or JSX resolves to the wrong runtime; `include: ["src"]` produces an editor diagnostic until `src/` exists — expected, it resolves once Step 6 writes the files.
- Preserve: do not copy type-check settings from a different framework.
- Next condition: file written → Step 5.

### Step 5: Write `index.html`
- Actions: standard HTML5 shell with `<div id="root"></div>` and `<script type="module" src="/src/index.tsx"></script>`.
- Inputs: project path, page title.
- Outputs: `<project>/index.html`.
- Cautions: the script path must match the entry written in Step 6 exactly (`/src/index.tsx`).
- Preserve: none.
- Next condition: file written → Step 6.

### Step 6: Write the `src/` entry files
- Actions: `src/index.tsx` — `render(() => <App />, document.getElementById('root')!)` from `solid-js/web` plus the CSS import; `src/index.css` — base styles; `src/App.tsx` — the page component using `class` attributes and `createSignal` where interactivity is needed.
- Inputs: app content requirements.
- Outputs: the three files under `<project>/src/`.
- Cautions: Solid uses `class`, not `className`; the entry must import the CSS file so styles bundle.
- Preserve: design-system tokens or content dictated by project docs.
- Next condition: files written → Step 7.

### Step 7: Install and build
- Actions: `npm install`, then `npm run build`.
- Inputs: project path.
- Outputs: install summary (`added N packages`, `found 0 vulnerabilities`) and build output (`modules transformed`, `built in <ms>ms`, `dist/index.html`).
- Cautions: a successful install does not prove the app compiles; the build is the required check. This verifies compilation and bundling only — no dev-server run was performed for this app in the trajectory.
- Preserve: `package-lock.json` produced by the install.
- Next condition: build passes → report success; if a second page or routing is required → Step 8.

### Step 8 (optional): Add routing and re-verify
- Actions: `npm install @solidjs/router`, wrap the entry in `<Router>` with `<Route>` entries, convert internal links to `<A href="...">` with `activeClass`, add the new page component, then run `npm run build` again.
- Inputs: route table, page components.
- Outputs: updated lockfile and a second passing build (module count grows: 7 modules → 27 modules observed).
- Cautions: plain `<a>` tags cause full page reloads instead of client navigation; each new page must be re-verified with a fresh build.
- Preserve: existing routes and components.
- Next condition: second build passes → done.

## Decision Rules
### When scaffolder output stops at a question prompt with no progress
Stop the task and scaffold manually; `--template bare --ssr false` did not skip the project-type prompt in the trajectory.

### When npm stderr noise (`npm warn exec ...`) appears in PowerShell
Ignore the wrapper; decide success by whether files exist and by later install/build results, not by the warning text.

### When the editor or tooling reports a missing `src` include
Expected right after Step 4; it resolves once Step 6 creates `src/`. Do not change `include` to silence it.

### When a build passes but more pages or routes are added later
Re-run `npm run build` after every structural addition; the trajectory re-verified after adding the router and a second page (7 → 27 modules transformed).

### When the task later requires navigation between pages
Install `@solidjs/router` and use `<A>` links with `activeClass` instead of plain anchors; verified by the subsequent passing build, not by runtime testing.

## Invariants
- Do not leave a stalled interactive scaffolder task running while writing files manually.
- Do not delete files outside the project directory or files the task said to preserve.
- Do not change dependency versions in `package.json` without re-running `npm install`.
- Do not claim the app runs in a browser or dev server based only on `vite build` — the trajectory verified install and build only.
- Do not skip the build after adding routes, pages, or config changes.
- Do not report npm stderr warnings as failures, or a passing build as an install check; each claim needs its own output.
- Do not invent templates or SSR behavior: this is a client-only Vite app.

## Common Failures
### Failure: create-solid stalls at the project-type prompt
- Symptoms: background task output ends at `What type of project would you like to create?` with the `SolidStart / SolidJS + Vite / Library` options and no further progress; no project files are created; the command was launched with `-- --template bare --ssr false`.
- Causes: the scaffolder requires an interactive terminal for at least one question; the flags used do not bypass it (root cause inside the tool not investigated further).
- Recovery: stop the task (`Successfully stopped task: <id>`), then follow Steps 2–7 to write the project by hand; verify with install + build.

### Failure: `src` include diagnostic right after writing tsconfig
- Symptoms: tooling reports the `src` folder does not exist after Step 4.
- Causes: `include: ["src"]` was written before any `src/` file exists.
- Recovery: proceed to Step 6; the diagnostic resolves when `src/index.tsx` is created — do not edit `tsconfig.json` for it.

### Failure: build fails after later edits
- Symptoms: `npm run build` prints transform errors instead of `built in <ms>ms`.
- Causes: not observed in this trajectory — every recorded build passed, so no cause list is available.
- Recovery: read the reported file/line from the build output, fix that source file, and re-run the build; do not report success until a clean build is captured.

## Verification
Check each item against raw tool output (do not mark them done in advance):
- Stopped task: the task-stop result names the `npm create solid...` command (e.g. `Successfully stopped task: <id>`).
- Files exist: a listing of `<project>` shows `package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, and `src/` with `index.tsx`, `index.css`, `App.tsx`.
- Install: `npm install` output contains `added <N> packages, and audited <M> packages` and `found 0 vulnerabilities`.
- Build: `npm run build` output contains `modules transformed`, `built in <ms>ms`, and emits `dist/index.html` plus hashed `dist/assets/*` files.
- Rebuild after changes: a fresh build still passes after adding the router and any new page (trajectory: `7 modules transformed` first, `27 modules transformed` after).
- Scope of the claim: no dev-server or browser run is required by this skill's success criteria, and none was captured in the trajectory — do not claim runtime behavior.

## Examples
### Example 1: Blank directory → verified SolidJS app
- Input: empty (or pre-cleaned) Windows project directory `<project>`; command `npm create solid@latest . -- --template bare --ssr false` stalls.
- Procedure: Step 1 (observe `What type of project would you like to create?`, stop the task), Steps 2–6 (write the seven files), Step 7 (`npm install`, `npm run build`).
- Expected result: install reports `added 73 packages, and audited 74 packages in 41s` / `found 0 vulnerabilities`; build reports `7 modules transformed` and `built in 568ms` with `dist/index.html` emitted.
- Parameterized values: project path, package name, versions (`solid-js ^1.9.5`, `vite ^6.3.5`, `vite-plugin-solid ^2.11.6`), page content.

### Example 2: Add a second page with client routing
- Input: the verified app from Example 1 plus a requirement for a `/timelines` page.
- Procedure: Step 8 — `npm install @solidjs/router`, wrap entries in `<Router>`/`<Route>`, replace nav anchors with `<A activeClass="is-active">`, add `src/pages/Timelines.tsx`, re-run `npm run build`.
- Expected result: `added 1 package, and audited 75 packages`, then a build showing `27 modules transformed` and `built in 889ms`.
- Parameterized values: route paths, component names, package name/version of the router.

## Evidence
- problem — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 199, source_part_index 0, quote `What type of project would you like to create?` — supports: even with `--template bare --ssr false`, `create-solid` stops at an interactive question in the agent shell, so manual scaffolding is required.
- action — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 205, source_part_index 0, quote `Successfully stopped task: bw7f05hh1` — supports: the stalled scaffolder was terminated before manual file creation, avoiding two concurrent creators.
- action — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 208, source_part_index 0, quote `"vite-plugin-solid": "^2.11.6"` — supports: hand-written `package.json` pins `vite-plugin-solid` as the build-time Solid compiler together with `vite`.
- action — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 213, source_part_index 0, quote `"jsxImportSource": "solid-js"` — supports: the manual `tsconfig.json` configures the Solid JSX runtime, a required piece of the scaffold.
- verification — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 236, source_part_index 0, quote `added 73 packages, and audited 74 packages in 41s` — supports: dependency installation succeeded against the hand-written `package.json`.
- verification — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 238, source_part_index 0, quote `7 modules transformed.` — supports: the first production build compiled and bundled the manually scaffolded app (`built in 568ms`, `dist/index.html` emitted).
- verification — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 368, source_part_index 0, quote `27 modules transformed.` — supports: after adding `@solidjs/router`, a second route, and a full second page, the build still passes — the scaffold supports growth, not just the initial app.
