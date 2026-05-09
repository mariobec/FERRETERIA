import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app, db, Proveedor, guardar_canal_compra_proveedor


PROVEEDORES_CHILEMAT = [
    {
        "nombre": "Chilemat Central de Compras",
        "contacto": "Mesa Comercial Chilemat",
        "telefono": "+56 2 2835 1100",
        "email": "compras@chilemat.cl",
        "canal_compra": "chilemat_portal",
    },
    {
        "nombre": "Aceros Chilemat",
        "contacto": "Ejecutivo Acero",
        "telefono": "+56 9 6123 4101",
        "email": "aceros@chilemat.cl",
        "canal_compra": "email",
    },
    {
        "nombre": "Cementos y Morteros Chilemat",
        "contacto": "Canal Constructor",
        "telefono": "+56 9 6123 4102",
        "email": "cementos@chilemat.cl",
        "canal_compra": "chilemat_portal",
    },
    {
        "nombre": "Electricidad y Iluminacion Chilemat",
        "contacto": "Asesor Tecnico",
        "telefono": "+56 9 6123 4103",
        "email": "electricidad@chilemat.cl",
        "canal_compra": "whatsapp",
    },
    {
        "nombre": "Ferreteria Santo Domingo - Convenios",
        "contacto": "Backoffice Convenios",
        "telefono": "+56 9 6123 4104",
        "email": "convenios@chilemat.cl",
        "canal_compra": "manual",
    },
]


def upsert_proveedor(item):
    nombre = (item.get("nombre") or "").strip()
    if not nombre:
        return None, False
    p = Proveedor.query.filter_by(nombre=nombre).first()
    creado = False
    if not p:
        p = Proveedor(nombre=nombre)
        db.session.add(p)
        db.session.flush()
        creado = True
    p.contacto = (item.get("contacto") or "").strip() or None
    p.telefono = (item.get("telefono") or "").strip() or None
    p.email = (item.get("email") or "").strip() or None
    db.session.flush()
    guardar_canal_compra_proveedor(p.id, item.get("canal_compra") or "manual")
    return p, creado


def main():
    with app.app_context():
        creados = 0
        actualizados = 0
        for item in PROVEEDORES_CHILEMAT:
            _, creado = upsert_proveedor(item)
            if creado:
                creados += 1
            else:
                actualizados += 1
        db.session.commit()
        print(f"Seed proveedores Chilemat completado: creados={creados}, actualizados={actualizados}")


if __name__ == "__main__":
    main()

