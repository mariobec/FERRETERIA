"""Audita url_for en templates vs endpoints registrados en Flask (runtime)."""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def collect_template_endpoints() -> set[str]:
    eps: set[str] = set()
    pat = re.compile(r"url_for\(['\"]([\w.]+)['\"]")
    for dirpath, _, files in os.walk(os.path.join(ROOT, "templates")):
        for name in files:
            if not name.endswith((".html", ".jinja", ".jinja2")):
                continue
            path = os.path.join(dirpath, name)
            try:
                text = open(path, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            eps.update(pat.findall(text))
    return eps


def main() -> None:
    from app import app

    registered = {r.endpoint for r in app.url_map.iter_rules()}
    refs = collect_template_endpoints()
    skip = {"static"}
    missing = sorted(refs - registered - skip)
    print(f"Referencias templates: {len(refs)} | Registradas Flask: {len(registered)} | Faltantes reales: {len(missing)}")
    for name in missing:
        print(name)


if __name__ == "__main__":
    main()
