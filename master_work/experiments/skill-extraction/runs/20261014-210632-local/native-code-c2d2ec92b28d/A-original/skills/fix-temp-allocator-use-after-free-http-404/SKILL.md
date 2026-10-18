---
name: fix-temp-allocator-use-after-free-http-404
description: Use when a hand-written HTTP server responds with its own 404 JSON for a route whose source code clearly matches. Helps the agent isolate the fault with a raw TCP request, find temp-allocator lifetime bugs in the dispatcher, and verify the fix with an end-to-end 200 response. Requires ability to run the server and open raw TCP connections to its port. Do not use when the server does not respond at all, or when the route string in code genuinely differs from the request path.
---
# Fix Route Matching That Always Falls Through to 404 in a Custom HTTP Server

## Goal
Given a custom HTTP server that answers its own `{"error":"not found"}` for a path that clearly matches a route case, locate the lifetime bug that corrupts the parsed path, remove it, and prove the route now returns a 200 response with real payload over a raw TCP request.

## Scope
### In scope
- A hand-written HTTP/1.1 server (custom dispatcher, not a framework) that responds with its own 404 JSON body for a path that equals a route case in source.
- Proving with a raw TCP request (manual `GET /path HTTP/1.1` bytes) which branch the server actually takes, before touching code.
- Lifetime bugs where the parsed request path/header strings are allocated on `context.temp_allocator` and freed before dispatch compares them.
- Re-verifying the route end-to-end with a raw TCP request showing `HTTP/1.1 200 OK` and the expected payload.

### Out of scope
- Servers that never accept connections or never respond (connection-level problems).
- Framework-based routers (Express, Gin, etc.).
- WebSocket handshake or frame-level failures — only the REST route-matching path is covered.
- Correctness of the payload body itself beyond "route matched and returned 200 with the expected shape".

## Inputs
- **Running server process**: process bound to the HTTP port, source = your own build launched just before testing (here port 7771), required = yes, constraint = must be the freshly built binary, default = 无
- **Port number**: integer, source = CLI flag or config file (here 7771), required = yes, constraint = must match what the server actually listens on, default = 7771
- **Failing request path**: string, source = reproduction of the user-visible 404 (here `/api/status`), required = yes, constraint = must be a path you believe is routed in code, default = 无
- **Server source files**: file(s), source = repository (here `src/api_routes.odin` dispatcher and `src/api_http.odin` request parser), required = yes, constraint = read-only inspection before editing, default = 无
- **Raw TCP client**: tool, source = PowerShell `System.Net.Sockets.TcpClient` or `nc`, required = yes, constraint = must let you send byte-exact `GET ... HTTP/1.1\r\n...\r\n\r\n`, default = 无
- **HTTP client for cross-check**: tool, source = `Invoke-WebRequest` or `curl`, required = no, constraint = used only after the raw TCP result looks correct, default = 无

## Outputs
### Artifacts
- **Raw TCP reproduction**: request bytes sent and the exact 404 response captured (tool output).
- **Code edit**: removal of the premature temp-allocator free (or equivalent lifetime fix) in the dispatcher, file edit.
- **Verification capture**: raw TCP response showing `HTTP/1.1 200 OK` with the route's JSON payload (tool output).

### Success criteria
- A raw TCP `GET <failing-path> HTTP/1.1` returns status 200 and the payload produced by the matched route handler.
- A second client (`Invoke-WebRequest`/curl) receives the same 200 with parseable JSON.

### Failure criteria
- Response is still the server's own 404 JSON after the edit — the path mismatch has a different cause; stop and re-measure instead of iterating blindly.
- Response is a connection error/refusal — the server is not running; out of scope.

## Preconditions
- The server builds and is running and listening on the expected port; a connection attempt must succeed before you analyze routing.
- The failing path is believed to match a route case in the dispatcher source (verified by reading the dispatcher), so the mismatch is genuinely unexplained.
- You can send a byte-exact raw HTTP request and read the raw response; otherwise you cannot distinguish "server 404" from "client-side error rendering".
- The request path string is produced by a parser you can read (so you can see which allocator owns it).
- You have edit rights on the server source and a rebuild command available.
- If the server does not respond at all, stop — that is a different failure class, not a routing bug.

## Procedure
### Step 1: Reproduce with a raw TCP request, not a high-level client
- actions: open a `TcpClient` to the port and write exact bytes: `GET /<path> HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n`, then read and print the response.
- inputs: port, failing path.
- outputs: full HTTP response.
- cautions: PowerShell syntax inside a Bash tool can be mangled — if the shell reports a syntax error, rerun via `powershell.exe -Command "..."` or `nc`. A high-level client's rendered error (`{"error": "not found"}` with exit code 1) hides the status line.
- preserve: raw response text.
- next: continue; you now know whether the server's own dispatcher produced the 404.

### Step 2: Confirm the 404 comes from the dispatcher's default case
- actions: read the route switch. If the path equals a case (e.g. `case req.path == "/api/status":`) yet the default `resp = http_err(404, ...)` body was returned, the path string is not what you think at comparison time.
- inputs: dispatcher source.
- outputs: confirmed "code says match, runtime says no match".
- cautions: do not start editing route cases.
- preserve: file unmodified.
- next: inspect the request path's lifetime.

### Step 3: Audit who owns the path string and when it is freed
- actions: read the request parser (`_parse_request`) to see which allocator `req.path` is cloned onto, then read the dispatcher entry. Look for an eager free before routing.
- inputs: parser + dispatcher source.
- outputs: the offending statement.
- cautions: a `defer free_all(...)` at function end is fine; an unconditional `free_all(context.temp_allocator)` on the FIRST line of the dispatcher frees strings the caller just parsed (observed: `api_dispatch :: proc(req: HttpRequest, sock: net.TCP_Socket) {\n    free_all(context.temp_allocator)\n    defer free_all(context.temp_allocator)`), so `req.path` compares against freed memory.
- preserve: the `defer free_all(...)` cleanup at the end.
- next: edit.

### Step 4: Remove the premature free only
- actions: delete the leading `free_all(context.temp_allocator)` line, keeping the trailing `defer free_all(context.temp_allocator)`.
- inputs: dispatcher source.
- outputs: one-line removal.
- cautions: do not remove the defer — temp allocations must still be reclaimed at the end of each request.
- preserve: all routing logic untouched.
- next: rebuild and rerun the server.

### Step 5: Verify with the same raw TCP request
- actions: rebuild, restart the server (wait for startup), repeat Step 1 exactly, then cross-check with `Invoke-WebRequest`/curl.
- inputs: rebuilt server.
- outputs: raw response.
- cautions: check the status line and body, not just that a connection succeeded.
- preserve: response text.
- next: done on `HTTP/1.1 200 OK` with the route's payload; if still 404, stop and re-measure rather than editing more routes.

## Decision Rules
### When a raw TCP request returns the server's own 404 JSON for a routed path
The route table is not the problem — audit the path's allocation lifetime before touching cases.

### When the high-level client shows only `{"error": "not found"}`
Re-run through a raw TCP request to capture the status line; client rendering hides which layer failed.

### When `req.path` is cloned onto `context.temp_allocator` by the parser
Any `free_all(context.temp_allocator)` executed before dispatch compares paths invalidates it — remove the eager free, keep the deferred one.

### When the route case and the request path genuinely differ (trailing `\r`, whitespace)
Fix the trimming in the parser instead; note that `strings.fields` splitting already handled `\r` in this trajectory, so verify before "fixing" it.

### When the first edit still yields 404
Stop editing and re-measure with the raw request (add a debug print of the path if needed); do not cascade route changes.

### When the response is a connection refusal or the client hangs
Out of scope — the server is not running or is blocked elsewhere, not a routing bug.

## Invariants
- Do not change route cases, path strings, or dispatcher structure while the cause is unproven — measure with a raw request first.
- Do not remove the trailing `defer free_all(context.temp_allocator)` when deleting an eager free; cleanup must still happen per request.
- Keep the edit minimal: one lifetime statement. Multiple simultaneous edits would make the verification meaningless.
- Do not claim the fix from a successful compile; the claim requires the same failing request now returning 200 with the expected payload.
- Do not substitute a client-side rendered error for the raw response when deciding where the 404 originated.
- Do not report success if only some routes work — re-run the originally failing path.

## Common Failures
### Failure: Debugging the route table when the path is already freed
- symptoms: dispatcher code reads perfectly, every comparison "should" match, yet the default 404 returns.
- causes: `req.path` was cloned onto `context.temp_allocator` and an eager `free_all(context.temp_allocator)` at the top of the handler destroyed it before the switch.
- recovery: delete the eager free, keep the `defer`, rebuild, retest with the same raw request.

### Failure: Using only a high-level HTTP client for diagnosis
- symptoms: tool shows `Exit code 1` and a rendered `{"error": "not found"}` with no status line or headers.
- causes: the client folds the error response into its own output.
- recovery: send byte-exact request over a raw TCP socket to see `HTTP/1.1 404 OK` and the server's own body.

### Failure: Running the raw-TCP test inside the wrong shell
- symptoms: `syntax error near unexpected token` because PowerShell script was executed by Bash.
- causes: wrong tool/shell pairing.
- recovery: wrap in `powershell.exe -Command "..."` or use `nc`/`curl` equivalents.

### Failure: Testing before the server is up
- symptoms: connection refused / curl exit code 28 / background task exit 56 during startup.
- causes: requests issued before the listener bound the port.
- recovery: wait (e.g. `sleep 2`) and retry; do not misread this as a routing bug.

### Failure: Still 404 after the lifetime fix
- symptoms: the same raw request returns 404 with the fix applied.
- causes: unknown in this trajectory (no such observation was made).
- recovery: re-measure, print the actual path at dispatch, and stop editing routes until the measurement says otherwise.

## Verification
- Before the fix: a raw TCP `GET /<path> HTTP/1.1` returns the server's own 404 body (observed: status line `HTTP/1.1 404 OK` with `{"error":"not found"}`) — this is the baseline you must beat.
- After the fix: the identical raw request returns `HTTP/1.1 200 OK` with `Content-Type: application/json` and the route's payload (observed body: `{"tick":0,"island_name":"","seed":"0000000000000000","speed":0,"weather":"","time_of_day":"","is_headless":false,"residents":0,"crushes":0,"rivals":0}`).
- The response `Content-Length` matches the body actually received.
- A second, independent client (`Invoke-WebRequest`/curl) against the same path receives HTTP 200 with parseable JSON.
- The build compiles cleanly after the one-line removal (no new warnings/errors introduced by the edit).
- Re-run the originally failing path only; a different route returning 200 does not verify this fix.

## Examples
### Example 1: /api/status always 404 despite an exact route case
- input: custom Odin HTTP server on port 7771; `Invoke-WebRequest http://localhost:7771/api/status` returns the server's `{"error": "not found"}` with exit code 1.
- procedure: raw TCP `GET /api/status HTTP/1.1` → baseline `HTTP/1.1 404 OK` + `{"error":"not found"}`; read `api_dispatch` and see `case req.path == "/api/status":` yet the default branch fires; note the handler began with `free_all(context.temp_allocator)` while `_parse_request` cloned `req.path` onto that allocator; delete that leading line (keep the `defer free_all(...)`); rebuild; repeat the same raw request.
- expected result: `HTTP/1.1 200 OK` with `{"tick":0,...,"residents":0,...}` and a cross-check via `Invoke-WebRequest` returning 200.
- parameterized values: port `7771`; path `/api/status`; allocator `context.temp_allocator`; file `src/api_routes.odin`.

### Example 2: raw-TCP test run in the wrong shell
- input: PowerShell one-liner executed by Bash, producing `syntax error near unexpected token`.
- procedure: re-run the same logic wrapped as `powershell.exe -Command "..."`, or use `printf 'GET ...\r\n...' | nc localhost <port>`.
- expected result: the actual HTTP response bytes are returned instead of a shell syntax error.
- parameterized values: shell (bash vs powershell); tool (`nc`, `curl`, `TcpClient`).

## Evidence
- problem — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 790, source_part_index 0, quote: `HTTP/1.1 404 OK`, supports: a byte-exact raw TCP request to `GET /api/status` was answered by the server itself with 404, isolating the fault inside the server.
- problem — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 790, source_part_index 0, quote: `{"error":"not found"}`, supports: the body is the dispatcher's own default-branch JSON, i.e. routing fell through despite an exact route case.
- problem — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 787, source_part_index 0, quote: `Invoke-WebRequest:`, supports: the high-level client only surfaced a rendered error, motivating the raw-TCP reproduction.
- action — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 819, source_part_index 0, quote: `on the very first line — before the routing switch.`, supports: the identified cause — api_dispatch called free_all(context.temp_allocator) as its first statement, freeing the `req.path` string the parser had cloned onto that allocator before the routing switch compared it (assistant diagnosis in the same paragraph: `The req.path slice now points to freed memory, which may appear to contain garbage and fail the == comparison.`).
- action — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 820, source_part_index 0, quote: `api_dispatch :: proc(req: HttpRequest, sock: net.TCP_Socket) {`, supports: the edit target — the dispatcher header whose leading `free_all(context.temp_allocator)` line was removed while the deferred `free_all(context.temp_allocator)` was kept.
- action — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 821, source_part_index 0, quote: `The file d:\DMLS\src\api_routes.odin has been updated successfully. (file state is current in your context — no need to Read it back)`, supports: the edit landed on the dispatcher file only.
- verification — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 891, source_part_index 0, quote: `HTTP/1.1 200 OK`, supports: the same raw request now matches the route after the lifetime fix.
- verification — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 891, source_part_index 0, quote: `{"tick":0,"island_name":"","seed":"0000000000000000","speed":0,"weather":"","time_of_day":"","is_headless":false,"residents":0,"crushes":0,"rivals":0}`, supports: the 200 body is the status-route payload, proving end-to-end routing, not just a connection.
