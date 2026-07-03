# Manual — Enrolador Bodega (tablet + pistola)

**Versión:** 2026-06-04 · **Módulo:** Inventario / enrolamiento  
**Audiencia:** Operador bodega · **Hardware:** tablet Android + pistola BCST-560B (Bluetooth)

---

## URLs en red local (Santo Domingo)

Con el PC servidor en WiFi `192.168.7.x` (ejemplo IP **192.168.7.10**):

| Uso | URL |
|-----|-----|
| **Instalador (QR desde PC)** | `http://192.168.7.10:5000/bodega/enrolador` |
| **Login tablet (primera vez)** | `http://192.168.7.10:5000/login` |
| **Escáner enrolador** | `http://192.168.7.10:5000/inventario/enrolamiento/tablet` |

Menú ERP: **Inventario y compras → Enrolador bodega (tablet)**.

---

## Instalación en 4 pasos

### 1. PC servidor
- Ejecutar `iniciar_servidor.bat` (ERP activo en puerto 5000).
- Anotar IPv4 WiFi: `ipconfig` → **192.168.7.10** (puede variar).

### 2. Tablet — red
- Conectar tablet a la **misma WiFi** que el PC (no datos móviles).

### 3. Tablet — acceso directo
1. Chrome → abrir URL de login → entrar con usuario **Enrolamiento inventario**.
2. Ir al escáner tablet (URL de arriba) o escanear QR desde el PC en `/bodega/enrolador`.
3. Tocar **Agregar a inicio** (banner amarillo) o menú ⋮ → **Agregar a pantalla de inicio**.
4. Icono sugerido: **Enrolador Bodega**.

### 4. Pistola BCST-560B
1. Ajustes Android → **Bluetooth** → emparejar la pistola.
2. Abrir app **Enrolador Bodega** (acceso directo).
3. Elegir **Almacén** → **Nueva sesión**.
4. Pistolar código; confirmar con **Sumar** si el producto ya existe.

---

## Variable opcional (IP fija)

Si el QR muestra `127.0.0.1`, agregar en `.env.local`:

```env
BODEGA_ENROLADOR_LAN_URL=http://192.168.7.10:5000
```

Reiniciar Flask.

---

## Permisos

Rol con permiso **Enrolamiento inventario** o **Admin inventario** (Mantenedores → Roles).

---

## Problemas frecuentes

| Síntoma | Solución |
|---------|----------|
| Tablet no abre la URL | Misma WiFi; firewall Windows permite puerto 5000 |
| QR lleva a 127.0.0.1 | Fijar `BODEGA_ENROLADOR_LAN_URL` |
| Pistola no escribe | Re-emparejar Bluetooth; tocar zona de escaneo antes de pistolar |
| No ve menú | Admin debe asignar permiso enrolamiento |

---

*Complementa `MANUAL_ENROLAMIENTO_INVENTARIO_OPERADOR.md` (casos A/B/C y recepciones).*
