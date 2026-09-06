#!/usr/bin/env python3
# Name: motd.py
# Version: 1.0.0
# Description: A Message-of-the-Day style status summary for this
#              Script-Server instance - system stats (uptime, load,
#              memory) plus a snapshot of this app's own state (bind
#              mounts, scripts/runners count, network inventory,
#              installed extras). Two render modes from one data set:
#              --html for use as a preload_script banner, plain ANSI
#              terminal output otherwise (the classic MOTD look). Run
#              standalone (./motd.py) or from Script-Server.

import html
import json
import os
import socket
import sys

NETWORK_INVENTORY_PATH = '/app/data/network_inventory.json'
INSTALLED_EXTRAS_PATH = '/app/data/installed_extras.json'
CAPABILITIES_PATH = '/app/conf/capabilities.json'
RUNNERS_DIR = '/app/conf/runners'
SCRIPTS_DIR = '/app/scripts'

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


def count_files(directory, suffix=None):
    if not os.path.isdir(directory):
        return 0
    count = 0
    for name in os.listdir(directory):
        if suffix is None or name.endswith(suffix):
            if os.path.isfile(os.path.join(directory, name)):
                count += 1
    return count


def get_network_inventory_summary():
    if not os.path.exists(NETWORK_INVENTORY_PATH):
        return None
    try:
        with open(NETWORK_INVENTORY_PATH) as f:
            inventory = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    total = len(inventory)
    labeled = sum(1 for entry in inventory.values() if entry.get('label'))
    return total, labeled


def get_installed_extras_count():
    if not os.path.exists(INSTALLED_EXTRAS_PATH):
        return 0
    try:
        with open(INSTALLED_EXTRAS_PATH) as f:
            return len(json.load(f))
    except (OSError, json.JSONDecodeError):
        return 0


def gather_stats():
    mounts_ok, mounts_total = get_bind_mount_status()
    network_summary = get_network_inventory_summary()

    return {
        'hostname': socket.gethostname(),
        'uptime': get_uptime(),
        'load_average': get_load_average(),
        'memory': get_memory(),
        'disk': get_disk_usage(),
        'mounts_ok': mounts_ok,
        'mounts_total': mounts_total,
        'runners_count': count_files(RUNNERS_DIR, '.json'),
        'scripts_count': count_files(SCRIPTS_DIR),
        'network_summary': network_summary,
        'installed_extras': get_installed_extras_count(),
    }


def render_terminal(stats):
    RESET = '\033[0m'
    BOLD = '\033[1m'
    CYAN = '\033[36m'
    YELLOW = '\033[33m'
    GREEN = '\033[32m'

    lines = []
    lines.append(f'{BOLD}{CYAN}{"=" * 50}{RESET}')
    lines.append(f'{BOLD}{CYAN}  Script-Server MOTD - {stats["hostname"]}{RESET}')
    lines.append(f'{BOLD}{CYAN}{"=" * 50}{RESET}')
    lines.append('')
    lines.append(f'{YELLOW}System{RESET}')
    lines.append(f'  Uptime:        {stats["uptime"]}')
    lines.append(f'  Load average:  {stats["load_average"]}')
    lines.append(f'  Memory:        {stats["memory"]}')
    lines.append(f'  Disk (/app):   {stats["disk"]}')
    lines.append('')
    lines.append(f'{YELLOW}Script-Server{RESET}')
    mounts_color = GREEN if stats['mounts_ok'] == stats['mounts_total'] else '\033[31m'
    lines.append(f'  Bind mounts:   {mounts_color}{stats["mounts_ok"]}/{stats["mounts_total"]} connected{RESET}')
    lines.append(f'  Runners:       {stats["runners_count"]}')
    lines.append(f'  Scripts:       {stats["scripts_count"]}')
    if stats['network_summary']:
        total, labeled = stats['network_summary']
        lines.append(f'  Network inv.:  {total} device(s), {labeled} labeled')
    if stats['installed_extras']:
        lines.append(f'  Extras added:  {stats["installed_extras"]} (runtime-installed)')
    lines.append('')
    lines.append(f'{BOLD}{CYAN}{"=" * 50}{RESET}')
    return '\n'.join(lines)


def render_html(stats):
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

    rows = [
        row('Hostname', stats['hostname']),
        row('Uptime', stats['uptime']),
        row('Load average', stats['load_average']),
        row('Memory', stats['memory']),
        row('Disk (/app)', stats['disk']),
        row('Bind mounts', f'{stats["mounts_ok"]}/{stats["mounts_total"]} connected',
            ok=(stats['mounts_ok'] == stats['mounts_total'])),
        row('Runners', stats['runners_count']),
        row('Scripts', stats['scripts_count']),
    ]
    if stats['network_summary']:
        total, labeled = stats['network_summary']
        rows.append(row('Network inventory', f'{total} device(s), {labeled} labeled'))
    if stats['installed_extras']:
        rows.append(row('Runtime-installed extras', stats['installed_extras']))

    return f"""
<div style="font-family: 'Roboto', Arial, sans-serif; max-width: 420px;
            border: 1px solid #ddd; border-radius: 4px; overflow: hidden;">
  <div style="background: #26a69a; color: white; padding: 10px 16px; font-size: 1.05rem;">
    Script-Server MOTD
  </div>
  <div style="padding: 8px 16px 12px 16px; font-size: 0.9rem;">
    {''.join(rows)}
  </div>
</div>
"""


def main():
    html_mode = '--html' in sys.argv
    stats = gather_stats()
    if html_mode:
        print(render_html(stats))
    else:
        print(render_terminal(stats))


if __name__ == '__main__':
    main()
