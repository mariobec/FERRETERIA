#!/usr/bin/env python3
"""
LhexIA ERP — Centro de Control (GUI).
Operación diaria e instalación desde carpeta INSTALACION portable.
"""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import threading
import tkinter as tk
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

APP_TITLE = "LhexIA Control"
APP_VERSION = "1.2.0"
CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def find_instalacion_root() -> Path:
    if _is_frozen():
        exe_dir = Path(sys.executable).resolve().parent
        if (exe_dir / "paquete").is_dir() or (exe_dir / "02_Iniciar_ERP.bat").is_file():
            return exe_dir
        nested = exe_dir / "INSTALACION"
        if nested.is_dir():
            return nested
        return exe_dir
    return Path(__file__).resolve().parent.parent / "INSTALACION"


def find_erp_root(instalacion: Path) -> Path:
    erp = instalacion / "erp"
    if (erp / "LhexIA_ERP.exe").is_file() or (erp / "app.py").is_file():
        return erp
    legacy = Path(r"C:\LhexIA\ERP")
    if (legacy / "LhexIA_ERP.exe").is_file() or (legacy / "app.py").is_file():
        return legacy
    return erp


INSTALACION_ROOT = find_instalacion_root()
ERP_ROOT = find_erp_root(INSTALACION_ROOT)
PAQUETE_DIR = INSTALACION_ROOT / "paquete"
SERVICIOS_DIR = INSTALACION_ROOT / "servicios"


def _resolve_bat(name: str) -> Path | None:
    for folder in (INSTALACION_ROOT, SERVICIOS_DIR, ERP_ROOT):
        p = folder / name
        if p.is_file():
            return p
    return None


def _run_bat(name: str, *, admin: bool = False, silent: bool = False) -> None:
    bat = _resolve_bat(name)
    if bat is None:
        raise FileNotFoundError(f"No existe: {name}\nBusque en {INSTALACION_ROOT}")
    args = [str(bat)]
    if silent:
        args.append("silent")
    cwd = str(bat.parent)
    if admin:
        params = " ".join(f'"{a}"' for a in args)
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "cmd.exe", f"/c {params}", cwd, 1
        )
        if rc <= 32:
            raise OSError(f"No se pudo ejecutar como administrador (código {rc})")
        return
    subprocess.Popen(
        ["cmd.exe", "/c", *args],
        cwd=cwd,
        creationflags=CREATE_NEW_CONSOLE,
    )


def _run_bat_instalador(name: str) -> None:
    candidates = [
        INSTALACION_ROOT / "00_Instalar_servidor_completo.bat",
        PAQUETE_DIR / name,
        INSTALACION_ROOT / name,
    ]
    for bat in candidates:
        if bat.is_file():
            subprocess.Popen(
                ["cmd.exe", "/c", str(bat)],
                cwd=str(bat.parent),
                creationflags=CREATE_NEW_CONSOLE,
            )
            return
    raise FileNotFoundError(
        "No se encontró el instalador en esta carpeta INSTALACION.\n\n"
        f"Esperado: paquete\\{name}\n"
        "Copie la carpeta INSTALACION completa (incluye erp\\ y paquete\\).\n"
        "En DEV ejecute COMPILAR_ERP_EXE.bat antes del USB."
    )


def _port_listening(port: int) -> bool:
    try:
        out = subprocess.check_output(
            ["netstat", "-ano"],
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
        )
    except Exception:
        return False
    needle = f":{port} "
    return any(needle in ln and "LISTENING" in ln for ln in out.splitlines())


def _wait_port(port: int, *, seconds: float = 20.0) -> bool:
    import time

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if _port_listening(port):
            return True
        time.sleep(0.6)
    return _port_listening(port)


def _start_postgres_admin_bat() -> str:
    bat = _resolve_bat("iniciar_postgresql.bat")
    if bat is None:
        return "No se encontro iniciar_postgresql.bat"
    params = f'/c "{bat}" silent'
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", params, str(bat.parent), 0)
    if rc <= 32:
        return f"No se pudo elevar admin para PostgreSQL (codigo {rc})"
    if _wait_port(5432, seconds=25):
        return "PostgreSQL iniciado (admin) — puerto 5432 OK"
    return "Se pidio admin para PostgreSQL; espere y pulse Actualizar estado"


def _start_postgres() -> str:
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "$msgs = @(); "
                "Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue | ForEach-Object { "
                "  if ($_.Status -ne 'Running') { "
                "    try { Start-Service $_.Name -ErrorAction Stop; $msgs += \"Iniciado: $($_.Name)\" } "
                "    catch { $msgs += \"Error $($_.Name): $($_.Exception.Message)\" } "
                "  } else { $msgs += \"Ya activo: $($_.Name)\" } "
                "}; "
                "if (-not $msgs) { 'No se encontro servicio postgresql*' } else { $msgs -join ' · ' }",
            ],
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        ).strip()
        msg = out or "PostgreSQL: sin respuesta"
        if _wait_port(5432, seconds=12):
            return msg + " · puerto 5432 OK"
        if "Error" in msg or "No se encontro" in msg:
            return msg + " · " + _start_postgres_admin_bat()
        return msg + " · puerto 5432 aun inactivo — ejecute Iniciar PostgreSQL como administrador"
    except Exception as exc:
        return f"Error al iniciar PostgreSQL: {exc}"


def _ollama_status() -> str:
    port_ok = _port_listening(11434)
    if port_ok:
        return "Ollama local: activo (puerto 11434)"
    env_url = (os.getenv("VITRINA_OLLAMA_BASE_URL") or "").strip()
    if env_url and "127.0.0.1" not in env_url and "localhost" not in env_url.lower():
        return f"Ollama remoto configurado: {env_url}"
    if (os.getenv("VITRINA_OLLAMA_ENABLED") or "").strip() in ("1", "true", "yes"):
        return "Ollama: configurado pero puerto 11434 inactivo"
    return "Ollama: no requerido / desactivado"


def _postgres_status() -> str:
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue | "
                "ForEach-Object { $_.Name + ': ' + $_.Status }",
            ],
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=12,
        ).strip()
        if out:
            return out.replace("\r\n", " · ")
    except Exception:
        pass
    if _port_listening(5432):
        return "Puerto 5432 activo (servicio no identificado)"
    return "No detectado"


def _healthz_ok() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:5000/healthz", timeout=4) as r:
            return r.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _lan_urls() -> list[str]:
    urls: list[str] = []
    cfg = ERP_ROOT / "data" / "empresa_config.json"
    if cfg.is_file():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            fixed = (data.get("url_red_erp") or "").strip()
            if fixed:
                urls.append(fixed.rstrip("/"))
        except Exception:
            pass
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-NetIPAddress -AddressFamily IPv4 | "
                "Where-Object { $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown' "
                "-and $_.IPAddress -notlike '169.254.*' } | "
                "Select-Object -ExpandProperty IPAddress -Unique",
            ],
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=12,
        )
        for ip in out.splitlines():
            ip = ip.strip()
            if ip:
                urls.append(f"http://{ip}:5000")
    except Exception:
        pass
    seen: set[str] = set()
    unique: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


def _kill_port_5000() -> str:
    try:
        out = subprocess.check_output(
            ["netstat", "-ano"],
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
        )
    except Exception as exc:
        return f"Error netstat: {exc}"
    pids: set[str] = set()
    for ln in out.splitlines():
        if ":5000 " in ln and "LISTENING" in ln:
            parts = ln.split()
            if parts:
                pids.add(parts[-1])
    if not pids:
        return "Nada escuchando en puerto 5000."
    msgs = []
    for pid in pids:
        if pid in ("0", "4"):
            continue
        r = subprocess.run(
            ["taskkill", "/PID", pid, "/F"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if r.returncode == 0:
            msgs.append(f"Proceso {pid} detenido.")
        else:
            msgs.append(f"No se pudo detener PID {pid}: {r.stderr.strip() or r.stdout.strip()}")
    return "\n".join(msgs) if msgs else "Sin procesos que detener."


def _erp_runtime_ok() -> bool:
    return (ERP_ROOT / "LhexIA_ERP.exe").is_file() or (ERP_ROOT / "app.py").is_file()


class CentroControlApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.minsize(720, 560)
        self.geometry("820x640")
        self._build_ui()
        self.after(400, self.refresh_status)

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 4}
        header = ttk.Frame(self)
        header.pack(fill="x", **pad)
        ttk.Label(header, text="LhexIA Control", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            header,
            text=f"Centro de Control v{APP_VERSION}  ·  INSTALACION: {INSTALACION_ROOT}",
            font=("Segoe UI", 9),
        ).pack(anchor="w")
        ttk.Label(header, text=f"ERP: {ERP_ROOT}", font=("Segoe UI", 9)).pack(anchor="w")

        status = ttk.LabelFrame(self, text="Estado", padding=8)
        status.pack(fill="x", **pad)
        self.lbl_pg = ttk.Label(status, text="PostgreSQL: …")
        self.lbl_pg.pack(anchor="w")
        self.lbl_erp = ttk.Label(status, text="Servidor ERP: …")
        self.lbl_erp.pack(anchor="w")
        self.lbl_ollama = ttk.Label(status, text="Ollama: …")
        self.lbl_ollama.pack(anchor="w")
        self.lbl_urls = ttk.Label(status, text="URLs tablet: …", wraplength=760)
        self.lbl_urls.pack(anchor="w", pady=(4, 0))
        ttk.Button(status, text="Actualizar estado", command=self.refresh_status).pack(
            anchor="e", pady=(6, 0)
        )

        svc = ttk.LabelFrame(self, text="Servicios (base de datos y servidores)", padding=8)
        svc.pack(fill="x", **pad)
        self._btn_row(
            svc,
            [
                ("Iniciar todo", self.start_all, "PostgreSQL + servidor ERP"),
                ("Iniciar PostgreSQL", self.start_postgres, "Servicio postgresql*"),
                ("Iniciar ERP", self.start_erp, "Flask en puerto 5000"),
                ("Detener ERP", self.stop_erp, "Libera el puerto 5000"),
            ],
        )

        ops = ttk.LabelFrame(self, text="Operacion diaria", padding=8)
        ops.pack(fill="x", **pad)
        self._btn_row(
            ops,
            [
                ("Abrir en PC", lambda: webbrowser.open("http://127.0.0.1:5000/login"), "Navegador local"),
                ("Abrir en tablet", self.open_tablet_url, "URL de red WiFi"),
            ],
        )

        red = ttk.LabelFrame(self, text="Red e intranet (tablets)", padding=8)
        red.pack(fill="x", **pad)
        self._btn_row(
            red,
            [
                ("Configurar intranet", lambda: self._safe_bat("03_Configurar_intranet.bat", admin=True), "Firewall + URL"),
                ("Ver URL red", lambda: self._safe_bat("04_URL_tablets.bat"), "Muestra IP LAN"),
                ("Verificar todo", lambda: self._safe_bat("05_Verificar_servicios.bat"), "Postgres + ERP"),
            ],
        )

        inst = ttk.LabelFrame(self, text="Instalacion (PC nuevo)", padding=8)
        inst.pack(fill="x", **pad)
        self._btn_row(
            inst,
            [
                ("Instalacion paso a paso", self.install_step_by_step, "Postgres, Python, BD, intranet"),
                ("Arranque automatico", lambda: self._safe_bat("07_Arranque_automatico.bat", admin=True), "Al encender el PC"),
                ("Crear usuario prueba", lambda: self._safe_bat("08_Crear_usuario_prueba.bat"), "Tablet / piso"),
            ],
        )

        log_frame = ttk.LabelFrame(self, text="Registro", padding=4)
        log_frame.pack(fill="both", expand=True, **pad)
        self.log = scrolledtext.ScrolledText(log_frame, height=8, font=("Consolas", 9))
        self.log.pack(fill="both", expand=True)
        self._log(f"Listo. INSTALACION: {INSTALACION_ROOT}")
        self._log(f"ERP: {ERP_ROOT}")

        if not _erp_runtime_ok():
            self._log("[AVISO] Falta erp\\LhexIA_ERP.exe — en DEV ejecute COMPILAR_ERP_EXE.bat")

    def _btn_row(self, parent: ttk.Frame, items: list[tuple[str, callable, str]]) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x")
        for i, (text, cmd, tip) in enumerate(items):
            b = ttk.Button(row, text=text, command=cmd)
            b.grid(row=0, column=i, padx=4, pady=2, sticky="ew")
            row.columnconfigure(i, weight=1)
            self._tooltip(b, tip)

    def _tooltip(self, widget: tk.Widget, text: str) -> None:
        tip = tk.Toplevel(widget)
        tip.withdraw()
        tip.overrideredirect(True)
        lbl = ttk.Label(tip, text=text, background="#ffffe0", relief="solid", borderwidth=1, padding=4)
        lbl.pack()

        def enter(_e: tk.Event) -> None:
            x = widget.winfo_rootx() + 10
            y = widget.winfo_rooty() + widget.winfo_height() + 4
            tip.geometry(f"+{x}+{y}")
            tip.deiconify()

        def leave(_e: tk.Event) -> None:
            tip.withdraw()

        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

    def _log(self, msg: str) -> None:
        self.log.insert("end", msg + "\n")
        self.log.see("end")

    def _safe_bat(self, name: str, *, admin: bool = False) -> None:
        try:
            _run_bat(name, admin=admin)
            self._log(f"[OK] Ejecutando: {name}")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            self._log(f"[ERROR] {name}: {exc}")

    def refresh_status(self) -> None:
        def work() -> None:
            pg = _postgres_status()
            ollama = _ollama_status()
            erp_port = _port_listening(5000)
            health = _healthz_ok() if erp_port else False
            urls = _lan_urls()

            def apply() -> None:
                self.lbl_pg.configure(text=f"PostgreSQL: {pg}")
                self.lbl_ollama.configure(text=ollama)
                if health:
                    erp_txt = "Servidor ERP: activo (healthz OK)"
                elif erp_port:
                    erp_txt = "Servidor ERP: puerto 5000 abierto (iniciando...)"
                else:
                    erp_txt = "Servidor ERP: detenido"
                self.lbl_erp.configure(text=erp_txt)
                if urls:
                    self.lbl_urls.configure(text="URLs tablet: " + "  ·  ".join(urls))
                else:
                    self.lbl_urls.configure(text="URLs tablet: (configure intranet o WiFi)")

            self.after(0, apply)

        threading.Thread(target=work, daemon=True).start()

    def start_postgres(self) -> None:
        def work() -> None:
            msg = _start_postgres()

            def apply() -> None:
                self._log(msg)
                self.refresh_status()

            self.after(0, apply)

        self._log("[...] Iniciando PostgreSQL...")
        threading.Thread(target=work, daemon=True).start()

    def start_erp(self) -> None:
        if not _port_listening(5432):
            if not messagebox.askyesno(
                APP_TITLE,
                "PostgreSQL NO esta activo (puerto 5432 cerrado).\n\n"
                "El ERP arrancara pero NO podra iniciar sesion.\n\n"
                "¿Iniciar PostgreSQL primero y luego el ERP?",
            ):
                return
            self.start_postgres()
            self.after(3500, self._start_erp_after_pg)
            return
        try:
            _run_bat("02_Iniciar_ERP.bat")
            self._log("[OK] Iniciando servidor ERP...")
            self.after(3000, self.refresh_status)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))

    def _start_erp_after_pg(self) -> None:
        if not _port_listening(5432):
            messagebox.showwarning(
                APP_TITLE,
                "PostgreSQL sigue sin responder en 5432.\n"
                "Clic derecho en LhexIA Control → Ejecutar como administrador,\n"
                "luego «Iniciar PostgreSQL» o «Iniciar todo».",
            )
            return
        try:
            _run_bat("02_Iniciar_ERP.bat")
            self._log("[OK] PostgreSQL listo — iniciando servidor ERP...")
            self.after(3000, self.refresh_status)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))

    def start_all(self) -> None:
        def work() -> None:
            pg_msg = _start_postgres()
            self.after(0, lambda: self._log(pg_msg))
            if _wait_port(5432, seconds=25):
                self.after(0, self._start_erp_after_pg)
            else:
                self.after(
                    0,
                    lambda: messagebox.showwarning(
                        APP_TITLE,
                        "PostgreSQL no respondio en puerto 5432.\n\n"
                        "Sin la base de datos el login SIEMPRE falla.\n\n"
                        "1. Cierre LhexIA Control\n"
                        "2. Clic derecho → Ejecutar como administrador\n"
                        "3. «Iniciar PostgreSQL» o «Arranque automatico»\n"
                        "4. Luego «Iniciar todo» de nuevo",
                    ),
                )
            self.after(5000, self.refresh_status)

        self._log("[...] Iniciando PostgreSQL y ERP...")
        threading.Thread(target=work, daemon=True).start()

    def stop_erp(self) -> None:
        if not messagebox.askyesno(APP_TITLE, "Detener el servidor ERP en puerto 5000?"):
            return
        msg = _kill_port_5000()
        self._log(msg)
        self.refresh_status()

    def open_tablet_url(self) -> None:
        urls = _lan_urls()
        if not urls:
            messagebox.showinfo(APP_TITLE, "No hay URL de red.\nEjecute Configurar intranet primero.")
            return
        webbrowser.open(urls[0] + "/login")
        self._log(f"[OK] Abriendo {urls[0]}/login")

    def install_step_by_step(self) -> None:
        if not (PAQUETE_DIR / "INSTALAR_LHEXIA.bat").is_file():
            messagebox.showerror(
                APP_TITLE,
                f"No existe:\n{PAQUETE_DIR}\\INSTALAR_LHEXIA.bat\n\n"
                "Copie la carpeta INSTALACION completa al USB.",
            )
            return
        if not _erp_runtime_ok():
            messagebox.showerror(
                APP_TITLE,
                "Falta erp\\LhexIA_ERP.exe en esta carpeta INSTALACION.\n\n"
                "En el PC de desarrollo ejecute:\n  COMPILAR_ERP_EXE.bat\n"
                "Luego vuelva a copiar INSTALACION al USB.\n\n"
                "NOTA: No se usa carpeta 02_APLICACION.\n"
                "La aplicacion va en INSTALACION\\erp\\ (hermana de paquete\\).",
            )
            return
        if not messagebox.askyesno(
            APP_TITLE,
            "Instalacion en este PC:\n\n"
            "1. PostgreSQL\n2. Python\n3. Aplicacion (erp\\LhexIA_ERP.exe)\n"
            "4. Base de datos\n5. Intranet\n\n"
            "Puede tardar varios minutos. Continuar?",
        ):
            return
        try:
            _run_bat_instalador("INSTALAR_LHEXIA.bat")
            self._log("[OK] Instalador paso a paso iniciado (paquete\\INSTALAR_LHEXIA.bat).")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))


def main() -> None:
    if sys.platform != "win32":
        print("Solo Windows.")
        sys.exit(1)
    app = CentroControlApp()
    app.mainloop()


if __name__ == "__main__":
    main()
