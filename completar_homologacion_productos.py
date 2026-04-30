import re
import unicodedata
import pandas as pd


def slug(value: str) -> str:
    value = str(value or "").strip().upper()
    value = "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))
    value = re.sub(r"[^A-Z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value[:28] or "ITEM"


ok = pd.read_csv("productos_homologados.csv", dtype=str).fillna("")
err = pd.read_csv("productos_homologacion_errores.csv", dtype=str).fillna("")

# Mantener solo filas rescatables: nombre presente (descarta filas totalmente vacias).
resc = err[err["nombre"].str.strip() != ""].copy()

# Generar codigo interno para filas sin codigo.
generated = []
for idx, row in resc.iterrows():
    nombre = row.get("nombre", "").strip()
    codigo = row.get("codigo_barra", "").strip()
    if not codigo:
        base = f"AUTO-{slug(nombre)}"
        codigo = base
        n = 2
        while (ok["codigo_barra"] == codigo).any() or (resc["codigo_barra"] == codigo).any() or codigo in generated:
            codigo = f"{base}-{n}"
            n += 1
        resc.at[idx, "codigo_barra"] = codigo
        generated.append(codigo)

full = pd.concat([ok, resc], ignore_index=True)
full.to_csv("productos_homologados_full.csv", index=False, encoding="utf-8")

print("Archivo final: productos_homologados_full.csv")
print(f"Base OK: {len(ok)}")
print(f"Rescatados: {len(resc)}")
print(f"Codigos auto-generados: {len(generated)}")
print(f"Total final: {len(full)}")
