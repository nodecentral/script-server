#!/usr/bin/env python3
# Name: download_image.py
# Version: 1.0.0
# Description: Downloads an image from a URL, saves it under /app/data,
#              and prints its path so Script-Server's inline-image
#              output_files pattern picks it up and displays it. Run
#              standalone (./download_image.py --url https://...) or from
#              Script-Server.

import argparse
import os
import sys
import time

import requests

DEBUG = os.environ.get('DEBUG', 'false') == 'true'


def log_debug(msg):
    if DEBUG:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] DEBUG: {msg}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default=os.environ.get('PARAM_URL', 'https://cataas.com/cat'))
    args = parser.parse_args()

    log_debug(f"Downloading {args.url}")

    try:
        response = requests.get(args.url, timeout=30)
    except requests.RequestException as e:
        print(f"Download failed: {e}", file=sys.stderr)
        sys.exit(1)

    if response.status_code != 200:
        print(f"Download failed: HTTP {response.status_code}", file=sys.stderr)
        sys.exit(1)

    content_type = response.headers.get('Content-Type', '')
    ext = 'jpg'
    if 'png' in content_type:
        ext = 'png'
    elif 'gif' in content_type:
        ext = 'gif'
    elif 'webp' in content_type:
        ext = 'webp'

    out_dir = '/app/data/downloads'
    os.makedirs(out_dir, exist_ok=True)
    file_name = f"download_{int(time.time())}.{ext}"
    file_path = os.path.join(out_dir, file_name)

    with open(file_path, 'wb') as f:
        f.write(response.content)

    print(f"Saved {len(response.content)} bytes to {file_path}")
    print(file_path, flush=True)


if __name__ == '__main__':
    main()
