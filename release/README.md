LhexIA — instalador tienda (publicado en git)
============================================

Ruta fija en el repo:
  release/instalador_tienda/

En máquina tienda (QAS)
-----------------------
1. Clonar o actualizar repo:
   cd C:\LhexIA\ERP\sistema_ventas_limpio
   git pull origin main

2. Ejecutar instalador:
   instalar_tienda.bat

   (equivale a release\instalador_tienda\03_INSTRUCCIONES\instalar_tienda_completo.bat)

3. Editar .env.local: DATABASE_URL localhost + PUBLIC_SITE_URL LAN

4. Arrancar: arrancar_erp.bat

Contenido del pack
------------------
  01_BASE_DATOS/   dump Postgres + erp_stats.txt
  02_CONFIG/       .env.local.template
  03_INSTRUCCIONES/instalar_tienda_completo.bat
  04_CODIGO/patch/ WIP sin commit (pinturas, etc.)
  MANIFEST.txt     commit y dump incluidos

Publicar nueva versión (DEV)
----------------------------
  .\scripts\crear_instalador_tienda_completo.ps1 -PublicarEnRepo
  git add release/instalador_tienda instalar_tienda.bat .gitignore scripts/
  git commit -m "release: instalador tienda"
  git push origin main
