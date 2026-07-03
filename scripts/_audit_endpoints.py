"""Audita endpoints referenciados en templates/nav vs rutas registradas."""
from __future__ import annotations

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def collect_template_endpoints() -> set[str]:
    eps: set[str] = set()
    pat1 = re.compile(r"url_for\(['\"]([\w.]+)['\"]")
    pat2 = re.compile(r"endpoint\s*=\s*['\"]([\w.]+)['\"]")
    for dirpath, _, files in os.walk(os.path.join(ROOT, "templates")):
        for name in files:
            if not name.endswith((".html", ".jinja", ".jinja2")):
                continue
            path = os.path.join(dirpath, name)
            try:
                text = open(path, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for m in pat1.finditer(text):
                eps.add(m.group(1))
            for m in pat2.finditer(text):
                eps.add(m.group(1))
    return eps


def collect_nav_endpoints() -> set[str]:
    app_path = os.path.join(ROOT, "app.py")
    text = open(app_path, encoding="utf-8", errors="ignore").read()
    return set(re.findall(r"'endpoint':\s*'([\w.]+)'", text))


def collect_registered() -> set[str]:
    registered: set[str] = set()
    files = [os.path.join(ROOT, "app.py")]
    bp_dir = os.path.join(ROOT, "blueprints")
    if os.path.isdir(bp_dir):
        files.extend(
            os.path.join(bp_dir, f)
            for f in os.listdir(bp_dir)
            if f.endswith(".py")
        )
    route_def = re.compile(
        r"@(?:app|\w+)\.route\([^\)]*\)\s*(?:\n@[^\n]+\s*)*def\s+([\w_]+)\s*\(",
        re.MULTILINE,
    )
    add_rule = re.compile(r"add_url_rule\([^,]+,\s*'([\w_]+)'")
    for path in files:
        try:
            text = open(path, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        registered.update(route_def.findall(text))
        registered.update(add_rule.findall(text))
    return registered


def main() -> None:
    refs = collect_template_endpoints() | collect_nav_endpoints()
    registered = collect_registered()
    missing = sorted(refs - registered)
    print(f"Referencias: {len(refs)} | Registradas: {len(registered)} | Faltantes: {len(missing)}")
    for name in missing:
        print(name)


if __name__ == "__main__":
    main()
