"""Paridad desglosar_iva_clp (Python) vs iva-chile.js (Node)."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from core.domain.shared.iva_chile import desglosar_iva_clp, iva_desde_neto_clp, subtotal_linea_bruto_clp

ROOT = Path(__file__).resolve().parents[1]
JS_SCRIPT = ROOT / 'scripts' / 'iva_chile_parity_check.js'

# Vectores compartidos Python ↔ JS (documentados en OFFLINE_API / ADR)
PARITY_VECTORS = [
    (1190, 1000, 190, 1190),
    (50000, 42017, 7983, 50000),
    (0, 0, 0, 0),
    (1, 1, 0, 1),
    (999, 839, 159, 998),
    (100000, 84034, 15966, 100000),
    (2380, 2000, 380, 2380),
]


@pytest.mark.parametrize('bruto, neto, iva, total', PARITY_VECTORS)
def test_python_vectors_documented_for_js(bruto, neto, iva, total):
    n, i, t = desglosar_iva_clp(bruto)
    assert (n, i, t) == (neto, iva, total)
    assert i == iva_desde_neto_clp(n)


@pytest.mark.offline_phase0
def test_subtotal_linea_parity_python():
    assert subtotal_linea_bruto_clp(3, 1990, 10) == 5373


@pytest.mark.offline_phase0
def test_node_parity_script_if_available():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js no instalado — paridad JS omitida en CI')
    if not JS_SCRIPT.is_file():
        pytest.skip('scripts/iva_chile_parity_check.js no encontrado')
    proc = subprocess.run(
        [node, str(JS_SCRIPT)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, (proc.stdout or '') + (proc.stderr or '')


@pytest.mark.offline_phase0
def test_node_desglosar_matches_python_per_vector():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js no instalado')
    inline = """
    const iva = require('./static/js/offline/iva-chile.js');
    const vectors = %s;
    const out = vectors.map(([b]) => {
      const r = iva.desglosarIvaClp(b);
      return [r.neto, r.iva, r.total];
    });
    console.log(JSON.stringify(out));
    """ % json.dumps([[b] for b, _, _, _ in PARITY_VECTORS])
    proc = subprocess.run(
        [node, '-e', inline],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    js_rows = json.loads(proc.stdout.strip())
    for (bruto, exp_n, exp_i, exp_t), (jn, ji, jt) in zip(PARITY_VECTORS, js_rows):
        pn, pi, pt = desglosar_iva_clp(bruto)
        assert (jn, ji, jt) == (pn, pi, pt) == (exp_n, exp_i, exp_t), 'bruto=%s' % bruto
