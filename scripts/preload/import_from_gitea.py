#!/usr/bin/env python3
# Name: preload/import_from_gitea.py
# Version: 2.0.0
# Description: preload_script for conf/runners/import_from_gitea.json - checks whether a Gitea
#              URL and token are configured in the Secrets Store before the form even loads.
#              With no URL, or no token, tells the user what to add via Secrets Manager. With a
#              URL and exactly one token, actually tries connecting and reports success (as
#              which user, how many repos) or failure (with the real reason) - genuinely
#              different job from the main script (a readiness/connectivity check, not an
#              import), per CLAUDE.md's preload_script guidance. Preload scripts receive no
#              parameter values at all (see CLAUDE.md) - this is exactly why the URL lives in
#              the Secrets Store rather than a runner form field: a value typed into the form
#              could never reach this banner anyway, so storing it means the preload always
#              checks the real configured URL, not a guess. Run standalone
#              (./preload/import_from_gitea.py) or from Script-Server.

import html
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'shared'))
from gitea_client import (  # noqa: E402
    GiteaApiError, get_authenticated_user, list_gitea_tokens, list_user_repos, resolve_gitea_url,
)
from secrets_store import get_secret  # noqa: E402

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
</style>
"""


def error_banner(message):
    print(f'<div class="banner error">{message}</div>')


def main():
    print(STYLE)

    try:
        gitea_url = resolve_gitea_url()
    except GiteaApiError as e:
        error_banner(html.escape(str(e)))
        return

    tokens = list_gitea_tokens()

    if not tokens:
        error_banner(
            'No Gitea token is configured yet. Add one via <b>Secrets Manager</b> (product '
            '<span class="mono">gitea</span>, e.g. key <span class="mono">TOKEN</span>) before '
            'importing from a private repo.'
        )
        return

    if len(tokens) > 1:
        token_list = html.escape(', '.join(f'gitea.{key}' for key, _ in tokens))
        print(
            f'<div class="banner info">{len(tokens)} Gitea tokens are stored ({token_list}) - '
            'pick one from the "Gitea Token" dropdown below.</div>'
        )
        return

    key, _updated_at = tokens[0]
    token = get_secret('gitea', key)

    try:
        username = get_authenticated_user(gitea_url, token)
        repos = list_user_repos(gitea_url, token)
        print(
            f'<div class="banner success">Connected to <span class="mono">{html.escape(gitea_url)}'
            f'</span> as <b>{html.escape(username)}</b> using '
            f'<span class="mono">gitea.{html.escape(key)}</span> - {len(repos)} repo(s) '
            'available.</div>'
        )
    except GiteaApiError as e:
        error_banner(
            f'Stored token <span class="mono">gitea.{html.escape(key)}</span> did not work '
            f'against <span class="mono">{html.escape(gitea_url)}</span>: {html.escape(str(e))}'
        )


if __name__ == '__main__':
    main()
