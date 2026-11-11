[![Build Status](https://travis-ci.com/bugy/script-server.svg?branch=master&status=passed)](https://travis-ci.com/bugy/script-server) [![Gitter](https://badges.gitter.im/script-server/community.svg)](https://gitter.im/script-server/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge)

# script-server

## About this repository

This repository is a fork / local copy of [bugy/script-server](https://github.com/bugy/script-server), the
original Script Server project and its author. It exists to build a tailored, self-contained version of
Script Server for our own use — in particular a custom Docker image (see [`tools/Dockerfile`](tools/Dockerfile))
with extra runtime prerequisites baked in (OCR, PDF/document tooling, browser automation, finance-quote
lookups, etc.) so scripts that depend on them work out of the box.

Except where noted, the documentation below is inherited from the upstream project and describes
Script Server itself rather than anything specific to this fork. For the original project, official
releases, issue tracker, and community support, see [bugy/script-server](https://github.com/bugy/script-server).

---

Script-server is a Web UI for scripts.  

As an administrator, you add your existing scripts into Script server and other users would be able to execute them via a web interface.
The UI is very straightforward and can be used by non-tech people.

No script modifications are needed - you configure each script in Script server and it creates the corresponding UI with parameters and takes care of validation, execution, etc.  

[DEMO server](https://script-server.net/)

[Admin interface screenshots](https://github.com/bugy/script-server/wiki/Admin-interface)

## Features
- Different types of script parameters (text, flag, dropdown, file upload, etc.)
- Real-time script output
- Users can send input during script execution
- Auth (optional): LDAP, Google OAuth, htpasswd file
- Access control
- Alerts
- Logging and auditing
- Formatted output support (colors, styles, cursor positioning, clearing)
- Download of script output files
- Execution history
- Admin page for script configuration

For more details check [how to configure a script](https://github.com/bugy/script-server/wiki/Script-config)
or [how to configure the server](https://github.com/bugy/script-server/wiki/Server-configuration)

## Requirements

### Server-side

Python 3.7 or higher with the following modules:

* Tornado 5 / 6

Some features can require additional modules. Such requirements are specified in a corresponding feature description.

OS support:

- Linux (main). Tested and working on Debian 10,11
- Windows (additional). Light testing
- macOS (additional). Light testing

### Client-side

Any more or less up to date browser with enabled JS

Internet connection is **not** needed. All the files are loaded from the server.

## Installation
### For production
1. Download script-server.zip file from [Latest release](https://github.com/bugy/script-server/releases/latest) or [Dev release](https://github.com/bugy/script-server/releases/tag/dev)
2. Create script-server folder anywhere on your PC and extract zip content to this folder

(For detailed steps on linux with virtualenv, please see [Installation guide](https://github.com/bugy/script-server/wiki/Installing-on-virtualenv-(linux)))

##### As a docker container
Upstream pre-built images: https://hub.docker.com/r/bugy/script-server/tags  
For the usage please check [this ticket](https://github.com/bugy/script-server/issues/171#issuecomment-461620836)

> This fork builds its own image from [`tools/Dockerfile`](tools/Dockerfile) with additional prerequisites
> installed (see that file for the current package/library list). It is not yet published to Docker Hub.
>
> **Building the image** — on the NAS over SSH (or any x86_64 machine with Docker), from a clone of
> this repo:
> ```
> git clone --branch <branch> https://github.com/nodecentral/script-server.git script-server-src
> cd script-server-src
> tools/build_and_push.sh v2        # builds tools/Dockerfile, pushes 192.168.102.227:5011/script-server:v2
> ```
> `REGISTRY=host:port` overrides the registry. The script refuses to push `latest` (what an existing
> install pulls) unless you add `--allow-latest`. To update later: `git pull`, run it again, then
> `docker compose pull && docker compose up -d` in the install folder.
>
> **Installing** — pick one of the ready-made setups in [`deploy/`](deploy):
> - [`deploy/container-station/`](deploy/container-station) — for QNAP Container Station (Applications ›
>   Create, paste the file). Absolute paths, since Container Station doesn't run compose from a folder.
>   This is how the NAS runs it.
> - [`deploy/standalone/`](deploy/standalone) — the same with `./` paths, for `docker compose up -d` over
>   SSH from a copy of that folder. Everything lives next to the compose file (`./conf`, `./scripts`,
>   `./data`, `./logs`), so nothing is written anywhere else on the NAS.
>
> Either way: empty folders are fine (they're seeded on first start), and never run compose from the
> source checkout itself. The **port and title are in `conf/conf.json`** (see
> `deploy/standalone/conf/conf.json`, port 5012): host networking means there's no `ports:` mapping.
> Each compose file explains the rest line by line.
>
> **Upgrading from v1 runners** — existing runner files aren't changed by a new image (they're your
> content). `tools/migrate_runners_v2.py` moves them to the v2 layout in place: Import from Gitea,
> Install Package and Secrets Manager to the Settings page, everything in the old "Admin" group to
> **Script Server › Demo / Tools**. Dry run first, then apply:
> ```
> docker exec -i script-server-v2 python3 - < tools/migrate_runners_v2.py
> docker exec -i script-server-v2 python3 - --apply < tools/migrate_runners_v2.py
> ```
> (`-i` matters: without it the script never reaches the container and nothing happens.)
>
> The image mounts four folders so they survive container restarts and rebuilds:
> - `conf/` — server config and runner definitions (`conf/runners/*.json`)
> - `scripts/` — the scripts your runners execute, including `scripts/shared/` for helper scripts used by
>   dynamic dropdowns
> - `data/` — persistent storage for files your scripts read/write
> - `logs/` — server and per-execution logs
>
> **Empty folders are fine — the image seeds them.** See [Bind mounts and first-run seeding](#bind-mounts-and-first-run-seeding)
> below for the recommended layout and exactly what is (and isn't) overwritten on an upgrade.
>
> Working examples ship in `conf/runners/` + `scripts/` out of the box. They sit under the **Script
> Server** category in the sidebar (groups **Tools** and **Demo**), while Import from Gitea, Install
> Package and Secrets Manager are admin-only tabs on the Settings page (`admin.html`). See
> `SCRIPTING.md` → "Where a Script Shows Up" for `category`, `group` and `"placement": "settings"`:
> - **Hello World** — basic parameters
> - **File Info** — native file browser over `data/`
> - **Disk Usage** — confirms the bind mounts above are actually connected, then shows a tree view of a
>   picked path
> - **Import from Gitea** — pulls scripts/runners from a Gitea repo using the same layout into this
>   instance (dry-run by default, `--apply` to write). No Gitea URL or owner/username field on the
>   form at all — both the URL and one or more tokens live in Secrets Manager (product `gitea`,
>   keys `URL` and `TOKEN`), and the Repo dropdown lists live `owner/repo` options straight from
>   Gitea's own API for whichever token is in play. The banner checks both are set, confirms the
>   token actually works, and lists your repos with when each last changed in Gitea and when it was
>   imported here. The stored token is pre-selected. The report lists every file with its installed
>   and Gitea version, and imported scripts get a one-tap **update from Gitea** button (cloud icon,
>   admins only) in their header.
> - **Download Image** — fetches a URL into `data/` and displays it inline
> - **Disk Usage Chart** — interactive Plotly chart of used/free space per mount
> - **Terminal Colors** / **Progress Demo** — ANSI colour and live-progress output, written in Lua
> - **Confirm Gate (template)** — a reusable typed-confirmation safety gate for destructive scripts
> - **MOTD** — the banner (before you click Run) shows a live system-stats dashboard via a genuinely
>   separate `scripts/preload/motd.py`; running it performs a **Script Ingredients Check** across every
>   runner, grouped and collapsible, confirming each one's script/preload files actually exist
> - **Secrets Manager** — set/update/delete an entry in a secrets store keyed by product (e.g. a
>   `finnhub` product holding an API key, a `paperless` product holding a token) shared by other
>   scripts; values are never echoed back
> - **Secrets Viewer** — browse that store as a table (`html_iframe`) — product, key, last-set,
>   never the actual value
>
> Use them as templates for your own.
>
> The network scanner / device labelling / device inventory examples that used to ship here now live
> in their own Gitea repo, `claude/ss_network_management` (`network_scan.lua`, `network_label_device.py`,
> `network_inventory_viewer.py`, `shared/network_inventory.py`) — bring them in with **Import from Gitea**.
> Upgrading an install that already had the old copies (`network_scanner`, `label_device`,
> `view_inventory`, `shared/merge_inventory.py`, `shared/list_inventory.py`)? The entrypoint never deletes
> anything, so remove those once from `scripts/` and `conf/runners/` on the NAS — the image no longer
> ships them, so they stay gone.
>
> **Slim auto-hide sidebar (desktop).** The left sidebar collapses to a 56px rail with a single
> menu icon by default, freeing up width for script output/parameters — click it to expand the
> full sidebar as a temporary overlay; picking a script or clicking outside it snaps it back to
> the rail automatically. Click the pin icon in the expanded header to turn this off entirely and
> revert to the original always-docked sidebar — your choice is remembered across reloads. This is
> a Core change to `web-src/` (not a runner), so picking it up after a `git pull` needs a full
> image rebuild (`tools/build_and_push.sh`, then `docker compose pull && docker compose up -d`), same as any
> other frontend change.
>
> If you downloaded this as a ZIP rather than `git clone`d it, the execute bit on `scripts/*.sh` is not
> preserved — the image's entrypoint runs `chmod -R +x /app/scripts` on every container start to fix this
> automatically (set `CHMOD_SCRIPTS=false` to turn that off).
>
> **Host networking.** Both `deploy/` setups run the container with `network_mode: host` (Linux Docker
> hosts only, which Container Station is), so the app listens directly on the NAS on `conf.json`'s
> `port`. Three reasons:
> - A network scanner (e.g. `network_scan` from `ss_network_management`) sees your real LAN.
> - With `cap_add: [NET_RAW, NET_ADMIN]`, nmap/arp-scan can resolve MAC addresses.
> - The port is set in one place (`conf.json`), with no `ports:` mapping to keep in step.
>
> **Set `access.trusted_ips` in `conf.json` to your own LAN range** (the `deploy/` files use
> `10.0.0.0/26`, this NAS's LAN). Without a match, each instance tells browsers apart with a signed
> cookie, and two instances on one NAS keep replacing each other's cookie (cookies ignore the port).
> History's User column shows each device's reverse-DNS name. Use a private LAN range (`10.x`, `172.16–31.x`,
> `192.168.x`): on public address space such as `172.2.x.x` that name comes from public DNS (this NAS's
> LAN was `172.2.2.0/24` and showed `...sbcglobal.net` names until it moved to `10.0.0.0/26`). Avoid
> `172.17–31.x` too if you can: Docker allocates its own networks from there.
>
> **Service URLs under host networking:** other containers can't be reached by container name (that
> only works inside Docker's own networks). Store `http://<NAS IP>:<published port>` instead, e.g.
> `http://10.0.0.41:8777` for Paperless (`docker ps` shows the published port). If a service is
> published on the same port it listens on, an `extra_hosts: ["name:<NAS IP>"]` entry in the compose
> file also keeps the container name working.
>
> The trade-off is no network isolation from the NAS. To keep the container isolated instead, remove
> `network_mode: host` and `cap_add` and add `ports: ["<host port>:<conf.json port>"]`; container
> names then resolve only for containers on the same Docker network.

#### Bind mounts and first-run seeding

Docker bind mounts don't inherit image content: mount an empty host folder over `/app/conf` and the container
sees an empty `/app/conf`. So the image keeps its own copy of everything a working install needs under
`/app/defaults` (a path no mount covers), and `tools/docker-entrypoint.sh` copies it into the mounts each time
the container starts. A brand-new install with **empty** host folders therefore comes up with a `conf.json`,
`logging.json`, all the example runners, and all the scripts (including `scripts/shared/` and
`scripts/preload/`, e.g. `secrets_store.py`) — nothing to copy by hand.

**Recommended layout** (this is what `deploy/standalone/docker-compose.yml` uses):

```yaml
volumes:
  - ./conf:/app/conf        # the whole conf DIRECTORY (runners included)
  - ./scripts:/app/scripts
  - ./data:/app/data
  - ./logs:/app/logs
```

Mount `/app/conf` as a **directory**, not `conf.json` as a single file. If the host path of a single-file
mount doesn't exist, Docker creates a *directory* there, so `conf.json` becomes a folder and the server can't
read it (and nothing can be seeded into it). Mounting `/app/conf/runners` separately also works — the
entrypoint seeds it either way — but there's no reason to unless you want runners kept apart from `conf.json`.

**What gets seeded, and what never gets overwritten**

| Kind | Files | On every container start |
|---|---|---|
| User content | `conf.json`, `capabilities.json`, `secrets_defaults.json`, everything in `conf/runners/`, every script not listed below (including your own), `data/` | Copied in **only if missing**. An existing file is never touched, so your edits survive restarts and image upgrades. |
| Platform files | The names in [`tools/PLATFORM_FILES`](tools/PLATFORM_FILES): `conf/logging.json`, `scripts/shared/*`, `scripts/preload/*` | Overwritten **one file at a time**, only when they differ from the image's copy, each one logged (`platform file updated: ...`). The containing folder is never replaced, and files the image doesn't ship (your own `scripts/shared/foo.py`) are never touched. |

Nothing is ever deleted. Consequences worth knowing:

- **Upgrades don't update your runners or scripts.** A newer image only delivers changed runners, example scripts
  or `secrets_defaults.json` to a *fresh* folder; an existing install keeps what it has. To pick up a changed
  one, delete or rename it and restart (it is re-seeded from the image), or copy it out of `/app/defaults`
  yourself: `docker exec script-server cp /app/defaults/runners/notify.json /app/conf/runners/notify.json`.
- **Deleting a shipped runner/script doesn't stick** — a missing file can't be told apart from a never-seeded
  one, so it comes back on the next start. Set `SEED_DEFAULTS=false` if you'd rather manage those by hand.
- **Sharing runners/scripts/data with another instance?** Not recommended: each instance's start-up refreshes
  the shared platform files to *its own* image's copies, so two different versions keep undoing each other
  (this happened while v1 and v2 ran side by side - see CLAUDE.md, v2.1.1). If you must, set
  `SEED_DEFAULTS=conf` and `PLATFORM_REFRESH=conf` on the newer instance and `PLATFORM_REFRESH=false` on the
  older one. `SEED_DEFAULTS=false` would leave the instance's own `conf/` empty (no `capabilities.json` etc.).
- **Edits to a platform file are lost on the next start.** Keep local changes in your own files, not in the ones
  listed in `PLATFORM_FILES`. Adding a new file to `scripts/shared/` or `scripts/preload/` in this repo also means
  listing it in `tools/PLATFORM_FILES`; the build prints a notice for any that are missing.
- `scripts/import_from_gitea.py` (the main script, as opposed to its preload) and `conf/secrets_defaults.json` are
  user content, so they are *not* refreshed on upgrade. If you'd rather they were, add them to `PLATFORM_FILES`.
- Build from a clean checkout. The build bakes `conf/`, `scripts/` and `data/` from the build context into the
  image, and `.dockerignore` excludes runtime state (`conf/.htpasswd`, `data/secrets.json`, `__pycache__`...) — but
  an *untracked script* sitting in `scripts/` would still ship as a default.

**Owner of the seeded files: `PUID` / `PGID`.** By default the container runs as root (which a network scanner
needs for raw sockets), so seeded files are owned by root. To run the app as your own user instead, set
`PUID` and `PGID` (`PGID` defaults to `PUID`) — everything the entrypoint creates is then owned by that user,
the app runs as them, and you can edit the files on the host. A mount folder the app user can't write to gets its
own owner changed (just that folder, not what's inside; the entrypoint says so in its log and tells you the
`chown -R` to run if pre-existing files need it). Trade-off: a non-root app can't use `nmap`/`arp-scan`
raw-socket scans, and Playwright's browser is installed under root's home, so leave `PUID` unset if you
rely on those.

| Variable | Default | Effect |
|---|---|---|
| `PUID` / `PGID` | unset (root) | Run as this uid/gid; own seeded files as them |
| `SEED_DEFAULTS` | `true` | `false` = don't seed user content |
| `PLATFORM_REFRESH` | `true` | `false` = don't overwrite platform files (they're still filled in if missing) |
| `CHMOD_SCRIPTS` | `true` | `false` = don't `chmod -R +x /app/scripts` |

The entrypoint logs everything it does (`docker logs script-server`), for example:

```
[entrypoint] seeded conf/conf.json
[entrypoint] platform file updated: scripts/shared/secrets_store.py
[entrypoint] summary: seeded 0 new file(s), left 44 existing file(s) alone; platform files: 0 installed, 1 updated, 9 already current
```

`conf.json` is seeded as just `{"address": "0.0.0.0", "port": 5000}`. It deliberately does **not** grant admin
access: by default only `127.0.0.1` is an admin, so the admin page isn't reachable from your LAN. If you accept
the home-lab trade-off, add `"access": {"admin_users": ["*"]}` to `conf.json` and restart the container.

*Proposed, not implemented:* an opt-in way to refresh user-content files without a manual delete-and-restart —
e.g. `docker exec script-server /usr/local/bin/docker-entrypoint.sh --refresh runners/notify.json`, which would
copy the named shipped file over the existing one after saving the old copy as `notify.json.bak-<timestamp>`.
Explicit, per-file and reversible, unlike silently overwriting on every start.

### For development
1. Clone/download the repository
2. Run 'tools/init.py --no-npm' script

`init.py` script should be run after pulling any new changes

If you are making changes to web files, use `npm run build` or `npm run serve`

### A issue running on OpenBSD and maybe other UNIX systems
See [A issue running on OpenBSD and maybe other UNIX systems](https://github.com/bugy/script-server/wiki/OpenBSD-process-termination-issues).


## Setup and run
1. Create configurations for your scripts in *conf/runners/* folder (see [script config page](https://github.com/bugy/script-server/wiki/Script-config) for details)
2. Launch launcher.py from script-server folder
  * Windows command: launcher.py
  * Linux command: ./launcher.py
3. Add/edit scripts on the admin page

By default, the server will run on http://localhost:5000

### Server config
All the features listed above and some other minor features can be configured in *conf/conf.json* file. 
It is allowed not to create this file. In this case, default values will be used.
See [server config page](https://github.com/bugy/script-server/wiki/Server-configuration) for details

### Admin panel
Admin panel is accessible on admin.html page (e.g. http://localhost:5000/admin.html)

## Logging

All web/operating logs are written to the *logs/server.log*
Additionally each script logs are written to separate file in *logs/processes*. File name format is
{script\_name}\_{client\_address}\_{date}\_{time}.log.

## Testing/demo

Script-server has bundled configs/scripts for testing/demo purposes, which are located in samples folder. You can
link/copy these config files (samples/configs/\*.json) to server config folder (conf/runners).

## Security

I do my best to make script-server secure and invulnerable to attacks, injections or user data security. However to be
on the safe side, it's better to run Script server only on a trusted network.  
Any security leaks report or recommendations are greatly appreciated!

### Shell commands injection

Script server guarantees that all user parameters are passed to an executable script as arguments and won't be executed
under any conditions. There is no way to inject fraud command from a client-side. However, user parameters are not
escaped, so scripts should take care of not executing them also (general recommendation for bash is at least to wrap all
arguments in double-quotes). It's recommended to use typed parameters when appropriate, because they are validated for
proper values and so they are harder to be subject of commands injection. Such attempts would be easier to detect also.

_Important!_ Command injection protection is fully supported for Linux, but _only_ for .bat and .exe files on Windows

### XSS and CSRF

_(v1.0 - v1.16)_  
Script server _is_ vulnerable to these attacks.

_(v1.17+)_  
Script server is protected against XSRF attacks via a special token.      
XSS protection: the code is written according to
[OWASP Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/DOM_based_XSS_Prevention_Cheat_Sheet.html)
and the only **known** vulnerabilities are:

* `output_format`=`html_iframe`, see the reasoning in the
  linked [Wiki page]((https://github.com/bugy/script-server/wiki/Script-config#output_format))

## Contribution

If you like the project and think you could help with making it better, there are many ways you can do it:

- Create a new issue for new feature proposal or a bug
- Implement existing issues (there are quite some of them: frontend/backend, simple/complex, choose whatever you like)
- Help with improving the documentation
- Set up a demo server
- Spread a word about the project to your colleagues, friends, blogs or any other channels
- Any other things you could imagine

Any contribution would be of great help and I will highly appreciate it! 
If you have any questions, please create a new issue, or contact me via buggygm@gmail.com

## Asking questions
If you have any questions, feel free to:
- Ask in gitter: https://gitter.im/script-server/community
- or [create a ticket](https://github.com/bugy/script-server/issues/new)
- or contact me via email: buggygm@gmail.com (for some non-shareable questions)

## Special thanks
![JetBrains logo](https://github.com/JetBrains/logos/blob/master/web/jetbrains/jetbrains.svg)
