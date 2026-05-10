"""Transacciones y utilidades de venta (Fase 2)."""
from contextlib import contextmanager


@contextmanager
def transaccion_critica():
    """Savepoint para agrupar mutaciones relacionadas (rollback parcial si falla)."""
    import app as app_module

    with app_module.db.session.begin_nested():
        yield
