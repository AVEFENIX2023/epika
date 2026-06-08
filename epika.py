import subprocess
import sys
import os
import shutil
import urllib.request
import tkinter as tk
from tkinter import ttk
import threading
import time
import socket
import http.server
import socketserver

VERSION_LOCAL = "4.5"
REPO = "https://raw.githubusercontent.com/AVEFENIX2023/epika/main/"
ARCHIVOS = [
    "epika_v4.5.html",
    "manifest.json",
    "icono.ico",
    "css/base.css",
    "css/temas/aurora.css",
    "css/temas/brasa.css",
    "css/temas/selva.css",
    "css/temas/tinta.css",
    "css/temas/neon.css",
    "css/temas/oro.css",
    "css/temas/cafe.css",
]

destino = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Epika")
_httpd_ref = None


# ─────────────────────────────────────────────
# SOLUCION PROBLEMA 1: MULTIPLES INSTANCIAS
# Busca ventana con "pika" en el titulo usando win32gui.
# Si la encuentra, la trae al frente y sale.
# Python se mantiene vivo (sirve HTTP), por lo que la
# ventana siempre existe mientras la app este abierta.
# ─────────────────────────────────────────────

def _buscar_ventana_epika():
    """Devuelve hwnd si hay una ventana Epika abierta, o 0."""
    try:
        import win32gui
        encontrada = []
        def cb(hwnd, _):
            titulo = win32gui.GetWindowText(hwnd).lower()
            # Busca titulo especifico de la app, no cualquier cosa con "pika"
            if win32gui.IsWindowVisible(hwnd) and "lector de voz" in titulo:
                encontrada.append(hwnd)
        win32gui.EnumWindows(cb, None)
        return encontrada[0] if encontrada else 0
    except Exception:
        return 0


def ventana_epika_abierta():
    """Si ya hay una ventana Epika, la trae al frente y devuelve True."""
    hwnd = _buscar_ventana_epika()
    if hwnd:
        try:
            import win32gui
            # SetForegroundWindow puede fallar si la ventana esta minimizada
            import win32con
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        return True
    return False


# ─────────────────────────────────────────────
# SOLUCION PROBLEMA 2: ICONO EN BARRA DE TAREAS
# Servidor HTTP local en lugar de file:///
# Edge con http://127.0.0.1 respeta el favicon del HTML.
# ─────────────────────────────────────────────

def encontrar_puerto_libre():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _SilentHandler(http.server.SimpleHTTPRequestHandler):
    """Servidor HTTP que sirve desde el directorio de Epika sin logs."""
    # Asegurar MIME types correctos (Windows no siempre los tiene)
    extensions_map = {
        '':      'application/octet-stream',
        '.html': 'text/html',
        '.css':  'text/css',
        '.js':   'application/javascript',
        '.ico':  'image/x-icon',
        '.png':  'image/png',
        '.jpg':  'image/jpeg',
        '.svg':  'image/svg+xml',
        '.txt':  'text/plain',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=destino, **kwargs)

    def log_message(self, fmt, *args):
        pass  # silenciar output en consola


def iniciar_servidor_http(puerto):
    global _httpd_ref
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", puerto), _SilentHandler) as httpd:
        _httpd_ref = httpd
        httpd.serve_forever()


def detener_servidor():
    global _httpd_ref
    if _httpd_ref:
        threading.Thread(target=_httpd_ref.shutdown, daemon=True).start()
        _httpd_ref = None


def abrir_edge(puerto):
    url = f"http://127.0.0.1:{puerto}/epika_v4.5.html"
    edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if not os.path.exists(edge):
        edge = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    subprocess.Popen([edge, f"--app={url}"])


def inyectar_icono_en_ventana():
    """Espera a que la ventana Epika abra y le inyecta el icono personalizado."""
    icono_path = os.path.join(destino, "icono.ico")
    if not os.path.exists(icono_path):
        return
    try:
        import win32gui
        import ctypes
        WM_SETICON   = 0x0080
        ICON_SMALL   = 0
        ICON_BIG     = 1
        IMAGE_ICON   = 1
        LR_LOADFROMFILE = 0x0010
        # Esperar hasta que la ventana aparezca (max 10 seg)
        hwnd = 0
        for _ in range(20):
            hwnd = _buscar_ventana_epika()
            if hwnd:
                break
            time.sleep(0.5)
        if not hwnd:
            return
        # Cargar icono en dos tamaños
        hicon_small = ctypes.windll.user32.LoadImageW(
            None, icono_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
        hicon_big = ctypes.windll.user32.LoadImageW(
            None, icono_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
        # Inyectar en la ventana
        win32gui.SendMessage(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
        win32gui.SendMessage(hwnd, WM_SETICON, ICON_BIG,   hicon_big)
    except Exception:
        pass


def esperar_cierre_epika():
    """Mantiene Python (y el servidor HTTP) vivo mientras la ventana Epika este abierta."""
    # Esperar hasta que la ventana aparezca (max 15 seg)
    for _ in range(30):
        if _buscar_ventana_epika():
            break
        time.sleep(0.5)
    # Esperar hasta que se cierre
    while _buscar_ventana_epika():
        time.sleep(2)
    detener_servidor()


# ─────────────────────────────────────────────
# ACTUALIZACIONES Y DESCARGA
# ─────────────────────────────────────────────

def obtener_version_remota():
    try:
        url = REPO + "version.txt"
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.read().decode().strip()
    except Exception:
        return VERSION_LOCAL


def obtener_novedades():
    try:
        url = REPO + "novedades.txt"
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.read().decode("utf-8").strip()
    except Exception:
        return ""


def descargar_archivos(progress_callback, status_callback):
    os.makedirs(destino, exist_ok=True)
    os.makedirs(os.path.join(destino, "css", "temas"), exist_ok=True)
    os.makedirs(os.path.join(destino, "temas"), exist_ok=True)
    total = len(ARCHIVOS)
    for i, archivo in enumerate(ARCHIVOS):
        try:
            status_callback("Descargando " + archivo + "...")
            url = REPO + archivo
            ruta_local = os.path.join(destino, archivo.replace("/", os.sep))
            urllib.request.urlretrieve(url, ruta_local)
        except Exception:
            pass
        progress_callback(int((i + 1) / total * 100))
        time.sleep(0.1)
    # Copiar imagenes de temas desde el exe
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    # Copiar icono.ico al destino (necesario para favicon via HTTP)
    ico_src = os.path.join(base, "icono.ico")
    ico_dst = os.path.join(destino, "icono.ico")
    if os.path.exists(ico_src) and not os.path.exists(ico_dst):
        shutil.copy2(ico_src, ico_dst)
    temas_src = os.path.join(base, "temas")
    temas_dst = os.path.join(destino, "temas")
    if os.path.exists(temas_src):
        shutil.copytree(temas_src, temas_dst, dirs_exist_ok=True)


def mostrar_novedades(novedades, version):
    ventana = tk.Tk()
    ventana.title("Epika Actualizado!")
    ventana.configure(bg="#0a0a0a")
    ventana.resizable(False, False)
    ventana.attributes("-topmost", True)
    ancho, alto = 500, 420
    x = (ventana.winfo_screenwidth() - ancho) // 2
    y = (ventana.winfo_screenheight() - alto) // 2
    ventana.geometry(f"{ancho}x{alto}+{x}+{y}")
    tk.Label(ventana, text="EPIKA ACTUALIZADO", font=("Georgia", 16, "bold"),
             fg="#d4af37", bg="#0a0a0a").pack(pady=(30, 5))
    tk.Label(ventana, text=f"Versión {version}", font=("Georgia", 11),
             fg="#a07820", bg="#0a0a0a").pack(pady=(0, 20))
    frame = tk.Frame(ventana, bg="#111111", highlightthickness=1, highlightbackground="#d4af37")
    frame.pack(padx=30, fill="both", expand=True)
    texto = tk.Text(frame, bg="#111111", fg="#f0e0a0", font=("Georgia", 10),
                    wrap="word", bd=0, padx=15, pady=15, relief="flat", highlightthickness=0)
    texto.insert("1.0", novedades)
    texto.config(state="disabled")
    texto.pack(fill="both", expand=True)
    tk.Button(ventana, text="Entendido", font=("Georgia", 11, "bold"),
              fg="#0a0a0a", bg="#d4af37", bd=0, padx=20, pady=8,
              cursor="hand2", command=ventana.destroy).pack(pady=20)
    ventana.mainloop()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    # Problema 1 resuelto: buscar ventana antes de abrir
    if ventana_epika_abierta():
        return

    version_remota = obtener_version_remota()
    hay_actualizacion = version_remota != VERSION_LOCAL
    html_existe = os.path.exists(os.path.join(destino, "epika_v4.5.html"))

    if not hay_actualizacion and html_existe:
        # Garantizar que icono.ico este en destino para el favicon HTTP
        if getattr(sys, "frozen", False):
            _base = sys._MEIPASS
        else:
            _base = os.path.dirname(os.path.abspath(__file__))
        _ico_src = os.path.join(_base, "icono.ico")
        _ico_dst = os.path.join(destino, "icono.ico")
        if os.path.exists(_ico_src) and not os.path.exists(_ico_dst):
            shutil.copy2(_ico_src, _ico_dst)
        # Lanzar directamente con servidor HTTP
        puerto = encontrar_puerto_libre()
        threading.Thread(target=iniciar_servidor_http, args=(puerto,), daemon=True).start()
        time.sleep(0.4)
        abrir_edge(puerto)
        threading.Thread(target=inyectar_icono_en_ventana, daemon=True).start()
        esperar_cierre_epika()
        return

    # Mostrar ventana de carga / actualizacion
    root = tk.Tk()
    root.overrideredirect(True)
    root.configure(bg="#0a0a0a")
    root.attributes("-topmost", True)
    ancho, alto = 480, 300
    x = (root.winfo_screenwidth() - ancho) // 2
    y = (root.winfo_screenheight() - alto) // 2
    root.geometry(f"{ancho}x{alto}+{x}+{y}")
    root.configure(highlightthickness=2, highlightbackground="#d4af37")

    tk.Label(root, text="EPIKA", font=("Georgia", 32, "bold"),
             fg="#d4af37", bg="#0a0a0a").pack(pady=(35, 0))
    tk.Label(root, text="V 4 . 5  -  L E C T O R  D E  V O Z",
             font=("Georgia", 9), fg="#a07820", bg="#0a0a0a").pack()
    tk.Label(root, text="-----------------------------",
             fg="#3a3a2a", bg="#0a0a0a").pack(pady=(10, 5))

    status_var = tk.StringVar(value="Verificando actualización...")
    tk.Label(root, textvariable=status_var, font=("Georgia", 9),
             fg="#a07820", bg="#0a0a0a").pack()

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Gold.Horizontal.TProgressbar",
                    troughcolor="#1a1a0a", background="#d4af37",
                    bordercolor="#0a0a0a", lightcolor="#d4af37", darkcolor="#a07820")
    progress_var = tk.IntVar(value=0)
    barra = ttk.Progressbar(root, variable=progress_var, maximum=100,
                            length=380, style="Gold.Horizontal.TProgressbar")
    barra.pack(pady=15)
    porcentaje_var = tk.StringVar(value="0%")
    tk.Label(root, textvariable=porcentaje_var, font=("Georgia", 9),
             fg="#d4af37", bg="#0a0a0a").pack()
    tk.Label(root, text="*", font=("Georgia", 14),
             fg="#3a3020", bg="#0a0a0a").pack(pady=(10, 0))

    def update_progress(val):
        progress_var.set(val)
        porcentaje_var.set(f"{val}%")
        root.update_idletasks()

    def update_status(msg):
        status_var.set(msg)
        root.update_idletasks()

    novedades_resultado = []

    def proceso():
        descargar_archivos(update_progress, update_status)
        update_status("¡Listo!")
        if hay_actualizacion:
            novedades_resultado.append(obtener_novedades())
        time.sleep(0.8)
        root.quit()

    hilo = threading.Thread(target=proceso, daemon=True)
    hilo.start()
    root.mainloop()
    root.destroy()

    # Lanzar con servidor HTTP (Problema 2 resuelto)
    puerto = encontrar_puerto_libre()
    threading.Thread(target=iniciar_servidor_http, args=(puerto,), daemon=True).start()
    time.sleep(0.4)
    abrir_edge(puerto)
    threading.Thread(target=inyectar_icono_en_ventana, daemon=True).start()

    if hay_actualizacion and novedades_resultado and novedades_resultado[0]:
        time.sleep(2)
        mostrar_novedades(novedades_resultado[0], version_remota)

    esperar_cierre_epika()


if __name__ == "__main__":
    main()
