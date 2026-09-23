"""Exporta filas a CSV (Excel en español) o JSON."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from intelligence.registros_chile.parser import COLUMNAS, Registro


def escribir(registros: list[Registro], ruta: Path, formato: str | None = None) -> Path:
    destino = Path(ruta)
    elegido = (formato or _formato_de(destino)).lower()
    destino.parent.mkdir(parents=True, exist_ok=True)
    if elegido == "json":
        payload = [registro.fila() for registro in registros]
        destino.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return destino
    if elegido == "csv":
        with destino.open("w", encoding="utf-8-sig", newline="") as archivo:
            writer = csv.DictWriter(archivo, fieldnames=COLUMNAS)
            writer.writeheader()
            for registro in registros:
                writer.writerow(registro.fila())
        return destino
    raise ValueError("El formato debe ser csv o json.")


def _formato_de(ruta: Path) -> str:
    if ruta.suffix.lower() == ".json":
        return "json"
    return "csv"
