#!/usr/bin/env python3
# Name: preload/secret_test.py
# Version: 1.0.0
# Description: Banner for Test a Secret - which default secrets are set, and what each test will
#              show. Reads the Secrets Store only: no network, no values shown.

import html
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'shared'))
sys.path.insert(0, os.path.join(HERE, '..'))
from secrets_store import get_secret, secrets_manager_link  # noqa: E402
from secret_test import CHECKS, ICONS  # noqa: E402

SHOWS = {
    'AI': 'a short reply from the model',
    'Finance': 'a live price or figure',
    'Services': 'what the key can see',
    'Notifications': 'a test notification on your phone',
}


def main():
    is_set = {p: all(get_secret(p, k, register=False) for k in keys)
              for p, (_label, _group, keys, _check) in CHECKS.items()}
    count = sum(is_set.values())
    e = html.escape
    rows = []
    for product, (label, group, _keys, _check) in CHECKS.items():
        state = ('<span style="color:#2e7d32">set</span>' if is_set[product]
                 else '<span style="color:#757575">not set</span>')
        rows.append(f'<tr><td>{ICONS[group]} {e(label)}</td><td>{state}</td>'
                    f'<td style="color:rgba(0,0,0,.56)">{e(SHOWS[group])}</td></tr>')
    print(f"""<div style="font-family:Roboto,-apple-system,'Segoe UI',sans-serif;font-size:13px;color:rgba(0,0,0,.87)">
<div style="margin-bottom:6px"><b>{count} of {len(CHECKS)}</b> secrets are set. Pick one below, or
<i>All secrets that are set</i>, then Execute. To add one, open
<a href="{e(secrets_manager_link())}" target="_top" style="color:#3949ab">Secrets Manager</a>.</div>
<details><summary style="cursor:pointer;color:#3949ab">Show all {len(CHECKS)}</summary>
<table style="border-collapse:collapse;margin-top:4px">{''.join(rows)}</table></details></div>""",
          flush=True)


if __name__ == '__main__':
    main()
