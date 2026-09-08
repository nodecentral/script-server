# SCRIPTING.md — Script-Server Scripting Conventions (Focused)

Version: 1.5.0
Last updated: 2026-09-08

This is the **focused** convention doc for any Claude session writing
scripts/runners destined for import into `nodecentral/script-server` —
whether you're working directly in that repo or in one of the independent
Gitea repos that feed it (`ss_music_file_management`,
`ss_movie_file_management`, `ss_photo_file_management`,
`ss_finance_management`, `ss_health_management`, `ss_document_file_management`,
etc.). It covers exactly what you need to produce a compliant script +
runner pair — parameter types, dropdowns, secrets, output formats — and
deliberately leaves out anything about Script-Server's own UI internals
(sidebars, colour themes, Vue components) or server administration (auth
config, admin access). If you need those, or deeper rationale behind any
rule here, the full doc is `CLAUDE.md` in the same repo:

```
https://raw.githubusercontent.com/nodecentral/script-server/master/CLAUDE.md
```

Fetch **this** file (`SCRIPTING.md`) before writing anything:

```
https://raw.githubusercontent.com/nodecentral/script-server/master/SCRIPTING.md
```

*(Kept in sync with `CLAUDE.md` by hand — if you're editing scripting rules
in one, check whether the other needs the same update.)*

-----

## Learning & Sharing — read this even if you skim everything else

Every rule below was learned the hard way, in this project, on a real
instance — confirmed bugs, not guesses. That only stays true if new
learnings flow back the same way. **You cannot write to
`nodecentral/script-server` from another repo's session** — different
repo, different access. So the loop is human-mediated:

1. When you hit something new and valuable — a confirmed gotcha, a
   mistake in this guidance, a convention that should exist but doesn't —
   flag it clearly in your own reply, in this exact format:

   ```
   ⚙ LEARNING DETECTED
   What was learned: <concise description>
   Confidence: high / medium
   Suggested update: <exact text to add, change, or remove, and which
   file it belongs in — SCRIPTING.md if any script-writing session needs
   it, CLAUDE.md if it's Script-Server-internals-specific>
   ```

2. Say plainly that it needs relaying: *"This is worth raising back in
   the `nodecentral/script-server` session so it's shared with every
   other repo — I can't update that doc myself from here."*
3. The human carries it across. A `nodecentral/script-server` session
   folds it into the canonical doc(s) and pushes.

Don't invent a parallel doc, a parallel secrets mechanism, or a parallel
convention "for now" instead of doing this — including restating this
document's own explanations in a repo-local README instead of linking to
it. A per-repo copy of a platform convention drifts the same way a
per-repo secrets mechanism does, and since every sibling repo is built by
a separate, context-isolated Claude session, it can happen independently
N times over. This is exactly how the `ss_document_file_management`
incident happened (see Secrets below): a real script shipped with its own
bespoke secrets file, unaware that the product it needed already existed
in the shared store. A flagged learning that takes a day to land beats a
silent divergence that takes months to notice.

-----

## Platform Overview

- Scripts live in `scripts/`, runners in `conf/runners/` (or `runners/`
  at your Gitea repo's own top level). **You do not need your own sync
  script.** Script-Server's own **Import from Gitea** runner (confirmed
  real, native, and already in production use — not a proposal) mirrors
  your repo's top-level `scripts/` → `/app/scripts` and `runners/` →
  `/app/conf/runners`, overwriting changed files and removing files it
  previously imported that are no longer present upstream. It resolves
  your Gitea URL/token from the Secrets Store and lists live `owner/repo`
  options — no manual sync/cp/diff script needed on your side. If a repo
  already has a hand-rolled puller for this, retire it in favour of Import
  from Gitea rather than maintaining both.
  Non-standalone support scripts live in subfolders named for their
  role: `scripts/shared/` for dynamic-dropdown helpers, `scripts/preload/`
  for preload scripts (see below).
- Prefer Lua for lightweight automation, Python where ecosystem matters
  (see Language Choice below).
- Lua 5.1+ compatibility required.
- Be conscious of QNAP OS limitations (limited shell utilities,
  non-standard paths).

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

**Filenames collide across repos.** There is no per-source folder
isolation on import — a script here named the same as one in another
repo silently overwrites it the moment either is applied. Check
`conf/runners/` in the main script-server repo (or ask) before naming
something generic like `check_script_permissions`.

**Exception:** a deliberate, byte-for-byte identical generic admin
script shared across sibling repos (e.g. `check_script_permissions` now
shipping identically from several) is fine — re-import is idempotent,
whichever import "wins" behaves the same. The warning above is about
**divergent** content sharing a name, not shared content sharing a name.

-----

## Script Requirements

- Shebang line always
- Header comment block: name, version, description
- Debug toggle (`DEBUG=true/false`) with timestamped output
- Flush stdout after every print — Script-Server streams live, buffered output
  will not appear until the buffer fills or the script exits. **Python is
  already covered**: Script-Server forces `PYTHONUNBUFFERED=1` into every
  script's environment (confirmed in `src/execution/process_base.py`,
  `prepare_env_variables()` — applies to both its execution paths), so bare
  `print()` already streams live with no `flush=True` or
  `sys.stdout.reconfigure()` needed. The requirement is real for **Lua and
  bash**, which have no such automatic override — flush explicitly there
  (e.g. `io.stdout:flush()` in Lua).
- Safe argument handling with defaults — never assume a parameter exists
- Runnable standalone from terminal AND inside Script-Server

-----

## Execute Permissions — CRITICAL

Script-Server will silently fail to run any `.sh` file without the execute bit.
For values scripts this means the dropdown is **greyed out with no error shown**.
Always `chmod +x` any new `.sh`/`.py`/`.lua` file.

**QNAP quirk, confirmed on a real NAS:** `chmod` from *inside* a
container against a bind-mounted host folder can fail with
`chmod: changing permissions of 'X': Bad address`, even though the same
command run natively on the NAS shell (over SSH) succeeds. If a script
you added shows as greyed out after import, try a native `chmod +x`
over SSH before assuming something else is wrong.

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
calling a shell script instead of using a static array — the primary
mechanism for dropdowns whose content depends on live state.

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

- Script-Server executes the helper when the form loads (and when an
  upstream parameter changes — see Dependent/Chained Dropdowns).
- The helper must print **one value per line** to stdout.
- Store shared helpers in `scripts/shared/`.
- Use absolute paths in `values.script`.
- Execute bit required (see above) — missing it silently greys out the dropdown.
- Keep helpers fast — they run on every upstream parameter change.
- Return a sentinel first line (e.g. `-- skip --` or `-- error: <reason> --`)
  so a failure or an optional level is visible/selectable, never a
  silently empty dropdown.

### shell option

- `"shell": false"` (default when variables present) — raw exec, no bash
  interpretation. Single-quoted args, pipes, and empty-string literals `''`
  will NOT work.
- `"shell": true` — full bash interpretation. Required whenever the script
  string uses shell quoting, empty literals, or pipe operators.
- Security note: `shell: true` with variable substitution is a shell injection
  risk if untrusted users can access the server. Accepted for home-lab use.

### Parameter substitution — and a hard rule

- `${parameter_name}` — injects the current value of another parameter
- `${auth.username}` / `${auth.audit_name}` — auth/user info

**Never substitute a `secure`, `constant`, or `no_value` parameter into
another parameter's `values.script`.** Confirmed on a real instance:
Script-Server hard-refuses to even load the runner —
`Unsupported parameter "X" of type "secure" in values.script!` — the
whole script fails with "Failed to load script info / Failed to connect
to the server" in the UI, not just a greyed-out dropdown. If a dropdown
genuinely needs a secret, resolve it server-side *inside* the dropdown
script itself (`secrets_store.get_secret(...)`), driven only by a plain
field that picks a *name*, never a secret value directly.

-----

## Dependent / Chained Dropdowns

Parameters can depend on each other — each level's values script receives
the upstream selection and filters accordingly, re-running live whenever
the upstream value changes (no browser refresh needed):

```json
{
  "parameters": [
    {"name": "root_path", "type": "text", "default": "/app/data"},
    {
      "name": "path_l1",
      "type": "list",
      "values": {"script": "/app/scripts/shared/fs_browse.sh '' ${root_path}", "shell": true}
    },
    {
      "name": "path_l2",
      "type": "list",
      "values": {"script": "/app/scripts/shared/fs_browse.sh '${path_l1}' ${root_path}", "shell": true}
    }
  ]
}
```

**Sentinel pattern for optional levels** — emit a sentinel as the first
line (e.g. `echo "-- skip --"`) so a user can stop early without
breaking the main script; resolve the deepest non-sentinel selection in
the main script.

**Icon encoding** — `values_ui_mapping` is static, can't be populated
dynamically. To add icons to dynamic entries, encode them into the value
itself (`echo "📁 /app/data/reports/"`) and strip the prefix before use
(`sed 's/^[^ ]* //'`).

| Need | Use |
|---|---|
| Dropdown depends on another field's value | Dynamic values script |
| Values fetched live (API, filesystem, DB) | Dynamic values script |
| Simple recursive file/folder picker | Native `server_file` type |
| Complex data with UI labels known in advance | Runner-Generator Pattern |

-----

## Native File Browser — server_file type

For pure file/folder picking without custom logic:

```json
{
  "name": "input_file",
  "type": "server_file",
  "file_dir": "/app/data",
  "file_recursive": true,
  "file_extensions": ["pdf", "csv", "json"]
}
```

`file_dir` required; `file_recursive` (default false), `file_extensions`,
`file_type` (`"file"`/`"dir"`) optional. Use chained dynamic dropdowns
instead when you need icon decoration, per-level filtering, or logic at
each level.

-----

## Secrets

**Use the Secrets Store for anything shared or repeated.** Three tiers,
in order of preference for most cases:

1. **Secrets Store** (preferred for API keys/tokens reused across runs) —
   a JSON store (`/app/data/secrets.json`) keyed by **product** (the
   service the secret belongs to - `gitea`, `paperless`, `finnhub`) then
   **key** (the credential within it - `TOKEN`, `API_KEY`, `URL`), managed
   via the **Secrets Manager**/**Secrets Viewer** runners in the main
   script-server repo, backed by `scripts/shared/secrets_store.py`. A
   product should always be one real product/service - never a grouping of
   several unrelated providers under one umbrella name (an earlier version
   of this store had exactly that, a `finance` product holding eight
   different providers, and it caused real confusion - see CLAUDE.md's
   Secrets Store section for the full account). If you're adding a new
   integration, give it its own product.

   **Consume from Python:**
   ```python
   import sys
   sys.path.insert(0, '/app/scripts/shared')
   from secrets_store import get_secret

   api_key = get_secret('finnhub', 'API_KEY')  # None if unset
   ```

   **Consume from Lua/bash** (shell out to the same Python helper):
   ```bash
   API_KEY=$(python3 /app/scripts/shared/secrets_store.py get finnhub API_KEY)
   ```

   **Never invent a parallel secrets mechanism** (a local `.env` file, a
   custom `secrets.py` helper, etc.) — this has already happened once
   (a `paperless_metrics_dashboard.py` script arrived with its own
   dotenv-based secrets, unaware `paperless.URL`/`paperless.TOKEN` were
   already reserved in the shared store). Check whether your service's
   product already exists (ask, or read `conf/secrets_defaults.json` -
   checked-in data, not a Python file) before building anything of your
   own.

   **Adding a new secret, via Secrets Manager (a runner in the main
   script-server repo, not something you edit here):** open Secrets
   Manager. If your product/key is already listed in the dropdown - either
   as a real set entry or a `not set yet` known-integration suggestion -
   pick it, that alone carries the product/key. Otherwise pick
   `+ CREATE NEW ENTRY` and fill in two fields together with Value in the
   same run: **New Product** (an `editable_list` - pick an existing
   product from the autocomplete, or type a brand new one, e.g. `Adobe`)
   and **New Key** (plain text, e.g. `API_KEY`). An optional **Description**
   field records what the secret is for - leaving it blank on an update
   keeps whatever description was already there. Run it - the value is
   never echoed back, only a character count confirms it was set. This is
   a human action inside Script-Server's UI; a Claude session in a
   sibling repo can tell the user exactly what product/key to add (and
   should, rather than guessing), but can't run Secrets Manager itself.

   **Never guess a product/key name** for a value you're about to
   consume — a wrong guess is worse than none (looks configured while
   silently failing). Confirm the exact key your script calls
   `get_secret()` for, and if it's new, that's a learning to flag (see
   Learning & Sharing above) so it gets added to `conf/secrets_defaults.json`
   and shows up in Secrets Manager/Viewer's readiness checklist.

   **Security posture:** plaintext on disk (`chmod 600` best-effort),
   same risk tier as a Docker environment block — not an encrypted
   vault. Fine for a home-lab, trusted-network key.

2. **Secure runner parameter** — a one-off value entered per run, masked
   in the UI and in execution-history logs:
   ```json
   { "name": "API_KEY", "secure": true, "pass_as": "env_variable" }
   ```
   Note: `secure: true` controls *both* the masked `<input type="password">`
   rendering *and* history-log redaction from one flag — there's no way
   to get one effect without the other.

3. **Docker environment block** — for a single value that rarely changes
   for the whole container (`environment:` in `docker-compose.yml`).
   Script-Server has **no UI panel** for environment variables generally.

Never hardcode secrets, paths, or IPs directly in a script.

-----

## Parameter Passing

- All positional args arrive as **strings** — cast manually:
  `tonumber(arg[1])` in Lua, `int(args.value)` / `args.flag == "true"` in Python
- Named flags: `--flag value` or `--flag` for booleans
- `multiselect` delivers comma-separated selected values as a single string
- In Python, prefer `os.environ.get('PARAM_{NAME}')` over argv parsing —
  Script-Server sets this automatically for every parameter (v1.18+)
- Default env var name: `PARAM_{CAPITALIZED_NAME_WITH_UNDERSCORES}`,
  override with `"env_var": "MY_CUSTOM_NAME"` in the runner

-----

## Storage

- Persistent storage base: `/app/data`
- Never hardcode paths
- Outputs under `/app/data/<job_name>/`

-----

## Persistent State Across Runs (Inventories / Registries)

A script can build up state *across* runs (device inventory, backup
registry, processed-jobs list) instead of just reporting a snapshot:

1. **Collector** gathers current data, upserts into a JSON file under
   `/app/data`, keyed by a **stable identifier** (MAC address, not IP; a
   filename hash, not a timestamp). Preserve human-customized fields
   (e.g. a label) rather than overwriting them each run.
2. **Editor** lets a human customize one entry, picked from a dynamic
   dropdown sourced from the same JSON file.
3. **Viewer** renders the whole store as a table.

**Lua has no JSON library by default** (Lua 5.1 via `apt install lua5.1`).
Don't hand-roll one — either write the store logic in Python (stdlib
`json`) as a shared helper that a Lua collector calls via
`os.execute`/`io.popen`, or install `lua-cjson` via luarocks.

**Escape user-supplied text before rendering as HTML** — if an editor
lets a human type free text and a viewer renders it with
`output_format: html`/`html_iframe`, escape it (`html.escape()` in
Python) at the point you build the markup.

-----

## Preload Scripts — Info Banner Before the Form

A runner can show a banner above the parameter form via a separate
command run the moment the page opens — before any parameter is set:

```json
{
  "preload_script": {
    "script": "/app/scripts/shared/check_something.sh",
    "output_format": "html"
  }
}
```

**Critical differences from a dynamic dropdown's `values.script`:**
- **No `shell` option** — always executes directly, never via `shell: true`.
  For pipes/`&&`/`$VAR`, invoke `bash -c "..."` as the command itself.
- **No stdin, no parameter values at all** — a preload script cannot
  read input or see any form field's value, even a default. Anything it
  needs (like a service URL) must come from somewhere else it CAN reach —
  the Secrets Store is the right answer here, not a hardcoded constant.
  **Yes, a preload script can call `get_secret()`** - it's a plain file
  read with no dependency on runner parameters at all, so it works
  identically inside a preload script and a main script. Real, working
  precedent: `scripts/preload/import_from_gitea.py` imports
  `secrets_store.get_secret` and `gitea_client.resolve_gitea_url()`
  directly to check readiness before the form even loads. One gotcha: a
  preload script under `scripts/preload/` is one directory deeper than a
  main script under `scripts/`, so its `sys.path.insert(...)` needs an
  extra `os.path.dirname(...)` to still land on `scripts/shared` - copying
  a main script's path-setup line verbatim into a preload script will look
  right but resolve one level wrong.
- **Purely informational, never blocking** — cannot prevent the main
  script from running; re-check anything that actually matters in the
  main script too.
- **Failure is visible** — non-zero exit shows as an error where the
  banner would be.

**Where the preload script should live** — four cases, in order of how
common they are:
1. **Inline** for a one-line static message (`"script": "echo '...'"`).
2. **The main script itself, with a flag** — ONLY when the preload
   content is genuinely a subset of what the main script already
   computes (true self-referential case).
3. **A standalone file under `scripts/preload/<name>.<ext>`**, matching
   the main script's base name — the common case. A preload's real job
   is different content (current defaults, live context, warnings), not
   a mode of the main script.
4. **Another runner's own script, pointed at directly** — when the
   desired content isn't a subset of *this* runner's logic, but is
   *exactly* what a separate, already-existing runner does as its whole
   job, point `preload_script` straight at it rather than duplicating
   the logic. Only safe when the reused script has no required
   arguments, no stdin, and is side-effect-free.

-----

## Output Formats

- `terminal` — plain stdout, ANSI colour codes supported
- `html_iframe` — full HTML/CSS/JS rendered inline, **no sanitisation**
- `html` — sanitised HTML — **strips `<style>` tags and inline `style=`
  attributes**, so any script needing custom CSS/theming must use
  `html_iframe`, not `html`

**Progress indicators in html_iframe** (CSS spinners never self-terminate):
1. Emit `<span class="spinner" id="spin-x"></span>` with the phase label
2. Do the work
3. On success emit `<script>document.getElementById('spin-x').className='done';</script>`
4. Define `.done::after { content: '✓'; color: green; }` in the page `<style>`

**iOS/iPadOS note:** `html_iframe` renders correctly on desktop; on
iOS/iPadOS avoid relying on copy-paste from rendered HTML output — use
`terminal` format or plain code blocks for anything the user needs to copy.

-----

## Language Choice: Lua vs Python

**Use Lua for:** single-endpoint HTTP calls to local services, file
operations/text processing, ANSI terminal output, runner-generator
scripts (read/patch/write JSON), lightweight automation.

**Use Python for:** multiple external HTTPS APIs with JSON bodies,
substantial HTML output, dispatching across provider SDKs, ecosystem
libraries.

-----

## Runner-Generator Pattern

A script can rewrite another script's runner JSON at runtime to inject
dynamic data (e.g. live API values into a `multiselect`).

- Only patch the parameters you own — leave all others untouched
- Refresh ALL dynamic parameters in a single run, not just the primary one
- After the generator runs, the user must **refresh the browser** —
  Script-Server does not hot-reload runner configs
- Use `_version` in the runner JSON to confirm the update took effect

-----

## Network Scanning Scripts

A script using `nmap`, `arp-scan`, or the ARP cache to discover *real*
LAN devices needs the container running with `network_mode: host` in
`docker-compose.yml` (a deployment-level setting, not something you
configure per-script) — a normal bridge-networked container only ever
sees Docker's own virtual network. If you're writing a scanning script
and it finds nothing, this is the first thing to check with whoever
manages the Script-Server deployment.

-----

## Avoid

- `"type": "select"` — use `"type": "list"`
- `"labels": []` — use `"values_ui_mapping": {}` instead
- Folder prefix in `script_path` when `working_directory` is set
- Hardcoded paths, IPs, or credentials anywhere in scripts
- Assuming parameters always exist — always provide defaults
- Claiming Script-Server has a UI for environment variables (it doesn't)
- Interactive prompts unless stdin automation is explicitly configured
- `"shell": false` (or omitting `shell`) when the values script string uses
  quoting, empty literals `''`, or pipe operators — dropdown will be silently
  greyed out
- Forgetting `chmod +x` on helper scripts — missing execute bit silently
  greys out any dropdown that depends on that script, with no UI error
- Substituting a `secure`/`constant`/`no_value` parameter into another
  parameter's `values.script` — Script-Server refuses to even load the
  runner, a more severe failure than a greyed-out dropdown
- Inventing a parallel secrets mechanism instead of using the Secrets Store
- Guessing a Secrets Store product/key name instead of confirming it
- Creating a grouping/topic product that bundles several unrelated
  providers under one umbrella name — one product should always be one
  real product/service, each with its own name

-----

## One more time: flag learnings, don't silently diverge

If you've read this far and you're about to do something not covered
above — a new parameter pattern, a new integration, a new gotcha you
just hit — that's exactly the moment to pause and write the
`⚙ LEARNING DETECTED` block from the top of this file, even if you also
go ahead and solve your immediate problem. The five minutes it takes to
flag it is what keeps every other repo's Claude session from hitting the
same wall, or worse, quietly building an incompatible answer to the same
question. See "Learning & Sharing" above.
