# Script-Server.md — Platform Context

Version: 1.13.0
Last updated: 2026-09-06

## Platform Overview

Script-Server by Bugy running in Docker on QNAP NAS. Provides a web UI
for running scripts with structured parameter forms and live streaming output.

- Scripts live in `scripts/`, runners in `runners/`. Non-standalone support
  scripts live in subfolders named for their role: `scripts/shared/` for
  dynamic-dropdown helpers, `scripts/preload/` for preload scripts (see
  Preload Scripts below)
- Prefer Lua for lightweight automation, Python where ecosystem matters
- Lua 5.1+ compatibility required
- Be conscious of QNAP OS limitations (limited shell utilities, non-standard paths)
- Confirmed version in use: v1.18

-----

## Matched Pair Rule

Every solution MUST produce a matched pair:

- `name.lua` / `name.py` / `name.sh` — the script
- `name.json` — the runner config
- Filenames must match exactly (same base name, different extension)
- Include `"_version": "x.y.z"` in every runner JSON — Script-Server ignores
  unknown fields, making it immediately clear which version is deployed on disk
- Increment both the script header `# Version:` AND runner `"_version"` together
  on every meaningful change, using semver:
  patch = bug fix · minor = new feature · major = breaking change

-----

## Script Requirements

- Shebang line always
- Header comment block: name, version, description
- Debug toggle (`DEBUG=true/false`) with timestamped output
- Flush stdout after every print — Script-Server streams live, buffered output
  will not appear until the buffer fills or the script exits
- Safe argument handling with defaults — never assume a parameter exists
- Runnable standalone from terminal AND inside Script-Server

-----

## Execute Permissions — CRITICAL

Script-Server will silently fail to run any `.sh` file without the execute bit.
For values scripts this means the dropdown is **greyed out with no error shown**.

**Fix at the Docker level** — add to your `docker-compose.yml` so permissions
are set automatically on every container start. Use `;` (or `2>/dev/null;`),
**not** `&&`, between the chmod and the app launch — see the QNAP note below
for why a failing chmod must never block the container from starting:

```yaml
services:
  script-server:
    entrypoint: ["/bin/sh", "-c", "chmod -R +x /app/scripts 2>/dev/null; exec python /app/server.py"]
```

**Manual fix** (after copying files into a running container):

```bash
chmod +x /app/scripts/shared/my_helper.sh
```

Never assume execute permissions survive a file copy into a Docker volume.

### QNAP: `chmod` inside a container can fail with "Bad address" (EFAULT)

Confirmed on a real QNAP NAS (Container Station): running `chmod` from *inside*
a container against a bind-mounted host folder can fail with
`chmod: changing permissions of 'X': Bad address`, even though the exact same
`chmod` command run natively on the NAS shell (outside Docker, directly via
SSH) on the same files succeeds without issue. This looks like a QNAP
bind-mount-specific quirk, not a general filesystem/ACL problem — test by
running the chmod natively first; if that works, the container-side chmod is
the only thing affected.

Consequences and fix:
- If your entrypoint uses `chmod ... && exec ...`, a failing chmod means the
  app **never starts at all** — always make the chmod best-effort (`;` or
  `2>/dev/null;`, not `&&`) so a permissions hiccup degrades to "scripts
  might not be executable yet" instead of "container won't boot."
- After extracting a ZIP download on the NAS (which doesn't preserve the
  execute bit), run `chmod +x scripts/*.sh scripts/**/*.sh` once, natively,
  directly over SSH — before relying on the container to fix it for you.
- When a script needs to verify a bind mount is genuinely connected (as
  opposed to just an empty directory created inside the image), check for a
  file that only ever arrives via that mount and is never baked into the
  image — don't rely on `df`/`mount` output alone, since bind-mount visibility
  there varies by host and storage driver.

-----

## Runner Requirements

### script_path — CRITICAL

When `working_directory` is set, `script_path` must be the **filename only**:

- ✓ CORRECT: `"script_path": "my_script.py"`
- ✗ WRONG:   `"script_path": "scripts/my_script.py"`

Including the folder in both fields causes a path error. Applies to all
script types: `.py`, `.lua`, `.sh`.

### Parameter types

- Use `"type": "list"` NOT `"type": "select"`
- Use `"type": "multiselect"` when the user must pick multiple values
- Display labels use `"values_ui_mapping": {"value": "Label"}` — a key/value object
- ⚠ `"labels": []` does NOT exist in Script-Server — silently ignored, never use it
- Label strings in `values_ui_mapping` are plain text. Only use UTF-8 characters or plain ASCII

### list example

```json
{
  "name": "phase",
  "param": "--phase",
  "type": "list",
  "values": ["preview", "analyse"],
  "values_ui_mapping": {
    "preview": "Phase 1 — Preview only",
    "analyse": "Phase 2 — Full analysis"
  },
  "default": "preview"
}
```

### multiselect example

```json
{
  "name": "tag_ids",
  "param": "--tags",
  "type": "multiselect",
  "multiselect_argument_type": "single_argument",
  "separator": ",",
  "values": ["1", "2", "3"],
  "values_ui_mapping": {
    "1": "Invoices (12 docs)",
    "2": "Contracts (4 docs)",
    "3": "Reports (7 docs)"
  }
}
```

Script receives selections as one comma-separated string — split on `,` to parse.

-----

## Dynamic Dropdown Values via Helper Scripts

A `list` or `multiselect` parameter can populate its values at runtime by
calling a shell script instead of using a static array. This is the primary
mechanism for dropdowns whose content depends on live state — folder contents,
API results, database entries, etc.

```json
{
  "name": "target_file",
  "type": "list",
  "values": {
    "script": "/app/scripts/shared/fs_browse.sh /app/data",
    "shell": true
  }
}
```

### How it works

- The `script` key replaces the `values` array entirely
- Script-Server executes the helper when the form loads (and when an upstream
  parameter changes — see Dependent/Chained Dropdowns below)
- The helper must print **one value per line** to stdout
- Each line becomes one entry in the dropdown

### Helper script rules

- Store shared helpers in `scripts/shared/` — they are not standalone SS scripts,
  just callables used by runner JSON
- Use absolute paths in `values.script` to avoid working_directory ambiguity
- The helper MUST have the execute bit set (`chmod +x`) — missing execute
  permission silently greys out the dropdown with no error in the UI
- Keep helpers fast — they run on every upstream parameter change
- Return a sentinel first line (e.g. `-- skip --`) so users can opt out of
  a level without the main script failing

### shell option

```json
"values": {
  "script": "./shared/my_helper.sh '${some_param}' /app/data",
  "shell": true
}
```

- `"shell": false"` (default when variables present) — raw exec, no bash
  interpretation. Single-quoted args, pipes, and empty-string literals `''`
  will NOT work.
- `"shell": true` — full bash interpretation. Required whenever the script
  string uses shell quoting, empty literals, or pipe operators.
- Security note: `shell: true` with variable substitution is a shell injection
  risk if untrusted users can access the server. Safe for home lab use.

### Parameter substitution in script strings

- `${parameter_name}` — injects the current value of another parameter
- `${auth.username}` — authenticated username
- `${auth.audit_name}` — user info when auth is disabled

-----

## Dependent / Chained Dropdowns

Parameters can depend on each other — each level’s values script receives the
upstream selection and filters accordingly. The script re-runs live whenever
the upstream value changes; no browser refresh needed.

```json
{
  "parameters": [
    {
      "name": "root_path",
      "type": "text",
      "default": "/app/data"
    },
    {
      "name": "path_l1",
      "type": "list",
      "values": {
        "script": "/app/scripts/shared/fs_browse.sh '' ${root_path}",
        "shell": true
      }
    },
    {
      "name": "path_l2",
      "type": "list",
      "values": {
        "script": "/app/scripts/shared/fs_browse.sh '${path_l1}' ${root_path}",
        "shell": true
      }
    },
    {
      "name": "path_l3",
      "type": "list",
      "values": {
        "script": "/app/scripts/shared/fs_browse.sh '${path_l2}' ${root_path}",
        "shell": true
      }
    }
  ]
}
```

### Sentinel pattern for optional levels

When chaining 3+ levels, the user may want to stop at level 1 or 2 without
being forced to interact with every downstream dropdown. Emit a sentinel as
the first output line:

```bash
echo "-- skip --"   # always the first line
# then list real values...
```

In the main script, resolve the deepest non-sentinel selection:

```bash
SKIP="-- skip --"
strip_icon() { echo "$1" | sed 's/^[^ ]* //'; }

resolve_selection() {
  local resolved=""
  for val in "$1" "$2" "$3"; do
    stripped=$(strip_icon "$val")
    if [ -n "$stripped" ] && [ "$stripped" != "$SKIP" ] && [ "$val" != "$SKIP" ]; then
      resolved="$stripped"
    fi
  done
  echo "$resolved"
}
```

### Icon encoding in dynamic values

`values_ui_mapping` is static — it cannot be populated dynamically. To add
folder/file icons to dynamic list entries, encode the icon into the value
the helper script prints:

```bash
echo "📁 /app/data/reports/"
echo "📄 /app/data/reports/summary.csv"
```

The main script must then strip the prefix before using the path:

```bash
clean_path=$(echo "$selected" | sed 's/^[^ ]* //')
```

### When to use each pattern

|Need                                                  |Use                                  |
|------------------------------------------------------|-------------------------------------|
|Dropdown depends on another field’s current value     |Dynamic values script                |
|Values fetched live from a local service or filesystem|Dynamic values script                |
|Simple recursive file/folder picker (no custom logic) |Native `server_file` type (see below)|
|Injecting complex data with UI labels known in advance|Runner-Generator Pattern             |
|Pre-populating values before the form opens           |Runner-Generator Pattern             |

-----

## Native File Browser — server_file type

For pure file/folder picking without custom logic, Script-Server has a built-in
`server_file` parameter type that provides recursive folder navigation natively:

```json
{
  "name": "input_file",
  "type": "server_file",
  "file_dir": "/app/data",
  "file_recursive": true,
  "file_extensions": ["pdf", "csv", "json"]
}
```

- `file_dir` — root directory (required)
- `file_recursive` — shows folder navigation UI (default: false)
- `file_extensions` — restrict to specific types (optional)
- `file_type` — `"file"` or `"dir"` to restrict selection type (optional)

Use the chained dynamic dropdown pattern instead when you need:
icon decoration, per-level filtering, or processing logic at each level.

-----

## Secrets

```json
{
  "name": "API_KEY",
  "description": "Your API key",
  "secure": true,
  "pass_as": "env_variable"
}
```

### Other runner fields

- `"output_files": []` — files to offer as downloads after run
- `"output_format": "html_iframe"` — preferred for rich output
- `"output_format": "terminal"` — plain stdout with ANSI support
- `"working_directory": "scripts"` — default for all scripts

-----

## Parameter Passing

- All positional args arrive as **strings** — cast manually:
  - `tonumber(arg[1])` in Lua
  - `int(args.value)` / `args.flag == "true"` in Python
- Named flags: `--flag value` or `--flag` for booleans
- `multiselect` delivers comma-separated selected values as a single string
- Env vars preferred for secrets: `os.getenv("KEY")` / `os.environ.get("KEY")`
- In Python, prefer `os.environ.get('PARAM_{NAME}')` over argv parsing —
  Script-Server sets this automatically for every parameter (v1.18+)
- All parameters are passed as both arguments AND env variables by default.
  Default env var name: `PARAM_{CAPITALIZED_NAME_WITH_UNDERSCORES}`
  Override with `"env_var": "MY_CUSTOM_NAME"` in the runner

-----

## Environment Variables

**Script-Server has NO UI panel for environment variables.** Two approaches:

**1. Docker environment block** — best for values that don’t change per-run:

```yaml
services:
  script-server:
    environment:
      - MY_API_KEY=abc123
      - SERVICE_URL=http://192.168.1.x:8080
```

**2. Secure runner parameter** — user enters at run time, masked in logs:

```json
{ "name": "MY_API_KEY", "secure": true, "pass_as": "env_variable" }
```

Never hardcode secrets in scripts. Always use env vars for host/URL config
so scripts are portable across environments.

**3. Secrets Store** — persistent, multiple values, no per-run re-entry, no
container restart. See below.

-----

## Secrets Store (Multi-Value, Admin-Managed, Persistent)

For secrets that many different scripts need repeatedly (a finance API key,
a Paperless-ngx token, etc.) — as opposed to a one-off value entered per run
(secure runner parameter) or a single value that rarely changes for the
whole container (Docker environment block) — use the categorized secrets
store: one JSON file, `/app/data/secrets.json`, organized as
`{category: {key: {value, updated_at}}}` (e.g. category `finance` holding
`FINNHUB_API_KEY`, category `paperless` holding `TOKEN`). One file rather
than one file per service: nothing here is injected into container-level
environment the way Docker's `env_file:` would need separate files, so a
category is just a namespace inside one store, not a filesystem boundary.

Managed via two runners in `conf/runners/` (`secrets_manager.py` /
`secrets_viewer.py`), both backed by the shared module
`scripts/shared/secrets_store.py`:

- **Secrets Manager** — set, update, or delete one entry. Pick an existing
  entry from a dynamic dropdown, or choose the sentinel `-- new entry --`
  and fill in a new category/key. The value parameter is `secure: true`, and
  no script in this pattern ever echoes a stored value back — only a
  character count confirms what was set, so nothing sensitive shows up in
  run history.
- **Secrets Viewer** — read-only, `output_format html_iframe`, themed like
  Network Device Inventory. Shows category/key/last-set only, never any part
  of the actual value.

### Known Integrations checklist

`scripts/shared/secrets_store.py`'s `KNOWN_INTEGRATIONS` list names
category/key pairs a script actually calls `get_secret()` for (or expects
to, once built), each with a one-line description. Secrets Manager's
dropdown lists these alongside real entries — a `not set yet` row is
selectable exactly like an already-set one, so filling in a known
integration never requires re-typing its category/key by hand. Secrets
Viewer surfaces the same list as a **Not Yet Configured** section (a
Script-Ingredients-Check-style readiness check for secrets, not just
files), so a missing credential is visible before a script fails on it
rather than after.

**When wiring a script to consume a secret, add it to `KNOWN_INTEGRATIONS`
in the same change** — that's what keeps the checklist accurate. A category
without a real consuming script yet (e.g. `paperless` below, added ahead of
an actual Paperless-ngx integration script) is a legitimate placeholder,
but say so in its description so it's clear nothing reads it yet.

Confirmed real integration (`notify.py` calls these directly):

```python
KNOWN_INTEGRATIONS = [
    ('pushover', 'TOKEN', 'Pushover application token - used by Send Notification'),
    ('pushover', 'USER_KEY', 'Pushover user key - used by Send Notification'),
    ('prowl', 'TOKEN', 'Prowl API key - used by Send Notification'),
]
```

**Never guess a category/key name for a script you can't see the source
of.** A wrong guess is worse than no placeholder at all — it looks
configured (a value sitting in the store) while the actual consuming
script, expecting a different key, still fails. Scripts imported from a
private Gitea repo (see Import from Gitea) are the case that bites here:
their source isn't visible from outside the NAS, so confirm the exact
`os.environ.get(...)` / `get_secret(...)` calls in the real script — by
reading it directly or grepping the imported copy under `/app/scripts` —

### Letting a runner pick among several stored tokens in one category

Some categories legitimately hold more than one value under different key
names — e.g. `gitea` might need a different access token per repo, not one
token for everything. For that case, use `secrets_store.py`'s
`dropdown-category <category>` subcommand (distinct from `dropdown-entries`,
which lists across *all* categories for Secrets Manager) as a second
dropdown's `values.script`, alongside `list_category_keys(category)` for
resolving the pick in the consuming script:

```json
{
  "name": "token_key",
  "param": "--token-key",
  "type": "list",
  "values": { "script": "/app/scripts/shared/secrets_store.py dropdown-category gitea" }
}
```

The dropdown always includes `secrets_store.AUTO_SENTINEL` as its first
value, meaning "don't force a specific one." Resolve it as: an explicit
manual value (if the runner also has one, e.g. Import from Gitea's `token`
field) always wins; otherwise if exactly one key is stored under that
category, auto-select it silently; if more than one is stored, require an
explicit pick (`token_key` not equal to `AUTO_SENTINEL`) and fail loudly
rather than guessing which one applies — see `import_from_gitea.py`'s
`resolve_gitea_token()` for the reference implementation. Log which source
was used (`"gitea.MUSIC_REPO (Secrets Store)"`, `"the manually entered token
field"`, etc.) so a run's own output explains itself — never log the value.
before adding it to `KNOWN_INTEGRATIONS` or setting a value for it.

**Consuming a secret from a Python script:**

```python
import sys
sys.path.insert(0, '/app/scripts/shared')
from secrets_store import get_secret

api_key = get_secret('finance', 'FINNHUB_API_KEY')  # None if unset
```

**Consuming a secret from Lua/bash** (same "shell out to a Python helper"
pattern as Lua's JSON handling above) — prints just the raw value to stdout,
exit code 1 if unset:

```bash
API_KEY=$(python3 /app/scripts/shared/secrets_store.py get finance FINNHUB_API_KEY)
```

**Security posture — read before treating this as more than it is:**
Storage is plaintext on disk (`chmod 600` best-effort after every write,
same QNAP bind-mount chmod caveat as elsewhere in this repo) — this is the
same risk tier as a Docker environment block or a plain `.env` file already
sitting on the NAS filesystem, *not* an encrypted vault. Fine for a
home-lab, trusted-network API key; genuine encryption-at-rest with real key
management is a separate, bigger piece of work (tracked in `ROADMAP.md`'s
Ideas/Backlog) — don't assume this store provides it.

-----

## Network Scanning Scripts Need Host Networking

A script that uses `nmap`, `arp-scan`, or reads the ARP cache to discover
*real* LAN devices will silently find nothing (or only Docker-internal
addresses) unless the container runs with `network_mode: host` in
`docker-compose.yml`. A normal bridge-networked container only ever sees
Docker's own virtual network, never the physical LAN.

Trade-off: `network_mode: host` removes network isolation for the **whole**
container, not just the one script, and makes the `ports:` mapping
meaningless (the app just binds directly to the host's port). It's a
Linux-only Docker feature. Weigh this against the isolation you're giving
up before turning it on just for one scanning script.

-----

## Storage

- Persistent storage base: `/app/data`
- Never hardcode paths
- Outputs under `/app/data/<job_name>/`
- Use env vars for any path that might differ between environments

-----

## Persistent State Across Runs (Inventories / Registries)

A script can build up state *across* runs instead of just reporting a point-in-time
snapshot — e.g. a device inventory, a backup registry, a list of processed jobs.
The pattern is the same regardless of domain:

1. **A collector script** gathers current data and upserts it into a JSON file
   under `/app/data`, keyed by a **stable identifier** — something that won't
   change between runs (MAC address for devices, not IP; a filename hash for
   backups, not a timestamp; a serial number, not a display name). Preserve any
   fields a human has already customized (e.g. a label) rather than overwriting
   them each run.
2. **An editor script** lets a human customize one entry — pick it from a
   dynamic dropdown (see Dynamic Dropdown Values via Helper Scripts) sourced
   from the same JSON file, then update just the field(s) being changed.
3. **A viewer script** renders the whole store as a table, typically via
   `output_format: html`.

```
scripts/
  collector.py              # gathers data, merges into the store
  editor.py                 # updates one entry, picked from a dropdown
  viewer.py                 # renders the store as a table
  shared/
    list_store_entries.py   # dropdown helper: reads the store, prints one line per entry
```

### Lua has no JSON library by default

Lua 5.1 (as installed via `apt install lua5.1`) ships with no JSON support. Don't
hand-roll a JSON encoder/decoder in Lua for this. Two options:

- Write the store read/write logic in Python (stdlib `json` module) as a small
  shared helper, and have a Lua collector script call it via `os.execute`/
  `io.popen` with the scan results passed as a temp file. This is the simpler,
  lower-risk option and works fine even when the rest of the script is Lua.
  Verified this way: an `nmap`/`arp-scan` device scanner written in Lua calls a
  Python `merge_inventory.py` to update `/app/data/network_inventory.json`.
- Or install a Lua JSON library (e.g. `lua-cjson` via luarocks) if you want to
  keep everything in Lua.

### Escape user-supplied text before rendering as HTML

If an editor script lets a human type free text (a label, a note) and a viewer
renders it with `output_format: html` or `html_iframe`, escape that text before
embedding it (Python: `html.escape()`). `html` format sanitizes scripts/CSS
links, but don't rely on that alone — escape at the point you build the markup.

-----

## Preload Scripts — Info Banner Before the Form

A runner can show a banner ABOVE the parameter form, populated by running a
separate command/script the moment the page opens — before any parameter is
set or Run is clicked. Good for precondition checks, warnings, or context that
would otherwise bloat the `description` field.

```json
{
  "preload_script": {
    "script": "/app/scripts/shared/check_something.sh",
    "output_format": "html"
  }
}
```

- `script` — a command string, executed directly (see below). Can be inline
  (`"echo '...'"`) or a path to a separate file, exactly like a dynamic
  dropdown's `values.script`.
- `output_format` — same options as a script's own output (`terminal`, `html`,
  `html_iframe`), independent of the main script's format.

### Critical differences from a dynamic dropdown's `values.script`

- **No `shell` option exists.** Only `script` and `output_format` are read —
  it always executes directly (no shell), never via `shell: true`. Pipes,
  `&&`, `$VAR` expansion, etc. won't work in the command string directly. If
  you need real shell behavior, invoke `bash -c "your pipeline here"` as the
  command itself (this exact pattern is used in script-server's own test
  suite).
- **No stdin.** A preload script cannot read input, so it can't implement
  anything interactive — that has to live in the main script itself (see
  "Runnable standalone from terminal AND inside Script-Server" above: a
  confirmation prompt needs to work even when there's no preload banner at
  all, i.e. run standalone from a terminal).
- **Purely informational, never blocking.** It cannot prevent the main script
  from running. If a precondition actually matters, the main script must
  re-check it itself rather than trusting the banner.
- **Failure is visible, not silent.** A non-zero exit raises an exception,
  shown as an error where the banner would be — write it as carefully as any
  other script.

### Where the preload script should live

Since `script` is just a command string, the path of least resistance is
dropping a new file into `scripts/shared/` — but that gives one runner two
script files with unrelated names, breaking the Matched Pair convention's
naming alignment (seen in practice: an early version pointed `preload_script`
at `check_jq_preload.sh` while the main script was `preload_demo.py` — two
unrelated names for one runner). The right choice depends on what the preload
is actually for:

1. **Inline**, for a one-line static message (`"script": "echo '...'"`).
2. **The main script itself, with a flag** — ONLY when the preload content is
   genuinely a subset/mode of what the main script already computes (a true
   self-referential case, e.g. `motd.py` rendering its own stats as `--html`
   for the banner and as an ANSI report when actually run):
   ```json
   "preload_script": { "script": "/app/scripts/motd.py --html", "output_format": "html" }
   ```
3. **A standalone file under `scripts/preload/<name>.<ext>`, using the same
   `<name>` as the main script** — this is the common case, not the
   exception. A preload script's real job is preparing the user for what
   they're about to configure and run: current defaults, live context ("3
   devices already in inventory", "last backup was 2 days ago"), warnings —
   content that's genuinely different from the main script's own logic, not
   a mode of it. Putting it in `scripts/preload/` keeps `scripts/shared/` for
   actually-shared dynamic-dropdown helpers, and matching the base name
   (`scripts/preload/network_scanner.sh` for `scripts/network_scanner.lua` +
   `conf/runners/network_scanner.json`) keeps all three files aligned by name
   despite living in different folders.

Real example in this repo: `scripts/preload/motd.py` (live system stats banner)
and `scripts/motd.py` (a "Script Ingredients Check" auditing every runner for
missing script/preload files, grouped and collapsible via `<details>`) are
deliberately different scripts, not a self-referential flag toggle — the
preload's job here is genuinely different content, matching case 3 above,
not case 2.

-----

## Output Formats

- `terminal` — plain stdout, ANSI colour codes supported
- `html_iframe` — full HTML/CSS/JS rendered inline, no sanitisation
- `html` — sanitised HTML (no scripts or CSS links)

**Progress indicators in html_iframe:**
CSS spinners never self-terminate. Pattern for live progress feedback:

1. Emit `<span class="spinner" id="spin-x"></span>` with the phase label
1. Do the work
1. On success emit `<script>document.getElementById('spin-x').className='done';</script>`
1. Define `.done::after { content: '✓'; color: green; }` in the page `<style>` block

**Note on iOS/iPadOS:** `html_iframe` output renders correctly on desktop.
On iOS/iPadOS, avoid copy-pasting code from rendered HTML output — use
`terminal` format or plain code blocks for anything the user needs to copy.

**Copy/Download buttons now work for `html_iframe`** (fixed in this fork,
see Core Changes below). Copy extracts the visible text of the rendered
iframe; Download saves the actual rendered HTML document (`.html`), not a
`.txt` file — reopening it in a browser looks the same as the on-screen
output.

-----

## Core Changes (Fork Divergence from Upstream)

Almost everything in this repo is "Admin scripts" — runner JSON + a
standalone script under `scripts/`, added without touching script-server's
own source. That's the default, low-risk way to extend this platform (see
`ROADMAP.md`'s effort classes). Occasionally a real bug lives in
script-server's own frontend/backend (`src/`, `web-src/`) and can only be
fixed there. Those are logged here — each entry says exactly what changed,
in which files, and why — because they're easy to lose track of on a
`git pull`/rebase from upstream `bugy/script-server`, and a full Docker
image rebuild (not just a scripts/conf file copy) is required to pick them
up.

### 2026-09-06 — Copy/Download buttons did nothing for `html_iframe` output

**Symptom:** running any script with `"output_format": "html_iframe"`
(e.g. MOTD's Script Ingredients Check), the log panel's Copy and Download
buttons produced nothing — no clipboard content, no file, no error.

**Root cause:** `HtmlIFrameOutput.js`'s `.element` is the outer `<iframe>`
tag. The rendered content actually lives in the iframe's own
`contentDocument`, a separate DOM document. `downloadLog()` read
`element.innerText`/`.textContent` directly off the `<iframe>` tag (always
empty for an iframe), and `copyLogToClipboard()`'s underlying
`Range.selectNodeContents()`/`window.getSelection()` calls used the *main
page's* `document`/`window`, which can't select across into a same-origin
iframe's separate document either.

**Fix:**
- `web-src/src/common/utils/common.js` — `readUserVisibleText(elem)` (now
  exported) resolves the document/window from `elem.ownerDocument`/
  `defaultView` instead of the global `document`/`window`, so it works
  correctly for elements inside an iframe. `copyToClipboard()` was
  simplified to take a plain string instead of a DOM element — extraction
  is now each Output class's job (see below), not the clipboard utility's.
- Every Output class (`TerminalOutput.js`, `TextOutput.js`, `HtmlOutput.js`,
  `HtmlIFrameOutput.js`) gained a `getText()` method returning its visible
  text — for `HtmlIFrameOutput` this reads from `contentDocument.body`.
- `HtmlIFrameOutput.js` additionally gained `getHtml()`, returning
  `contentDocument.documentElement.outerHTML` — the full rendered document.
- `web-src/src/common/components/log_panel.vue` — `copyLogToClipboard()`
  now calls `this.output.getText()` and passes the string to
  `copyToClipboard()`. `downloadLog()` uses `getHtml()` when the current
  Output class provides one (i.e. only for `html_iframe`), saving a real
  `.html` file; otherwise it falls back to `getText()` and saves `.txt`,
  matching prior behaviour for `terminal`/`text`/`html`.

**Result:** Copy still extracts plain text for every format, unchanged for
`terminal`/`text`/`html`. Download now saves a genuine, reopenable `.html`
file for `html_iframe` scripts instead of an empty/plain-text one.

**Deploying this fix:** since it changes compiled Vue frontend source
(`web-src/`), a file copy + `chmod` is not enough — the Docker image must
be rebuilt (`docker compose up -d --build`) so `npm run build` recompiles
`web-src/` into `web/`.

-----

## Language Choice: Lua vs Python

**Use Lua for:**

- Single-endpoint HTTP calls to local services
- File operations and text processing
- ANSI terminal output scripts
- Runner-generator scripts (read/patch/write JSON)
- Lightweight automation with minimal dependencies

**Use Python when:**

- Calling multiple external HTTPS APIs with JSON bodies
- Generating substantial HTML output
- Dispatching across multiple provider SDKs
- Needing ecosystem libraries (parsing, data processing, etc.)

-----

## Runner-Generator Pattern

A script can rewrite another script’s runner JSON at runtime to inject
dynamic data — e.g. fetching live values from an API and writing them
into a `multiselect` parameter.

Rules:

- Only patch the parameters you own — leave all others untouched
- Refresh ALL dynamic parameters in a single run (not just the primary one)
- After the generator runs, the user must **refresh the browser** —
  Script-Server does not hot-reload runner configs
- Use `_version` in the runner JSON to confirm the update took effect

-----

## Avoid

- `"type": "select"` — use `"type": "list"`
- `"labels": []` — use `"values_ui_mapping": {}` instead
- Folder prefix in `script_path` when `working_directory` is set
- Hardcoded paths, IPs, or credentials anywhere in scripts
- Assuming parameters always exist — always provide defaults
- Claiming Script-Server has a UI for environment variables (it doesn’t)
- Interactive prompts unless stdin automation is explicitly configured
- `"shell": false` (or omitting `shell`) when the values script string uses
  quoting, empty literals `''`, or pipe operators — dropdown will be silently
  greyed out
- Forgetting `chmod +x` on helper scripts — missing execute bit silently
  greys out any dropdown that depends on that script, with no UI error

-----

## Self-Learning Protocol

When you discover something new and valuable during a session — a corrected
convention, a confirmed quirk, or a mistake in this guidance — flag it:

```
⚙ LEARNING DETECTED
What was learned: <concise description>
Confidence: high / medium
Suggested update: <exact text to add, change, or remove>
```

If confidence is high and the learning applies platform-wide:

```
📝 PROPOSED SCRIPT-SERVER.MD UPDATE
Section: <which section>
Change: add / replace / remove
New text: <proposed text>
```

If the learning is project-specific, capture it in the project’s own `.md`
file instead — keep this platform doc free of project-specific detail.

```
🚀 TO DEPLOY
1. This file is CLAUDE.md at the root of nodecentral/script-server — any
   Claude Code session working in this repo loads it automatically.
2. Propose edits in place (see Self-Learning Protocol above) rather than
   maintaining a separate copy elsewhere, so history stays in one place.
```
