# -*- coding: utf-8 -*-
"""Convierte plantillas HTML guardadas en cp1252 a UTF-8 (evita 500 en /index)."""
from __future__ import annotations

import os
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
TEMPLATES = os.path.join(ROOT, 'templates')


def main() -> int:
    fixed = 0
    for dirpath, _, files in os.walk(TEMPLATES):
        for fn in files:
            if not fn.endswith('.html'):
                continue
            path = os.path.join(dirpath, fn)
            raw = open(path, 'rb').read()
            try:
                raw.decode('utf-8')
                continue
            except UnicodeDecodeError:
                text = raw.decode('cp1252')
                with open(path, 'w', encoding='utf-8', newline='\n') as f:
                    f.write(text)
                fixed += 1
                print('fixed', path)
    print('total fixed', fixed)
    return 0 if fixed >= 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
