# What's new

This is the nodecentral fork of [Script-Server](https://github.com/bugy/script-server) by bugy,
running on the home NAS. The version number is the one in `version.txt`, shown at the bottom of
the sidebar. Newest first.

## 2.3.0 — 2026-11-12

- **Scripts can install what they need again.** A script that needs a program (like `exiftool`),
  a Lua module or a Python package installs it on its first run, as it was meant to, even though
  Script Server doesn't run scripts as root.
- **Lua modules and Python packages are kept** in the data folder (`data/.deps`), so they
  survive recreating the container and upgrading Script Server.
- **Programs need installing again after the container is recreated:** the script does this by
  itself on its next run, which is slower that one time.
- **Install Package works the same way,** and says which installs are kept.
- Don't want scripts installing system packages? Set `ALLOW_APT=false` on the container.

## 2.2.1 — 2026-11-12

- **Photo Dashboard works:** the SQLite module for Lua (`lsqlite3`) now comes with Script Server.
  Scripts can't install it themselves because Script Server doesn't run them as root.
- **Clearer message for a missing dependency.** When a script needs a program or Lua module that
  isn't installed, it now says straight away that it can't install it, and how to add it,
  instead of failing with "Permission denied".
- New categories with their own icons: **Audiobooks**, **Energy**, **Docker**.

## 2.2.0 — 2026-11-12

- **Import from Gitea keeps shared files.** If two repos ship the same file and one of them stops,
  the file now stays (shown as **KEPT**, "still shipped by …") instead of being deleted for both.
- **More versions recognised in the import report:** lines like `Version     : 1.0.0`, and version
  lines further down a long header, no longer show as CHANGED.
- **Shared helpers now ship with Script Server:** `ensure_module.lua` and `ensure_binary.lua` (which
  install a missing Lua module or program on first use) come with Script Server itself instead of
  being copied between repos. Import from Gitea never overwrites or deletes Script Server's own shared
  files; a repo still carrying a copy is shown **PLATFORM**, with a note to delete it.
- **Check Script Permissions is retired:** Script Server already makes scripts runnable on start-up
  and after every import.
- Updated scripting guide (SCRIPTING.md 2.2.0) for the `ss_*` repos.

## 2.1.1 — 2026-11-11

- **Fixed:** Import from Gitea wouldn't open ("Failed to connect to the server") when the shared
  `gitea_client.py` was an older copy, which happens when v1 runs alongside v2 and puts its own
  copy back on start. The form now always opens, without the token pre-fill in that case, and the
  import itself works with either copy.
- v1 is retired: v2 now runs on its own (QNAP Container Station, port 5012), with its own copies
  of the scripts, runners and data. `deploy/container-station/` holds the setup to paste into
  Container Station. The temporary "v2 alongside v1" setup has been removed.

## 2.1.0 — 2026-11-11

### Import from Gitea
- **Your Gitea token is filled in for you.** The Gitea Token field now starts on the token
  stored in Secrets Manager (the most recently set one if you have several), so the Repo list
  fills in straight away.
- **See what you're about to pick up.** The banner lists your repos, most recently updated
  first, with the time each last changed in Gitea, its default branch, and when it was last
  imported here. It flags any repo where Gitea has newer changes.
- **Versions and dates per file.** The import report lists every file with its installed and
  Gitea version, when it last changed in Gitea, and whether it's new, an update, unchanged, or
  **older** than what's installed (a warning that you may be on the wrong branch).
- **One-tap update (admins).** Scripts imported from Gitea get a cloud icon at the top right, next
  to the parameter-history clock. Tap it to re-import that script's repo straight away, without a
  dry run, and the script reloads with the new version. Hover over it to see which repo, branch
  and commit it came from.

### Sidebar
- The built-in scripts now sit under a **Script Server** category, in two groups: **Tools** (Secrets
  Viewer, Secret Ingredients Check, MOTD, Disk Usage, Backup, Send Notification, View
  Capabilities) and **Demo** (Hello World, Progress Demo, Terminal Colors, Confirm Gate, Download
  Image, File Info, Disk Usage Chart). The old "Admin" group is gone: real admin tools are on the
  Settings page.

### Installing and updating
- New ready-to-copy setups in `deploy/`: a standalone install, plus (for a while) v2 running
  alongside v1 sharing its scripts. Both use host networking, so History shows each device's real name and
  the port is set in `conf/conf.json`.
- `tools/build_and_push.sh v2` builds the image and pushes it to the registry (it won't push
  `latest` unless you ask).
- `tools/migrate_runners_v2.py` moves existing runner files to the v2 layout in one go.
- An instance sharing another's scripts (`SEED_DEFAULTS=conf`) now gets all of its own
  configuration on first start, so nothing can go missing.

## 2.0.0 — 2026-11-11

**A new layout: admin tools have their own Settings page, and scripts are organised by category.**

### Settings page (admins only)
- The admin page (the ⚙ cog) now has a horizontal menu: **Logs · Scripts · Import from Gitea ·
  Install Package · Secrets Manager**. The menu scrolls sideways when it doesn't fit.
- Import from Gitea, Install Package and Secrets Manager run right there, with the same banner, form
  and live output as before, and they no longer appear in the sidebar.
- Only admins can see or run them, even by typing the address in directly.
- Any runner can be moved here with `"placement": "settings"`, or with the new
  **Settings tab (admin only)** box when editing a script.

### Categories in the sidebar
- Scripts are now arranged **Category › Group › Script**. When the sidebar is tucked away, the slim
  bar on the left shows one icon per category (e.g. **£** for Finance). Click one to open it.
- Scripts without a category are listed under **Uncategorised**, always last. Scripts without a
  group are listed after the groups.
- Search looks across every category and shows where each match lives, e.g. *Finance › Portfolio*.
- Category icons and order are set in one place, `conf/categories.json`. A new category used by a
  script is added there automatically, with a plain label icon you can change.
- The built-in scripts now sit under one category (see 2.1.0 for where they ended up).

### Look and feel
- New indigo colour scheme, set by `conf/theme/theme.css`. Edit or empty that file to change it.
- The version number is shown at the bottom of the sidebar, with this page one click away.

### From upstream Script-Server (up to August 2026)
- **History loads in pages:** a Rows / Previous / Next control under the list, so History stays
  quick however many runs build up.
- Login cookies are hardened (httponly; "secure" automatically when using HTTPS).
- Only if `access.user_header_name` is set in `conf.json` (not used here): the identity header is
  now trusted only with a matching `access.user_header_secret`.

### Under the hood
- Missing-secret banners now link to Secrets Manager on the Settings page.
- Runner JSON gains two fields: `category` and `placement`.
- Fixed the script editor dialog occasionally erroring after it closes.

## 1.x — September – October 2026

The first releases of this fork, built on upstream Script-Server (December 2025).

- **Secrets Store**: Secrets Manager and Secrets Viewer keep API keys and tokens in one place.
  Scripts ask for the secrets they need, and anything not set yet shows up ready to fill in, with a
  warning banner on the script itself.
- **Import from Gitea**: pull scripts and runners from the Gitea repos, with a live repo
  picker and a readiness check before you run it.
- **Install Package**, **MOTD** (system stats plus a check that every script's files exist),
  **Send Notification** (Pushover/Prowl), **Backup**, **Disk Usage** and more example scripts.
- **Slim sidebar rail** on desktop, so scripts get more room. The lock icon pins the sidebar open.
- **Fixes**: Copy/Download now work for rich (HTML) script output. iPad Safari no longer changes
  the capitalisation of what you type into fields.
- **Docker**: a fresh install with empty folders sets itself up; NAS folders live under
  `/share/...`.
- The network scanner examples moved to their own repo, `ss_network_management`.
