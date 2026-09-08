#!/usr/bin/env python3
# Shared module (not a standalone Script-Server script): Gitea API client + URL/token
# resolution, used by Import from Gitea's main script, its preload banner, and the live
# "repo"/"token" dropdowns.
#
# Both the Gitea URL and its token(s) live in the Secrets Store's "gitea" product (matching
# the paperless URL+TOKEN pattern) rather than as runner form fields - preload scripts get no
# parameter context at all (see CLAUDE.md), so a URL typed into the form could never reach the
# preload banner anyway; storing it means the preload, the dropdowns, and the main script all
# resolve the exact same value with no risk of drifting from a stale runner-JSON default.
# RESERVED_GITEA_KEYS marks key names under that product that are NOT tokens (currently just
# "URL") so the multi-token picker/dropdown never treats them as one.
#
# Token resolution: an explicit manually entered token always wins. Otherwise looks at the
# "gitea" product - if exactly one token is stored there it's auto-selected, if more than one
# a token_key must be given (see dropdown-tokens below), and if none are stored, no token is
# used (public repo assumed - any Gitea API call that actually needs auth then fails with a
# clear message rather than a confusing generic one).
#
# API calls use Gitea's token auth header: `Authorization: token <token>`. Every failure mode
# (network unreachable, bad token, wrong URL, non-JSON response) is normalized into
# GiteaApiError with a message meant to be shown directly to a user - callers should never need
# to catch raw `requests` exceptions.

import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from secrets_store import AUTO_SENTINEL, get_secret, list_product_keys  # noqa: E402

REQUEST_TIMEOUT_SECONDS = 10
REPOS_PAGE_SIZE = 50
REPOS_MAX_PAGES = 20  # safety cap - 1000 repos is far beyond any real personal Gitea instance

RESERVED_GITEA_KEYS = {'URL'}


class GiteaApiError(Exception):
    pass


def resolve_gitea_url():
    """Returns the configured Gitea base URL (no trailing slash). Raises GiteaApiError if
    none is set - the "gitea" product's reserved "URL" key, via Secrets Manager."""
    url = get_secret('gitea', 'URL')
    if not url:
        raise GiteaApiError('No Gitea URL configured - add one via Secrets Manager (product '
                             'gitea, key URL, e.g. http://192.168.102.148:3011).')
    return url.rstrip('/')


def list_gitea_tokens():
    """Keys under the "gitea" product that are actual tokens - excludes the reserved URL
    entry, so it's never offered as a fake "token" candidate."""
    return [(key, updated_at) for key, updated_at in list_product_keys('gitea')
            if key not in RESERVED_GITEA_KEYS]


def resolve_gitea_token(explicit_token, token_key):
    """Returns (token, source_description) - source_description is for logging/display only,
    never the token value itself. Raises GiteaApiError if the caller must resolve ambiguity
    (more than one token stored, none picked) or named a key that isn't actually stored."""
    if explicit_token:
        return explicit_token, 'the manually entered token field'

    stored = list_gitea_tokens()

    if token_key and token_key != AUTO_SENTINEL:
        # dropdown-tokens prints "KEY | last set <date>" - the selected value is that whole
        # line, not just the key, so pull the key back out before looking it up.
        key = token_key.split('|')[0].strip()
        value = get_secret('gitea', key)
        if value is None:
            raise GiteaApiError(f'No stored Gitea token found for gitea.{key} - check Secrets Manager.')
        return value, f'gitea.{key} (Secrets Store)'

    if len(stored) == 1:
        key = stored[0][0]
        return get_secret('gitea', key), f'gitea.{key} (Secrets Store, auto-selected - only one stored)'

    if len(stored) > 1:
        stored_names = ', '.join(f'gitea.{key}' for key, _ in stored)
        raise GiteaApiError(
            f'Multiple Gitea tokens are stored ({stored_names}) - pick one from the '
            '"Gitea Token" dropdown, or fill in the manual token field directly.'
        )

    return '', 'none (public repo assumed)'


def api_get(gitea_url, token, path):
    """GET <gitea_url>/api/v1<path>, authenticated if a token is given. Raises GiteaApiError
    with a clear, user-facing message on any failure - never raises a raw requests exception."""
    url = gitea_url.rstrip('/') + '/api/v1' + path
    headers = {'Authorization': f'token {token}'} if token else {}
    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.exceptions.ConnectionError:
        raise GiteaApiError(f'Could not reach {gitea_url} - check the URL and that this Gitea '
                             'instance is reachable from the container.')
    except requests.exceptions.Timeout:
        raise GiteaApiError(f'{gitea_url} did not respond within {REQUEST_TIMEOUT_SECONDS}s.')
    except requests.exceptions.RequestException as e:
        raise GiteaApiError(f'Request to {gitea_url} failed: {e}')

    if response.status_code == 401:
        raise GiteaApiError('Gitea rejected the token (401 Unauthorized) - it may be invalid, '
                             'expired, or revoked.')
    if response.status_code == 403:
        raise GiteaApiError('Gitea denied access (403 Forbidden) - the token may be missing '
                             'required scopes.')
    if response.status_code == 404:
        raise GiteaApiError(f'Not found (404) at {path} - check the Gitea URL is correct.')
    if not response.ok:
        raise GiteaApiError(f'Gitea returned HTTP {response.status_code} for {path}.')

    try:
        return response.json()
    except ValueError:
        raise GiteaApiError(f'Gitea returned a non-JSON response for {path} - is the URL '
                             'actually a Gitea instance?')


def get_authenticated_user(gitea_url, token):
    """Returns the username the token authenticates as. Requires a token."""
    if not token:
        raise GiteaApiError('No token available to identify the authenticated user.')
    data = api_get(gitea_url, token, '/user')
    username = data.get('login')
    if not username:
        raise GiteaApiError('Gitea did not return a username for this token.')
    return username


def list_user_repos(gitea_url, token):
    """Returns a sorted list of 'owner/repo' full names accessible to this token - the user's
    own repos plus any orgs it belongs to. Requires a token. This is what lets Import from
    Gitea's repo dropdown skip a separate "owner" field entirely: each entry already carries
    its real owner exactly as Gitea itself resolves it for that token, not a guess."""
    if not token:
        raise GiteaApiError('No token available to list repos.')

    repos = []
    for page in range(1, REPOS_MAX_PAGES + 1):
        data = api_get(gitea_url, token, f'/user/repos?limit={REPOS_PAGE_SIZE}&page={page}')
        if not data:
            break
        repos.extend(data)
        if len(data) < REPOS_PAGE_SIZE:
            break

    return sorted({repo['full_name'] for repo in repos if repo.get('full_name')})


def _cmd_dropdown_repos(args):
    # Only token_key, never an explicit manually-typed token: Script-Server hard-refuses to load
    # any runner where a "secure" parameter is referenced in another parameter's values.script
    # (raises "Unsupported parameter ... of type secure in values.script!" at config-load time,
    # confirmed on a real instance - not a runtime issue, the whole script fails to open). The
    # manual token field can still drive the actual import/clone step, just not this dropdown.
    if len(args) != 1:
        print('-- usage: dropdown-repos <token_key> --')
        return

    token_key = args[0]
    try:
        gitea_url = resolve_gitea_url()
        token, _source = resolve_gitea_token('', token_key)
        if not token:
            print('-- no Gitea token available - add one via Secrets Manager (a manually typed '
                  'token cannot drive this dropdown, only the actual import) --')
            return
        repos = list_user_repos(gitea_url, token)
    except GiteaApiError as e:
        print(f'-- could not fetch repos: {e} --')
        return

    if not repos:
        print('-- no repos found for this token --')
        return

    for full_name in repos:
        print(full_name)


def _cmd_dropdown_tokens(_args):
    print(AUTO_SENTINEL)
    for key, updated_at in list_gitea_tokens():
        print(f'{key} | last set {updated_at}')


def main():
    if len(sys.argv) < 2:
        print('Usage: gitea_client.py <dropdown-repos|dropdown-tokens> [args...]', file=sys.stderr)
        sys.exit(1)

    command, rest = sys.argv[1], sys.argv[2:]
    commands = {
        'dropdown-repos': _cmd_dropdown_repos,
        'dropdown-tokens': _cmd_dropdown_tokens,
    }
    if command not in commands:
        print(f'Unknown command: {command}', file=sys.stderr)
        sys.exit(1)

    commands[command](rest)


if __name__ == '__main__':
    main()
