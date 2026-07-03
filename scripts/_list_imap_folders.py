#!/usr/bin/env python3
import imaplib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
p = ROOT / '.env.local'
if p.is_file():
    for raw in p.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, _, v = line.partition('=')
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        os.environ.setdefault(k.strip(), v)

c = imaplib.IMAP4_SSL(os.getenv('IMAP_HOST', 'imap.gmail.com'), int(os.getenv('IMAP_PORT', '993')))
c.login(os.environ['IMAP_USER'], os.environ['IMAP_PASSWORD'])
typ, folders = c.list()
print('=== Carpetas IMAP ===')
for f in folders or []:
    print(f.decode('utf-8', errors='replace'))
c.logout()
