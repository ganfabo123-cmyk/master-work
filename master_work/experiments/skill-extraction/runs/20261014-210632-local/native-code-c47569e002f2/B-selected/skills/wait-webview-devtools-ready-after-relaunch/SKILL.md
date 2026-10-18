---
name: wait-webview-devtools-ready-after-relaunch
description: Use when a Node CDP script against an Android WebView over `adb forward tcp:9222 localabstract:webview_devtools_remote_$pid` dies with `ECONNRESET` / `socket hang up` right after rebuilding, reinstalling, or force-stopping the app. Helps the agent gate the CDP connection on the devtools HTTP endpoint actually answering, then re-run the evaluation and screenshot. Requires adb device access, curl, Node, and an existing CDP eval script (e.g. `/tmp/cdp-eval.mjs`). Do not use when the build or install itself failed, or when the failure persists after the endpoint has answered `/json`.
---
# Wait for Android WebView DevTools Endpoint Before CDP Eval (ECONNRESET)

## Goal
Diagnose and recover from an `ECONNRESET` / `socket hang up` produced by a Node CDP evaluation script right after an Android WebView app was rebuilt, reinstalled, or relaunched, by gating the CDP connection on the WebView devtools HTTP endpoint actually answering, then re-running the evaluation and screenshot so on-device state is verified.

## Scope
### In scope
- A Node script (e.g. `/tmp/cdp-eval.mjs`) that talks to an Android app's WebView over `adb forward tcp:9222 localabstract:webview_devtools_remote_$pid` and fails with `Error: socket hang up` / `code: 'ECONNRESET'`.
- Failures occurring in a pipeline where typecheck, APK build, `adb install -r`, `am force-stop`/`am start`, and `adb shell pidof` all already succeeded (failure is isolated to the CDP step).
- Re-establishing the port forward from a freshly read pid and polling `http://localhost:9222/json` until the devtools endpoint answers before reconnecting.
- Subsequent verification: CDP evaluation returning page state plus `adb exec-out screencap` screenshot.

### Out of scope
- Build, install, or launch failures (`BUILD EXIT` non-zero, `adb install` failure, app pid never appearing) — fix those first; the readiness wait does not help them.
- ECONNRESET that persists after `curl http://localhost:9222/json` succeeds — the cause is then not endpoint readiness; trajectory did not exercise that branch.
- Non-WebView CDP targets (Chrome on desktop, `adb forward` to other sockets) — pattern is plausible but untested here.
- Inspecting or modifying the content of the CDP eval script itself.

## Inputs
- **Failing command output**: string, from the failed Bash tool_result (the CDP step of the rebuild/deploy pipeline). Required. Must show `Error: socket hang up` with `code: 'ECONNRESET'` while earlier stages report `BUILD EXIT=0` and `Success`. Default: 无.
- **adb binary with device serial**: shell string, agent-provided. Required. Observed form: `adb="$HOME/Android/Sdk/platform-tools/adb -s [REDACTED_IP]:40859"`; serial differs per device. Default: 无.
- **App package / activity**: string, from the project's Android manifest or prior commands. Required. Observed: `net.opendsp.x4x4` launched as `net.opendsp.x4x4/.MainActivity`. Default: 无.
- **Devtools socket template**: string, Android WebView convention. Required. Observed: `localabstract:webview_devtools_remote_$pid` where `$pid` comes from `adb shell pidof <package>`. Default: `webview_devtools_remote_` + pid.
- **Local forward port**: integer. Required. Observed: `9222`. Default: `9222`.
- **CDP eval script**: file path. Required for re-running the evaluation. Observed: `/tmp/cdp-eval.mjs`, invoked as `node cdp-eval.mjs '<expression>'` from `/tmp`; its source content is 轨迹未提供. Default: `/tmp/cdp-eval.mjs`.
- **curl**: CLI, for readiness polling. Required. Used as `curl -sf http://localhost:9222/json`. Default: 无.
- **Screenshot output path**: file path. Optional. Observed: `/tmp/pads7.png`, `/tmp/topinset3.png`, written via `$adb exec-out screencap -p`. Default: 无.

## Outputs
### Artifacts
- **CDP evaluation result**: stdout of `node cdp-eval.mjs ...`, JSON such as `{"connected": true}` or page state like `{"safeTop": "50.333332px", "safeBottom": "24.0px"}`. Location: Bash tool_result. Format: JSON text.
- **Device screenshot**: PNG written to a local path via `$adb exec-out screencap -p > <file>`. Location: e.g. `/tmp/pads7.png`. Format: `image/png`.
- **Readiness confirmation**: the `until curl -sf http://localhost:9222/json ...` loop exiting (implicit in the pipeline reaching the CDP step).

### Success criteria
- The readiness poll returns success before the CDP script starts, the CDP script exits 0 and prints its JSON result, and the pipeline reaches the `shot saved` echo (e.g. tool_result containing `shot saved`).

### Failure criteria
- The pipeline still reports `Error: socket hang up` / `code: 'ECONNRESET'` after the readiness poll has passed.
- The `until curl ...` loop never exits (endpoint never answers) — treat as an app/forward problem, not a readiness race.
- Build/install/launch stages fail (`BUILD EXIT` non-zero or `adb install` error) — the CDP step never becomes meaningful.

## Preconditions
- adb is on PATH or referenced by full path and the target device is online (`adb devices` lists the serial used in commands); otherwise stop and report the device state.
- The app builds and installs: the failing pipeline already showed `BUILD EXIT=0` and `Success` from `adb install -r` — confirm this before attributing the error to readiness.
- The app process is running: `adb shell pidof <package>` returns a pid (the pipeline waits with `until $adb shell pidof ... do sleep 1; done`); if it never returns, stop and report a launch problem.
- `curl` and `node` are available on the host; the CDP eval script exists at the expected path (observed `/tmp/cdp-eval.mjs`).
- The WebView exposes a devtools socket named `webview_devtools_remote_<pid>` for that pid; if `adb forward` fails, stop and report.
- Host port 9222 is free or stale forwards are removable via `adb forward --remove tcp:9222` (the observed pipeline tolerates removal failure with `2>/dev/null`).

## Procedure
### Step 1: Classify the failure from the tool result
- Actions: read the failed Bash output; confirm the failure is `Error: socket hang up` with `code: 'ECONNRESET'` raised inside `node cdp-eval.mjs`, while the same output shows `BUILD EXIT=0` and `Success` (install) earlier.
- Inputs: failing tool_result text.
- Outputs: classification — "CDP endpoint not ready" vs. build/install/launch failure.
- Cautions: `ECONNRESET` alone does not prove readiness is the cause; only treat it as such when build and install succeeded and the app pid was obtained.
- Preserve: the original command text (it shows which pid/port/socket were used).
- Next: proceed to Step 2 only if the failure is confined to the CDP step.

### Step 2: Re-read the app pid and rebuild the port forward
- Actions: run `pid=$($adb shell pidof <package> | tr -d '\r')`, then `$adb forward --remove tcp:9222 2>/dev/null; $adb forward tcp:9222 localabstract:webview_devtools_remote_$pid >/dev/null`.
- Inputs: adb path with serial, app package, port 9222, socket template `webview_devtools_remote_$pid`.
- Outputs: a forward bound to the current pid (the app was relaunched, so any older forward points at a dead socket).
- Cautions: `pidof` can return multiple pids or trailing `\r`; the observed pipeline strips `\r` with `tr -d '\r'`.
- Preserve: do not change the port or socket name used elsewhere in the pipeline.
- Next: go to Step 3.

### Step 3: Gate on the devtools HTTP endpoint answering
- Actions: insert `until curl -sf http://localhost:9222/json >/dev/null 2>&1; do sleep 1; done` immediately after the forward is created and before any `node cdp-eval.mjs` call.
- Inputs: `curl`, `http://localhost:9222/json`.
- Outputs: loop exit once the WebView devtools endpoint responds; the CDP step then starts against a live endpoint.
- Cautions: this loop has no timeout in the observed pattern — if it never exits, the app or forward is broken (see Common Failures); also `adb forward` succeeding does not mean the remote socket is listening yet.
- Preserve: keep the readiness poll in every subsequent rebuild/deploy command (the observed trajectory added it permanently after the first failure).
- Next: run the CDP evaluation.

### Step 4: Re-run the CDP evaluation
- Actions: `cd /tmp && node cdp-eval.mjs '<expression>'` with the original expression (observed: an async expression awaiting `globalThis.device.connect()` with a poll loop, returning state such as `globalThis.device.connected`).
- Inputs: eval script path, expression, forward on port 9222.
- Outputs: JSON result on stdout; non-zero exit means go to Decision Rules.
- Cautions: keep the expression's own internal retry/poll (the observed expression loops up to 25 × 200 ms waiting for `device.connected`), but do not rely on it to mask an unready endpoint.
- Preserve: the original expression semantics — it is the verification of the thing being tested.
- Next: capture the screenshot.

### Step 5: Capture a screenshot as the on-device verification
- Actions: `$adb exec-out screencap -p > <out>.png 2>/dev/null && echo "shot saved"`.
- Inputs: adb with serial, output path.
- Outputs: PNG file plus the `shot saved` marker in the tool_result.
- Cautions: `screencap` works regardless of CDP; a saved screenshot alone does not prove the CDP step succeeded — check both markers.
- Preserve: output path naming so later reads (e.g. `Read /tmp/pads7.png`) match.
- Next: verification per the Verification section.

## Decision Rules
### When the tool result shows `BUILD EXIT=0` + `Success` but `node cdp-eval.mjs` dies with `code: 'ECONNRESET'`
Treat it as a readiness race: the app was relaunched, so re-read the pid, recreate `adb forward tcp:9222 localabstract:webview_devtools_remote_$pid`, add the `until curl -sf http://localhost:9222/json >/dev/null 2>&1; do sleep 1; done` gate, then re-run the CDP script (observed recovery at source_index 689 → success at 690).

### When the same pipeline fails at build or install instead
Do not apply the readiness wait; fix the build/install/launch stage first. The readiness gate only covers the window after the app pid exists.

### When `until curl -sf http://localhost:9222/json ...` never exits
Stop and report: the forward or the WebView devtools socket is not working (wrong pid, app not fully started, or WebView not exposing devtools). Re-read the pid and verify with `adb forward --list` before retrying; the trajectory did not exercise this branch, so no further recovery is asserted.

### When ECONNRESET still occurs after the curl gate passed
The observed trajectory never hit this case; do not claim the readiness fix covers it. Report the exact output and investigate the eval script or the WebSocket side separately.

### When a rebuild/deploy loop repeats
Carry the curl readiness gate forward into every subsequent command (the observed trajectory did this from source_index 707 onward, and every later run completed with `shot saved`).

## Invariants
- Never report the CDP step as working when only the build/install succeeded — the two are separate stages with separate evidence (`BUILD EXIT=0` ≠ CDP connected).
- Do not skip the `/json` readiness gate on retry; a bare re-run can hit the same race.
- Do not reuse an `adb forward` created before a `force-stop`/`am start`; always re-read the pid and recreate the forward.
- Do not modify the CDP eval expression or the app source as part of recovering from this transport error.
- Do not treat `adb forward` returning success as proof the remote devtools socket is listening.
- Do not report success without the observable markers: CDP JSON output and/or `shot saved`.
- Keep the app package, port, and socket template consistent across all commands in one pipeline.

## Common Failures
### Failure: CDP connects before the WebView devtools socket accepts connections
- Symptoms: `Error: socket hang up` emitted on a `ClientRequest`, `code: 'ECONNRESET'`, Node exits non-zero, while `BUILD EXIT=0` and `Success` appear earlier in the same output.
- Causes: the app was force-stopped and restarted, so the devtools socket for the new pid was not yet accepting when the script connected; the port forward was set up but the remote end was not ready. (In this trajectory the assistant attributed it to readiness — "CDP hit the devtools endpoint before it was ready (build/install/launch all succeeded)" — and the fix verified; exact adb-side timing internals were not inspected.)
- Recovery: re-read pid, recreate the forward, insert `until curl -sf http://localhost:9222/json >/dev/null 2>&1; do sleep 1; done`, re-run `node cdp-eval.mjs`.

### Failure: stale port forward after app restart
- Symptoms: endpoint never answers the readiness curl even though the app pid exists.
- Causes: forward bound to a pid from before `am force-stop`; exact failure mode not reproduced in the trajectory.
- Recovery: `adb forward --remove tcp:9222` then re-create with the freshly read pid; verify with `adb forward --list` (verification method not exercised in the trajectory).

### Failure: readiness loop hangs forever
- Symptoms: the Bash call produces no output past the forward step.
- Causes: WebView not exposing devtools or app still starting; cause not confirmed in the trajectory.
- Recovery: bounded-retry variant of the loop plus pid re-check is the logical next action but was not exercised here — report the hang rather than claim a fix.

## Verification
- Readiness gate observed: the `until curl -sf http://localhost:9222/json >/dev/null 2>&1; do sleep 1; done` step completes before `node cdp-eval.mjs` starts (i.e. the command chain reaches the script at all).
- CDP result present: the tool_result contains the JSON produced by the eval expression, e.g. `{"connected": true}` (as in the recovery run) or the requested page-state fields.
- Screenshot marker: the same tool_result ends with `shot saved`, and the PNG file can be read back (e.g. `Read /tmp/pads7.png` returns `image/png`).
- No transport error: the output contains no `Error: socket hang up` and no `code: 'ECONNRESET'`.
- Repeatable across rebuilds: subsequent rebuild/deploy pipelines that include the same gate also end in `shot saved` (observed for several later runs in the trajectory).
- For state assertions, the value itself is the evidence (e.g. `safeTop` reported as `50.333332px`, `safeBottom` as `24.0px` in a later run) — check the value, not just the exit code.

## Examples
### Example 1: recover a failed deploy-and-screenshot run
- Input: pipeline output `Exit code 1 / OK / BUILD EXIT=0 / Success / ... Error: socket hang up ... code: 'ECONNRESET'` (Node.js v22.21.0) from a command that rebuilt the APK, ran `adb install -r`, `am force-stop` + `am start`, waited for the pid, forwarded `tcp:9222`, then ran `node cdp-eval.mjs`.
- Procedure: Step 1 classify (build/install OK → readiness race); Step 2 re-read pid and recreate forward; Step 3 insert `until curl -sf http://localhost:9222/json >/dev/null 2>&1; do sleep 1; done`; Step 4 re-run `node cdp-eval.mjs '(async()=>{await globalThis.device.connect();for(let k=0;k<25&&!globalThis.device.connected;k++)await new Promise(r=>setTimeout(r,200));return {connected:globalThis.device.connected};})()'`; Step 5 `screencap` to `/tmp/pads7.png`.
- Expected result: tool_result shows `{"connected": true}` followed by `shot saved`; no ECONNRESET.
- Parameterized values: package `net.opendsp.x4x4`, serial `[REDACTED_IP]:40859`, port `9222`, socket `webview_devtools_remote_$pid`, script `/tmp/cdp-eval.mjs`, screenshot `/tmp/pads7.png`.

### Example 2: keep the gate in every later rebuild loop
- Input: a follow-up rebuild needing on-device verification (e.g. reading computed CSS values).
- Procedure: same chain as Example 1 with the curl gate after the forward: `... $adb forward tcp:9222 localabstract:webview_devtools_remote_$pid >/dev/null && until curl -sf http://localhost:9222/json >/dev/null 2>&1; do sleep 1; done; cd /tmp && node cdp-eval.mjs '<expression>' && $adb exec-out screencap -p > /tmp/topinset3.png ...`.
- Expected result: single-pass success; observed output `OK / BUILD=0 / ... / Success / {"safeTop": "50.333332px", "safeBottom": "24.0px"} / shot saved`.
- Parameterized values: expression returns `getComputedStyle(document.documentElement)` custom properties; screenshot `/tmp/topinset3.png`; port and socket as above.

## Evidence
- **problem** — file_id `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-05`, source_index 686, source_part_index 0. Quote: `Exit code 1\nOK\nBUILD EXIT=0\nSuccess\nnode:events:497\n      throw er; // Unhandled 'error' event\n      ^\n\nError: socket hang up` (the same tool_result continues through `Emitted 'error' event on ClientRequest instance at:` and ends `  code: 'ECONNRESET'\n}\n\nNode.js v22.21.0`). Supports: the CDP step failed with ECONNRESET after build and install already succeeded, isolating the fault to endpoint readiness.
- **problem (failing command context)** — same file, source_index 685, source_part_index 0. Quote: `until $adb shell pidof net.opendsp.x4x4 >/dev/null 2>&1; do sleep 1; done; pid=$($adb shell pidof net.opendsp.x4x4 | tr -d '\\r') && $adb forward --remove tcp:9222 2>/dev/null; $adb forward tcp:9222 localabstract:webview_devtools_remote_$pid >/dev/null && cd /tmp && node cdp-eval.mjs`. Supports: the pid wait and forward existed, yet the CDP script still crashed — waiting for the pid is not sufficient.
- **action** — same file, source_index 689, source_part_index 0. Quote: `until curl -sf http://localhost:9222/json >/dev/null 2>&1; do sleep 1; done; cd /tmp && node cdp-eval.mjs` (within the retry command that also re-reads the pid and recreates `adb forward tcp:9222 localabstract:webview_devtools_remote_$pid`). Supports: the fix is a readiness gate on the devtools HTTP endpoint before launching the CDP script.
- **action (diagnosis)** — same file, source_index 688, source_part_index 0. Quote: `CDP hit the devtools endpoint before it was ready (build/install/launch all succeeded). Let me retry the connect + screenshot now that the app's up.` Supports: the agent's stated cause, consistent with the tool evidence; it is a claim, not verification.
- **verification** — same file, source_index 690, source_part_index 0. Quote: `{\n  "connected": true\n}\nshot saved\nShell cwd was reset to /home/USER/Code/tracks-dsp`. Supports: after adding the readiness gate, the CDP evaluation succeeded and the screenshot was captured — the exact problem from index 686 is resolved.
- **verification (repeat in later pipelines with the same gate)** — same file, source_index 708, source_part_index 0. Quote: `OK\nBUILD EXIT=0\nSuccess\nshot saved\nShell cwd was reset to /home/USER/Code/tracks-dsp`. Supports: carrying the gate into subsequent rebuild/deploy commands keeps working.
- **verification (state assertion via the gated channel)** — same file, source_index 851, source_part_index 0. Quote: `{\n  "safeTop": "50.333332px",\n  "safeBottom": "24.0px"\n}\nshot saved\nShell cwd was reset to /home/USER/Code/tracks-dsp`. Supports: the gated CDP channel returns real page state, not just a connection.
