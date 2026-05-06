"""
Crea todas las tablas del ERP en la base MySQL indicada en SQLALCHEMY_DATABASE_URI.
Uso: configurar variables de entorno (ver .env.demo de ejemplo) y ejecutar una vez
tras haber creado la base de datos vacía.
"""
from app import app, db

with app.app_context():
    db.create_all()
print("Tablas creadas correctamente.")
