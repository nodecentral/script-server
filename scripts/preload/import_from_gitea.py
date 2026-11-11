#!/usr/bin/env python3
# Name: preload/import_from_gitea.py
# Version: 2.2.0
# Description: preload_script for conf/runners/import_from_gitea.json - checks whether a Gitea
#              URL and token are configured in the Secrets Store before the form even loads. With
#              no URL, or no token, shows secrets_store.missing_secret_banner_html()'s themed
#              banner with a one-click deep link straight into Secrets Manager (New Product/New
#              Key already filled in) - the reference example for the pattern documented in
#              CLAUDE.md/SCRIPTING.md's Secrets Store section: every script that needs a secret
#              checks for it itself, in its own preload, rather than relying on any centralized
#              discovery. With a URL and exactly one token, actually tries connecting and reports
#              success (as which user, how many repos) or failure (with the real reason) -
#              genuinely different job from the main script (a readiness/connectivity check, not
#              an import), per CLAUDE.md's preload_script guidance. Preload scripts receive no
#              parameter values at all (see CLAUDE.md) - this is exactly why the URL lives in
#              the Secrets Store rather than a runner form field: a value typed into the form
#              could never reach this banner anyway, so storing it means the preload always
#              checks the real configured URL, not a guess. Run standalone
#              (./preload/import_from_gitea.py) or from Script-Server.
#              2.2.0: with several tokens stored, checks the one the form pre-selects (the most
#              recently set - gitea_client.most_recent_gitea_token(), same as the Gitea Token
#              field's default) instead of stopping, and lists the token's repos, most recently
#              updated first, with what's installed from each (commit + import time, from the
#              import state file) - so it's clear whether Gitea has something newer.

import html
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'shared'))
from gitea_client import (  # noqa: E402
    GiteaApiError, format_time, get_authenticated_user, list_gitea_tokens, list_user_repo_details,
    most_recent_gitea_token, parse_gitea_time, resolve_gitea_url,
)
from secrets_store import get_secret, missing_secret_banner_html  # noqa: E402

STYLE = """
<style>
  body {
    margin: 0;
    font-family: "Roboto", "Helvetica Neue", Arial, sans-serif;
  }
  .banner {
    border-radius: 2px;
    border-left: 4px solid;
    padding: 12px 16px;
    font-size: 0.9rem;
  }
  .banner.success {
    background: #e8f5e9;
    border-left-color: #26a69a;
  }
  .banner.info {
    background: #fff8e1;
    border-left-color: #f9a825;
  }
  .banner.error {
    background: #ffebee;
    border-left-color: #c62828;
  }
  .mono { font-family: "Roboto Mono", "Courier New", monospace; }
  table.repos {
    width: 100%;
    margin-top: 8px;
    border-collapse: collapse;
    font-size: 0.85rem;
  }
  table.repos th {
    text-align: left;
    font-weight: 500;
    color: rgba(0, 0, 0, 0.56);
    padding: 4px 8px;
    border-bottom: 1px solid #ddd;
  }
  table.repos td {
    padding: 4px 8px;
    border-bottom: 1px solid #eee;
    vertical-align: top;
  }
  .newer { color: #e65100; font-weight: 500; }
  .muted { color: rgba(0, 0, 0, 0.56); }
</style>
"""


STATE_PATH = '/app/data/gitea_import_state.json'
MAX_REPOS_SHOWN = 15


def load_import_state(gitea_url):
    """owner/repo -> what import_from_gitea.py recorded for it (commit, times), for this URL."""
    try:
        with open(STATE_PATH) as f:
            state = json.load(f)
    except (OSError, ValueError):
        return {}
    result = {}
    for source_key, entry in (state.items() if isinstance(state, dict) else []):
        url, _, rest = source_key.partition('|')
        owner, _, repo = rest.partition('|')
        if url.rstrip('/') == gitea_url.rstrip('/') and isinstance(entry, dict):
            result[f'{owner}/{repo}'] = entry
    return result


def repos_table(gitea_url, repos):
    installed = load_import_state(gitea_url)
    rows = []
    for repo in repos[:MAX_REPOS_SHOWN]:
        name = repo['full_name']
        updated = repo['updated_at']
        entry = installed.get(name)
        if entry is None:
            imported_cell = '<span class="muted">not imported</span>'
        else:
            imported_at = format_time(entry.get('imported_at')) or 'before import tracking'
            commit = entry.get('commit')
            imported_cell = html.escape(imported_at) + (
                f' <span class="mono muted">{html.escape(commit)}</span>' if commit else '')
            imported_dt = parse_gitea_time(entry.get('imported_at'))
            if updated and imported_dt and updated > imported_dt:
                imported_cell += ' <span class="newer">- Gitea has newer changes</span>'
        rows.append(
            f'<tr><td class="mono">{html.escape(name)}</td>'
            f'<td>{html.escape(format_time(updated))}</td>'
            f'<td class="mono">{html.escape(repo["default_branch"])}</td>'
            f'<td>{imported_cell}</td></tr>')
    more = len(repos) - MAX_REPOS_SHOWN
    footer = f'<div class="muted" style="margin-top:4px">...and {more} more</div>' if more > 0 else ''
    return (
        '<table class="repos"><tr><th>Repo</th><th>Last updated in Gitea</th><th>Default branch</th>'
        '<th>Imported here</th></tr>' + ''.join(rows) + '</table>' + footer)


def error_banner(message):
    print(f'<div class="banner error">{message}</div>')


def main():
    print(STYLE)

    url_banner = missing_secret_banner_html('gitea', 'URL', 'the Gitea instance to import from')
    if url_banner:
        print(url_banner)
        return

    try:
        gitea_url = resolve_gitea_url()
    except GiteaApiError as e:
        error_banner(html.escape(str(e)))
        return

    tokens = list_gitea_tokens()

    if not tokens:
        # product/key kept on the call's own line so Secret Ingredients Check's per-line scan sees it
        print(missing_secret_banner_html('gitea', 'TOKEN', (
            'needed before importing from a private repo - a public repo needs no token')))
        return

    # The same token the form's Gitea Token field pre-selects (its default script)
    key, _updated_at = most_recent_gitea_token()
    token = get_secret('gitea', key)
    choice_note = ''
    if len(tokens) > 1:
        others = html.escape(', '.join(f'gitea.{k}' for k, _ in tokens if k != key))
        choice_note = (f' It is the most recently set of {len(tokens)} stored tokens and is '
                       f'pre-selected below - switch to {others} in the Gitea Token field if needed.')

    try:
        username = get_authenticated_user(gitea_url, token)
        repos = list_user_repo_details(gitea_url, token)
        print(
            f'<div class="banner success">Connected to <span class="mono">{html.escape(gitea_url)}'
            f'</span> as <b>{html.escape(username)}</b> using '
            f'<span class="mono">gitea.{html.escape(key)}</span> - {len(repos)} repo(s) '
            f'available.{choice_note}'
            + (repos_table(gitea_url, repos) if repos else '') +
            '</div>'
        )
    except GiteaApiError as e:
        error_banner(
            f'Stored token <span class="mono">gitea.{html.escape(key)}</span> did not work '
            f'against <span class="mono">{html.escape(gitea_url)}</span>: {html.escape(str(e))}'
        )


if __name__ == '__main__':
    main()
