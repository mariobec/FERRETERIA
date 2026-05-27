"""Aplica _NAV_MAP y _MODULOS_HUB fase 2 en app.py."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
app_path = ROOT / 'app.py'
snippet_path = ROOT / 'scripts' / '_nav_hub_fase2_snippet.py'

text = app_path.read_text(encoding='utf-8')
snippet = snippet_path.read_text(encoding='utf-8')

nav_start = text.index('_NAV_MAP = [')
# Cortar solo hasta _MODULOS_HUB (no borrar _construir_nav_usuario)
hub_start_marker = '\n_MODULOS_HUB = ['
hub_end_marker = '\n]\n\n\ndef _hub_usuario_tiene_permiso'
hub_start = text.index(hub_start_marker, nav_start)
hub_end = text.index(hub_end_marker, hub_start)

snippet_nav_start = snippet.index('_NAV_MAP = [')
snippet_nav_end = snippet.index('\n_MODULOS_HUB = [')
snippet_hub_start = snippet_nav_end
snippet_hub_end = snippet.rindex(']') + 1

new_nav = snippet[snippet_nav_start:snippet_nav_end].rstrip() + '\n\n'
new_hub = snippet[snippet_hub_start:snippet_hub_end].rstrip() + '\n\n'

# Preservar _construir_nav_usuario entre _NAV_MAP y _MODULOS_HUB
construir_marker = '\ndef _construir_nav_usuario():'
if construir_marker in text[nav_start:hub_start]:
    mid = text[nav_start:hub_start]
    nav_only_end = nav_start + mid.index(construir_marker)
    preserved_fn = text[nav_start + mid.index(construir_marker):hub_start]
    text = text[:nav_start] + new_nav + preserved_fn + new_hub + text[hub_end + len('\n]\n\n'):]
else:
    text = text[:nav_start] + new_nav + new_hub + text[hub_end + len('\n]\n\n'):]

app_path.write_text(text, encoding='utf-8')
print('OK: NAV_MAP + MODULOS_HUB replaced')
