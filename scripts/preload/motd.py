#!/usr/bin/env python3
# Name: preload/motd.py
# Version: 1.0.0
# Description: preload_script for conf/runners/motd.json - a standalone
#              file under scripts/preload/, matching the base name of the
#              main script (scripts/motd.py) per CLAUDE.md's "Where the
#              preload script should live" convention. Shows a live system
#              stats banner (uptime, load, memory, disk, bind-mount health)
#              PLUS what clicking Run will actually do: a Script Ingredients
#              Check across every configured runner. Run standalone
#              (./preload/motd.py) or from Script-Server.

import html
import os
import socket

RUNNERS_DIR = '/app/conf/runners'

BIND_MOUNTS = [
    ('conf', '/app/conf', '/app/conf/runners/hello_world.json'),
    ('scripts', '/app/scripts', '/app/scripts/hello_world.sh'),
    ('data', '/app/data', '/app/data/.gitkeep'),
    ('logs', '/app/logs', None),
]


def format_uptime(seconds):
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, _ = divmod(seconds, 60)
    parts = []
    if days:
        parts.append(f'{days}d')
    if hours or days:
        parts.append(f'{hours}h')
    parts.append(f'{minutes}m')
    return ' '.join(parts)


def get_uptime():
    try:
        with open('/proc/uptime') as f:
            seconds = float(f.read().split()[0])
        return format_uptime(seconds)
    except OSError:
        return 'unknown'


def get_load_average():
    try:
        one, five, fifteen = os.getloadavg()
        return f'{one:.2f}, {five:.2f}, {fifteen:.2f}'
    except OSError:
        return 'unknown'


def format_bytes(n):
    for unit in ('B', 'K', 'M', 'G', 'T'):
        if abs(n) < 1024:
            return f'{n:.1f}{unit}'
        n /= 1024
    return f'{n:.1f}P'


def get_memory():
    try:
        info = {}
        with open('/proc/meminfo') as f:
            for line in f:
                key, _, rest = line.partition(':')
                info[key] = int(rest.strip().split()[0]) * 1024  # kB -> bytes

        total = info.get('MemTotal', 0)
        available = info.get('MemAvailable', 0)
        used = max(total - available, 0)
        percent = (used / total * 100) if total else 0
        return f'{format_bytes(used)} / {format_bytes(total)} ({percent:.0f}%)'
    except OSError:
        return 'unknown'


def get_disk_usage():
    try:
        usage = os.statvfs('/app')
        total = usage.f_frsize * usage.f_blocks
        free = usage.f_frsize * usage.f_bavail
        used = total - free
        percent = (used / total * 100) if total else 0
        return f'{format_bytes(used)} / {format_bytes(total)} ({percent:.0f}%)'
    except OSError:
        return 'unknown'


def get_bind_mount_status():
    connected = 0
    for _label, path, marker in BIND_MOUNTS:
        if not os.path.isdir(path):
            continue
        if marker is None or os.path.exists(marker):
            connected += 1
    return connected, len(BIND_MOUNTS)


def count_runners():
    if not os.path.isdir(RUNNERS_DIR):
        return 0
    return sum(1 for name in os.listdir(RUNNERS_DIR) if name.endswith('.json'))


def main():
    hostname = socket.gethostname()
    uptime = get_uptime()
    load_average = get_load_average()
    memory = get_memory()
    disk = get_disk_usage()
    mounts_ok, mounts_total = get_bind_mount_status()
    runners_count = count_runners()

    def row(label, value, ok=None):
        color = ''
        if ok is True:
            color = 'color: #2e7d32;'
        elif ok is False:
            color = 'color: #c62828;'
        return (
            '<div style="display:flex; justify-content:space-between; padding:3px 0;">'
            f'<span style="color:#757575;">{html.escape(label)}</span>'
            f'<span style="font-weight:500; {color}">{html.escape(str(value))}</span>'
            '</div>'
        )

    rows = ''.join([
        row('Hostname', hostname),
        row('Uptime', uptime),
        row('Load average', load_average),
        row('Memory', memory),
        row('Disk (/app)', disk),
        row('Bind mounts', f'{mounts_ok}/{mounts_total} connected', ok=(mounts_ok == mounts_total)),
    ])

    print(f"""
<div style="font-family: 'Roboto', Arial, sans-serif; max-width: 460px;
            border: 1px solid #ddd; border-radius: 4px; overflow: hidden;">
  <div style="background: #26a69a; color: white; padding: 10px 16px; font-size: 1.05rem;">
    Script-Server MOTD
  </div>
  <div style="padding: 8px 16px 12px 16px; font-size: 0.9rem;">
    {rows}
  </div>
  <div style="padding: 8px 16px; font-size: 0.85rem; background: #f5f5f5;
              border-top: 1px solid #ddd; color: #555;">
    Clicking Run will perform a <b>Script Ingredients Check</b> across all
    {runners_count} configured runner(s) - confirming each one's script and
    preload files actually exist on disk.
  </div>
</div>
""")


if __name__ == '__main__':
    main()
