import pandas as pd


RULES = [
    ("Ferreteria", "Fijaciones", ["PERNO", "TORNILLO", "TUERCA", "ARANDELA", "REMACHE", "ANCLAJE"]),
    ("Construccion", "Materiales", ["CEMENTO", "MORTERO", "HORMIGON", "YESO", "CAL", "LADRILLO"]),
    ("Aceros y Techumbre", "Planchas", ["PL ZINC", "PLANCHA", "ZINC", "PERFIL", "VIGA", "ACERO"]),
    ("Electricidad", "Cables y Accesorios", ["CABLE", "ALAMBRE", "ENCHUFE", "INTERRUPTOR", "TOMA", "THHN"]),
    ("Gasfiteria", "Tuberias y Conexiones", ["PVC", "TUBO", "CODO", "TEE", "VALVULA", "LLAVE", "SIFON"]),
    ("Pinturas", "Aplicacion", ["PINTURA", "ESMALTE", "BROCHA", "RODILLO", "DILUYENTE"]),
    ("Herramientas", "Discos y Corte", ["DISCO", "SIERRA", "TALADRO", "ESMERIL", "MARTILLO", "ALICATE"]),
    ("Hogar", "Banio y Decoracion", ["ESPEJO", "BISAGRA", "CERRADURA", "MANILLA", "CANDADO"]),
]


def classify(name: str):
    txt = (name or "").upper()
    for cat, sub, keys in RULES:
        if any(k in txt for k in keys):
            return cat, sub
    return "General", "Otros"


def clip(text, n):
    return str(text or "").strip()[:n]


df = pd.read_csv("productos_homologados_full.csv", dtype=str).fillna("")

cats = []
subs = []
for _, row in df.iterrows():
    cat = row.get("categoria", "").strip()
    sub = row.get("subcategoria", "").strip()
    if not cat or not sub:
        c, s = classify(row.get("nombre", ""))
        cat = cat or c
        sub = sub or s
    cats.append(clip(cat, 50))
    subs.append(clip(sub, 50))

df["nombre"] = df["nombre"].apply(lambda x: clip(x, 100))
df["codigo_barra"] = df["codigo_barra"].apply(lambda x: clip(x, 50))
df["unidad"] = df.get("unidad", "").apply(lambda x: clip(x, 20)) if "unidad" in df.columns else ""
df["unidad_compra"] = df["unidad_compra"].apply(lambda x: clip(x or "Unidad", 20))
df["unidad_venta"] = df["unidad_venta"].apply(lambda x: clip(x or "Unidad", 20))
df["categoria"] = cats
df["subcategoria"] = subs
df["ubicacion_pasillo"] = df["ubicacion_pasillo"].apply(lambda x: clip(x, 12))
df["ubicacion_estante"] = df["ubicacion_estante"].apply(lambda x: clip(x, 12))
df["ubicacion_nivel"] = df["ubicacion_nivel"].apply(lambda x: clip(x, 12))

df.to_csv("productos_importacion_final.csv", index=False, encoding="utf-8")
print("Archivo generado: productos_importacion_final.csv")
print("Total filas:", len(df))
print("Categorias top:")
print(df["categoria"].value_counts().head(10).to_string())
