"""Probe: cuantas categorias/departamentos expone Chilemat (VTEX)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE = 'https://www.chilemat.com'
UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)

SKIP_SLUGS = frozenset({
    '', 'p', 'account', 'login', 'checkout', 'cart', 'busca', 'search',
    'institucional', 'contacto', 'sucursales', 'nosotros', 'terminos',
    'politicas', 'api', 'files', 'arquivos', 'sitemap', 'robots.txt',
})


def _fetch(url: str) -> tuple[int, str]:
    req = Request(url, headers={'User-Agent': UA, 'Accept-Language': 'es-CL'})
    with urlopen(req, timeout=60) as r:
        return r.status, r.read().decode('utf-8', errors='replace')


def _slug_from_path(path: str) -> str | None:
    path = (path or '').strip().rstrip('/')
    if not path or path == '/':
        return None
    parts = [p for p in path.split('/') if p]
    if not parts:
        return None
    if parts[0] in SKIP_SLUGS:
        return None
    # paginas producto: /slug/p
    if parts[-1] == 'p' or (len(parts) >= 2 and parts[-1] == 'p'):
        return None
    slug = parts[0].lower()
    if slug in SKIP_SLUGS:
        return None
    if '.' in slug or slug.startswith('_'):
        return None
    if re.match(r'^[a-z0-9]+(?:-[a-z0-9]+)+$', slug):
        return slug
    if re.match(r'^[a-z][a-z0-9-]{2,60}$', slug):
        return slug
    return None


def extract_slugs_from_html(html: str) -> set[str]:
    slugs: set[str] = set()
    for href in re.findall(r'href="([^"]+)"', html, re.I):
        href = href.split('#')[0].split('?')[0]
        if href.startswith('/'):
            s = _slug_from_path(href)
        elif 'chilemat.com' in href.lower():
            s = _slug_from_path(urlparse(href).path)
        else:
            continue
        if s:
            slugs.add(s)
    return slugs


def extract_vtex_category_tree(html: str) -> list[dict]:
    """Busca arbol de categorias en JSON embebido VTEX."""
    found: list[dict] = []

    def walk(obj, depth=0):
        if depth > 15:
            return
        if isinstance(obj, dict):
            if 'slug' in obj and ('id' in obj or 'categoryId' in obj or 'name' in obj):
                slug = str(obj.get('slug') or '').strip()
                if slug and slug not in SKIP_SLUGS:
                    found.append({
                        'id': obj.get('id') or obj.get('categoryId'),
                        'slug': slug,
                        'name': obj.get('name') or obj.get('Title') or '',
                    })
            for v in obj.values():
                walk(v, depth + 1)
        elif isinstance(obj, list):
            for v in obj[:500]:
                walk(v, depth + 1)

    for m in re.finditer(
        r'<script[^>]*type="application/json"[^>]*>(.*?)</script>',
        html,
        re.I | re.S,
    ):
        raw = m.group(1).strip()
        if len(raw) < 50 or 'category' not in raw.lower():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        walk(data)
    return found


def try_vtex_api() -> list[dict]:
    """API publica VTEX catalog (si esta habilitada)."""
    urls = [
        f'{BASE}/api/catalog_system/pub/category/tree/1',
        f'{BASE}/api/catalog_system/pub/category/tree/2',
        f'{BASE}/api/catalog_system/pub/category/tree/3',
    ]
    out: list[dict] = []

    def flatten(nodes, depth=0):
        if depth > 8:
            return
        for n in nodes or []:
            if not isinstance(n, dict):
                continue
            slug = str(n.get('url') or n.get('slug') or '').strip().strip('/')
            if slug and '/' in slug:
                slug = slug.split('/')[-1]
            out.append({
                'id': n.get('id'),
                'slug': slug,
                'name': n.get('name') or '',
                'depth': depth,
            })
            children = n.get('children') or []
            flatten(children, depth + 1)

    for url in urls:
        try:
            status, body = _fetch(url)
            if status != 200:
                continue
            data = json.loads(body)
            if isinstance(data, list) and data:
                flatten(data)
                return out
        except Exception as ex:
            print('API', url, '->', ex)
    return out


def main() -> int:
    print('=== Chilemat probe categorias ===\n')

    api_cats = try_vtex_api()
    if api_cats:
        slugs_api = {c['slug'] for c in api_cats if c.get('slug')}
        print(f'API VTEX category/tree: {len(api_cats)} nodos, {len(slugs_api)} slugs unicos')
        by_depth: dict[int, int] = {}
        for c in api_cats:
            d = int(c.get('depth') or 0)
            by_depth[d] = by_depth.get(d, 0) + 1
        print('Por nivel:', dict(sorted(by_depth.items())))
        leaves = [c for c in api_cats if c.get('slug')]
        print('Muestra (15):')
        for c in leaves[:15]:
            print(f"  [{c.get('id')}] {c.get('slug')} — {c.get('name')}")
    else:
        print('API VTEX category/tree: no disponible o vacia')

    print()
    try:
        status, home = _fetch(BASE + '/')
        print(f'Home HTTP {status}, len={len(home)}')
    except Exception as ex:
        print('Home ERROR:', ex)
        return 1

    slugs_html = extract_slugs_from_html(home)
    print(f'Slugs desde enlaces home: {len(slugs_html)}')
    vtex_embed = extract_vtex_category_tree(home)
    slugs_embed = {c['slug'] for c in vtex_embed if c.get('slug')}
    print(f'Nodos categoria en JSON embebido (home): {len(vtex_embed)} ({len(slugs_embed)} slugs)')

    all_slugs = slugs_html | slugs_embed
    if api_cats:
        all_slugs |= {c['slug'] for c in api_cats if c.get('slug')}

    print(f'\nTOTAL slugs candidatos (union): {len(all_slugs)}')
    print('\nListado ordenado (primeros 40):')
    for s in sorted(all_slugs)[:40]:
        print(f'  https://www.chilemat.com/{s}')

    # Probar una categoria conocida
    test_url = f'{BASE}/bano-y-cocina'
    print(f'\n=== Test listado: {test_url}')
    try:
        from scripts._chilemat_listado import parse_chilemat_listado

        st, html_cat = _fetch(test_url)
        prods = parse_chilemat_listado(html_cat)
        print(f'HTTP {st}, productos parseados (HTTP simple): {len(prods)}')
        if len(prods) < 5:
            print('(pocos con requests; Playwright suele traer mas en extraer_chilemat.py)')
    except Exception as ex:
        print('Test listado:', ex)

    out_path = ROOT / 'respaldos' / 'chilemat_categorias_probe.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'total_slugs': len(all_slugs),
        'api_nodes': len(api_cats),
        'slugs': sorted(all_slugs),
        'api_tree': api_cats[:500],
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\nGuardado: {out_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
