"""Secuencias PostgreSQL — reparación rol_permisos."""
from services.db_sequence_service import es_violacion_pk_rol_permisos, reparar_secuencia_id


def test_reparar_secuencia_noop_si_no_postgres(app_ctx, monkeypatch):
    from app import db

    class FakeDialect:
        name = 'sqlite'

    class FakeBind:
        dialect = FakeDialect()

    monkeypatch.setattr(db.session, 'get_bind', lambda: FakeBind())
    assert reparar_secuencia_id(db.session, 'rol_permisos') is False


def test_reparar_secuencias_tablas_cuenta(monkeypatch, app_ctx):
    from app import db

    calls = []

    def _fake(session, tabla):
        calls.append(tabla)
        return tabla == 'rol_permisos'

    monkeypatch.setattr(
        'services.db_sequence_service.reparar_secuencia_id',
        _fake,
    )
    from services.db_sequence_service import reparar_secuencias_tablas

    n = reparar_secuencias_tablas(db.session, ('rol_permisos', 'permisos'))
    assert n == 1
    assert calls == ['rol_permisos', 'permisos']


def test_detecta_violacion_rol_permisos():
    class FakeOrig:
        def __str__(self):
            return 'duplicate key rol_permisos_pkey'

    class FakeEx(Exception):
        orig = FakeOrig()

    assert es_violacion_pk_rol_permisos(FakeEx()) is True
