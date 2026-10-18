---
name: scaffold-multiroute-solidjs-vite-app
description: Use when you need a client-routed SolidJS app in a non-interactive shell where `create-solid` hangs on prompts, or when a SolidJS SPA breaks on CSS-import type errors or cross-route layout rules. Helps the agent scaffold the project by hand, wire `@solidjs/router`, split CSS per page, and verify each increment with the production build. Do not use when SSR/SolidStart is required, when an interactive terminal is available for the official scaffolder, or for React/Remix projects.
---
# Scaffold a Multi-Route SolidJS + Vite SPA Manually and Keep the Build Green

## Goal
Produce a working client-routed SolidJS + Vite + TypeScript SPA (scaffolded by hand because the official scaffolder is interactive), with `@solidjs/router` navigation, per-page CSS imports that typecheck, and a production build that stays green after every route is added.

## Scope
### In scope
- Non-interactive environments where `npm create solid@latest` stalls on the project-type prompt despite flags; manual creation of `package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `src/index.tsx`.
- Adding `@solidjs/router`: `<Router>`/`<Route>` wiring and nav links via `<A>` with `activeClass="is-active"` (plus `end` for the home route so `/` matches exactly).
- Splitting styles into shared tokens (`src/index.css`) plus one CSS file per page imported at the top of each page component, and fixing the TypeScript complaint about CSS imports with `src/vite-env.d.ts` (`/// <reference types="vite/client" />`).
- Layout gotcha: locking one route's viewport without breaking scrolling on the other routes (scope `overflow: hidden` to the page's own root element).
- Verification with `npm install` + `npm run build` after each increment.

### Out of scope
- SolidStart / SSR setups and server rendering.
- Visual design decisions, color palettes, fonts.
- Other frameworks (React, Remix); plain static HTML sites.

## Inputs
- **Node.js + npm** — type: runtime — source: preinstalled — required: yes — constraints: observed v22.20.0 / npm 11.8.0; network access needed for `npm install` — default: 无.
- **Target project directory** — type: path — source: user/working dir — required: yes — constraints: should be empty or contain only files you intend to keep (the scaffold writes root files) — default: 无.
- **Package versions** — type: dependency pins — source: package.json written by the agent — required: no — constraints: observed working set: `solid-js ^1.9.5`, `vite ^6.3.5`, `vite-plugin-solid ^2.11.6`, later `@solidjs/router` — default: 轨迹未提供 beyond these.
- **Page content and routes** — type: list of (path, component, page CSS file) — source: user requirements — required: yes for multi-route builds — constraints: each page gets its own CSS file; shared tokens stay in `index.css` — default: 无.
- **Scroll behavior per route** — type: boolean (locked viewport vs. normal scroll) — source: user requirements — required: no — constraints: a locked-viewport route must apply `overflow: hidden` on its own root container only — default: normal scrolling.

## Outputs
### Artifacts
- `package.json`, `vite.config.ts`, `tsconfig.json`, `index.html` in the project root.
- `src/index.tsx` (render + `<Router>` with all routes), `src/vite-env.d.ts`, `src/index.css` (tokens + shared header/footer classes).
- `src/App.tsx` + `src/home.css` for the home route; `src/pages/<Name>.tsx` + matching page CSS for each additional route.

### Success criteria
- `npm install` completes with no vulnerabilities reported; `npm run build` exits 0 and emits `dist/` assets (observed: `built in 568ms` for 7 modules, `built in 889ms` after routes were added).
- Every route is registered in the router and reachable from nav via `<A>`; the home link highlights only on `/` (thanks to `end`).
- TypeScript accepts `import '../page.css'` in page components without disabling any checks.

### Failure criteria
- The scaffolder hangs waiting for input; the build fails on CSS imports; or a layout fix for one route visibly breaks another route (e.g. the second route stops scrolling) — each must be resolved or explicitly reported before claiming done.

## Preconditions
- A non-interactive shell is confirmed (commands run through an agent tool with no TTY); if a real interactive terminal exists, prefer `npm create solid@latest` with prompts answered normally.
- `npm` can reach the registry (the observed install added 73 packages in 41s).
- The project directory is either empty or the user has approved overwriting root config files; do not delete unrelated files.
- TypeScript strictness must remain on — the CSS-import problem is fixed with a type reference file, not by relaxing `tsconfig`.
- The user has stated whether any route must be a locked (non-scrolling) viewport on desktop.

## Procedure
### Step 1: Try the scaffolder briefly, then abandon it if it blocks
Actions: run `npm create solid@latest . -- --template bare --ssr false`. Watch the output file: if it stops at the prompt `What type of project would you like to create?` (options `SolidStart` / `SolidJS + Vite` / `Library`) even with `--yes`-style flags, kill the task and go manual — flags do not bypass the interactive menu in this version (create-solid@0.7.0).
Inputs: project dir. Outputs: either a scaffolded app, or a confirmed "interactive-only" verdict. Cautions: don't wait indefinitely; the prompt never resolves without a TTY. Preserve: nothing from the aborted run (verify the dir is clean before continuing). Next: Step 2.

### Step 2: Write the project files by hand
Actions: create `package.json` with `"type": "module"`, scripts `dev`/`build`/`preview` (vite), deps `solid-js`, devDeps `vite` + `vite-plugin-solid`; `vite.config.ts` exporting `defineConfig({ plugins: [solidPlugin()] })`; `tsconfig.json` with `"jsx": "preserve"`, `"jsxImportSource": "solid-js"`, `"moduleResolution": "bundler"`, `"strict": true`, `"include": ["src"]`; `index.html` with `<div id="root">` and `<script type="module" src="/src/index.tsx">`; `src/index.tsx` calling `render(() => <App />, document.getElementById('root')!)`.
Inputs: none beyond the plan. Outputs: five root/src files. Cautions: keep `"jsx": "preserve"` — vite-plugin-solid compiles JSX, tsc must not. Next: Step 3.

### Step 3: Install and get the first green build
Actions: `npm install`, then `npm run build`. Expect a small bundle (observed: 7 modules, ~10 kB JS, `built in 568ms`).
Inputs: the written files. Outputs: `dist/` + build log. Cautions: a clean install (`added 73 packages ... found 0 vulnerabilities`) confirms the version set is coherent. Next: Step 4.

### Step 4: Add client routing
Actions: `npm install @solidjs/router`; rewrite `src/index.tsx` to wrap the app: `<Router><Route path="/" component={App} /><Route path="/timelines" component={Timelines} />...</Router>`; convert nav anchors to `<A href="/" class="nav-item" activeClass="is-active" end>Home</A>` and `<A href="/timelines" class="nav-item" activeClass="is-active">Timelines</A>`.
Inputs: page components. Outputs: router + nav. Cautions: plain `<a href="/">` causes full page reloads; `end` is required on the home link or it stays active on every route. Next: Step 5.

### Step 5: Split CSS per page and fix the type error it causes
Actions: keep design tokens, reset, and truly shared classes (page header/footer/back-link) in `src/index.css`; move route-specific rules into `src/home.css`, `src/timelines.css`, etc.; import each at the top of its page component (`import '../timelines.css'`). When TypeScript flags the CSS import, add `src/vite-env.d.ts` containing `/// <reference types="vite/client" />` instead of loosening tsconfig.
Inputs: the monolithic stylesheet. Outputs: 1 shared + N page CSS files; a passing typecheck/build. Cautions: when renaming shared classes during the split (e.g. `tl-header` → `page-header`), grep the page components for the old names so JSX and CSS stay in sync. Next: Step 6.

### Step 6: Lock a viewport route correctly (only if required)
Actions: for a route that must not scroll on desktop, put `height: 100vh; overflow: hidden;` on that page's own root element (e.g. `.viewport`), never on `html, body, #root`.
Inputs: scroll requirement per route. Outputs: scoped CSS. Cautions: a global `html, body, #root { overflow: hidden }` breaks scrolling on every other route — in the source session the user reported "the scrolling in the timelines page is broken fix it" right after such a global rule was introduced, and the fix was to remove it globally and re-add it on `.viewport` only (this correction was applied but not re-verified in the trace). Next: Step 7.

### Step 7: Verify after every route addition
Actions: after each new route/page/CSS file, run `npm run build`; the observed healthy log grows from `7 modules transformed` to `27 modules transformed` while staying `is_error: false`.
Inputs: the app after each increment. Outputs: build log. Cautions: do not batch five routes and build once — a class rename or missing import then becomes hard to attribute. Next: done when build is green and all routes are linked.

## Decision Rules
### When the scaffolder blocks on a prompt in a non-interactive shell
Stop the task and scaffold manually (Step 2); repeating the command with more flags was not observed to help — create-solid@0.7.0 still showed `What type of project would you like to create?`.

### When TypeScript errors on `import './page.css'` in a `.tsx` file
Add `src/vite-env.d.ts` with `/// <reference types="vite/client" />`; do not delete `strict`, do not add `// @ts-ignore`, do not exclude the file from `tsconfig`.

### When a nav item must highlight only on the exact home route
Use `<A ... end>` on the `/` link; without it the prefix match keeps Home active on all routes.

### When one route needs a locked viewport and others need scrolling
Apply `overflow: hidden` to the locked route's own root container; never to `html`/`body`/`#root`, which are shared by every route in the SPA.

### When page CSS grows past what the page needs
Extract the truly shared parts (tokens, reset, page header/footer) into `index.css` and keep page-unique selectors in the page file; rename shared classes to page-neutral names (`page-header`, not `tl-header`) and grep-update the JSX.

## Invariants
- Run the production build after every increment; never report a route as "live" on the strength of having written files only.
- Keep `strict: true` and fix type errors at the type level (vite-env.d.ts), not by relaxing compiler options.
- Each route owns its CSS file; global CSS holds only tokens/reset/shared page chrome.
- No global rule may change behavior on routes other than the one it was written for (the `overflow: hidden` incident).
- Use `<A>` for internal navigation; never leave internal `<a href="/">` links that force full reloads.
- Don't fabricate build output: quote the actual module count/exit status from the run, or say it wasn't run.

## Common Failures
### Failure: Scaffolder appears to run but never finishes
Symptoms: the background task sits at the project-type prompt (`What type of project would you like to create?`) with flags like `--template bare --ssr false` supplied. Cause: create-solid@0.7.0 requires interactive input for the project type; flags don't select it. Recovery: stop the task, scaffold manually per Step 2, and verify with install+build.

### Failure: TS diagnostic on CSS imports after splitting styles
Symptoms: the editor/tsc flags `import './home.css'` in `.tsx` even though Vite bundles it fine. Cause: no Vite client types in the TS project. Recovery: add `src/vite-env.d.ts` with `/// <reference types="vite/client" />`; the diagnostic resolves and the build stays green.

### Failure: Home nav item stays active on every route
Symptoms: `is-active` on Home while viewing other routes. Cause: `<A href="/">` prefix-matches all paths. Recovery: add `end` to the home link.

### Failure: Second route cannot scroll
Symptoms: a newly added route renders but the page won't scroll on desktop. Cause: a global `html, body, #root { overflow: hidden }` introduced to lock the home viewport leaks to all routes. Recovery: remove the global rule and put `overflow: hidden` on the locked page's own root element. Note: in the source trace this correction was applied but never re-verified, so confirm scrolling empirically after fixing.

### Failure: Renamed shared CSS classes leave stale JSX
Symptoms: after extracting shared styles (`tl-header` → `page-header`), some headers lose styling. Cause: not all components updated. Recovery: grep the old class names across `src/` and update every occurrence before building.

## Verification
1. `npm install` exits 0; log shows packages added and `found 0 vulnerabilities` (observed: `added 73 packages, and audited 74 packages in 41s`, then `added 1 package, and audited 75 packages in 4s` after the router).
2. `npm run build` exits 0 and reports transformed modules plus a bundle (observed: `7 modules transformed` / `built in 568ms` initially; `27 modules transformed` / `built in 889ms` after five routes existed).
3. Every route appears in `src/index.tsx` as a `<Route>` and in the nav as an `<A>`; the home link alone carries `end`.
4. `src/vite-env.d.ts` exists so CSS imports typecheck without compiler relaxations.
5. If a locked-viewport route exists: load each other route and confirm the page scrolls (the trace contains no automated check for this — it must be observed in a browser or reported as unverified).

## Examples
### Example 1: Manual scaffold after the interactive scaffolder stalls
Input: empty project dir; non-interactive shell; `npm create solid@latest . -- --template bare --ssr false` hangs at `What type of project would you like to create?`.
Procedure: kill the task; write `package.json` (deps `solid-js ^1.9.5`; devDeps `vite ^6.3.5`, `vite-plugin-solid ^2.11.6`; scripts `dev`/`build`/`preview`), `vite.config.ts` with `plugins: [solidPlugin()]`, `tsconfig.json` with `"jsx": "preserve"` + `"jsxImportSource": "solid-js"`, `index.html` loading `/src/index.tsx`, `src/index.tsx` with `render(() => <App />, document.getElementById('root')!)`; then `npm install && npm run build`.
Expected result: install reports ~73 packages with 0 vulnerabilities; build emits `dist/` and prints `built in 568ms`.

### Example 2: Adding a second route with its own CSS and fixing the TS complaint
Input: working single-route app; new page `src/pages/Timelines.tsx` importing `../timelines.css`.
Procedure: `npm install @solidjs/router`; wrap render in `<Router>` with `<Route path="/" component={App} />` and `<Route path="/timelines" component={Timelines} />`; nav `<A href="/" ... end>Home</A>`, `<A href="/timelines" activeClass="is-active">Timelines</A>`; on the CSS-import type error add `src/vite-env.d.ts` with `/// <reference types="vite/client" />`; run `npm run build`.
Expected result: build passes with `27 modules transformed`; no tsconfig relaxations were made. Parameterized values: page name `Timelines`, route `/timelines`, CSS file `timelines.css`.

## Evidence
Quotes from `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01` (full-content slice, events ≤ 409) and `...__segment-02` (tool-call arguments and `is_error` flags visible; result bodies collapsed).

- **problem (scaffolder is interactive-only)** — segment-01, source_index 196 (tool_call): command `npm create solid@latest . -- --template bare --ssr false`; source_index 199 (tool_result): visible prompt text `What type of project would you like to create?` with option `SolidStart`; source_index 205 (tool_result): `Successfully stopped task`; source_index 207 (assistant_text): `is interactive-only. I'll scaffold manually instead`. supports: the manual-scaffold decision, not a guess about flags.
- **action (manual scaffold)** — segment-01, source_index 208 (Write package.json): `"solid-js": "^1.9.5"`, `"vite": "^6.3.5"`, `"vite-plugin-solid": "^2.11.6"`; source_index 211 (Write vite.config.ts): `import solidPlugin from 'vite-plugin-solid'` / `plugins: [solidPlugin()]`; source_index 213 (Write tsconfig.json): `"jsx": "preserve"`, `"jsxImportSource": "solid-js"`. supports: the exact minimal file set.
- **verification (scaffold works)** — segment-01, source_index 236 (tool_result): `added 73 packages, and audited 74 packages in 41s` and `found 0 vulnerabilities`; source_index 238 (tool_result): `7 modules transformed` and `built in 568ms`. supports: install + production build succeeded for the hand-written scaffold.
- **action (router)** — segment-01, source_index 323 (tool_result): `added 1 package, and audited 75 packages in 4s`; source_index 327 (Edit src/index.tsx): `<Router>` with `<Route path="/" component={App} />` and `<Route path="/timelines" component={Timelines} />`; source_index 363 (Edit App.tsx): `<A href="/" class="nav-item" activeClass="is-active" end>Home</A>` and `<A href="/timelines" class="nav-item" activeClass="is-active">Timelines</A>`.
- **verification (multi-route build stays green)** — segment-01, source_index 368 (tool_result): `27 modules transformed` and `built in 889ms`. supports: the app with added routes still builds.
- **problem (CSS import type error)** — segment-02, source_index 489 (assistant_text): `That's a TypeScript config issue — Vite handles CSS imports fine at runtime, but TS doesn't know about them.`; action, source_index 493 (Write src/vite-env.d.ts): `/// <reference types="vite/client" />`; per-page imports at source_index 500/502 (Edits): `import '../timelines.css'`, `import '../connections.css'`; verification: source_index 521 (tool_result) has `"is_error": false` for the post-split `npm run build` (body collapsed in this slice).
- **problem (global overflow breaks other routes) + action** — segment-01, source_index 374 (user_text): `the scrolling in the timelines page is broken fix it`; source_index 378 (assistant_text): `the `overflow: hidden` on `html/body/#root` that locks the home page to viewport is bleeding into the Timelines page`; source_index 379 (Edit): old_string `html, body, #root {` … `overflow: hidden;` removed; source_index 382 (Edit): `overflow: hidden;` added to `.viewport`. supports: the scoping rule and its causal incident; note the correction itself was never re-verified in the trace, which is why the skill requires empirical confirmation.
