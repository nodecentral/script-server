#!/usr/bin/env python3
# Name: disk_usage_chart.py
# Version: 1.0.0
# Description: Renders an interactive bar chart (via Plotly) of used vs
#              free space for /app and its bind-mounted subfolders.
#              Rendered with output_format html_iframe. Run standalone
#              (./disk_usage_chart.py) or from Script-Server.

import os
import shutil

import plotly.graph_objects as go

PATHS = ['/app', '/app/conf', '/app/scripts', '/app/data', '/app/logs']


def main():
    labels = []
    used_gb = []
    free_gb = []

    for path in PATHS:
        if not os.path.isdir(path):
            continue
        usage = shutil.disk_usage(path)
        labels.append(path)
        used_gb.append(round(usage.used / (1024 ** 3), 2))
        free_gb.append(round(usage.free / (1024 ** 3), 2))

    if not labels:
        print("No paths found to chart.")
        return

    fig = go.Figure(data=[
        go.Bar(name='Used (GB)', x=labels, y=used_gb),
        go.Bar(name='Free (GB)', x=labels, y=free_gb),
    ])
    fig.update_layout(barmode='group', title='Disk usage by mount')

    print(fig.to_html())


if __name__ == '__main__':
    main()
