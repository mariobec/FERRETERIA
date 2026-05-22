#!/usr/bin/env python3
"""Semilla catálogo SD PRUEBA PRODUCTO para todas las casuísticas QA (alias del seed CAS)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.seed_ventas_casuisticas_qa import main

if __name__ == '__main__':
    # Por defecto exporta CSV + limpia + siembra
    if '--export-csv' not in sys.argv and '--help' not in sys.argv and '-h' not in sys.argv:
        sys.argv.append('--export-csv')
    main()
