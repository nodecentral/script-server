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
  Colors, Progress Demo, Confirm Gate, Download Image, Disk Usage Chart, Network Scanner, Label
  Device, View Inventory
- Persistent MAC-keyed device inventory pattern (collector + editor + viewer over a JSON store)
- `network_mode: host` + `cap_add: [NET_RAW, NET_ADMIN]` for real LAN scanning

## In Progress

*(nothing right now)*

## Planned

1. **Package/capability library** — *Admin script + Dockerfile*. A manifest (JSON) listing what's
   baked into the image (with versions) plus optional extras (imagemagick, etc.) not installed by
   default. An "Install Package" runner installs from the same manifest at runtime (ephemeral until
   rebuild) and can regenerate `tools/Dockerfile`'s package list so the same choice can be baked in
   permanently. Ties into the Runner-Generator and Persistent State patterns already in `CLAUDE.md`.

2. **Notifications (Pushover/Prowl)** — *Admin script*. A reusable "Send Notification" script
   (secure API token param, calls Pushover/Prowl's HTTP API directly) other scripts can invoke —
   e.g. Network Scanner pinging you when a new device appears. Not touching core `alerts_service.py`
   (its fixed `{title, message}` JSON payload doesn't match either API's expected fields anyway).

3. **Backups** — *Admin script*. Archives `conf/`, `scripts/`, and optionally `data/` into a
   timestamped tarball, offered as a download via `output_files`. Low effort, no open questions.

4. **Scheduling** — *Config/verification*. Already a built-in script-server feature
   (`src/scheduling/`, `SchedulePanel.vue`). Needs verifying it works cleanly with our runner
   parameter types (e.g. dynamic dropdowns re-resolving at scheduled run time) and documenting the
   workflow — not built from scratch.

5. **System-following theme** — *Config only*. Author `conf/theme/theme.css` using
   `@media (prefers-color-scheme: dark)` — script-server already serves this file if present. Zero
   code changes for automatic light/dark; a manual in-UI toggle would be a Core change on top of this.

## Ideas / Backlog (need more design discussion before committing)

- **Secrets management UI** — *Core-adjacent*. No existing vault to build on
  (`encryption_utils.py` is auth password-hashing only). Would need our own encrypted-at-rest JSON
  store plus real thought on key management and how it interacts with script-server's own auth
  model before writing code.
- **Form-first UI, terminal minimized** — *partly already possible* by designing runners around
  rich parameter forms (chained dropdowns, `server_file`, `html`/`html_iframe` output) rather than
  raw terminal text — Label Device/Network Scanner already lean this way. *Fully* hiding the
  terminal/log panel is a **Core change** to `web-src/` (e.g. `script-view.vue`).
- **Auto-hide left sidebar** — *Core change* to `AppLayout.vue`/`MainAppSidebar.vue`. Contained in
  scope, but still frontend source, not just a runner.

-----

## Notes on Core changes

Everything shipped in this fork so far has been runner JSON + standalone scripts — zero edits to
script-server's own Python/Vue source. The two "Core change" items above (#2 hide-terminal, #4
auto-hide sidebar) would be the first departure from that. Since Playwright + Chromium are already
baked into the Docker image (and available in the dev sandbox), frontend changes can actually be
visually verified with screenshots before shipping, rather than shipped untested — worth doing
before touching `web-src/` for real.
