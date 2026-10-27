#!/usr/bin/env python3
"""
comparar.py: Compara los resultados de la PC (Python nativo) con los del
navegador (Pyodide WebAssembly) para la Aplicación 2 (tolerancia 1e-6).
"""
import os
import sys
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
        # Evitar problemas de caché en desarrollo
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format, *args):
        # Silenciar logs normales del servidor HTTP para mantener limpia la consola
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
    print("=" * 80)
    print("VALIDACIÓN HITO 1: NAVEGADOR (Pyodide) vs PC (Python nativo)")
    print(f"Tolerancia exigida: {TOLERANCIA}")
    print("=" * 80)

    # 1. Asegurar módulos actualizados en web/py/
    script_construir = os.path.join(AQUI, "construir.sh")
    if os.path.exists(script_construir):
        print("==> Ejecutando construir.sh para sincronizar módulos...")
        subprocess.run(["bash", script_construir], check=True, stdout=subprocess.DEVNULL)

    # 2. Calcular solución de referencia en PC
    ruta_ejemplo = os.path.join(P2D_DIR, "ejemplos", "aplicacion2_portico_QD.json")
    print(f"==> Resolviendo en PC con Python nativo: {os.path.basename(ruta_ejemplo)}")
    sol_pc = resolver_en_pc(ruta_ejemplo)

    # 3. Iniciar servidor HTTP local
    puerto = buscar_puerto_libre()
    evento = threading.Event()
    ServidorPyodideTest.evento_resultado = evento
    ServidorPyodideTest.resultado_recibido = None

    servidor = HTTPServer(("127.0.0.1", puerto), ServidorPyodideTest)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    url = f"http://127.0.0.1:{puerto}/?test=1"
    print(f"==> Servidor HTTP local iniciado en {url}")

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
        print(f"==> Navegador no encontrado automáticamente. Por favor abre: {url}")

    # 5. Esperar resultado del navegador (Pyodide descarga WebAssembly y NumPy)
    print("==> Esperando respuesta del navegador (Pyodide)...")
    espera_max = 60  # segundos
    completado = evento.wait(timeout=espera_max)

    if proc_navegador:
        try:
            proc_navegador.terminate()
            proc_navegador.wait(timeout=2)
        except Exception:
            pass

    servidor.shutdown()

    if not completado or ServidorPyodideTest.resultado_recibido is None:
        print(f"ERROR: No se recibió resultado del navegador en {espera_max} s.")
        sys.exit(1)

    sol_web = ServidorPyodideTest.resultado_recibido
    print("==> Resultado recibido con éxito desde Pyodide WebAssembly.\n")

    # 6. Comparación rigurosa de {D} y {q}
    errores = []
    max_error_global = 0.0

    # A. Comparar {D}
    D_pc = sol_pc["D"]
    D_web = np.array(sol_web["D"])
    diff_D = np.abs(D_pc - D_web)
    max_diff_D = np.max(diff_D)
    max_error_global = max(max_error_global, max_diff_D)

    print("-" * 80)
    print("1. VECTOR DE DESPLAZAMIENTOS GLOBALES {D}")
    print(f"   {'GDL':<8} {'PC (Nativo)':<18} {'Web (Pyodide)':<18} {'Diferencia':<16} {'Estado'}")
    print("   " + "-" * 70)
    for i in range(len(D_pc)):
        gdl_label = f"D{i+1}"
        d_pc = D_pc[i]
        d_web = D_web[i]
        err = diff_D[i]
        estado = "✓ COINCIDE" if err <= TOLERANCIA else "✗ DIFERENCIA"
        if err > TOLERANCIA:
            errores.append(f"{gdl_label}: err={err} > {TOLERANCIA}")
        print(f"   {gdl_label:<8} {d_pc:<18.10f} {d_web:<18.10f} {err:<16.2e} {estado}")

    # B. Comparar {q} por barra
    print("\n" + "-" * 80)
    print("2. VECTORES DE FUERZAS EN EXTREMOS DE BARRA {q}")
    print(f"   {'Barra':<8} {'Extremo':<10} {'PC (Nativo)':<16} {'Web (Pyodide)':<16} {'Diferencia':<14} {'Estado'}")
    print("   " + "-" * 74)

    extremos = ["V_i (t)", "M_i (t·m)", "V_j (t)", "M_j (t·m)"]
    for b_id, q_pc in sol_pc["q"].items():
        if b_id not in sol_web["q"]:
            errores.append(f"Falta barra {b_id} en resultado web")
            continue
        q_web = np.array(sol_web["q"][b_id])
        diff_q = np.abs(q_pc - q_web)
        max_diff_q = np.max(diff_q)
        max_error_global = max(max_error_global, max_diff_q)

        for j in range(4):
            ext_label = extremos[j]
            v_pc = q_pc[j]
            v_web = q_web[j]
            err = diff_q[j]
            estado = "✓ COINCIDE" if err <= TOLERANCIA else "✗ DIFERENCIA"
            if err > TOLERANCIA:
                errores.append(f"Barra {b_id} {ext_label}: err={err} > {TOLERANCIA}")
            b_label = f"Barra {b_id}" if j == 0 else ""
            print(f"   {b_label:<8} {ext_label:<10} {v_pc:<16.6f} {v_web:<16.6f} {err:<14.2e} {estado}")

    # C. Comparar [K] y {R}
    K_pc = sol_pc["K"]
    K_web = np.array(sol_web["K"])
    diff_K = np.abs(K_pc - K_web)
    max_diff_K = np.max(diff_K)
    max_error_global = max(max_error_global, max_diff_K)

    R_pc = sol_pc["R"]
    R_web = np.array(sol_web["R"])
    diff_R = np.abs(R_pc - R_web)
    max_diff_R = np.max(diff_R)
    max_error_global = max(max_error_global, max_diff_R)

    print("\n" + "-" * 80)
    print("3. MATRIZ DE RIGIDEZ [K] Y VECTOR DE CARGAS DE FIJACIÓN {R}")
    print(f"   Diferencia máxima en [K]: {max_diff_K:.2e} ({'✓ OK' if max_diff_K <= TOLERANCIA else '✗ ERROR'})")
    print(f"   Diferencia máxima en {{R}}: {max_diff_R:.2e} ({'✓ OK' if max_diff_R <= TOLERANCIA else '✗ ERROR'})")

    print("\n" + "=" * 80)
    if not errores:
        print(f"RESULTADO FINAL: ✓ ÉXITO TOTAL")
        print(f"Todos los valores de {{D}} y {{q}} coinciden con tolerancia {TOLERANCIA}.")
        print(f"Diferencia máxima detectada en todo el cálculo: {max_error_global:.2e}")
        print("=" * 80)
        sys.exit(0)
    else:
        print(f"RESULTADO FINAL: ✗ DISCREPANCIAS DETECTADAS")
        for e in errores:
            print(f" - {e}")
        print("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    ejecutar_comparacion()
