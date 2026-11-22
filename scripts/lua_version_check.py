#!/usr/bin/env python3
# Name: lua_version_check.py
# Version: 1.0.0
# Description: Lua Version Check - for every Lua script installed here, says whether it runs on
#              Script Server 2 (Lua 5.1) and Script Server 3 (Lua 5.4 by default, 5.1 still
#              there), what to change if not, and which imported repo it came from. Read-only.
#
# Standalone: python3 lua_version_check.py [--all] [--scripts-dir D] [--runners-dir D] [--state F]

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

BOLD_BLUE, BOLD, GREEN, MAGENTA, RED, CYAN, GREY, RESET = (
    '\033[1;34m', '\033[1;30m', '\033[1;32m', '\033[1;35m', '\033[1;31m', '\033[36m', '\033[90m', '\033[0m')

# Lua 5.1 functions that Lua 5.4 no longer has, with what to use instead. A file that shims one
# (e.g. `local unpack = table.unpack or unpack`) is fine.
GONE_IN_54 = [
    (r'(?<![.\w])unpack\s*\(', 'unpack()', 'table.unpack (add: local unpack = table.unpack or unpack)',
     r'table\.unpack\s+or\s+unpack|unpack\s+or\s+table\.unpack'),
    (r'(?<![.\w])loadstring\s*\(', 'loadstring()', 'load (add: local loadstring = loadstring or load)',
     r'loadstring\s+or\s+load|load\s+or\s+loadstring'),
    (r'(?<![.\w])setfenv\s*\(', 'setfenv()', 'pass an environment table to load() instead', None),
    (r'(?<![.\w])getfenv\s*\(', 'getfenv()', '_ENV, or pass values in explicitly', None),
    (r'^\s*module\s*\(', 'module()', 'return a table from the file: local M = {} ... return M', None),
    (r'\bmath\.pow\s*\(', 'math.pow()', 'x ^ y', None),
    (r'\bmath\.mod\s*\(', 'math.mod()', 'math.fmod() or %', None),
    (r'\bmath\.(?:ldexp|frexp|cosh|sinh|tanh|log10)\s*\(', 'an old math function', 'see the Lua 5.4 manual', None),
    (r'\btable\.(?:getn|setn|maxn)\s*\(', 'table.getn/setn/maxn()', '#t', None),
    (r'\bstring\.gfind\s*\(', 'string.gfind()', 'string.gmatch()', None),
]

# Functions Lua 5.1 doesn't have (syntax such as // goto <const> is caught by luac5.1 instead).
NEW_IN_54 = [
    (r'\btable\.unpack\b', 'table.unpack', r'table\.unpack\s+or\s+unpack|unpack\s+or\s+table\.unpack'),
    (r'\btable\.(?:pack|move)\s*\(', 'table.pack/move()', None),
    (r'\butf8\.', 'the utf8 library', None),
    (r'\bmath\.(?:type|tointeger|ult|maxinteger|mininteger)\b', 'math.type/tointeger/maxinteger', None),
    (r'\bstring\.(?:pack|unpack|packsize)\s*\(', 'string.pack/unpack()', None),
    (r'(?<![.\w])load\s*\(\s*["\'\[]', 'load() with a string', r'loadstring\s+or\s+load|load\s+or\s+loadstring'),
    (r'\bcoroutine\.(?:isyieldable|close)\s*\(', 'coroutine.isyieldable/close()', None),
]

# Runs on both, but can print differently: on 5.4, 10/2 is 5.0, and %d refuses 2.5.
FORMAT_D_WITH_DIVISION = re.compile(r'%d.*[^/]/[^/]|[^/]/[^/].*%d')


def strip_comment(line):
    """The line without a trailing -- comment (approximate: ignores -- inside strings)."""
    pos = line.find('--')
    return line if pos < 0 else line[:pos]


def import_sources(state_path):
    """{path relative to /app/scripts: 'owner/repo'} from Import from Gitea's state file."""
    try:
        with open(state_path, encoding='utf-8') as f:
            state = json.load(f)
    except (OSError, ValueError):
        return {}
    sources = {}
    for key, entry in state.items():
        if isinstance(entry, dict):
            _url, _, rest = key.partition('|')
            for rel in entry.get('scripts') or []:
                sources.setdefault(rel, rest.replace('|', '/'))
    return sources


def runner_interpreters(runners_dir):
    """{script file name: interpreter named in a runner's script_path, e.g. 'lua5.1'}."""
    found = {}
    try:
        names = sorted(os.listdir(runners_dir))
    except OSError:
        return found
    for name in names:
        if not name.endswith('.json'):
            continue
        try:
            with open(os.path.join(runners_dir, name), encoding='utf-8') as f:
                runner = json.load(f)
        except (OSError, ValueError):
            continue
        match = re.match(r'\s*(?:/usr/bin/(?:env\s+)?)?(lua(?:5\.\d)?)\s+(\S+\.lua)', str(runner.get('script_path', '')))
        if match:
            found[os.path.basename(match.group(2))] = match.group(1)
    return found


def syntax_errors(path):
    """{'5.1': error or None, ...} for each luac installed here."""
    result = {}
    for version in ('5.1', '5.4'):
        luac = shutil.which('luac' + version)
        if not luac:
            continue
        proc = subprocess.run([luac, '-p', path], capture_output=True, text=True)
        message = (proc.stderr.strip().splitlines() or ['error'])[-1]
        message = re.sub(r'^.*?\.lua:(\d+):\s*', r'line \1: ', message.replace(luac + ': ', ''))
        result[version] = None if proc.returncode == 0 else message
    return result


def check_file(path, interpreter_override=None):
    with open(path, encoding='utf-8', errors='replace') as f:
        text = f.read()
    lines = text.splitlines()
    shebang = lines[0] if lines and lines[0].startswith('#!') else ''
    match = re.search(r'\blua(5\.\d)?\b', shebang)
    runs_as = interpreter_override or (('lua' + (match.group(1) or '')) if match else '')

    gone, new, advisories = [], [], []
    for number, raw in enumerate(lines, 1):
        if raw.lstrip().startswith('--') or (number == 1 and shebang):
            continue
        line = strip_comment(raw)
        for pattern, what, instead, shim in GONE_IN_54:
            if re.search(pattern, line) and not (shim and re.search(shim, text)):
                gone.append(f'line {number}: {what} - use {instead}')
        for pattern, what, shim in NEW_IN_54:
            if re.search(pattern, line) and not (shim and re.search(shim, text)):
                new.append(f'line {number}: {what} is not in Lua 5.1')
        if 'format' in line and FORMAT_D_WITH_DIVISION.search(line) and not re.search(r'math\.(?:floor|ceil)', line):
            advisories.append(f'line {number}: %d with a division - on 5.4 a result such as 2.5 is an '
                              'error; wrap it in math.floor()')

    syntax = syntax_errors(path)
    if syntax.get('5.1'):
        new.insert(0, f'Lua 5.1 can\'t parse it: {syntax["5.1"]}')
    if syntax.get('5.4'):
        gone.insert(0, f'Lua 5.4 can\'t parse it: {syntax["5.4"]}')

    # Which interpreters must the file work with? A pinned lua5.1/lua5.4 is the same on every image
    # that has it; plain `lua` (or no first line: a helper loaded with dofile/require) is 5.1 on
    # Script Server 2 and 5.4 on Script Server 3.
    if runs_as == 'lua5.1':
        needs, note = ['5.1'], 'pinned to Lua 5.1 - runs the same on v2 and v3'
    elif runs_as == 'lua5.4':
        needs, note = ['5.4'], 'pinned to Lua 5.4 - v3 only (v2 has no lua5.4)'
    else:
        needs = ['5.1', '5.4']
        note = 'plain lua - 5.1 on v2, 5.4 on v3' if runs_as else 'no #! line - runs as its caller does'

    problems = []
    if '5.4' in needs and gone:
        problems += [('v3', g) for g in gone]
    if '5.1' in needs and new:
        problems += [('v2', n) for n in new]
    if runs_as == 'lua5.4':
        problems.insert(0, ('v2', 'Script Server 2 has no lua5.4 - use #!/usr/bin/env lua while v2 is supported'))
    checks = advisories if '5.4' in needs else []
    return {'runs_as': runs_as or '(caller)', 'note': note, 'problems': problems, 'checks': checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all', action='store_true', help='list files with nothing to change too')
    parser.add_argument('--scripts-dir', default='/app/scripts')
    parser.add_argument('--runners-dir', default='/app/conf/runners')
    parser.add_argument('--state', default='/app/data/gitea_import_state.json')
    args = parser.parse_args()
    show_all = args.all or os.environ.get('PARAM_SHOW', '') == 'all'

    sources = import_sources(args.state)
    overrides = runner_interpreters(args.runners_dir)
    files = []
    for root, dirs, names in os.walk(args.scripts_dir):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
        files += [os.path.join(root, n) for n in sorted(names) if n.endswith('.lua')]

    lua = shutil.which('lua')
    default = subprocess.run([lua, '-v'], capture_output=True, text=True) if lua else None
    default_text = ((default.stdout or default.stderr).split(' Copyright')[0].strip() if default else 'not installed')
    have = [v for v in ('5.1', '5.4') if shutil.which('lua' + v)]
    print(f'{BOLD_BLUE}Lua Version Check{RESET}', flush=True)
    print(f'Here, plain lua runs {CYAN}{default_text}{RESET}; installed: '
          f'{", ".join("lua" + v for v in have) or "none"}.', flush=True)
    if '5.4' not in have:
        print(f'{GREY}No Lua 5.4 here (Script Server 2), so 5.4 problems are found by pattern only.{RESET}', flush=True)
    print(f'{GREY}Script Server 2 runs plain lua as 5.1; Script Server 3 as 5.4 (LUA_DEFAULT=5.1 on the '
          f'container switches it back). Until v2 is retired, a script must run on both.{RESET}', flush=True)
    print(flush=True)

    counts = {'ok': 0, 'check': 0, 'fix': 0}
    by_repo = {}
    for path in files:
        rel = os.path.relpath(path, args.scripts_dir)
        result = check_file(path, overrides.get(os.path.basename(path)))
        repo = sources.get(rel, 'not imported (this image, or copied in)')
        state = 'fix' if result['problems'] else 'check' if result['checks'] else 'ok'
        counts[state] += 1
        if state == 'ok' and not show_all:
            continue
        by_repo.setdefault(repo, []).append((rel, state, result))

    for repo in sorted(by_repo):
        print(f'{BOLD}{repo}{RESET}', flush=True)
        for rel, state, result in by_repo[repo]:
            label = {'fix': f'{RED}FIX{RESET}  ', 'check': f'{MAGENTA}CHECK{RESET}', 'ok': f'{GREEN}OK{RESET}   '}[state]
            print(f'  {label} {CYAN}{rel}{RESET}  {GREY}{result["note"]}{RESET}', flush=True)
            for where, text in result['problems']:
                print(f'         breaks on {where}: {text}', flush=True)
            for text in result['checks']:
                print(f'         check: {text}', flush=True)
        print(flush=True)

    total = len(files)
    print(f'{BOLD}SUMMARY:{RESET} {total} Lua files - {GREEN}{counts["ok"]} OK{RESET}, '
          f'{MAGENTA}{counts["check"]} to check{RESET}, {RED}{counts["fix"]} to fix{RESET}.', flush=True)
    if counts['fix']:
        print(f'{GREY}Fix a file in the repo it came from, then re-import it. Until then, LUA_DEFAULT=5.1 on '
              f'the v3 container keeps plain-lua scripts on 5.1.{RESET}', flush=True)
    if not show_all and counts['ok']:
        print(f'{GREY}Files with nothing to change are hidden: pick "Every Lua file" to list them.{RESET}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
