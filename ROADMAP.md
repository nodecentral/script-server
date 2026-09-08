# Roadmap

Local planning doc for enhancements to this fork. Not upstream-facing — see `CLAUDE.md` for
AI-facing conventions/guidance (this file is *what we're building*, that one is *how to build it*).

Each item is tagged by effort class, since that's the main thing that changes how risky/quick a
change is in this repo:

- **Admin script** — a matched-pair runner + script under `conf/runners/` + `scripts/`. No changes
  to script-server's own source. Low risk, fast to build and test, easily reverted.
- **Core change** — editing script-server's own Python/Vue source (`src/`, `web-src/`). Requires a
  frontend rebuild, is harder to test without a live browser, and is a bigger, riskier change than
  anything shipped so far in this fork.
- **Config only** — already supported by script-server, just needs setting up.

-----

## Done

- Self-contained multi-stage Docker build + `docker-compose.yml` for NAS deployment
- 13 example "Admin" runners: Hello World, File Info, Disk Usage, Import from Gitea, Terminal
  Colors, Progress Demo, Confirm Gate, Download Image, Disk Usage Chart, Network Scanner, Network
  Device Labelling, Network Device Inventory
- Persistent MAC-keyed device inventory pattern (collector + editor + viewer over a JSON store)
- `network_mode: host` + `cap_add: [NET_RAW, NET_ADMIN]` for real LAN scanning
- **Backups** — `backup.sh`: tars `conf/` + `scripts/` (+ optional `data/`) to a downloadable
  tarball under `/app/data/backups`, correctly excluding its own backups folder from the archive.
- **Notifications** — `notify.py`: Pushover/Prowl via their public HTTP APIs. Field names/POST
  structure verified against a local mock server; **actual delivery not verified** (no live
  Pushover/Prowl credentials available) - confirm on first real run.
- **Package/capability library (runtime-install only)** — `conf/capabilities.json` manifest
  (preinstalled vs optional apt/pip packages) + `install_package.py` (installs selected extras via
  apt/pip, records to `/app/data/installed_extras.json`) + `view_capabilities.py` (shows
  preinstalled / available / runtime-installed status). Verified with real installs (`jq`, `psutil`,
  etc.), not just argument parsing. **Scope cut from the original idea**: this only covers the
  ephemeral runtime-install half - it does *not* regenerate `tools/Dockerfile` to bake a choice in
  permanently. That's still open, see Planned below.
- **Script Ingredients Check / MOTD** — `scripts/motd.py` audits every runner under
  `conf/runners/` for missing script/preload files, rendered as a themed collapsible HTML table;
  `scripts/preload/motd.py` is a genuinely separate preload script showing live system stats,
  proving out the `scripts/preload/<name>` convention documented in `CLAUDE.md`.
- **Core change: fix Copy/Download for `html_iframe` output** — first real edit to script-server's
  own frontend source (`web-src/`), not just an Admin script. Full root-cause + fix details logged
  in `CLAUDE.md` under "Core Changes (Fork Divergence from Upstream)". **Verified on the real NAS
  instance**: Download on MOTD's `html_iframe` output now saves a genuine, reopenable `.html` file
  (confirmed by inspecting the actual downloaded file), not an empty/plain-text one.
- **Secrets Store** — categorized JSON store (`/app/data/secrets.json`, `{category: {key: {value,
  updated_at}}}`) for API keys/tokens shared across scripts (finance, paperless, etc.), replacing
  the old "one flat env var per secret" gap called out in the Ideas/Backlog item below. Shared
  module `scripts/shared/secrets_store.py` (importable by Python scripts, CLI-callable by
  Lua/bash), **Secrets Manager** (set/update/delete, values never echoed back) and **Secrets
  Viewer** (`html_iframe`, themed, category/key/last-set only — never values). Documented in
  `CLAUDE.md`. Plaintext on disk (chmod 600) by design — not an encrypted vault; see CLAUDE.md's
  security note. Verified end-to-end (set/get/update/delete/dropdown/rendered viewer, including
  confirming no raw value ever appears in viewer output) in the dev sandbox.
- **Known Integrations checklist + wire up `notify.py`** — `secrets_store.KNOWN_INTEGRATIONS` lists
  category/key pairs a script consumes (or expects to), shown as selectable `not set yet` rows in
  Secrets Manager's dropdown and as a **Not Yet Configured** section in Secrets Viewer, so a missing
  credential is visible before a script fails on it. `notify.py` (Send Notification) now actually
  calls `get_secret('pushover'/'prowl', 'TOKEN'/'USER_KEY')` as a fallback when the runner
  parameter is left blank, with an explicit CLI value still overriding — first real script wired to
  the store, not just a standalone feature. `paperless` (`URL`/`TOKEN`) added as an explicit
  placeholder ahead of any real consuming script. **`finance` (e.g. `FINNHUB_API_KEY`) deliberately
  NOT added**: no finance script exists in this repo or in what's been imported to the NAS so far
  (only `ss_music_file_management` has been imported per the Gitea import state) — the real key
  name(s) that repo's finance script(s) actually expect are unconfirmed, and guessing would be
  worse than leaving it open (see CLAUDE.md's "never guess a category/key name" note). Verified
  end-to-end in the dev sandbox: dropdown/placeholder-list transitions correctly as entries are
  set, and `notify.py`'s credential resolution (store fallback, CLI override, clean failure with
  neither) all confirmed with the real functions monkeypatched out to avoid live network calls.
- **Multi-token support for Import from Gitea** — a `gitea` category was added to
  `KNOWN_INTEGRATIONS` (default key `TOKEN`), and a new `secrets_store.py dropdown-category
  <category>` subcommand lets a runner offer a second dropdown scoped to just one category (for
  when, unlike most categories, more than one differently-named key legitimately coexists there -
  e.g. a different Gitea token per repo). `import_from_gitea.py`'s `resolve_gitea_token()`: an
  explicit manual token always wins; with nothing stored, assumes a public repo; with exactly one
  stored token, auto-selects it silently; with more than one, refuses to guess and requires an
  explicit pick from the new "Gitea Token" dropdown. The chosen source (never the value) is printed
  in the run output for transparency. Documented as the reference pattern for any future
  multi-value-per-category case in `CLAUDE.md`. Verified end-to-end in the dev sandbox: all five
  resolution paths (none/one/many stored, explicit override, unknown key) behave correctly.
- **Secrets Manager UX fix: real confusion, real cause** — a user picked a known-but-unset
  suggested entry (e.g. Prowl's `TOKEN`) straight from the dropdown and still felt like they had to
  fill in a separate "new category" field, since it was sitting right there on the form. Root cause
  confirmed against the actual script-server source: this version has no conditional field
  visibility, so `new_category`/`new_key` always showed regardless of what was picked in `entry`.
  Fixed within that real constraint rather than assuming a feature that doesn't exist: merged
  `new_category`/`new_key` into one `new_entry` field (`category/KEY`), and changed the sentinel
  itself from `-- new entry --` to `+ CREATE NEW ENTRY (fill in New Entry field below:
  category/KEY)` so the instruction lives in the option you actually see, not a separate field
  description easy to skip past. Verified end-to-end: picking a suggested entry directly (leaving
  New Entry blank) resolves correctly, exactly reproducing and then fixing the reported scenario.
- **Fix Import from Gitea's "Gitea Token" dropdown always failing** — real bug hit immediately
  after adding a `gitea.TOKEN` value: `dropdown-category` prints `"KEY | last set <date>"`, but
  `resolve_gitea_token()` passed the entire selected line to `get_secret()` as the key instead of
  just `KEY`, so picking the token from the dropdown always reported it as not found even though it
  was set. Fixed by parsing out the key portion before the `|`, same pattern already used in
  Secrets Manager's own `parse_entry()`. Verified by reproducing the exact reported error string
  (`"TOKEN | last set 2026-09-06 22:06:26"`) and confirming it now resolves correctly.
- **Fix `motd.py` false-positive missing-script reports for relative `working_directory`** —
  Gitea-imported runners (e.g. the Music group) use a relative `working_directory` (`"scripts"`)
  rather than this repo's own `"/app/scripts"` convention, which `motd.py`'s existence check
  resolved against its own process cwd instead of Script-Server's actual root, wrongly flagging
  real, runnable scripts as missing. Fixed by resolving relative `working_directory` (and preload
  paths) against `/app`. **Verified on the real NAS instance**: after the fix, the Script Ingredients
  Check correctly reports "24 runner(s) across 2 group(s). All script/preload files present." for
  the actual Music-group runners imported from `ss_music_file_management`.
- **Core change: slim auto-hide sidebar rail (desktop)** — closes the "Auto-hide left sidebar"
  Ideas/Backlog item below. `AppLayout.vue`/`MainAppSidebar.vue`/`MainApp.vue`: a persistent 56px
  rail (single toggle icon) replaces the fixed 300px sidebar by default above the mobile
  breakpoint, expanding to a temporary overlay on click and snapping back on navigation or a
  click outside - reusing the collapse mechanism that already existed for mobile rather than
  building a new one. A pin toggle reverts to the original always-docked behaviour, remembered in
  `localStorage`. Full root-cause-free design writeup in `CLAUDE.md`'s Core Changes section.
  **Verified**: `vue-cli-service build` compiles cleanly; the exact CSS/JS state logic was checked
  visually via a standalone Playwright-driven mock (all four states: collapsed, expanded overlay,
  collapse-on-outside-click, pinned open) since no live backend was available in this environment
  to run the real app end-to-end. **Needs a live-browser check on the real NAS instance** before
  being considered fully verified - a static mock can't catch genuine Vue/router integration bugs.
- **Fix invalid Material Icons names breaking the sidebar header** — exactly the live-browser bug
  the entry above was waiting on, reported on the real NAS instance: `push_pin` and
  `keyboard_double_arrow_left` don't exist in this project's bundled icon font (predates Google's
  newer Material Symbols set), silently consuming real width in the header row without ever
  showing visibly broken text, squeezing the server name down to one letter and displacing the
  admin/GitHub link. Confirmed directly against the installed font's codepoints file, not assumed.
  Fixed with `lock_open`/`lock` (confirmed valid and correctly-sized via a real-font Playwright
  render) plus defensive fixed-size CSS on the toggle button so a bad icon name degrades small
  instead of blowing out the row again. Verified no other invalid icon name exists anywhere else
  in the codebase via a one-line cross-check against the codepoints file (documented in
  `CLAUDE.md`, reusable for any future icon addition).
- **Diagnosed and resolved: admin cog not showing at all** — separate from the icon-name bug above
  and not caused by any sidebar code. `conf/conf.json` genuinely never existed on the real NAS
  instance, so the default admin check (`access.admin_users` = `127.0.0.1`/`::1` only) correctly
  denied admin rights to a LAN-only iPad session, both before and after the sidebar work - traced
  through `server_conf.py`/`web/server.py`/`auth/identification.py` to confirm, not assumed. Real
  procedural lesson along the way: `docker compose up -d` alone did NOT pick up a fresh
  `conf/conf.json` on the actual NAS - it's a no-op for a bind-mounted file's content changing
  under an already-running container. `docker compose restart script-server` was required, and the
  startup warning log line (`Any user is allowed to access admin page...`) is the real confirmation
  a config change took effect, not just running the restart command. Both corrected in `CLAUDE.md`'s
  "Admin Access Without Auth Configured" section. Resolved and confirmed on the real instance -
  cog now shows.
- **Secrets Manager preload banner** — shows what's already in the store (via Secrets Viewer,
  including the Not Yet Configured checklist) before you make any change, so you're never guessing
  what's already set. Reuses `scripts/secrets_viewer.py` directly as the `preload_script` rather
  than duplicating its rendering logic into a new file - documented as a fourth preload pattern
  ("another runner's own script, pointed at directly") in `CLAUDE.md`, alongside the existing
  inline/self-referential/standalone-file cases. Verified the script runs cleanly standalone with
  no arguments and no stdin (required for preload compatibility) via a simulated subprocess
  invocation.
- **Secrets Manager: unmasked value field + rich confirmation view** — two real usability
  complaints fixed together. (1) The value field was `secure: true`, making it hard to proofread
  and triggering iOS/iPadOS Safari's password-save prompt; removed the flag entirely, trading away
  Script-Server's own execution-history redaction for a plain, readable input - a conscious,
  documented trade-off (see `CLAUDE.md`'s "The `secure` flag is one setting for two different
  things"), not a silent gap, consistent with this fork's existing home-lab trust posture. (2) A
  bare "Set X (N characters)" terminal line replaced with a themed confirmation banner (green for
  success, red for errors, both still exit-code-correct) followed by the full up-to-date store -
  `secrets_viewer.py` refactored to expose a reusable `render_body()`, called directly by
  `secrets_manager.py` after every action so the result and the next entry to set are both visible
  without leaving the page. Verified end-to-end: successful set, successful delete, and all error
  paths (bad new-entry format, missing value, delete-not-found, no entry selected) all render the
  correct banner with the correct exit code; confirmed standalone Secrets Viewer still works
  unchanged after the refactor; screenshotted the full rendered output via Playwright.
- **Import from Gitea overhaul: preload readiness check, live repo dropdown, no URL/owner fields**
  — new shared `scripts/shared/gitea_client.py` (Gitea API client + URL/token resolution) and
  `scripts/preload/import_from_gitea.py`. Both the Gitea URL and its token(s) now live in the
  Secrets Store's `gitea` category (`URL` key alongside one or more token keys) instead of runner
  form fields - motivated directly by preload scripts receiving no parameter context at all, so a
  form-typed URL could never reach the preload banner anyway; storing it means the preload, both
  dropdowns, and the main script always resolve the identical, current value. The banner checks
  both are set and, when exactly one token is stored, actually connects and reports success (as
  whom, how many repos) or the real failure reason. The Repo dropdown lists live `owner/repo`
  options straight from Gitea's own `/user/repos` API for whichever token is in play (paginated,
  handles 50+ repos) - answers a direct question about whether a separate owner/username field is
  even needed: no, since a token already identifies one account, `owner/repo` values come
  pre-resolved from the API itself. A Manual Repo field (`owner/repo`) is the sole fallback, only
  used when the dropdown can't populate live (public repo, no token). `RESERVED_GITEA_KEYS`
  excludes `URL` from ever being offered as a fake token candidate in the multi-token
  picker/dropdown - a real category-design edge case now documented in `CLAUDE.md` as a reusable
  pattern for any future "category holds more than just tokens" case. Verified extensively against
  a real local mock Gitea HTTP server (not just unit-tested in isolation): authenticated/
  unauthenticated requests, pagination across multiple pages of repos, unreachable-host and
  invalid-token error messages, all four preload states (no URL, no token, ambiguous multi-token,
  working single-token connection), the dropdown CLI's sentinel-vs-real-value distinction
  (including the critical edge case of an error message itself containing URL slashes, which must
  never be mistaken for a real `owner/repo` selection), and a full clone-and-sync run against a
  real local git repository with the URL/owner/repo entirely resolved from the Secrets Store.
- **Fix: Import from Gitea failed to load at all on the real NAS instance** — real bug caught
  immediately on first live use, not in the dev sandbox testing above (a live Script-Server
  instance enforces a validation rule a standalone script test can't reproduce). Server log showed
  `Unsupported parameter "token" of type "secure" in values.script!` - Script-Server hard-refuses
  to load any runner where a `secure`/`constant`/`no_value` parameter is referenced in another
  parameter's `values.script`, confirmed in `parameter_config.py`'s `validate_parameter_dependencies`.
  The live Repo dropdown had substituted `${token}` (the manual secure token field) alongside
  `${token_key}`. Fixed by dropping `${token}` from the dropdown entirely - the manual token field
  now only drives the actual import step, not the live listing, with both the field description and
  `dropdown-repos`'s own no-token message saying so explicitly. Re-scanned every runner JSON in the
  repo for the same pattern (secure/constant/no_value param referenced in another param's
  `values.script`) - no other instance found. Documented as a hard platform rule in `CLAUDE.md`,
  including the fix pattern (resolve secrets server-side inside the dropdown script itself, driven
  only by a plain field like `token_key` that picks a *name*, never a secret value).
- **Cross-repo convention drift: caught and addressed** — a dry-run import from a new work stream
  (`ss_document_file_management`) surfaced two real problems at once: a `check_script_permissions`
  filename collision with an already-imported runner from a different repo, and a completely
  independent secrets mechanism (`scripts/shared/secrets.py` + a gitignored `paperless.env`
  dotenv file) built with no awareness that `paperless.URL`/`TOKEN` were already reserved
  placeholders in this repo's own Secrets Store. Added a new "For Claude Sessions Working In Other
  Gitea Repos" section at the top of `CLAUDE.md` - the canonical, single source of truth other
  work streams are now expected to fetch (raw GitHub URL) before writing anything destined for
  import here, with the highest-stakes rules (Secrets Store only, filename collisions, Matched
  Pair) called out explicitly using this exact incident as the cautionary example. The
  `ss_document_file_management` script itself still needs migrating to `secrets_store.get_secret()`
  - that's a change to a different repo, outside this session's access; flagged for whoever
  picks up that repo next.
- **`SCRIPTING.md` — focused scripting-only doc for other Gitea repos' Claude sessions** —
  follow-up to the cross-repo pointer above, after measuring `CLAUDE.md` at 1219 lines / ~13.7K
  tokens and confirming most of that (sidebar/theme/Vue internals, admin-auth internals) is
  irrelevant to a session whose whole job is writing one script + runner pair. `SCRIPTING.md` is
  a ~550-line trim covering everything actually needed to author a compliant pair - parameter
  types, dynamic dropdowns (including the hard `secure`-in-`values.script` rule), Secrets Store
  usage, output formats, preload scripts, the Matched Pair rule - and deliberately excludes
  Admin Access and Core Changes (Fork Divergence). Carries a "Learning & Sharing" section at both
  the top and bottom (bookended on purpose) explaining the human-mediated relay loop back to this
  repo, using the `ss_document_file_management` secrets-divergence incident as the cautionary
  example. `CLAUDE.md`'s own cross-repo section now points other-repo sessions at `SCRIPTING.md`
  first, keeping `CLAUDE.md` itself as the fuller reference. The two files need to be kept in
  sync by hand going forward - each carries a note saying so.
- **First real-world relay of the Learning & Sharing loop** — the `⚙ LEARNING DETECTED` format
  in `SCRIPTING.md` worked end-to-end for the first time: a `ss_document_file_management` session
  (its first script built against `SCRIPTING.md` v1.0.0) flagged three findings, relayed here by
  the user, all folded in:
  1. `secrets_store.py`'s `KNOWN_INTEGRATIONS` entries for `paperless.URL`/`paperless.TOKEN` were
     stale ("placeholder, no consuming script yet") now that `paperless_metrics_dashboard.py`
     actually calls `get_secret()` for both - descriptions corrected to name the real consumer.
  2. The Matched Pair filename-collision warning didn't distinguish a genuine collision from a
     deliberate, byte-for-byte identical generic admin script shared across sibling repos (now
     confirmed real: `check_script_permissions.sh`/`.json` ships identically from
     `ss_finance_management`, `ss_health_management`, and `ss_document_file_management`) - added
     an explicit exception to both `CLAUDE.md` and `SCRIPTING.md`: the warning is about divergent
     content sharing a name, not shared content sharing a name.
  3. A repo can independently re-derive `SCRIPTING.md`'s own explanations into a local README
     instead of linking to it (`ss_document_file_management` briefly had two such READMEs, since
     removed) - same drift risk as a parallel secrets mechanism, and just as likely to happen
     independently across sibling repos since each is built by a separate, context-isolated
     session. Extended `SCRIPTING.md`'s "don't invent a parallel doc/mechanism/convention" line to
     name this case explicitly. Both docs bumped (`CLAUDE.md` 1.26.0, `SCRIPTING.md` 1.1.0).
- **Second relay batch - one correction, one confirmation** — two more findings came back from
  sibling sessions; this time one of them was itself wrong, which is exactly what the relay loop
  is for:
  1. A `ss_...` session reported that Python's `print()` defaults to block-buffering under
     Script-Server and proposed adding `sys.stdout.reconfigure(line_buffering=True)` to every
     Python script. Checked against the actual source before accepting: `src/execution/
     process_base.py`'s `prepare_env_variables()` (used by both the popen and pty execution
     paths) already forces `PYTHONUNBUFFERED=1` into every script's environment, which fully
     unbuffers Python's stdout - bare `print()` already streams live, no fix needed. Declined the
     suggested change and instead corrected `SCRIPTING.md`'s "Script Requirements" section to
     state this explicitly, scoping the real flush requirement to Lua/bash (which have no such
     automatic override) - heading off every other repo re-deriving the same unnecessary
     boilerplate independently.
  2. A `ss_movie_file_management` session asked (medium confidence, correctly flagged as needing
     human confirmation rather than guessed at) whether "Import from Gitea" is a real working
     native feature, since its own hand-rolled `sync_gitea_repos.sh` (cp -a + diff -rq puller,
     unconfirmed/never run for real) would be redundant if so. Confirmed: yes, real, native,
     already in production use (extensively tested this session against a mock Gitea server and a
     live NAS run) - and does more than the hand-rolled version (Secrets Store-driven URL/token
     resolution, live repo dropdown, removes files no longer present upstream). `SCRIPTING.md`'s
     Platform Overview no longer just implies this parenthetically; it says so outright and tells
     a repo with its own puller to retire it. Bumped to 1.2.0.
- **Fix: iPad Safari silently re-cased a typed Secrets Manager value** — real bug hit live on the
  NAS: typing `EOHD` into the "New Entry" text field posted as `Eohd`, no error, no visible sign
  it happened. Root cause confirmed in `web-src/src/common/components/textfield.vue` - the
  `<input>` set no `autocapitalize`/`autocorrect`/`spellcheck` attributes, so every plain-text
  parameter fell back to iOS/iPadOS Safari's defaults (`autocapitalize="sentences"` + autocorrect
  on), which can silently re-case or "correct" a short all-caps token a human typed on purpose
  (category names, key fragments, hostnames). Different field type and different mechanism from
  the earlier masked-field/password-manager issue - same root cause class (an iOS Safari default
  nobody had turned off). Fixed by adding `autocapitalize="off" autocorrect="off"
  spellcheck="false"` to the input - applies to every plain-text parameter across every runner, no
  case where the browser's default was ever wanted. **Needs a live-iPad check on the real NAS
  instance** before considered fully verified - `vue-cli-service build` wasn't run in this
  environment (static attribute change, no `node_modules` installed here).
- **Added 8 `finance` category entries to `KNOWN_INTEGRATIONS`** — `EOD_API_KEY` (used by
  Portfolio Setup/Update Prices in `ss_finance_management` for price fallback when FT
  Markets/Yahoo fail) plus 7 reserved-for-now placeholders (`FMP_API_KEY`, `FRED_API_KEY`,
  `ALPH_API_KEY`, `MKTSTACK_API_KEY`, `FINNHUB_API_KEY`, `COINAPI_API_KEY`, `TIINGO_API_KEY`),
  each explicitly marked as having no consuming script yet so they don't look silently configured.
  Requested directly by the user ahead of upcoming `ss_finance_management` scripts.
- **Secrets Manager: fixed the New Entry field, again, for a different reason than last time** -
  direct user feedback: the merged `category/KEY` text field (see the cross-repo-drift entry
  above) was now the confusing part - no way to tell category and key apart, and no way to reuse
  an existing category without retyping it from memory (risking a silent `Finance` vs `finance`
  duplicate). Fixed without adding a second always-visible field (still the real constraint - see
  the same earlier entry): `secrets_store.py`'s `dropdown-entries` now also emits one
  `+ ADD NEW KEY TO <category>` sentinel per category already in the store, so picking an existing
  category happens in the dropdown, not a text field - `New Entry` then only needs the bare `KEY`
  name. Brand new category still goes through `New Entry` as `category/KEY`, now behind its own
  clearer sentinel (`+ CREATE NEW ENTRY IN A NEW CATEGORY`). Added
  `category_from_add_key_sentinel()` to `secrets_store.py` and taught `secrets_manager.py`'s
  `parse_entry()` the new case, with its own validation errors (blank key, or a `/` typed out of
  habit when it's not needed). Verified standalone: all 3 successful paths (add-to-existing,
  brand-new-category, pick-existing-entry) plus both new error paths return exactly the expected
  result - **still needs a live-NAS check through the real UI/preload banner**.
  `secrets_manager.py` -> 1.3.0, `conf/runners/secrets_manager.json` -> 1.4.0, `CLAUDE.md` ->
  1.28.0.
- **Secrets Manager: "Category" renamed to "Product," and the underlying data model actually
  fixed to earn that rename** - more direct user feedback, and this time the fix from the prior
  entry was itself part of the problem. Two complaints: (1) "Category" read as a product name for
  `gitea`/`paperless`/etc. but not for `finance`, which secretly grouped eight unrelated
  providers under one name; (2) the sentinel-based "+ ADD NEW KEY TO X" flow from the prior entry
  still errored with a confusing "must be in the form category/KEY" message when a user picked
  the wrong sentinel, because two genuinely different concepts (product name, key name) were
  still being packed into other flows as a single string. Root-caused properly this time instead
  of patching around it again: split `finance` into one product per provider (`eod`, `fmp`,
  `fred`, `alphavantage`, `marketstack`, `finnhub`, `coinapi`, `tiingo`, each holding just
  `API_KEY`), which let "Category" become an honest, accurate rename to "Product" everywhere -
  UI labels, runner descriptions, `secrets_store.py`'s own function names
  (`get_secret`/`set_secret`/`delete_secret(product, key)`, `list_products()`,
  `list_product_keys()`), and every consumer (`gitea_client.py`, `import_from_gitea.py`, its
  preload). The now-unnecessary "+ ADD NEW KEY TO `<category>`" per-category sentinel mechanism
  was deleted entirely (simpler than adding a fourth field to keep patching it) in favor of a
  single `+ CREATE NEW ENTRY` sentinel paired with two always-visible fields: **New Product**
  (`editable_list` type - autocomplete-suggests every existing product via
  `secrets_store.py list-products`, but still accepts a typed new one) and **New Key** (plain
  text). `category/KEY`-as-one-string parsing is gone completely - no more slash format to get
  wrong. `CLAUDE.md`'s Secrets Store section now carries the full three-round history of this
  field's design (see "Real confusion, three times") so a future redesign doesn't re-walk the
  same dead ends. Verified standalone: all `parse_entry()` paths (new entry with existing
  product, new entry with brand new product, picking a real/suggested entry, both blank-field
  error cases) return exactly the expected result - **still needs a live-NAS check**, and
  `editable_list`'s autocomplete behavior specifically hasn't been visually confirmed in a real
  browser. `secrets_manager.py` -> 1.4.0, `conf/runners/secrets_manager.json` -> 1.5.0,
  `secrets_viewer.py`/`secrets_viewer.json` -> 1.4.0, `import_from_gitea.json` -> 4.1.1,
  `CLAUDE.md` -> 1.29.0, `SCRIPTING.md` -> 1.3.0. **Real cost, not free**: the already-built
  `Portfolio Setup/Update Prices` script in `ss_finance_management` calls
  `get_secret('finance', 'EOD_API_KEY')` and needs updating to `get_secret('eod', 'API_KEY')` -
  a change to a different repo, outside this session's access (see In Progress below).

## In Progress

- **Needs a Docker rebuild + live-iPad verification**: the `textfield.vue`
  autocapitalize/autocorrect/spellcheck fix (see Done above, 2026-09-07 entry).
  Code is committed and pushed; nothing has been rebuilt or retested on the
  real NAS yet. Run `docker compose up -d --build`, then retype `EOHD` (or
  any short all-caps token) into a plain text field on the actual iPad and
  confirm it now posts unmangled.
- **Needs the same rebuild to actually appear**: the new `KNOWN_INTEGRATIONS` entries for `eod`,
  `fmp`, `fred`, `alphavantage`, `marketstack`, `finnhub`, `coinapi`, `tiingo` (see the
  Category-to-Product rework below) - code-only change to a Python list, picked up on next
  container restart (no frontend rebuild strictly required for this one, but it'll land alongside
  the textfield fix anyway). Confirm they show up in Secrets Manager's dropdown and Secrets
  Viewer's "Not Yet Configured" list after restart.
- **Needs a live-NAS check**: Secrets Manager's reworked New Product (`editable_list`) + New Key
  fields, replacing the old single "New Entry" text field entirely - `parse_entry()` logic
  verified standalone (see Done below), but not yet exercised through the real dropdown/preload
  banner on the NAS, and `editable_list`'s autocomplete-suggest-but-still-type-new behavior
  specifically hasn't been visually confirmed in a real browser. No rebuild needed (Python + JSON
  only, no `web-src/` touched) - just restart the container and try creating a new entry.
- **Cross-repo change needed, outside this session's access**: `ss_finance_management`'s
  `Portfolio Setup/Update Prices` script calls `get_secret('finance', 'EOD_API_KEY')` (the old
  grouped-category name, now removed from this store) - it needs updating to
  `get_secret('eod', 'API_KEY')` to match the Category-to-Product rework below. Flag this to
  whoever picks up that repo next; until it's updated, that script's EOD Historical Data fallback
  will silently find no secret (returns `None`, same as "never configured") rather than erroring
  loudly - worth a quick manual check there after the rename lands.

## Planned

1. **Bake runtime-installed packages into the image permanently** — *Admin script + Dockerfile*.
   The install-at-runtime half is done (see Done above); this closes the loop so a package chosen
   via Install Package can also be added to `tools/Dockerfile` and rebuilt in, rather than staying
   ephemeral. Runner-Generator-shaped: read `installed_extras.json`, patch the Dockerfile's package
   list, prompt for a rebuild.

2. **Scheduling** — *Config/verification*. Already a built-in script-server feature
   (`src/scheduling/`, `SchedulePanel.vue`). Needs verifying it works cleanly with our runner
   parameter types (e.g. dynamic dropdowns re-resolving at scheduled run time) and documenting the
   workflow — not built from scratch.

3. **System-following theme** — *Config only*. Author `conf/theme/theme.css` using
   `@media (prefers-color-scheme: dark)` — script-server already serves this file if present. Zero
   code changes for automatic light/dark; a manual in-UI toggle would be a Core change on top of this.

4. **Per-secret description field, settable via Secrets Manager** — *Admin script + data model*.
   Direct user feedback: right now a description only exists for entries still listed in
   `KNOWN_INTEGRATIONS` (a hardcoded Python list) - once a value is actually set, or for any
   ad-hoc product/key created via Secrets Manager's New Product/New Key fields (e.g. a hand-typed
   `Adobe`/`API_KEY`), there is no way to record or see *why* that secret exists or how it's used.
   Add a `description` field to each entry in `secrets.json` (alongside `value`/`updated_at`),
   settable/updatable via a new optional field in Secrets Manager, and shown in Secrets Viewer for
   both set and not-yet-set entries (today only the not-yet-set/placeholder table shows a
   description, sourced from the hardcoded list - the "set" table shows none at all). For an
   entry that's also in `KNOWN_INTEGRATIONS`, a user-entered description should probably override
   the coded one rather than sit alongside it - the user's own words about their actual use case
   are more useful once they've actually configured it.

## Ideas / Backlog (need more design discussion before committing)

- **Ship a default/example `secrets.json` instead of hardcoding known integrations in Python** —
  *needs a design decision on merge strategy before building*. Direct user feedback:
  `KNOWN_INTEGRATIONS` in `secrets_store.py` hides the list of expected secrets inside a script
  instead of making it visible as data, and doesn't let a user browse/edit "known but unset"
  entries the same way as real ones. Proposed direction: ship a checked-in seed/example file
  (e.g. `conf/secrets.default.json`) with empty-value placeholder entries carrying the same
  description text `KNOWN_INTEGRATIONS` has today (ties into the per-secret description field
  above), and have Secrets Manager/Viewer read that file merged with the real
  `/app/data/secrets.json` rather than a Python constant - so the expected-secrets list is just
  data, visible and diffable in git, not buried in `secrets_store.py`. Open question that needs
  resolving before this is buildable: how does the seed get applied - copied into
  `/app/data/secrets.json` once on first run (simple, but a later `git pull` that adds new
  placeholder products would never reach an already-initialized store), or merged in live on
  every read (stays current, but needs to correctly distinguish "seed says not-yet-set" from "user
  explicitly set an empty string" and must never let a re-copied seed clobber a real value).
  Whichever direction, this would retire `KNOWN_INTEGRATIONS` as a Python list entirely - the same
  product/key/description data, just moved into the data file it was always describing.
- **Secret Ingredients Check** — *Admin script, mirrors the existing `motd.py` "Script Ingredients
  Check" pattern*. User's request, explicitly flagged as exploratory/not urgent: a scanner that
  greps every script under `scripts/` for `get_secret(...)` / `secrets_store.py get ...` calls,
  extracts the product/key pairs actually referenced in code, and cross-checks them against what's
  really set in the store - flagging any secret a script expects that isn't configured yet,
  visible before the script fails on it at runtime rather than after. Script-Server has no
  built-in file-watcher/webhook trigger to run this truly "whenever something is added or
  updated," so the realistic options are: (a) run it as an extra step at the end of every Import
  from Gitea execution, since that's the actual point in this fork's workflow where scripts get
  added/changed, or (b) a standalone on-demand Admin script the user runs periodically, same
  pattern as MOTD's own Script Ingredients Check. User's own framing: this could extend later to
  wider health/quality-control signals beyond secrets, not just a secrets-only checker - worth
  designing with that extensibility in mind (e.g. folding into or running alongside `motd.py`'s
  existing missing-file audit) rather than as a one-off.

- **Encrypted-at-rest secrets store** — *Core-adjacent*. The plaintext categorized store (Secrets
  Manager/Viewer, see Done above) now covers the "manage multiple API keys via the Admin UI, no
  restart" need. What's still open is genuine encryption at rest: no existing vault to build on
  (`encryption_utils.py` is auth password-hashing only), and it would need real thought on key
  management and how it interacts with script-server's own auth model before writing code. Only
  worth doing if the plaintext-on-disk risk tier (same as a Docker environment block) stops being
  acceptable.
- **Form-first UI, terminal minimized** — *partly already possible* by designing runners around
  rich parameter forms (chained dropdowns, `server_file`, `html`/`html_iframe` output) rather than
  raw terminal text — Network Device Labelling/Network Scanner already lean this way. *Fully*
  hiding the terminal/log panel is a **Core change** to `web-src/` (e.g. `script-view.vue`).
- **Nested script groups (multi-level hierarchy)** — *Core change*. Confirmed in the actual code,
  not assumed: `"group"` on a runner is a single flat string, `ScriptListGroup.vue` renders
  `group.scripts` as a flat list with no recursion into child groups, and folder-based grouping
  (`group_by_folders`) collapses any nested subfolder path down to just the top-level folder name
  (`src/model/script_config.py`'s `read_short` walks up to the outermost segment only). So today
  there is genuinely one level of grouping, and the only way to cluster related scripts inside a
  group is naming them to sort adjacently (confirmed scripts sort alphabetically by name within a
  group - `web-src/src/main-app/store/scripts.js`). That's the workaround already in use: renaming
  Label Device / View Inventory to **Network Device Labelling** / **Network Device Inventory** so
  they sort next to **Network Scanner** instead of appearing unrelated. Real nested groups (e.g.
  Network > Scanner / Labelling / Inventory, collapsible per level) would need both a backend model
  change (group as a path, not a single string) and a frontend change (`ScriptListGroup.vue`
  recursing into child groups) - a genuine Core change, not a config tweak.

-----

## Notes on Core changes

The first real Core change has now shipped and been **verified on the real NAS instance**: a fix for
the log panel's Copy/Download buttons doing nothing on `html_iframe` output (found while testing
MOTD). Full write-up — root cause, exact files changed, and why — lives in `CLAUDE.md` under "Core
Changes (Fork Divergence from Upstream)", which is now the standing place to log any future edit to
script-server's own `src`/`web-src` source, so these don't get lost on a `git pull`/rebase from
upstream `bugy/script-server` and so it's clear a full image rebuild (not just a scripts/conf file
copy) is needed to pick them up.

That same MOTD testing surfaced and led to fixing a second, unrelated bug (an Admin script, not a
Core change): `motd.py` was resolving a relative `working_directory` against its own process cwd
instead of Script-Server's actual root, wrongly flagging real Gitea-imported scripts as missing.
Also verified fixed on the real NAS instance.

The "Core change" backlog items above (nested groups, hide-terminal, auto-hide sidebar) are the
next candidates. Since Playwright + Chromium are already baked into the Docker image (and available
in the dev sandbox), frontend changes can actually be visually verified with screenshots before
shipping, rather than shipped untested — worth doing before touching `web-src/` for real.
