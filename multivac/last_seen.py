#!/usr/bin/env python

import os
import sys
import glob
from datetime import datetime
import json
import csv
import argparse
import importlib.resources as pkg_resources


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_DIR)
from multivac.sensors import test_status  # noqa: E402


parser = argparse.ArgumentParser(description="""
    Search for fails and sort by last occurence.
    The resulting report is stored in the output/ directory.
    """)
parser.add_argument('--branch', type=str, action='append',
                    help='branch (may be passed several times)')
parser.add_argument('--format', choices=['csv', 'html'], default='csv',
                    help='result format')
args = parser.parse_args()
branch_list = args.branch
result_format = args.format


def fails(log):
    for event in test_status.execute(log):
        if event['event'] != 'test status':
            continue
        status = event['status']
        if status in ('fail', 'transient fail'):
            yield event['test'], event['conf'], status


timestamps_min = dict()
timestamps_max = dict()
res = dict()
for log in glob.glob('runs/*.log'):
    meta_path = log.split('.', 1)[0] + '.json'
    with open(meta_path, 'r') as f:
        run = json.load(f)
    branch = run['head_branch']

    if branch not in branch_list:
        continue

    timestamp = datetime.fromisoformat(run['created_at'].rstrip('Z'))
    if branch not in timestamps_min or timestamps_min[branch] > timestamp:
        timestamps_min[branch] = timestamp
    if branch not in timestamps_max or timestamps_max[branch] < timestamp:
        timestamps_max[branch] = timestamp

    url = run['html_url']

    for test, conf, status in fails(log):
        key = (test, conf, status)
        if key not in res:
            res[key] = (timestamp, branch, 1, url)
        elif res[key][0] < timestamp:
            res[key] = (timestamp, branch, res[key][2] + 1, url)
        else:
            res[key] = (res[key][0], res[key][1], res[key][2] + 1, res[key][3])

res = sorted(res.items(), key=lambda kv: (kv[1][0], kv[1][2]), reverse=True)


output_fh = None


def write_line(line):
    global output_fh
    print(line, file=output_fh)


def write_csv():
    global output_fh

    print('Statistics for the following log intervals\n', file=sys.stderr)
    for branch in branch_list:
        timestamp_min = timestamps_min[branch].isoformat()
        timestamp_max = timestamps_max[branch].isoformat()
        print('{}: [{}, {}]'.format(branch, timestamp_min, timestamp_max),
              file=sys.stderr)

    w = csv.writer(output_fh)
    write_line('timestamp,test,conf,branch,status,count,url')
    for key, value in res:
        test, conf, status = key
        timestamp, branch, count, url = value
        w.writerow([timestamp, test, conf, branch, status, count, url])


def write_html_header():
    write_line('<!DOCTYPE html>')
    write_line('<html>')
    write_line('  <head>')
    write_line('    <meta http-equiv="Content-Type" content="text/html; ' +
               'charset=utf-8">')
    write_line('    <title>Last seen fails in CI</title>')
    write_line('    <link rel="stylesheet" type="text/css" href="main.css">')
    write_line('  </head>')
    write_line('  <body>')


def write_html_footer():
    write_line('  </body>')
    write_line('</html>')


def write_html():
    write_html_header()
    write_line('    <h1>Last seen fails in CI</h1>')

    write_line('    <table class="log_intervals">')
    write_line('      <caption>Log intervals</caption>')
    write_line('      <tr>')
    write_line('        <th>Timestamp</th>')
    write_line('        <th>Starting from</th>')
    write_line('        <th>Ending at</th>')
    write_line('      </tr>')
    write_line('      <tr>')
    for branch in branch_list:
        timestamp_min = timestamps_min[branch].isoformat()
        timestamp_max = timestamps_max[branch].isoformat()
        write_line('        <td class="branch">{}</td>'.format(branch))
        write_line('        <td class="timestamp_min">{}</td>'.format(
            timestamp_min))
        write_line('        <td class="timestamp_max">{}</td>'.format(
            timestamp_max))
        write_line('      </tr>')
    write_line('    </table>')

    write_line('    <table class="last_seen">')
    write_line('      <caption>Last seen fails in CI</caption>')
    write_line('      <tr>')
    write_line('        <th>Timestamp</th>')
    write_line('        <th>Test</th>')
    write_line('        <th>Conf</th>')
    write_line('        <th>Branch</th>')
    write_line('        <th>Status</th>')
    write_line('        <th>Count</th>')
    write_line('        <th>URL</th>')
    write_line('      </tr>')
    for key, value in res:
        test, conf, status = key
        timestamp, branch, count, url = value
        write_line('      <tr>')
        write_line('        <td class="timestamp">{}</td>'.format(timestamp))
        write_line('        <td class="test">{}</td>'.format(test))
        write_line('        <td class="conf">{}</td>'.format(conf or ''))
        write_line('        <td class="branch">{}</td>'.format(branch))
        write_line('        <td class="status">{}</td>'.format(status))
        write_line('        <td class="count">{}</td>'.format(count))
        write_line('        <td class="url"><a href="{}">[log]</td>'.format(
            url))
        write_line('      </tr>')
    write_line('    </table>')

    write_html_footer()


if not os.path.isdir('output'):
    os.makedirs('output')

if result_format == 'csv':
    output_file = 'output/last_seen.csv'

    with open(output_file, 'w') as f:
        output_fh = f
        write_csv()

    print('Written {}'.format(output_file), file=sys.stderr)
elif result_format == 'html':
    output_css_file = 'output/main.css'
    output_html_file = 'output/last_seen.html'

    css = pkg_resources.read_text('multivac.resources', 'main.css')
    with open(output_css_file, 'w') as f:
        f.write(css)
    print('Written {}'.format(output_css_file), file=sys.stderr)

    with open(output_html_file, 'w') as f:
        output_fh = f
        write_html()
    print('Written {}'.format(output_html_file), file=sys.stderr)
else:
    raise ValueError('Unknown result format: {}'.format(result_format))
