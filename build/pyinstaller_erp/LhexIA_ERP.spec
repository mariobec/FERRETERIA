# -*- mode: python ; coding: utf-8 -*-
# Generado por scripts/build_pyinstaller_erp.py — no editar a mano

block_cipher = None

a = Analysis(
    ['C:/ERP FERRETERIA/PROYECTO FERRETERIA/sistema_ventas_limpio/scripts/erp_launcher.py'],
    pathex=['C:/ERP FERRETERIA/PROYECTO FERRETERIA/sistema_ventas_limpio'],
    binaries=[],
    datas=[
        ('C:\\ERP FERRETERIA\\PROYECTO FERRETERIA\\sistema_ventas_limpio\\templates', 'templates'),
        ('C:\\ERP FERRETERIA\\PROYECTO FERRETERIA\\sistema_ventas_limpio\\static', 'static'),
        ('C:\\ERP FERRETERIA\\PROYECTO FERRETERIA\\sistema_ventas_limpio\\config', 'config'),
        ('C:\\ERP FERRETERIA\\PROYECTO FERRETERIA\\sistema_ventas_limpio\\data\\empresa_config.json', 'data'),
        ('C:\\ERP FERRETERIA\\PROYECTO FERRETERIA\\sistema_ventas_limpio\\data\\proveedores_config.json', 'data'),
        ('C:\\ERP FERRETERIA\\PROYECTO FERRETERIA\\sistema_ventas_limpio\\data\\cross_sell_associations.json', 'data'),
        ('C:\\ERP FERRETERIA\\PROYECTO FERRETERIA\\sistema_ventas_limpio\\data\\pintura_cartilla_sd.json', 'data'),
        ('C:\\ERP FERRETERIA\\PROYECTO FERRETERIA\\sistema_ventas_limpio\\data\\zebra_etiqueta_config.json', 'data'),
        ('C:\\ERP FERRETERIA\\PROYECTO FERRETERIA\\sistema_ventas_limpio\\INSTALACION\\paquete\\04_SCRIPTS_OPERACION\\crear_usuario_test_piso.py', 'scripts'),
        ('C:\\ERP FERRETERIA\\PROYECTO FERRETERIA\\sistema_ventas_limpio\\scripts\\__init__.py', 'scripts')
    ],
    hiddenimports=[
        'PIL',
        'app',
        'cryptography',
        'email.mime.multipart',
        'email.mime.text',
        'fitz',
        'flask',
        'flask_login',
        'flask_sqlalchemy',
        'init_db',
        'jinja2.ext',
        'lxml',
        'lxml.etree',
        'openpyxl',
        'pandas',
        'pg8000',
        'pkg_resources.extern',
        'psycopg2',
        'qrcode',
        'schema_sync',
        'signxml',
        'sqlalchemy',
        'sqlalchemy.dialects.postgresql',
        'zeep'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tests', 'pytest', 'matplotlib', 'tkinter', 'IPython', 'notebook'],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LhexIA_ERP',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='LhexIA_ERP',
)
