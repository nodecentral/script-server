#!/usr/bin/env python3
# Name: preload/notify.py
# Version: 1.1.0
# Description: preload_script for conf/runners/notify.json - checks which notification
#              services have their credentials in the Secrets Store before the form loads, per
#              the "every script owns preparing for its own secret" pattern (CLAUDE.md/
#              SCRIPTING.md's Secrets Store section; reference: preload/import_from_gitea.py).
#              Pushover and Prowl are alternatives, so this only shows the red
#              missing_secret_banner_html() warnings when NEITHER is fully configured - with at
#              least one ready, it confirms which, and names the other's entries to pick
#              in Secrets Manager rather than warning about a service you may never use. Either way every
#              missing secret is registered as a placeholder in Secrets Manager (via
#              get_secret()). Run standalone (./preload/notify.py) or from Script-Server.

import html
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'shared'))
from secrets_store import (  # noqa: E402
    dropdown_entry_label, get_secret, missing_secrets_banner_html, secrets_manager_link,
)

SERVICES = {
    'Pushover': [('pushover', 'TOKEN', 'Send Notification via Pushover'),
                 ('pushover', 'USER_KEY', 'Send Notification via Pushover')],
    'Prowl': [('prowl', 'TOKEN', 'Send Notification via Prowl')],
}

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
    background: #e8f5e9;
    border-left-color: #26a69a;
  }
  .mono { font-family: "Roboto Mono", "Courier New", monospace; }
</style>
"""


def main():
    print(STYLE)

    missing = {}
    for service, requirements in SERVICES.items():
        missing[service] = [(product, key, purpose) for product, key, purpose in requirements
                            if get_secret(product, key, purpose) is None]
    ready = [service for service in SERVICES if not missing[service]]

    if not ready:
        print(missing_secrets_banner_html(
            [req for service in SERVICES for req in missing[service]]))
        return

    others = []
    for service in SERVICES:
        for product, key, _purpose in missing[service]:
            others.append(f'<b class="mono">{html.escape(dropdown_entry_label(product, key))}</b>')
    extra = (f' Not set up (only needed to use them) - to add, <a href="{secrets_manager_link()}" '
             f'target="_top">open Secrets Manager</a> and pick {", ".join(others)} from the Entry '
             'dropdown.') if others else ''
    print(f'<div class="banner">Ready to send via {html.escape(" and ".join(ready))} '
          f'(Secrets Store) - or type a token below to override.{extra}</div>')


if __name__ == '__main__':
    main()
