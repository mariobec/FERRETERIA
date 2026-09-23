#!/usr/bin/env python3
"""Lanzador del extractor. No importa nada del ERP."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from intelligence.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
