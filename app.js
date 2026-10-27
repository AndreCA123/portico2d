// ==============================================================================
// Pórtico 2D Web · Lógica del cliente Pyodide
// Ejecuta portico2d/solver.py y modelo.py originales en WebAssembly
// ==============================================================================

let pyodide = null;

const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const btnResolver = document.getElementById('btn-resolver');
const selEjemplo = document.getElementById('sel-ejemplo');
const tiempoCalc = document.getElementById('tiempo-calc');
const seccionResultados = document.getElementById('seccion-resultados');

const elVectorD = document.getElementById('vector-D');
const tablaQBody = document.querySelector('#tabla-q tbody');
const tablaReacBody = document.querySelector('#tabla-reacciones tbody');
const elVectorR = document.getElementById('vector-R');
const elMatrizK = document.getElementById('matriz-K');
const elJsonSalida = document.getElementById('json-salida');

function setStatus(tipo, texto) {
  statusDot.className = `status-dot ${tipo}`;
  statusText.textContent = texto;
}

// ----------------------------------------------------------- Inicializar Pyodide
async function inicializarPyodide() {
  try {
    setStatus('loading', 'Cargando biblioteca Pyodide...');
    while (typeof loadPyodide === 'undefined') {
      await new Promise(r => setTimeout(r, 50));
    }

    setStatus('loading', 'Descargando motor Pyodide (WebAssembly)...');
    pyodide = await loadPyodide({
      indexURL: "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/"
    });

    setStatus('loading', 'Cargando paquete NumPy...');
    await pyodide.loadPackage("numpy");

    setStatus('loading', 'Copiando módulos de portico2d a entorno virtual...');
    try {
      pyodide.FS.mkdirTree('/home/pyodide/portico2d');
    } catch (e) {
      // ya existe
    }

    const modulos = ['__init__.py', 'modelo.py', 'solver.py'];
    for (const mod of modulos) {
      const resp = await fetch(`py/portico2d/${mod}`);
      if (!resp.ok) {
        throw new Error(`No se pudo cargar py/portico2d/${mod} (HTTP ${resp.status})`);
      }
      const contenido = await resp.text();
      pyodide.FS.writeFile(`/home/pyodide/portico2d/${mod}`, contenido);
    }

    // Configurar Python y preparar la función de análisis
    setStatus('loading', 'Configurando intérprete Python...');
    pyodide.runPython(`
import sys
if '/home/pyodide' not in sys.path:
    sys.path.insert(0, '/home/pyodide')

import json
import numpy as np
from portico2d.modelo import Modelo
from portico2d.solver import analizar

def resolver_modelo_json(json_str):
    datos = json.loads(json_str)
    modelo = Modelo.de_dict(datos)
    res = analizar(modelo)
    
    salida = {
        "titulo": modelo.titulo,
        "ea_infinito": bool(modelo.ea_infinito),
        "D": res.D.tolist(),
        "R": res.R.tolist(),
        "K": res.K.tolist(),
        "barras": [
            {
                "id": int(b.id),
                "i": int(b.i),
                "j": int(b.j),
                "q": b.q.tolist()
            }
            for b in res.barras
        ],
        "q": {str(b.id): b.q.tolist() for b in res.barras},
        "reacciones": {str(k): list(v) for k, v in res.reacciones.items()},
        "u_nudos": {str(k): list(v) for k, v in res.u_nudos.items()}
    }
    return json.dumps(salida)
`);

    setStatus('ready', 'Pyodide listo para resolver');
    btnResolver.disabled = false;

    // Si viene con parámetro ?test=1 o ?autorun=1, ejecuta automáticamente
    const params = new URLSearchParams(window.location.search);
    if (params.get('test') === '1' || params.get('autorun') === '1') {
      await resolver();
    }
  } catch (err) {
    console.error("Error al iniciar Pyodide:", err);
    setStatus('error', `Error: ${err.message}`);
  }
}

// ----------------------------------------------------------- Resolver Modelo
async function resolver() {
  if (!pyodide) return;

  btnResolver.disabled = true;
  setStatus('loading', 'Resolviendo estructura...');
  tiempoCalc.textContent = '';

  try {
    const ejemplo = selEjemplo.value;
    const resp = await fetch(`ejemplos/${ejemplo}`);
    if (!resp.ok) {
      throw new Error(`Error al leer archivo ejemplos/${ejemplo} (HTTP ${resp.status})`);
    }
    const jsonStr = await resp.text();

    const t0 = performance.now();
    // Ejecutar el solver a través de Python en Pyodide
    const resolverFn = pyodide.globals.get('resolver_modelo_json');
    const resJsonStr = resolverFn(jsonStr);
    const t1 = performance.now();

    const resultado = JSON.parse(resJsonStr);
    window.__ultimoResultado = resultado;

    renderizarResultados(resultado, t1 - t0);
    setStatus('success', `Resuelto con éxito · ${(t1 - t0).toFixed(1)} ms`);

    // Notificar al backend si se invoca desde el script de test
    const params = new URLSearchParams(window.location.search);
    if (params.get('test') === '1') {
      try {
        await fetch('/api/resultado', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(resultado)
        });
        console.log("Resultado enviado al servidor de prueba");
      } catch (postErr) {
        console.warn("No se pudo enviar resultado a /api/resultado:", postErr);
      }
    }
  } catch (err) {
    console.error("Error durante la resolución:", err);
    setStatus('error', `Fallo al resolver: ${err.message}`);
  } finally {
    btnResolver.disabled = false;
  }
}

// ----------------------------------------------------------- Renderizar Resultados
function renderizarResultados(res, tiempoMs) {
  seccionResultados.style.display = 'grid';
  tiempoCalc.textContent = `(${tiempoMs.toFixed(1)} ms)`;

  // 1. Vector {D}
  elVectorD.innerHTML = '';
  res.D.forEach((val, idx) => {
    const div = document.createElement('div');
    div.className = 'vector-item';
    const numFmt = Math.abs(val) < 1e-4 ? val.toExponential(6) : val.toFixed(6);
    div.innerHTML = `
      <span class="label">GDL D${idx + 1}</span>
      <span class="val mono-num ${val >= 0 ? 'positive' : 'negative'}">${numFmt}</span>
    `;
    elVectorD.appendChild(div);
  });

  // 2. Fuerzas en extremos {q}
  tablaQBody.innerHTML = '';
  res.barras.forEach(b => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>Barra ${b.id}</strong> (${b.i} → ${b.j})</td>
      <td class="mono-num">${b.q[0].toFixed(4)}</td>
      <td class="mono-num">${b.q[1].toFixed(4)}</td>
      <td class="mono-num">${b.q[2].toFixed(4)}</td>
      <td class="mono-num">${b.q[3].toFixed(4)}</td>
    `;
    tablaQBody.appendChild(tr);
  });

  // 3. Reacciones en apoyos
  tablaReacBody.innerHTML = '';
  Object.keys(res.reacciones).sort((a,b) => Number(a)-Number(b)).forEach(nudoId => {
    const reac = res.reacciones[nudoId];
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>Nudo ${nudoId}</strong></td>
      <td class="mono-num">${reac[0].toFixed(3)}</td>
      <td class="mono-num">${reac[1].toFixed(3)}</td>
      <td class="mono-num">${reac[2].toFixed(3)}</td>
    `;
    tablaReacBody.appendChild(tr);
  });

  // 4. Vector {R} y Matriz [K]
  elVectorR.textContent = `[ ${res.R.map(v => v.toFixed(3)).join(', ')} ]`;
  
  let htmlK = '<table class="matrix-table">';
  res.K.forEach(fila => {
    htmlK += '<tr>';
    fila.forEach(val => {
      htmlK += `<td>${val.toFixed(2)}</td>`;
    });
    htmlK += '</tr>';
  });
  htmlK += '</table>';
  elMatrizK.innerHTML = htmlK;

  // 5. Raw JSON
  elJsonSalida.textContent = JSON.stringify(res, null, 2);
}

// Event Listeners
btnResolver.addEventListener('click', resolver);
selEjemplo.addEventListener('change', () => {
  resolver();
});

// Arrancar al cargar el DOM
window.addEventListener('DOMContentLoaded', inicializarPyodide);
