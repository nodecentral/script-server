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
- **Fix `motd.py` false-positive missing-script reports for relative `working_directory`** —
  Gitea-imported runners (e.g. the Music group) use a relative `working_directory` (`"scripts"`)
  rather than this repo's own `"/app/scripts"` convention, which `motd.py`'s existence check
  resolved against its own process cwd instead of Script-Server's actual root, wrongly flagging
  real, runnable scripts as missing. Fixed by resolving relative `working_directory` (and preload
  paths) against `/app`. **Verified on the real NAS instance**: after the fix, the Script Ingredients
  Check correctly reports "24 runner(s) across 2 group(s). All script/preload files present." for
  the actual Music-group runners imported from `ss_music_file_management`.

## In Progress

*(nothing right now)*

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

## Ideas / Backlog (need more design discussion before committing)

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
- **Auto-hide left sidebar** — *Core change* to `AppLayout.vue`/`MainAppSidebar.vue`. Contained in
  scope, but still frontend source, not just a runner.
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
