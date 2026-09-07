# Script-Server.md — Platform Context

Version: 1.28.0
Last updated: 2026-09-07

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

## For Claude Sessions Working In Other Gitea Repos

Several independent Gitea repos (`ss_music_file_management`,
`ss_movie_file_management`, `ss_photo_file_management`,
`ss_finance_management`, `ss_health_management`, `ss_document_file_management`,
etc.) each produce scripts imported into **this** Script-Server instance via
**Import from Gitea** — all landing in the same flat `/app/scripts` +
`/app/conf/runners` namespace. **This file (and its focused companion,
`SCRIPTING.md`) is the single canonical source of convention for all of
them.**

If you're a Claude session working in one of those repos, fetch and read
**`SCRIPTING.md`** first — it's the trimmed, scripting-only doc (no UI/
sidebar/admin internals) built specifically so a scripting session doesn't
have to ingest this entire file:

```
https://raw.githubusercontent.com/nodecentral/script-server/master/SCRIPTING.md
```

Come back to this full file only if you need deeper rationale behind a
rule, or anything about Script-Server's own server/admin/UI internals that
`SCRIPTING.md` deliberately leaves out:

```
https://raw.githubusercontent.com/nodecentral/script-server/master/CLAUDE.md
```

Keep the two in sync — a rule that applies to script/runner authoring
belongs in both (trimmed appropriately for `SCRIPTING.md`); anything about
this app's own internals belongs only here. `SCRIPTING.md` itself carries
the same reminder at its top.

The highest-stakes rules — confirmed to actually bite in practice, not
theoretical:

- **Secrets go through the Secrets Store, nowhere else.** One consuming
  script (`paperless_metrics_dashboard.py`) arrived via Gitea import having
  independently invented its own mechanism — a gitignored `paperless.env`
  dotenv file plus a custom `scripts/shared/secrets.py` helper — with zero
  awareness that `paperless.URL`/`paperless.TOKEN` were *already* reserved
  placeholders in this repo's own `secrets_store.py`. Use
  `sys.path.insert(0, '/app/scripts/shared'); from secrets_store import
  get_secret; get_secret('paperless', 'TOKEN')` instead — see Secrets Store
  below. Never invent a parallel secrets mechanism.
- **Matched Pair Rule** (below): `name.ext` script + `name.json` runner,
  same base name, both versioned together.
- **Filenames collide across repos** — there is no per-source folder
  isolation on import, so a script here named the same as one in another
  repo will silently overwrite it the moment either is applied. Check
  `conf/runners/` in this repo (or ask) before naming something generic like
  `check_script_permissions` — that exact collision has already happened
  between multiple of these repos. **Exception:** if the collision is a
  deliberate, byte-for-byte identical generic admin script shared across
  sibling repos (confirmed real: `check_script_permissions.sh`/`.json` now
  ship identically from `ss_finance_management`, `ss_health_management`,
  and `ss_document_file_management`), it's harmless — re-import is
  idempotent and whichever import "wins" behaves the same. The warning is
  about **divergent** content sharing a name, not shared content sharing a
  name.
- Execute bit (`chmod +x`), dynamic dropdown quoting/`shell: true`, and
  every other convention in this file applies equally regardless of which
  repo a script originated from — Script-Server itself has no idea which
  Gitea repo anything came from once it's imported.

If anything here is unclear or a convention seems to conflict with what a
specific repo needs, that's worth raising back in the `nodecentral/
script-server` session rather than deciding unilaterally — this file only
stays authoritative if changes flow through one place.

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

**Never substitute a `secure`, `constant`, or `no_value` parameter into
another parameter's `values.script`.** Confirmed on a real instance, not
assumed: Script-Server hard-refuses to even load the runner, throwing
`Unsupported parameter "X" of type "secure" in values.script!`
(`parameter_config.py`'s `validate_parameter_dependencies`, called for
every parameter at config-load time) — the whole script fails with
"Failed to load script info / Failed to connect to the server" in the UI,
not just a greyed-out dropdown like a missing execute bit would cause.
Bit this in practice: Import from Gitea's live Repo dropdown originally
substituted `${token}` (the manual, `secure: true` token field) alongside
`${token_key}` (a plain `list` field, fine) — removing `${token}` fixed
it. If a dropdown genuinely needs a secret to do its job, resolve that
secret server-side inside the dropdown script itself (e.g. via
`secrets_store.get_secret()`/`gitea_client.resolve_gitea_token()`) rather
than passing it through form-field substitution — exactly the pattern
`gitea_client.py dropdown-repos` uses, driven only by `token_key` (which
picks a *name*, not a secret) with the actual token value resolved
internally. A one-off manually-typed secure value (like Import from
Gitea's manual `token` field) simply can't drive a live dropdown at all;
say so in the field's own description rather than leaving it to silently
not work.

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

## Admin Access Without Auth Configured

If no `"auth"` block is set in `conf/conf.json` (the common case for a
single-user home-lab NAS — no login screen at all), Script-Server still
decides who gets admin rights (the settings cog, admin.html, editing
runner configs) via a server-side check against `access.admin_users` in
`conf/conf.json` — confirmed in `src/model/server_conf.py`/
`src/web/server.py`/`src/auth/identification.py`, not assumed. With no
`access` block at all, the default is only requests from `127.0.0.1`/
`::1` (literal localhost) — a browser on the LAN, even the NAS's own
regular IP, never qualifies, with nothing in the UI hinting this is
IP-dependent. Confirmed on a real instance: a user accessing exclusively
from an iPad over the LAN (never localhost) never had admin rights,
consistent with the default and with an absent `conf/conf.json` — not a
regression from any frontend change.

Fix: `conf/conf.json` is deliberately **not** tracked in git (see
`.gitignore`) since it's NAS-local/user-specific — create it directly on
the NAS:

```json
{
  "access": {
    "admin_users": ["*"]
  }
}
```

Grants admin rights to any device on the LAN — matches this fork's
existing "safe for home lab, trusted network" posture (same trade-off
already accepted for the plaintext Secrets Store, `shell: true` dropdowns,
etc.), and the server logs `Any user is allowed to access admin page, be
careful!` on startup as confirmation it was actually parsed. Prefer
`"admin_users": ["<your IP>"]` (or `"trusted_ips"`) over the wildcard if
the NAS is reachable beyond a fully trusted LAN.

**Read only once, at process startup — `docker compose up -d` alone is
NOT enough and was confirmed NOT to pick up a conf.json change on a real
instance.** `up -d` only recreates a container whose *service definition*
changed (image, env, volume list); it's a no-op for a bind-mounted file's
*content* changing underneath an already-running container. An actual
restart is required so the Python process re-execs and re-reads the file:

```bash
docker compose restart script-server
```

Verify the fix actually took with `docker compose logs script-server 2>&1
| grep admin_users` — that startup warning line is the confirmation, not
just running the restart command. The app logs to stdout (`conf/logging.json`'s
`console` handler at root DEBUG), so `docker compose logs` reliably
captures it — an empty grep result is a real signal the config was never
re-read, not a logging gap.

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
  and fill in a new category/key. The value field is deliberately **plain
  text, not `secure: true`** — see "The `secure` flag is one setting for two
  different things" below for why. No script in this pattern ever echoes a
  stored value back on its own — the Secrets Viewer-style confirmation shown
  after every run (success or error, reusing `secrets_viewer.render_body()`
  directly) only ever shows a character count, never the value itself, and
  the same confirmation lets you immediately verify the change and set the
  next entry without leaving the page.

  ### The `secure` flag is one setting for two different things

  `"secure": true` on a runner parameter controls two separate effects from
  one config value, confirmed in the actual source
  (`src/model/parameter_config.py`'s `value_to_str`/`get_secured_value` for
  logging, `web-src/src/common/components/textfield.vue`'s `fieldType` for
  the `<input type="password">` rendering) — there's no way to have one
  without the other via this flag. `type="password"` is also what makes a
  browser (especially iOS/iPadOS Safari) treat the field as a login password
  and offer to save/autofill it, and masked dots make it hard to proofread
  what was typed before submitting - real friction reported in practice for
  Secrets Manager's value field specifically.

  Decision made here: Secrets Manager's value parameter deliberately has NO
  `secure` flag at all, trading away Script-Server's own execution-history
  redaction (a value typed here **will** be visible to anyone who can view
  this script's past runs, unlike a genuinely `secure: true` field) for a
  plain, proofreadable input with no browser password-manager interference.
  Accepted as consistent with this fork's existing "safe for home-lab,
  trusted-network" posture (same trade-off already made for the plaintext
  Secrets Store file itself, `shell: true` dropdowns, etc.) — the runner's
  own description states this explicitly so it's a conscious choice, not a
  silent gap. Reconsider `secure: true` (accepting the masked-input/
  password-manager friction) if this NAS is ever reachable beyond a fully
  trusted network.

  Script-Server has no conditional field visibility — every parameter shows
  on the form regardless of what's picked elsewhere, so a second "only used
  if you picked X" field reads as a required next step even when it isn't.
  Real confusion hit this exact spot: a user picked a suggested entry
  straight from the dropdown (which already carries its own category/key)
  and still felt obligated to fill in the separate new-entry fields sitting
  right there on the form. Fixes that don't require conditional visibility
  (which this version of script-server doesn't have): merge what would be
  multiple "only if creating new" fields into as few fields as possible (one
  `new_entry` field taking `category/KEY`, not two), and make the sentinel
  option itself carry the instruction (`+ CREATE NEW ENTRY (fill in New
  Entry field below: category/KEY)`) rather than relying on a separate
  field's description that's easy to skip past.

  **Follow-up confusion, also real:** merging into one `category/KEY` text
  field fixed the "extra field feels mandatory" problem but created a new
  one — a user couldn't tell category and key were two separate concepts
  packed into one string, and had no way to see or reuse an existing
  category (e.g. `finance`) without retyping it from memory, risking a
  silent miscased duplicate (`Finance` vs `finance` are different
  categories to a plain dict key). Fixed by pushing the category choice
  into the **dropdown itself** rather than a text field: `dropdown-entries`
  now also emits one `+ ADD NEW KEY TO <category>` sentinel per category
  already in the store (`secrets_store.category_from_add_key_sentinel()`
  parses it back out), so picking an existing category is a selection, not
  something typed — and once picked, `New Entry` only ever needs the bare
  `KEY` name. `category/KEY` in `New Entry` is now reserved for the
  genuinely-rare case of a brand new category via a separate, more
  explicit sentinel (`+ CREATE NEW ENTRY IN A NEW CATEGORY`). Net effect:
  still one "only if creating new" field, but the dropdown does the part a
  human shouldn't have to retype correctly from memory.
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
token for everything. `secrets_store.py`'s generic `dropdown-category
<category>` subcommand (distinct from `dropdown-entries`, which lists
across *all* categories for Secrets Manager) is the reusable building
block for this — a second dropdown's `values.script`, alongside
`list_category_keys(category)` for resolving the pick in the consuming
script:

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
manual value (if the runner also has one, e.g. a `token` field) always
wins; otherwise if exactly one key is stored under that category,
auto-select it silently; if more than one is stored, require an explicit
pick (`token_key` not equal to `AUTO_SENTINEL`) and fail loudly rather
than guessing which one applies. Log which source was used
(`"gitea.MUSIC_REPO (Secrets Store)"`, `"the manually entered token
field"`, etc.) so a run's own output explains itself — never log the
value.

**When the category also holds a non-token value** (see the URL example
below), the generic `dropdown-category` would wrongly offer it as if it
were a token. Import from Gitea's actual dropdown is
`gitea_client.py dropdown-tokens`, a thin domain-specific wrapper around
`list_gitea_tokens()` (itself `list_category_keys('gitea')` filtered
through `RESERVED_GITEA_KEYS`) — same output shape as `dropdown-category`
so `resolve_gitea_token()`'s parsing is unchanged, just with the reserved
key excluded. Keep the domain-specific exclusion knowledge in the
domain's own shared module (`gitea_client.py`), not leaked into
`secrets_store.py`, which stays fully generic — see
`gitea_client.resolve_gitea_token()`/`resolve_gitea_url()` for the
reference implementation, shared across Import from Gitea's main script,
preload banner, and both dropdowns.

### Storing more than a token in a category — e.g. a service's own URL

A category isn't limited to tokens. Import from Gitea stores its Gitea
instance's base URL as `gitea.URL` alongside its token(s), rather than as
a runner form field — motivated directly by preload scripts receiving
**no parameter values at all** (see Preload Scripts above): a URL typed
into the form could never reach the preload banner anyway, so storing it
means the preload, both dropdowns, and the main script all resolve the
exact same value with no risk of a stale runner-JSON default drifting
from what's actually configured. `gitea_client.resolve_gitea_url()` is
the reference implementation — raises the same `GiteaApiError` pattern as
token resolution when unset, with a message pointing at Secrets Manager.
Add any such reserved key to `RESERVED_GITEA_KEYS` (or the equivalent set
for a different domain's shared module) so it's excluded everywhere
tokens are enumerated, and add it to `KNOWN_INTEGRATIONS` in
`secrets_store.py` too, exactly like a token, so it shows up in Secrets
Manager/Viewer's readiness checklist the same way.

### Deriving an identity from a token instead of asking for it separately

If the token itself is tied to a specific identity (a Gitea personal
access token belongs to one account, same idea as a GitHub PAT), don't add
a separate "username"/"owner" field the user has to keep in sync with
whichever token they picked — call the service's own "who am I" API
endpoint and derive it. Import from Gitea used to have a manual `owner`
text field (default `"claude"`, silently wrong the moment a different
token was used); replaced with `gitea_client.list_user_repos()` calling
Gitea's `GET /user/repos`, which returns each accessible repo's real
`full_name` (`owner/repo`) already resolved for that exact token — own
repos and any orgs it belongs to, in one call, no separate identity
lookup needed for that part. `gitea_client.get_authenticated_user()`
(`GET /user`) is used separately only where a human-readable name is
actually wanted (the preload banner's "Connected as `<username>`").
Dropdown values carrying real data this way also need a way to signal
"this failed" without crashing the dropdown blank — `dropdown-repos`
prefixes every sentinel/error line with `--` specifically so the
consuming script can tell a real `owner/repo` selection apart from an
error message that might itself contain a URL (and therefore slashes) —
never assume "contains a `/`" alone means "real value" once error text is
in the mix.

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

4. **Another runner's own script, pointed at directly** — when the desired
   preload content isn't a subset of *this* runner's own logic (ruling out
   case 2) but is *exactly* what a separate, independently-existing runner
   already does as its whole job, don't duplicate that rendering logic into
   a new `scripts/preload/<name>` file (case 3) — just point `preload_script`
   straight at the other runner's script:
   ```json
   "preload_script": { "script": "/app/scripts/secrets_viewer.py", "output_format": "html_iframe" }
   ```
   Real example: **Secrets Manager**'s banner shows what's already in the
   store before you change anything, by reusing **Secrets Viewer**'s script
   directly rather than re-implementing the same store-rendering logic a
   second time — one place to fix if the store's schema ever changes, and
   the preload always stays in sync with what running Secrets Viewer
   standalone actually shows. Only safe when the reused script is already
   preload-compatible on its own merits (no required arguments, no stdin,
   side-effect-free) — true here since Secrets Viewer is read-only by design.

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

### 2026-09-06 — Slim "auto-hide" sidebar rail for desktop

**Motivation:** the main script-running UI's left sidebar was a fixed
300px, always docked, with no way to reclaim that width for script
output/parameters on desktop. A collapse mechanism already existed for
mobile (`<992px`, sidebar fully hides off-canvas, hamburger button brings
it back as an overlay) but nothing above that breakpoint.

**Design:** extended the existing mobile mechanism to desktop rather than
building a true VS-Code-style icon-per-item rail — scripts/groups have no
icon data today, so a real icon rail would need new iconography (auto
avatars or a new runner JSON field), a separate, bigger piece of work.
Instead: a persistent 56px slim rail with a single menu-toggle icon,
in normal document flow (not hidden, unlike mobile) so it always stays
reachable; clicking it expands the full sidebar as a temporary overlay on
top of content (not a layout push) with the same dark backdrop as mobile;
clicking outside it, or navigating to a script (reusing the existing
`router.afterEach` hook that already auto-collapses on mobile), snaps it
back to the rail. A pin icon in the expanded sidebar's header lets a user
turn rail mode off entirely, reverting to the original always-docked
behaviour — persisted in `localStorage` (`sidebarRailMode`), default on.

**Files:**
- `web-src/src/common/components/AppLayout.vue` — added `railMode` state
  (persisted), `isRailCollapsed`/`isRailOverlay`/`sidebarClasses`
  computeds, `toggleRailMode()`. The sidebar slot is now a **scoped
  slot**, passing `railCollapsed`/`railMode`/`onToggleExpand`/
  `onToggleRailMode` down to whatever fills it (Vue scoped-slot props use
  the exact key as written on the `<slot>` binding, unlike component
  props which auto-convert kebab-case - bound them in camelCase directly
  to avoid a real mismatch bug here). New CSS: `.rail-collapsed` (56px,
  static, in-flow) and `.rail-expanded` (`position: fixed`, 300px,
  elevated z-index) plus a `.sidenav-overlay.rail-overlay` backdrop
  variant scoped separately from the pre-existing mobile-only overlay
  styling so neither interferes with the other.
- `web-src/src/main-app/components/MainAppSidebar.vue` — new
  `railCollapsed`/`railMode` props; renders just the toggle button when
  collapsed, otherwise the existing full content plus a pin/unpin icon in
  the header.
- `web-src/src/main-app/MainApp.vue` — destructures the new scoped-slot
  props and wires them into `MainAppSidebar`.

**Scope:** only the main script-running UI (`MainApp.vue`) uses
`AppLayout.vue` - the admin panel (`admin.html`) has its own separate
layout and is unaffected.

**Verified:** `vue-cli-service build` compiles cleanly. Full interactive
verification wasn't possible in this environment (no live backend to run
the actual app against), so the exact CSS/JS state-transition logic was
reproduced in a standalone HTML/JS mock and checked visually via
Playwright screenshots for all four states: rail-collapsed, expanded via
the rail icon (overlay + backdrop), collapsed again via clicking the
backdrop, and pinned open (rail mode off, classic docked layout). **Ask
for a live-browser check on the real NAS instance before considering this
fully verified** - genuine Vue reactivity/router-integration bugs
wouldn't show up in a static mock.

**Deploying this fix:** same as above — Vue frontend source changed, so
`docker compose up -d --build` is required, not just a file copy.

### 2026-09-06 — Sidebar rail follow-up: invalid Material Icons names broke the header layout

**Symptom, confirmed on the real NAS instance** (exactly the live-browser
check the entry above asked for): the server name in the sidebar header
was squeezed down to its first visible letter, and the admin settings cog
appeared to have been "replaced" by the GitHub link.

**Root cause:** the two new icon names used for the pin/auto-hide toggle -
`push_pin` and `keyboard_double_arrow_left` - do **not exist** in this
project's bundled icon font (`material-design-icons@3.0.1`, the classic
932-icon set predating Google's newer Material Symbols, where both of
these names were later added). Confirmed directly against the installed
package's `iconfont/codepoints` file, not assumed. Effect in a real
browser: Material Icons is a ligature font — you write the icon's plain
English name as literal text and the font's own OpenType ligature table
substitutes it for a glyph; there's no CSS `content:` fallback involved.
`push_pin` matched no ligature at all and rendered fully invisible
(no glyphs exist for plain ASCII letters in an icon-only font, no
fallback font was specified). `keyboard_double_arrow_left` partially
matched — the font substituted just the `keyboard` prefix into an
unrelated keyboard glyph, then rendered the remaining ~18 characters as
invisible-but-still-space-reserving `.notdef` glyphs. Both cases silently
consumed real horizontal width in the header row without showing any
visibly broken text to hint at the cause - it just looked like everything
else got squeezed for no visible reason, including pushing the
admin/GitHub link link partially out of its usual space.

**Lesson for future icon choices:** always confirm a `material-icons`
name against this project's actual bundled font before using it -
`grep <name> web-src/node_modules/material-design-icons/iconfont/codepoints`
after `npm install` in `web-src/`, or cross-check every icon name already
used in `web-src/src` against that file in one pass:
```bash
comm -23 \
  <(grep -rohE 'class="material-icons[^"]*">[a-z_]+' web-src/src --include=*.vue | sed -E 's/.*>//' | sort -u) \
  <(cut -f1 -d' ' web-src/node_modules/material-design-icons/iconfont/codepoints | sort -u)
```
An empty result means every icon name in use is valid. A name existing in
newer Google documentation/Material Symbols is not sufficient proof it
exists in *this* older bundled set.

**Fix:** swapped to `lock_open`/`lock` (confirmed present in the
codepoints file, and confirmed rendering as correctly-sized real glyphs
against the actual bundled font file via a Playwright screenshot) for the
same pin/auto-hide toggle. Also hardened `.pin-toggle-button` in
`MainAppSidebar.vue` with a fixed 24x24 box and `overflow: hidden` so a
bad icon name in the future degrades to a small blank square instead of
blowing out the whole header row's width again.

**Verified:** ran the cross-check command above against every icon name
in `web-src/src` post-fix - no other invalid names found anywhere in the
codebase. Re-rendered the actual header markup against the real bundled
font file via Playwright, confirming the server name now truncates
reasonably (e.g. "My Home N...") rather than collapsing to one letter,
with both icons rendering as small, correctly-sized glyphs.

### 2026-09-07 — iPad Safari silently mangled a typed text-field value

**Symptom, reported directly from the real NAS instance (iPad browser,
the only way this fork is ever accessed):** typing `EOHD` into a plain
text parameter (Secrets Manager's "New Entry" field) submitted as `Eohd`
- no error, no visible change on screen while typing, the value was just
silently different from what was typed by the time the form posted.

**Root cause:** `web-src/src/common/components/textfield.vue`'s `<input>`
sets no `autocapitalize`, `autocorrect`, or `spellcheck` attribute, so
every plain-text parameter falls back to the browser's own defaults.
iOS/iPadOS Safari's default for a text input is `autocapitalize="sentences"`
plus autocorrect on - exactly the combination that can re-case or "correct"
a short all-caps token a human typed deliberately (a category name, an API
key fragment, a hostname) into something else, with nothing in the UI to
show it happened. This is a plain `type="text"` field, not the masked
`secure`/password-manager issue documented in the Secrets Store section
above - a different iOS input quirk hitting a different field type.

**Fix:** added `autocapitalize="off"`, `autocorrect="off"`, and
`spellcheck="false"` to the `<input>` in `textfield.vue`. Applies to every
plain-text parameter across every runner (category/key combos, hostnames,
manual tokens, file paths) - none of these are natural-language input, so
there's no case where autocapitalize/autocorrect was ever doing something
wanted, only cases where it silently could have been doing harm.

**Verified:** `vue-cli-service build` not run in this environment (no
`node_modules` installed here) - this is a static attribute addition to a
single `<input>` element with no logic change, but **still needs a
live-iPad check on the real NAS instance** before being considered fully
verified, per this fork's own standing rule for frontend changes that
can't be exercised against a live backend.

**Deploying this fix:** same as every other `web-src/` change in this
log - `docker compose up -d --build` is required, a file copy is not
enough.

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
- Substituting a `secure`/`constant`/`no_value` parameter into another
  parameter's `values.script` — Script-Server refuses to even load the
  runner (see Parameter substitution in script strings above), a more
  severe failure than a greyed-out dropdown

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
