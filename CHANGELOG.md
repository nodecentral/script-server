# What's new

This is the nodecentral fork of [Script-Server](https://github.com/bugy/script-server) by bugy,
running on the home NAS. The version number is the one in `version.txt`, shown at the bottom of
the sidebar. Newest first.

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
- The built-in scripts now sit under **System**, in Secrets, Maintenance and Examples.

### Look and feel
- New indigo colour scheme, set by `conf/theme/theme.css`. Edit or empty that file to change it.
- The version number is shown at the bottom of the sidebar, with this page one click away.

### Under the hood
- Missing-secret banners now link to Secrets Manager on the Settings page.
- Runner JSON gains two fields: `category` and `placement`.

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
