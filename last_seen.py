#!/usr/bin/env python

import sys
import os
import re
import glob
from datetime import datetime
import json
from subprocess import PIPE
from subprocess import Popen
import csv

RE = re.compile(r'event: fail; test: (?P<test>[^ ]+)(; conf: (?P<conf>[^ ]+))?')

def fails(log):
    with Popen(['sensors/fails.py', log], stdout=PIPE, encoding='utf-8') as process:
        for line in process.stdout:
            m = RE.match(line.rstrip())
            if m:
                yield m['test'], m['conf']

res = dict()
for log in glob.glob('runs/*.log'):
    meta_path = log.split('.', 1)[0] + '.json'
    with open(meta_path, 'r') as f:
        run = json.load(f)
    branch = run['head_branch']
    timestamp = datetime.fromisoformat(run['created_at'].rstrip('Z'))

    if branch != 'master' and not re.match('\d+\.\d+', branch):
        continue

    for test, conf in fails(log):
        key = (test, conf)
        if key not in res or res[key][0] < timestamp:
            res[key] = (timestamp, branch, log)

res = sorted(res.items(), key=lambda kv: kv[1][0], reverse=True)
w = csv.writer(sys.stdout)
for key, value in res:
    test, conf = key
    timestamp, branch, log = value
    w.writerow([test, conf, timestamp, branch, log])
