#!/usr/bin/env python3
"""
comparar.py: Compara los resultados de la PC (Python nativo) con los del
navegador (Pyodide WebAssembly) para TODOS los ejemplos en Portico2D/ejemplos/
(tolerancia exigida: 1e-6).
"""
import os
import sys
import glob
import json
import time
import shutil
import socket
import threading
import subprocess
from http.server import SimpleHTTPRequestHandler, HTTPServer
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
P2D_DIR = os.path.abspath(os.path.join(AQUI, ".."))
sys.path.insert(0, P2D_DIR)

from portico2d.modelo import Modelo
from portico2d.solver import analizar

TOLERANCIA = 1e-6


class ServidorPyodideTest(SimpleHTTPRequestHandler):
    resultado_recibido = None
    evento_resultado = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=AQUI, **kwargs)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        if self.path.startswith("/api/resultado"):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                ServidorPyodideTest.resultado_recibido = json.loads(body.decode("utf-8"))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
                if ServidorPyodideTest.evento_resultado:
                    ServidorPyodideTest.evento_resultado.set()
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format, *args):
        pass


def buscar_puerto_libre():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def resolver_en_pc(ruta_json):
    modelo = Modelo.abrir(ruta_json)
    res = analizar(modelo)
    return {
        "D": res.D,
        "K": res.K,
        "R": res.R,
        "q": {str(b.id): b.q for b in res.barras},
        "reacciones": {str(k): v for k, v in res.reacciones.items()},
    }


def ejecutar_comparacion():
    print("=" * 86)
    print("VALIDACIÓN MULTI-EJEMPLO: NAVEGADOR (Pyodide) vs PC (Python nativo)")
    print(f"Tolerancia exigida: {TOLERANCIA}")
    print("=" * 86)

    # 1. Asegurar módulos y ejemplos sincronizados en web/
    script_construir = os.path.join(AQUI, "construir.sh")
    if os.path.exists(script_construir):
        print("==> Ejecutando construir.sh para sincronizar módulos...")
        subprocess.run(["bash", script_construir], check=True, stdout=subprocess.DEVNULL)

    # 2. Descubrir y resolver todos los ejemplos en PC
    archivos_ejemplos = sorted(glob.glob(os.path.join(P2D_DIR, "ejemplos", "*.json")))
    if not archivos_ejemplos:
        print("ERROR: No se encontraron archivos en Portico2D/ejemplos/")
        sys.exit(1)

    print(f"==> Resolviendo {len(archivos_ejemplos)} ejemplos en PC con Python nativo...")
    soluciones_pc = {}
    for ruta in archivos_ejemplos:
        nombre = os.path.basename(ruta)
        soluciones_pc[nombre] = resolver_en_pc(ruta)

    # 3. Iniciar servidor HTTP local
    puerto = buscar_puerto_libre()
    evento = threading.Event()
    ServidorPyodideTest.evento_resultado = evento
    ServidorPyodideTest.resultado_recibido = None

    servidor = HTTPServer(("127.0.0.1", puerto), ServidorPyodideTest)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    url = f"http://127.0.0.1:{puerto}/?test_todos=1"
    print(f"==> Servidor HTTP iniciado en {url}")

    # 4. Lanzar navegador headless
    navegadores = ["google-chrome", "chromium", "chromium-browser", "firefox"]
    binario_nav = None
    for nav in navegadores:
        binario_nav = shutil.which(nav)
        if binario_nav:
            break

    proc_navegador = None
    if binario_nav:
        print(f"==> Ejecutando navegador headless: {binario_nav}")
        cmd = [
            binario_nav,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            url
        ]
        proc_navegador = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        print(f"==> Abre en cualquier navegador: {url}")

    # 5. Esperar resolución completa de los 9 ejemplos en el navegador
    print("==> Esperando cálculo de todos los ejemplos en Pyodide...")
    espera_max = 75  # segundos
    completado = evento.wait(timeout=espera_max)

    if proc_navegador:
        try:
            proc_navegador.terminate()
            proc_navegador.wait(timeout=2)
        except Exception:
            pass

    servidor.shutdown()

    if not completado or ServidorPyodideTest.resultado_recibido is None:
        print(f"ERROR: No se recibió respuesta del navegador en {espera_max} s.")
        sys.exit(1)

    soluciones_web = ServidorPyodideTest.resultado_recibido
    print("==> Resultados de todos los ejemplos recibidos desde Pyodide.\n")

    # 6. Comparar cada ejemplo individualmente
    print("-" * 86)
    print(f"{'#':<3} {'Ejemplo':<36} {'Max Diff {D}':<15} {'Max Diff {q}':<15} {'Estado'}")
    print("-" * 86)

    discrepancias = []
    max_global = 0.0

    for idx, (nombre, sol_pc) in enumerate(soluciones_pc.items(), 1):
        if nombre not in soluciones_web:
            discrepancias.append(f"{nombre}: No fue resuelto por el navegador")
            print(f"{idx:<3} {nombre:<36} {'NO ENCONTRADO':<15} {'-':<15} ✗ ERROR")
            continue

        sol_web = soluciones_web[nombre]
        if "error" in sol_web:
            discrepancias.append(f"{nombre}: Error en navegador -> {sol_web['error']}")
            print(f"{idx:<3} {nombre:<36} {'FALLO PYTHON':<15} {'-':<15} ✗ ERROR")
            continue

        # Comparar {D}
        D_pc = np.array(sol_pc["D"])
        D_web = np.array(sol_web["D"])
        diff_D = np.abs(D_pc - D_web)
        max_d_D = np.max(diff_D) if len(diff_D) > 0 else 0.0

        # Comparar {q}
        max_d_q = 0.0
        for b_id, q_pc in sol_pc["q"].items():
            if b_id not in sol_web["q"]:
                discrepancias.append(f"{nombre}: falta barra {b_id} en web")
                continue
            q_web = np.array(sol_web["q"][b_id])
            diff_q = np.abs(q_pc - q_web)
            max_d_q = max(max_d_q, np.max(diff_q))

        # Comparar [K] y {R}
        K_pc = np.array(sol_pc["K"])
        K_web = np.array(sol_web["K"])
        max_d_K = np.max(np.abs(K_pc - K_web))

        R_pc = np.array(sol_pc["R"])
        R_web = np.array(sol_web["R"])
        max_d_R = np.max(np.abs(R_pc - R_web))

        max_ejemplo = max(max_d_D, max_d_q, max_d_K, max_d_R)
        max_global = max(max_global, max_ejemplo)

        ok = max_ejemplo <= TOLERANCIA
        estado = "✓ COINCIDE" if ok else "✗ DIFERENCIA"
        if not ok:
            discrepancias.append(f"{nombre}: max diff = {max_ejemplo:.2e} > {TOLERANCIA}")

        print(f"{idx:<3} {nombre:<36} {max_d_D:<15.2e} {max_d_q:<15.2e} {estado}")

    print("=" * 86)
    if not discrepancias:
        print(f"RESULTADO: ✓ TODOS LOS {len(soluciones_pc)} EJEMPLOS COINCIDEN CON LA PC.")
        print(f"Tolerancia exigida: {TOLERANCIA} | Diferencia máxima global: {max_global:.2e}")
        print("=" * 86)
        sys.exit(0)
    else:
        print(f"RESULTADO: ✗ DISCREPANCIAS DETECTADAS EN {len(discrepancias)} EJEMPLO(S):")
        for d in discrepancias:
            print(f"  - {d}")
        print("=" * 86)
        sys.exit(1)


if __name__ == "__main__":
    ejecutar_comparacion()
