#!/usr/bin/env python3
# Name: secret_ingredients_check.py
# Version: 1.0.0
# Description: Secret Ingredients Check - scans every script under scripts/
#              for get_secret(...) calls (Python) and secrets_store.py get
#              <product> <key> calls (Lua/bash shelling out), then cross-
#              checks each referenced product/key against what's actually
#              set in /app/data/secrets.json. Flags any secret a script
#              expects but that isn't configured yet, visible before the
#              script fails on it at runtime rather than after - the same
#              "readiness check, not just files" idea as motd.py's own
#              Script Ingredients Check, applied to secrets instead of
#              missing script/preload files. Also lists set secrets that no
#              script currently references, in case they're safe to remove.
#              Best-effort static scan (regex over file contents, not a real
#              parser) - it CANNOT resolve a product/key built dynamically at
#              runtime from a variable, so a script using that pattern won't
#              be caught here; scan results should be read as "at least
#              this many issues found," not an exhaustive guarantee. Run
#              standalone (./secret_ingredients_check.py) or from
#              Script-Server.

import html
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shared'))
from secrets_store import list_entries_metadata  # noqa: E402

SCRIPTS_DIR = '/app/scripts'
SCAN_EXTENSIONS = ('.py', '.sh', '.lua')

# This scanner's own filename - excluded from the scan itself. Its docstrings/comments
# necessarily contain literal get_secret('product', 'key')-shaped example text to document the
# patterns being matched, which is indistinguishable from a real call at the regex level; it
# isn't a secret consumer itself, so scanning it only ever produces false positives.
SELF_FILENAME = os.path.basename(__file__)

# Matches get_secret('product', 'key') / get_secret("product", "key") in Python source - single
# or double quotes, no whitespace crossing a newline (applied per-line, see scan_file() below, so
# a wrapped comment/docstring can never accidentally join two unrelated lines into one false
# match - confirmed the hard way: an earlier whole-file version of this regex matched this very
# script's own multi-line header comment as if it were a real call). Cannot resolve a call built
# from variables (e.g. get_secret(product_var, key_var)) - a real, accepted limitation of a
# static regex scan, not a bug; such a script just won't show up here either way.
PYTHON_CALL_RE = re.compile(r"""get_secret\(\s*['"]([^'"]+)['"]\s*,\s*['"]([^'"]+)['"]""")

# Matches the Lua/bash shell-out pattern: secrets_store.py get <product> <key>, applied per-line
# for the same reason as PYTHON_CALL_RE above.
SHELL_CALL_RE = re.compile(r"""secrets_store\.py\s+get\s+(\S+)\s+(\S+)""")

# A real product/key name in this store is always a plain identifier (letters, digits,
# underscore - matches every example actually in use: gitea, paperless, finnhub, TOKEN,
# API_KEY...). Anything else caught by the regexes above - "<product>", "$VAR", "#" from a
# comment continuation, etc. - is a doc/usage string or an unresolvable variable, not a real
# reference, and is dropped in scan_file() rather than reported as a false "missing" secret.
VALID_TOKEN_RE = re.compile(r'^[A-Za-z0-9_]+$')

STYLE = """
<style>
  body {
    margin: 0;
    padding: 20px;
    background: #eeeeee;
    color: rgba(0,0,0,0.87);
    font-family: "Roboto", "Helvetica Neue", Arial, sans-serif;
  }
  .intro {
    margin-bottom: 16px;
    font-size: 0.9rem;
    color: #555;
  }
  .limitation-note {
    background: #fff8e1;
    border-left: 4px solid #f9a825;
    border-radius: 2px;
    padding: 10px 16px;
    margin-bottom: 16px;
    font-size: 0.85rem;
  }
  details.group {
    background: #ffffff;
    border-radius: 4px;
    box-shadow: 0 4px 5px 0 rgba(0,0,0,0.14), 0 1px 10px 0 rgba(0,0,0,0.12), 0 2px 4px -1px rgba(0,0,0,0.20);
    margin-bottom: 14px;
  }
  details.group summary {
    cursor: pointer;
    list-style: none;
    background: #26a69a;
    color: white;
    padding: 10px 16px;
    font-size: 1rem;
    font-weight: 500;
    border-radius: 4px;
  }
  details.group.has-issues summary { background: #c62828; }
  details.group[open] summary { border-radius: 4px 4px 0 0; }
  details.group summary::-webkit-details-marker { display: none; }
  details.group summary::before {
    content: '\\25B6';
    display: inline-block;
    margin-right: 8px;
    transition: transform 0.15s;
  }
  details.group[open] summary::before { transform: rotate(90deg); }
  .table-scroll { overflow-x: auto; border-radius: 0 0 4px 4px; }
  table { border-collapse: collapse; width: 100%; }
  th, td { text-align: left; padding: 8px 16px; font-size: 0.85rem; }
  th {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: #757575;
    border-bottom: 1px solid #ddd;
  }
  tbody tr:nth-child(odd) { background: rgba(0,0,0,0.025); }
  tbody tr:hover { background: rgba(0,0,0,0.04); }
  td { border-bottom: 1px solid #eee; }
  .mono { font-family: "Roboto Mono", "Courier New", monospace; font-size: 0.82rem; }
  .missing { color: #c62828; font-weight: 500; }
  .empty-state { padding: 30px 20px; text-align: center; color: #757575; }
</style>
"""


def scan_file(path):
    """Returns a list of (product, key) tuples this file references via get_secret() or a
    secrets_store.py shell-out - best-effort, see the module docstring's limitation note."""
    try:
        with open(path, errors='replace') as f:
            lines = f.readlines()
    except OSError:
        return []

    found = []
    for line in lines:
        for m in PYTHON_CALL_RE.finditer(line):
            product, key = m.group(1), m.group(2)
            if VALID_TOKEN_RE.match(product) and VALID_TOKEN_RE.match(key):
                found.append((product, key))
        for m in SHELL_CALL_RE.finditer(line):
            product, key = m.group(1).strip('\'"'), m.group(2).strip('\'"')
            if VALID_TOKEN_RE.match(product) and VALID_TOKEN_RE.match(key):
                found.append((product, key))
    return found


def scan_scripts():
    """Walks scripts/ for get_secret()/secrets_store.py references, including scripts/shared and
    scripts/preload - both call get_secret() too (see CLAUDE.md/SCRIPTING.md's Secrets Store
    section) and are just as worth checking. Returns {(product, key): sorted [relative paths]}."""
    references = {}
    if not os.path.isdir(SCRIPTS_DIR):
        return references

    for root, _dirs, files in sorted(os.walk(SCRIPTS_DIR)):
        for filename in sorted(files):
            if not filename.endswith(SCAN_EXTENSIONS):
                continue
            if filename == SELF_FILENAME:
                continue
            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, SCRIPTS_DIR)
            for product, key in scan_file(full_path):
                references.setdefault((product, key), set()).add(rel_path)

    return {pk: sorted(paths) for pk, paths in references.items()}


def build_report():
    references = scan_scripts()
    configured = {(product, key) for product, key, _updated_at, _length, _description
                  in list_entries_metadata()}

    missing = sorted(
        (product, key, paths) for (product, key), paths in references.items()
        if (product, key) not in configured
    )
    referenced_keys = set(references.keys())
    unused = sorted(configured - referenced_keys)

    return missing, unused, len(references)


def render_missing_group(missing):
    group_class = 'group has-issues' if missing else 'group'
    print(f'<details class="{group_class}" open><summary>Referenced but Not Configured '
          f'({len(missing)})</summary>')
    if not missing:
        print('<div class="empty-state">Every get_secret() / secrets_store.py call found in '
              'scripts/ has a value set. Nothing missing.</div></details>')
        return
    print('<div class="table-scroll"><table><thead><tr>'
          '<th>Product</th><th>Key</th><th>Referenced By</th></tr></thead><tbody>')
    for product, key, paths in missing:
        files_html = '<br>'.join(f'<span class="mono">{html.escape(p)}</span>' for p in paths)
        print(
            '<tr>'
            f'<td class="mono missing">{html.escape(product)}</td>'
            f'<td class="mono missing">{html.escape(key)}</td>'
            f'<td>{files_html}</td>'
            '</tr>'
        )
    print('</tbody></table></div></details>')


def render_unused_group(unused):
    print(f'<details class="group"><summary>Set but Never Referenced ({len(unused)})</summary>')
    if not unused:
        print('<div class="empty-state">Every secret currently set is referenced by at least '
              'one script (that this scan could find).</div></details>')
        return
    print('<div class="section-note" style="padding:10px 16px;font-size:0.8rem;font-style:'
          'italic;color:#757575;">Not necessarily unused for real - this scan can\'t see a '
          'product/key built from a variable at runtime. Worth a manual check before deleting '
          'anything via Secrets Manager.</div>')
    print('<div class="table-scroll"><table><thead><tr>'
          '<th>Product</th><th>Key</th></tr></thead><tbody>')
    for product, key in unused:
        print(
            '<tr>'
            f'<td class="mono">{html.escape(product)}</td>'
            f'<td class="mono">{html.escape(key)}</td>'
            '</tr>'
        )
    print('</tbody></table></div></details>')


def render_html():
    missing, unused, total_references = build_report()

    parts = [STYLE]
    summary = f'{total_references} distinct secret(s) referenced across scripts/.'
    if missing:
        summary += f' <span class="missing">{len(missing)} missing.</span>'
    else:
        summary += ' All referenced secrets are configured.'
    parts.append(f'<div class="intro">Secret Ingredients Check - {summary}</div>')
    parts.append(
        '<div class="limitation-note">Best-effort static scan (regex over file contents) - it '
        'cannot resolve a product/key built from a variable at runtime, so this is a floor on '
        'real issues, not an exhaustive guarantee. Doesn\'t replace actually running a script.'
        '</div>'
    )

    render_missing_group(missing)
    render_unused_group(unused)

    return '\n'.join(parts)


def main():
    print(render_html())


if __name__ == '__main__':
    main()
