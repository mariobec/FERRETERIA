# -*- coding: utf-8 -*-
"""Genera JSON del logo 3D desde docs/lhexia_logo_coordenadas.csv"""
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
CSV_PATH = os.path.join(ROOT, 'docs', 'lhexia_logo_coordenadas.csv')
OUT_PATH = os.path.join(
    ROOT, 'frontend', 'lhexia-logo-3d', 'src', 'data', 'lhexiaLogoFromCsv.json',
)

SCALE = 5.2
NODE_EVERY = 6


def to_three(norm_x: float, norm_y: float, z: float = 0.0) -> list[float]:
    return [
        round((norm_x - 0.5) * SCALE, 5),
        round((0.5 - norm_y) * SCALE, 5),
        round(z, 5),
    ]


def main() -> int:
    by_element: dict[str, list[dict]] = defaultdict(list)
    with open(CSV_PATH, newline='', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            el = row['Elemento_ID'].strip()
            by_element[el].append({
                'punto_id': int(row['Punto_ID']),
                'nx': float(row['Normalizado_X']),
                'ny': float(row['Normalizado_Y']),
            })

    paths: dict[str, list[list[float]]] = {}
    nodes: list[dict] = []
    seen: set[tuple[float, float, float]] = set()

    def add_node(nid: str, pos: list[float], scale: float = 0.65) -> None:
        key = (pos[0], pos[1], pos[2])
        if key in seen:
            return
        seen.add(key)
        nodes.append({'id': nid, 'position': pos, 'scale': scale})

    for el in sorted(by_element.keys(), key=int):
        pts = sorted(by_element[el], key=lambda p: p['punto_id'])
        path = [to_three(p['nx'], p['ny']) for p in pts]
        if len(path) < 2:
            continue
        paths[el] = path
        add_node(f'n-{el}-start', path[0], 0.75)
        add_node(f'n-{el}-end', path[-1], 0.75)
        step = max(1, len(path) // NODE_EVERY)
        for i in range(0, len(path), step):
            add_node(f'n-{el}-p{i}', path[i], 0.55)

    payload = {
        'meta': {
            'source': 'docs/lhexia_logo_coordenadas.csv',
            'scale': SCALE,
            'elements': len(paths),
            'points': sum(len(p) for p in paths.values()),
            'nodes': len(nodes),
        },
        'paths': paths,
        'nodes': nodes,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(payload, f, separators=(',', ':'))

    print('OK', OUT_PATH)
    print('  elementos', len(paths), 'nodos', len(nodes), 'puntos', payload['meta']['points'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
