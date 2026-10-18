# Domain feature cards

每个簇先用这些低成本特征交给 LLM 判断，只有需要时再展开完整切片。

## D001
- 轨迹数：65；session 数：25；信息完整度：0.0417
- 核心词：public, session, anything, whether, pull, report, git, trace, Step, donate
- 高频词（前 60）：the, and, to, a, is, in, The, it, s, me, for, on, Let, with, 1, Now, of, I, that, md, from, at, not, or, build, t, you, so, no, are, but, 2, as, check, all, 0, kernel, this, test, what, path, fix, file, 3, c, only, run, by, now, can, ll, which, use, if, user, be, your, before, has, 4
- 代表首句：
  - Tables create now; new error `Lens getter must not throw` — a zoom getter is hitting a null `state()`.
  - Base directory for this skill: /Users/USER/ComparIA/.claude/skills/comparia-model-writer # compar:IA Model Description Writer This skill produces JSON model entries for the compar:IA catalog.
  - GloomChat has no release APK (skip — can't get it without building).
  - Both fixes in.
  - Generated i18n files are gitignored (regenerated at build) — good.
  - <user_query> J'aimerais que tu m'indiques à partir de quel log je peux monitorer l'utilisation de l'API document-ia ?
  - Two fixes needed: the dedup fixture has no triangle (stale assertion), and `Var<Tuple<Shape>>` direct form isn't parsed by the ORM.
  - Build a job board website where employers can post job openings and job seekers can search and apply for jobs.
  - Both are the same device (the Pixel = your Haven host), and I'm cleared to post factual reports directly.
  - Good idea — I'll reframe ANDROID.md from a design-notes/status doc into a light, educational build walkthrough.

## D002
- 轨迹数：43；session 数：20；信息完整度：0.0544
- 核心词：kernel, shell, bash, boot, GOP, framebuffer
- 高频词（前 60）：the, and, to, a, is, in, it, The, s, me, 1, for, on, with, Let, md, I, Now, that, kernel, build, of, from, not, you, at, or, 0, t, so, as, 2, no, this, c, path, are, check, but, what, file, only, 3, run, all, ll, 4, by, can, if, your, test, source, before, now, user, o, bin, sys, fix
- 代表首句：
  - Now add the build rule for `kernel/gop.o` and update the `iso` target to pass UEFI flags to `grub-mkrescue`:
  - Now let me check the kernel's VGA and detect headers to understand what needs changing:
  - Let me explore the relevant parts of the kernel source for both of these changes.
  - This is the code for Linux v3.0.1 so read README and tell me how to get a minimilast build or code, so I can add my custom to it
  - Exactly right — `/proc` exposes PIDs directly, so anyone with shell access can `kill -9 1` or mess with `/proc/sysrq-trigger` and take down the whole system.
  - [Request interrupted by user for tool use]
  - Also update the step number comments in build.sh for consistency:
  - ```bash make iso && make run-uefi ``` Paste the `[BOOT] fb tag:` line from the serial output.
  - Now wire it into build.sh:
  - The

## D003
- 轨迹数：45；session 数：15；信息完整度：0.0408
- 核心词：grid, screen, buttons, panel
- 高频词（前 60）：the, and, to, is, a, The, in, it, s, me, for, on, with, of, Let, md, Now, I, from, that, not, at, 1, build, or, 0, no, are, so, t, you, as, but, check, use, app, all, She, page, can, fix, file, button, 2, what, by, now, this, text, be, color, ll, kernel, only, if, run, 3, has, add, which
- 代表首句：
  - `items` not `tokens`.
  - read DLC.MD and implement
  - Now I have a clear picture.
  - Now let me read the current state of the key files I need to modify.
  - Clean build.
  - Now wire `starters_seed` into the World_Setup → Residents transition:
  - `rl.DrawCircle` takes `(i32, i32, f32, Color)` — the radius arg is `f32`, not `i32`:
  - Fixed the unused import.
  - Now update the shared header/footer class names in both page JSX files — they were using `tl-header`, `tl-back` etc., which I've renamed to `page-header`, `page-back` etc.
  - Now add the `.Resolution` case to the switch:

## D004
- 轨迹数：29；session 数：11；信息完整度：0.0501
- 核心词：icon, html, styles, icons
- 高频词（前 60）：the, and, to, a, is, The, in, it, s, md, for, on, of, with, me, Let, from, Now, not, that, I, at, or, She, page, button, build, no, are, so, app, color, t, as, can, 1, you, use, but, text, sys, check, all, ts, icon, routes, file, this, now, 0, 3, what, by, her, only, an, fix, server, CSS, layout
- 代表首句：
  - read AGENTS.md build a site that takes username then pings redditcom/u/<username>.json fetches the json and then displays the details obtained from it in a stylized way.
  - make it use the PlusJakartaSans font and override default/system font
  - `rl.DrawCircle` takes `(i32, i32, f32, Color)` — the radius arg is `f32`, not `i32`:
  - Build a job board website where employers can post job openings and job seekers can search and apply for jobs.
  - `"module": "dist/esm/lucide.mjs"` — esbuild will pick that up correctly.
  - No `.desktop-icon` styles at all — the icon div has no defined layout.
  - Good idea — I'll reframe ANDROID.md from a design-notes/status doc into a light, educational build walkthrough.
  - Now I have a clear picture.
  - Fixed the unused import.
  - The `iconToSvg` type is too strict — lucide's `SVGProps` allows `undefined` values.

## D005
- 轨迹数：45；session 数：16；信息完整度：0.0353
- 核心词：page, title, max, pages
- 高频词（前 60）：the, and, to, a, is, in, The, it, s, for, me, with, on, of, Now, Let, md, from, that, I, not, at, 1, or, are, build, as, 0, you, t, no, page, but, so, use, all, 2, check, this, fix, file, can, be, She, what, by, only, text, now, button, add, path, run, 3, app, kernel, an, ll, when, color
- 代表首句：
  - A two-column master-detail split — folders on the left, items on the right.
  - Now verify the build is clean and the route actually returns 200:
  - follow CLAUDE.MD
  - Clean build.
  - write a bun backend that uses the databases available in ORV/*.db to serve data, make this backend under ./backend, use Elysia JS
  - Fixed the unused import.
  - Generated i18n files are gitignored (regenerated at build) — good.
  - read AGENTS.md build a site that takes username then pings redditcom/u/<username>.json fetches the json and then displays the details obtained from it in a stylized way.
  - Build a job board website where employers can post job openings and job seekers can search and apply for jobs.
  - Now verify it builds and the home page actually returns database cards:

## D006
- 轨迹数：36；session 数：16；信息完整度：0.0477
- 核心词：CSS, index, css
- 高频词（前 60）：the, and, to, a, is, The, in, it, s, for, with, me, md, of, Now, on, Let, from, I, not, that, build, at, 1, or, She, are, all, use, no, fix, so, as, t, button, check, color, but, 2, now, app, what, path, text, 3, has, this, by, sys, file, when, 0, icon, add, update, CSS, test, first, be, her
- 代表首句：
  - Now update the landing page to support both user and subreddit lookup:
  - read AGENTS.md build a site that takes username then pings redditcom/u/<username>.json fetches the json and then displays the details obtained from it in a stylized way.
  - Build a job board website where employers can post job openings and job seekers can search and apply for jobs.
  - make it use the PlusJakartaSans font and override default/system font
  - `rl.DrawCircle` takes `(i32, i32, f32, Color)` — the radius arg is `f32`, not `i32`:
  - Clean build.
  - follow CLAUDE.MD
  - Now I have a clear picture.
  - Now implement the C FFI layer.
  - Now update the JSX to match the renamed classes:

## D007
- 轨迹数：27；session 数：11；信息完整度：0.0654
- 核心词：cpp, parser, lexer
- 高频词（前 60）：the, and, is, a, to, in, The, it, s, me, Let, Now, 1, for, with, build, from, test, on, that, I, at, all, check, 2, but, of, fix, t, c, are, md, path, not, cpp, as, 3, no, or, so, 0, C, be, source, if, file, X, static, then, which, first, run, when, files, now, issue, use, what, parser, before
- 代表首句：
  - Still IDE false positives — no `-Iinclude` configured for the language server.
  - Now update the `parse()` entry point to use recovery mode when an ErrorCollector is provided:
  - Now implement the C FFI layer.
  - Clean compile.
  - Also apply the same fix to the output-comparison block where `2>&1` can throw on error exit — wrap that in a try/catch too:
  - All headers written.
  - read PLAN.MD, complete M0, M1, create a README.MD
  - PLAN and BUILD STAGE 4/IV Yggdrasil Stage 4 — Modular Library & Embedding Interface Since GlacioJS will embed Yggdrasil, Stage 4 splits it from a CLI tool into a C library with a thin CLI wrapper.
  - this is what we are going to make, do a PROJECT.MD with several milestones layouted so we can do it one by one 🤣 Alright, here's the unofficial specification of your masterpiece.
  - Good — clang++ 21.1 is available.

## D008
- 轨迹数：24；session 数：12；信息完整度：0.0396
- 核心词：web, device, Android
- 高频词（前 60）：the, and, is, to, a, it, in, The, s, md, on, for, me, of, with, Let, not, I, 1, build, from, that, or, no, you, at, She, so, t, as, Now, but, are, this, 0, ll, only, check, file, color, run, what, sys, text, 2, kernel, by, app, can, has, her, web, if, before, source, 4, 3, one, your, use
- 代表首句：
  - Build a job board website where employers can post job openings and job seekers can search and apply for jobs.
  - read AGENTS.md build a site that takes username then pings redditcom/u/<username>.json fetches the json and then displays the details obtained from it in a stylized way.
  - `rl.DrawCircle` takes `(i32, i32, f32, Color)` — the radius arg is `f32`, not `i32`:
  - Web bundle built and synced; Gradle is now assembling.
  - The System panel now expands **upward from the bottom bar** — test tones, lock, defaults — with the top bar fully freed of it.
  - Good idea — I'll reframe ANDROID.md from a design-notes/status doc into a light, educational build walkthrough.
  - Both are the same device (the Pixel = your Haven host), and I'm cleared to post factual reports directly.
  - I'll read ANDROID.md to see what we're picking up.
  - No system Gradle or Android SDK here — so the APK can't be compiled or the `gradle-wrapper.jar` generated in this environment.
  - File is on the branch (verified, 1897 bytes).
