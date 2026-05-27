import json
import re
from pathlib import Path

h = Path("respaldos/debug_extractor_proveedor/pagina_buscar.html").read_text(
    encoding="utf-8", errors="replace"
)
print("len", len(h))
print("__NEXT_DATA__", "__NEXT_DATA__" in h)
m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
if m:
    d = json.loads(m.group(1))
    pp = (d.get("props") or {}).get("pageProps") or {}
    print("pageProps keys", list(pp.keys())[:25])

for pat in (
    r'href="([^"]*chilemat[^"]*)"',
    r'href="(/[^"]{5,80})"',
    r'"price"\s*:\s*"?([\d.]+)',
    r'data-sku="([^"]+)"',
    r'class="[^"]*product[^"]*"',
):
    ms = re.findall(pat, h, re.I)
    print(pat[:40], "count", len(ms), "sample", ms[:3])

# title / blocked?
if "captcha" in h.lower() or "access denied" in h.lower():
    print("BLOCKED?")
print("title snippet", re.search(r"<title>([^<]+)</title>", h, re.I))
