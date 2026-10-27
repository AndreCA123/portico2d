// ==============================================================================
// Pórtico 2D Web · Hitos 1 a 4: Entrada Móvil, Pyodide, Diagramas y Pasos 1–14
// ==============================================================================

let pyodide = null;
let ultimoResultado = null;
let diagramaActual = "modelo";

const APOYOS = [
  "libre",
  "empotrado",
  "articulado",
  "rodillo (fija Y)",
  "rodillo (fija X)",
  "guía (fija X y giro)",
  "guía (fija Y y giro)"
];

const EXTREMOS = [
  "rígido–rígido",
  "rótula en i",
  "rótula en j",
  "rótula i y j (armadura)"
];

const DIRECCIONES = [
  "perpendicular (y local)",
  "axial (x local)",
  "global X",
  "global Y"
];

const TODOS_LOS_EJEMPLOS = [
  "aplicacion2_portico_QD.json",
  "figura33_profesor.json",
  "figura33_portico_dos_vanos.json",
  "portico_simple.json",
  "viga_continua.json",
  "v02_armadura_triangular.json",
  "v02_portico_brazos_rigidos.json",
  "v02_viga_gerber_rotula.json",
  "v02_viga_trapezoidal_parcial.json"
];

// Estado local del modelo
let modeloActual = {
  titulo: "Aplicación 2 – Pórtico Q-D con barra inclinada",
  ea_infinito: true,
  nudos: [],
  barras: [],
  cargas_nudo: [],
  cargas_repartidas: [],
  cargas_puntuales: []
};

// Elementos DOM
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const btnResolver = document.getElementById('btn-resolver');
const selEjemplo = document.getElementById('sel-ejemplo');
const tiempoCalc = document.getElementById('tiempo-calc');

const modeloTituloInput = document.getElementById('modelo-titulo');
const modeloEaInfInput = document.getElementById('modelo-ea-inf');

const inputArchivo = document.getElementById('input-archivo');
const btnAbrirJson = document.getElementById('btn-abrir-json');
const btnGuardarJson = document.getElementById('btn-guardar-json');
const btnExportarPdf = document.getElementById('btn-exportar-pdf');

const badgeNudos = document.getElementById('badge-nudos');
const badgeBarras = document.getElementById('badge-barras');
const badgeCargas = document.getElementById('badge-cargas');

const tablaNudosBody = document.querySelector('#tabla-nudos tbody');
const tablaBarrasBody = document.querySelector('#tabla-barras tbody');
const tablaCargasNudoBody = document.querySelector('#tabla-cargas-nudo tbody');
const tablaCargasRepartidasBody = document.querySelector('#tabla-cargas-repartidas tbody');
const tablaCargasPuntualesBody = document.querySelector('#tabla-cargas-puntuales tbody');

const elVectorD = document.getElementById('vector-D');
const tablaQHead = document.getElementById('tabla-q-thead');
const tablaQBody = document.querySelector('#tabla-q tbody');
const tablaReacBody = document.querySelector('#tabla-reacciones tbody');
const tablaUNudosBody = document.querySelector('#tabla-u-nudos tbody');
const elVectorR = document.getElementById('vector-R');
const elMatrizK = document.getElementById('matriz-K');

const pasosContenedor = document.getElementById('pasos-contenedor');
const diagramaSvg = document.getElementById('diagrama-svg');
const diagramaWrapper = document.getElementById('diagrama-wrapper');
const diagramaInfo = document.getElementById('diagrama-info');

function setStatus(tipo, texto) {
  statusDot.className = `status-dot ${tipo}`;
  statusText.textContent = texto;
}

// ----------------------------------------------------------- Pestañas Móviles
document.querySelectorAll('.nav-tabs .tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-tabs .tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    
    btn.classList.add('active');
    const tabId = btn.getAttribute('data-tab');
    document.getElementById(tabId).classList.add('active');

    if (tabId === 'tab-diagramas' && ultimoResultado) {
      actualizarDiagrama();
    }
  });
});

function activarPestanaResultados() {
  document.querySelectorAll('.nav-tabs .tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  const btn = document.querySelector('.tab-btn[data-tab="tab-resultados"]');
  if (btn) btn.classList.add('active');
  document.getElementById('tab-resultados').classList.add('active');
}

// ----------------------------------------------------------- Inicializar Pyodide
async function inicializarPyodide() {
  try {
    setStatus('loading', 'Cargando motor Pyodide...');
    while (typeof loadPyodide === 'undefined') {
      await new Promise(r => setTimeout(r, 50));
    }

    pyodide = await loadPyodide({
      indexURL: "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/"
    });

    setStatus('loading', 'Cargando biblioteca NumPy...');
    await pyodide.loadPackage("numpy");

    setStatus('loading', 'Cargando módulos portico2d...');
    try {
      pyodide.FS.mkdirTree('/home/pyodide/portico2d');
    } catch (e) {}

    const modulos = ['__init__.py', 'modelo.py', 'solver.py', 'informe.py', 'dibujo.py'];
    for (const mod of modulos) {
      const resp = await fetch(`py/portico2d/${mod}`);
      if (!resp.ok) throw new Error(`Error al cargar ${mod} (HTTP ${resp.status})`);
      const txt = await resp.text();
      pyodide.FS.writeFile(`/home/pyodide/portico2d/${mod}`, txt);
    }

    // Configurar Python y función de análisis
    setStatus('loading', 'Configurando entorno Python...');
    pyodide.runPython(`
import sys
if '/home/pyodide' not in sys.path:
    sys.path.insert(0, '/home/pyodide')

import json
import numpy as np
from portico2d.modelo import Modelo
from portico2d.solver import analizar, esfuerzos
from portico2d.informe import html_pasos

def resolver_modelo_json(json_str):
    datos = json.loads(json_str)
    modelo = Modelo.de_dict(datos)
    res = analizar(modelo)
    
    # 1. Pasos 1–14 de informe.py
    try:
        pasos_html = html_pasos(res)
    except Exception as e:
        pasos_html = f"<p style='color:red;'>Error al generar pasos: {e}</p>"

    # 2. Datos de diagramas desde esfuerzos()
    barras_diag = []
    for rb in res.barras:
        xs, N, V, M, v, u = esfuerzos(rb, npts=101)
        barras_diag.append({
            "id": int(rb.id),
            "i": int(rb.i),
            "j": int(rb.j),
            "xi": float(rb.geo.xi),
            "yi": float(rb.geo.yi),
            "L": float(rb.geo.L),
            "c": float(rb.geo.c),
            "s": float(rb.geo.s),
            "bi": float(rb.bi),
            "bj": float(rb.bj),
            "xs": xs.tolist(),
            "N": N.tolist(),
            "V": V.tolist(),
            "M": M.tolist(),
            "v": v.tolist(),
            "u": u.tolist(),
        })

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
                "L": float(b.geo.L),
                "q": b.q.tolist(),
                "filas": list(b.filas)
            }
            for b in res.barras
        ],
        "q": {str(b.id): b.q.tolist() for b in res.barras},
        "reacciones": {str(k): list(v) for k, v in res.reacciones.items()},
        "u_nudos": {str(k): list(v) for k, v in res.u_nudos.items()},
        "html_pasos": pasos_html,
        "diagramas_barras": barras_diag
    }
    return json.dumps(salida)
`);

    setStatus('ready', 'Listo para calcular');
    btnResolver.disabled = false;

    // Cargar ejemplo por defecto (Aplicación 2)
    await cargarEjemploDesdeServidor(selEjemplo.value, false);

    // Modos de test automatizado
    const params = new URLSearchParams(window.location.search);
    if (params.get('test_todos') === '1') {
      await ejecutarTestTodos();
    } else if (params.get('test') === '1' || params.get('autorun') === '1') {
      await resolver();
    }
  } catch (err) {
    console.error("Fallo al iniciar Pyodide:", err);
    setStatus('error', `Error: ${err.message}`);
  }
}

// ----------------------------------------------------------- Gestión del Estado
function actualizarBadges() {
  badgeNudos.textContent = modeloActual.nudos.length;
  badgeBarras.textContent = modeloActual.barras.length;
  const totalCargas = (modeloActual.cargas_nudo?.length || 0) +
                      (modeloActual.cargas_repartidas?.length || 0) +
                      (modeloActual.cargas_puntuales?.length || 0);
  badgeCargas.textContent = totalCargas;
}

function cargarModelo(obj, autoCalcular = true) {
  modeloActual = {
    titulo: obj.titulo || "Modelo sin título",
    ea_infinito: obj.ea_infinito !== undefined ? Boolean(obj.ea_infinito) : true,
    nudos: (obj.nudos || []).map(n => ({
      id: Number(n.id),
      x: Number(n.x) || 0,
      y: Number(n.y) || 0,
      apoyo: n.apoyo || "libre"
    })),
    barras: (obj.barras || []).map(b => ({
      id: Number(b.id),
      i: Number(b.i),
      j: Number(b.j),
      EI: Number(b.EI) || 3000.0,
      EA: Number(b.EA) || 1e8,
      rot_i: Boolean(b.rot_i),
      rot_j: Boolean(b.rot_j),
      bi: Number(b.bi || b.brazo_i) || 0.0,
      bj: Number(b.bj || b.brazo_j) || 0.0
    })),
    cargas_nudo: (obj.cargas_nudo || []).map(c => ({
      nudo: Number(c.nudo),
      Fx: Number(c.Fx) || 0.0,
      Fy: Number(c.Fy) || 0.0,
      M: Number(c.M) || 0.0
    })),
    cargas_repartidas: (obj.cargas_repartidas || []).map(c => ({
      barra: Number(c.barra),
      w: Number(c.w) || 0.0,
      w2: c.w2 !== null && c.w2 !== undefined ? Number(c.w2) : null,
      a: Number(c.a) || 0.0,
      b: c.b !== null && c.b !== undefined && c.b !== 0 ? Number(c.b) : null,
      direccion: c.direccion || "global Y"
    })),
    cargas_puntuales: (obj.cargas_puntuales || []).map(c => ({
      barra: Number(c.barra),
      P: Number(c.P) || 0.0,
      a: Number(c.a) || 0.0,
      direccion: c.direccion || "global Y"
    }))
  };

  modeloTituloInput.value = modeloActual.titulo;
  modeloEaInfInput.checked = modeloActual.ea_infinito;

  renderizarTodasLasTablas();
  if (autoCalcular && pyodide) {
    resolver();
  }
}

async function cargarEjemploDesdeServidor(nombreArchivo, autoCalcular = true) {
  try {
    setStatus('loading', `Cargando ${nombreArchivo}...`);
    const resp = await fetch(`ejemplos/${nombreArchivo}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    cargarModelo(data, autoCalcular);
    setStatus('ready', `Cargado: ${nombreArchivo}`);
  } catch (err) {
    console.error("Error al cargar ejemplo:", err);
    setStatus('error', `Error: ${err.message}`);
  }
}

// ----------------------------------------------------------- Renderizado de Tablas
function renderizarTodasLasTablas() {
  renderizarTablaNudos();
  renderizarTablaBarras();
  renderizarTablaCargas();
  actualizarBadges();
}

function renderizarTablaNudos() {
  tablaNudosBody.innerHTML = '';
  modeloActual.nudos.forEach((n, idx) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><input type="number" class="tbl-input" value="${n.id}" data-idx="${idx}" data-field="id" style="width: 50px;"></td>
      <td><input type="number" step="any" class="tbl-input" value="${n.x}" data-idx="${idx}" data-field="x"></td>
      <td><input type="number" step="any" class="tbl-input" value="${n.y}" data-idx="${idx}" data-field="y"></td>
      <td>
        <select class="tbl-input" data-idx="${idx}" data-field="apoyo">
          ${APOYOS.map(ap => `<option value="${ap}" ${ap === n.apoyo ? 'selected' : ''}>${ap}</option>`).join('')}
        </select>
      </td>
      <td style="text-align: center;">
        <button class="btn-icon-danger" onclick="eliminarNudo(${idx})" title="Eliminar nudo">✕</button>
      </td>
    `;
    tablaNudosBody.appendChild(tr);
  });

  tablaNudosBody.querySelectorAll('input, select').forEach(el => {
    el.addEventListener('change', e => {
      const idx = Number(e.target.dataset.idx);
      const field = e.target.dataset.field;
      modeloActual.nudos[idx][field] = field === 'apoyo' ? e.target.value : Number(e.target.value);
    });
  });
}

window.eliminarNudo = function(idx) {
  modeloActual.nudos.splice(idx, 1);
  renderizarTablaNudos();
  actualizarBadges();
};

document.getElementById('btn-agregar-nudo').addEventListener('click', () => {
  const maxId = modeloActual.nudos.reduce((max, n) => Math.max(max, n.id), 0);
  modeloActual.nudos.push({ id: maxId + 1, x: 0, y: 0, apoyo: 'libre' });
  renderizarTablaNudos();
  actualizarBadges();
});

function obtenerExtremosNombre(rot_i, rot_j) {
  if (rot_i && rot_j) return "rótula i y j (armadura)";
  if (rot_i) return "rótula en i";
  if (rot_j) return "rótula en j";
  return "rígido–rígido";
}

function renderizarTablaBarras() {
  tablaBarrasBody.innerHTML = '';
  modeloActual.barras.forEach((b, idx) => {
    const extremosActual = obtenerExtremosNombre(b.rot_i, b.rot_j);
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><input type="number" class="tbl-input" value="${b.id}" data-idx="${idx}" data-field="id" style="width: 45px;"></td>
      <td><input type="number" class="tbl-input" value="${b.i}" data-idx="${idx}" data-field="i" style="width: 55px;"></td>
      <td><input type="number" class="tbl-input" value="${b.j}" data-idx="${idx}" data-field="j" style="width: 55px;"></td>
      <td><input type="number" step="any" class="tbl-input" value="${b.EI}" data-idx="${idx}" data-field="EI"></td>
      <td><input type="number" step="any" class="tbl-input" value="${b.EA}" data-idx="${idx}" data-field="EA"></td>
      <td>
        <select class="tbl-input" data-idx="${idx}" data-field="extremos">
          ${EXTREMOS.map(ex => `<option value="${ex}" ${ex === extremosActual ? 'selected' : ''}>${ex}</option>`).join('')}
        </select>
      </td>
      <td><input type="number" step="any" class="tbl-input" value="${b.bi}" data-idx="${idx}" data-field="bi"></td>
      <td><input type="number" step="any" class="tbl-input" value="${b.bj}" data-idx="${idx}" data-field="bj"></td>
      <td style="text-align: center;">
        <button class="btn-icon-danger" onclick="eliminarBarra(${idx})" title="Eliminar barra">✕</button>
      </td>
    `;
    tablaBarrasBody.appendChild(tr);
  });

  tablaBarrasBody.querySelectorAll('input, select').forEach(el => {
    el.addEventListener('change', e => {
      const idx = Number(e.target.dataset.idx);
      const field = e.target.dataset.field;
      if (field === 'extremos') {
        const val = e.target.value;
        modeloActual.barras[idx].rot_i = val === "rótula en i" || val === "rótula i y j (armadura)";
        modeloActual.barras[idx].rot_j = val === "rótula en j" || val === "rótula i y j (armadura)";
      } else {
        modeloActual.barras[idx][field] = Number(e.target.value);
      }
    });
  });
}

window.eliminarBarra = function(idx) {
  modeloActual.barras.splice(idx, 1);
  renderizarTablaBarras();
  actualizarBadges();
};

document.getElementById('btn-agregar-barra').addEventListener('click', () => {
  const maxId = modeloActual.barras.reduce((max, b) => Math.max(max, b.id), 0);
  modeloActual.barras.push({
    id: maxId + 1,
    i: 1,
    j: 2,
    EI: 3000.0,
    EA: 1e8,
    rot_i: false,
    rot_j: false,
    bi: 0.0,
    bj: 0.0
  });
  renderizarTablaBarras();
  actualizarBadges();
});

function renderizarTablaCargas() {
  tablaCargasNudoBody.innerHTML = '';
  modeloActual.cargas_nudo.forEach((c, idx) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><input type="number" class="tbl-input" value="${c.nudo}" data-idx="${idx}" data-tipo="nudo" data-field="nudo" style="width: 60px;"></td>
      <td><input type="number" step="any" class="tbl-input" value="${c.Fx}" data-idx="${idx}" data-tipo="nudo" data-field="Fx"></td>
      <td><input type="number" step="any" class="tbl-input" value="${c.Fy}" data-idx="${idx}" data-tipo="nudo" data-field="Fy"></td>
      <td><input type="number" step="any" class="tbl-input" value="${c.M}" data-idx="${idx}" data-tipo="nudo" data-field="M"></td>
      <td style="text-align: center;">
        <button class="btn-icon-danger" onclick="eliminarCargaNudo(${idx})">✕</button>
      </td>
    `;
    tablaCargasNudoBody.appendChild(tr);
  });

  tablaCargasRepartidasBody.innerHTML = '';
  modeloActual.cargas_repartidas.forEach((c, idx) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><input type="number" class="tbl-input" value="${c.barra}" data-idx="${idx}" data-tipo="rep" data-field="barra" style="width: 55px;"></td>
      <td><input type="number" step="any" class="tbl-input" value="${c.w}" data-idx="${idx}" data-tipo="rep" data-field="w"></td>
      <td><input type="number" step="any" class="tbl-input" value="${c.w2 !== null ? c.w2 : ''}" placeholder="=w₁" data-idx="${idx}" data-tipo="rep" data-field="w2"></td>
      <td><input type="number" step="any" class="tbl-input" value="${c.a || 0}" data-idx="${idx}" data-tipo="rep" data-field="a"></td>
      <td><input type="number" step="any" class="tbl-input" value="${c.b !== null ? c.b : ''}" placeholder="fin" data-idx="${idx}" data-tipo="rep" data-field="b"></td>
      <td>
        <select class="tbl-input" data-idx="${idx}" data-tipo="rep" data-field="direccion">
          ${DIRECCIONES.map(d => `<option value="${d}" ${d === c.direccion ? 'selected' : ''}>${d}</option>`).join('')}
        </select>
      </td>
      <td style="text-align: center;">
        <button class="btn-icon-danger" onclick="eliminarCargaRepartida(${idx})">✕</button>
      </td>
    `;
    tablaCargasRepartidasBody.appendChild(tr);
  });

  tablaCargasPuntualesBody.innerHTML = '';
  modeloActual.cargas_puntuales.forEach((c, idx) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><input type="number" class="tbl-input" value="${c.barra}" data-idx="${idx}" data-tipo="punt" data-field="barra" style="width: 55px;"></td>
      <td><input type="number" step="any" class="tbl-input" value="${c.P}" data-idx="${idx}" data-tipo="punt" data-field="P"></td>
      <td><input type="number" step="any" class="tbl-input" value="${c.a}" data-idx="${idx}" data-tipo="punt" data-field="a"></td>
      <td>
        <select class="tbl-input" data-idx="${idx}" data-tipo="punt" data-field="direccion">
          ${DIRECCIONES.map(d => `<option value="${d}" ${d === c.direccion ? 'selected' : ''}>${d}</option>`).join('')}
        </select>
      </td>
      <td style="text-align: center;">
        <button class="btn-icon-danger" onclick="eliminarCargaPuntual(${idx})">✕</button>
      </td>
    `;
    tablaCargasPuntualesBody.appendChild(tr);
  });

  document.querySelectorAll('#tab-cargas input, #tab-cargas select').forEach(el => {
    el.addEventListener('change', e => {
      const idx = Number(e.target.dataset.idx);
      const tipo = e.target.dataset.tipo;
      const field = e.target.dataset.field;
      const rawVal = e.target.value.trim();

      if (tipo === 'nudo') {
        modeloActual.cargas_nudo[idx][field] = Number(rawVal);
      } else if (tipo === 'rep') {
        if (field === 'direccion') {
          modeloActual.cargas_repartidas[idx][field] = rawVal;
        } else if (field === 'w2' || field === 'b') {
          modeloActual.cargas_repartidas[idx][field] = rawVal === '' ? null : Number(rawVal);
        } else {
          modeloActual.cargas_repartidas[idx][field] = Number(rawVal);
        }
      } else if (tipo === 'punt') {
        if (field === 'direccion') {
          modeloActual.cargas_puntuales[idx][field] = rawVal;
        } else {
          modeloActual.cargas_puntuales[idx][field] = Number(rawVal);
        }
      }
    });
  });
}

window.eliminarCargaNudo = function(idx) {
  modeloActual.cargas_nudo.splice(idx, 1);
  renderizarTablaCargas();
  actualizarBadges();
};

window.eliminarCargaRepartida = function(idx) {
  modeloActual.cargas_repartidas.splice(idx, 1);
  renderizarTablaCargas();
  actualizarBadges();
};

window.eliminarCargaPuntual = function(idx) {
  modeloActual.cargas_puntuales.splice(idx, 1);
  renderizarTablaCargas();
  actualizarBadges();
};

document.getElementById('btn-agregar-carga-nudo').addEventListener('click', () => {
  modeloActual.cargas_nudo.push({ nudo: 1, Fx: 0, Fy: -10, M: 0 });
  renderizarTablaCargas();
  actualizarBadges();
});

document.getElementById('btn-agregar-carga-repartida').addEventListener('click', () => {
  modeloActual.cargas_repartidas.push({
    barra: 1,
    w: -10,
    w2: null,
    a: 0,
    b: null,
    direccion: "perpendicular (y local)"
  });
  renderizarTablaCargas();
  actualizarBadges();
});

document.getElementById('btn-agregar-carga-puntual').addEventListener('click', () => {
  modeloActual.cargas_puntuales.push({
    barra: 1,
    P: -20,
    a: 2.0,
    direccion: "global Y"
  });
  renderizarTablaCargas();
  actualizarBadges();
});

modeloTituloInput.addEventListener('change', e => {
  modeloActual.titulo = e.target.value;
});

modeloEaInfInput.addEventListener('change', e => {
  modeloActual.ea_infinito = e.target.checked;
});

// ----------------------------------------------------------- Abrir y Guardar JSON
btnAbrirJson.addEventListener('click', () => inputArchivo.click());

inputArchivo.addEventListener('change', e => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = ev => {
    try {
      const data = JSON.parse(ev.target.result);
      cargarModelo(data, true);
    } catch (err) {
      alert("Error al leer JSON: " + err.message);
    }
  };
  reader.readAsText(file);
  e.target.value = '';
});

btnGuardarJson.addEventListener('click', () => {
  const dataToSave = {
    titulo: modeloActual.titulo || "Modelo",
    nudos: modeloActual.nudos.map(n => ({
      id: Number(n.id),
      x: Number(n.x),
      y: Number(n.y),
      apoyo: n.apoyo
    })),
    barras: modeloActual.barras.map(b => ({
      id: Number(b.id),
      i: Number(b.i),
      j: Number(b.j),
      EI: Number(b.EI),
      EA: Number(b.EA),
      rot_i: Boolean(b.rot_i),
      rot_j: Boolean(b.rot_j),
      bi: Number(b.bi || 0),
      bj: Number(b.bj || 0)
    })),
    cargas_nudo: modeloActual.cargas_nudo.map(c => ({
      nudo: Number(c.nudo),
      Fx: Number(c.Fx || 0),
      Fy: Number(c.Fy || 0),
      M: Number(c.M || 0)
    })),
    cargas_repartidas: modeloActual.cargas_repartidas.map(c => {
      const r = { barra: Number(c.barra), w: Number(c.w), direccion: c.direccion || "global Y" };
      if (c.w2 !== null && c.w2 !== undefined) r.w2 = Number(c.w2);
      if (c.a) r.a = Number(c.a);
      if (c.b) r.b = Number(c.b);
      return r;
    }),
    cargas_puntuales: modeloActual.cargas_puntuales.map(c => ({
      barra: Number(c.barra),
      P: Number(c.P),
      a: Number(c.a),
      direccion: c.direccion || "global Y"
    })),
    ea_infinito: Boolean(modeloActual.ea_infinito)
  };

  const jsonStr = JSON.stringify(dataToSave, null, 2);
  const blob = new Blob([jsonStr], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  const nombreLimpio = (modeloActual.titulo || "modelo").toLowerCase().replace(/[^a-z0-9]/g, '_');
  a.href = url;
  a.download = `${nombreLimpio}.json`;
  a.click();
  URL.revokeObjectURL(url);
});

// Botón Exportar PDF (vista de impresión @media print)
btnExportarPdf.addEventListener('click', () => {
  const meta = document.getElementById('print-meta');
  if (meta) {
    const fecha = new Date().toLocaleString('es-PE');
    meta.textContent = `${modeloActual.titulo} · EA = ${modeloActual.ea_infinito ? '∞' : 'finito'} · Impreso: ${fecha}`;
  }
  window.print();
});

selEjemplo.addEventListener('change', () => {
  cargarEjemploDesdeServidor(selEjemplo.value, true);
});

// ----------------------------------------------------------- Resolver Modelo
async function resolver(cambiarPestana = false) {
  if (!pyodide) return null;

  btnResolver.disabled = true;
  setStatus('loading', 'Resolviendo estructura...');
  tiempoCalc.textContent = '';

  try {
    const jsonStr = JSON.stringify(modeloActual);

    const t0 = performance.now();
    const resolverFn = pyodide.globals.get('resolver_modelo_json');
    const resJsonStr = resolverFn(jsonStr);
    const t1 = performance.now();

    const resultado = JSON.parse(resJsonStr);
    ultimoResultado = resultado;
    window.__ultimoResultado = resultado;

    renderizarResultados(resultado, t1 - t0);
    renderizarPasos(resultado.html_pasos);
    actualizarDiagrama();

    setStatus('success', `Resuelto en ${(t1 - t0).toFixed(1)} ms`);

    if (cambiarPestana) {
      activarPestanaResultados();
    }

    const params = new URLSearchParams(window.location.search);
    if (params.get('test') === '1') {
      await fetch('/api/resultado', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(resultado)
      });
    }

    return resultado;
  } catch (err) {
    console.error("Error durante el cálculo:", err);
    setStatus('error', `Fallo: ${err.message}`);
    return null;
  } finally {
    btnResolver.disabled = false;
  }
}

// ----------------------------------------------------------- Renderizar Resultados Numéricos
function renderizarResultados(res, tiempoMs) {
  tiempoCalc.textContent = `${tiempoMs.toFixed(1)} ms`;

  // 1. Vector {D}
  elVectorD.innerHTML = '';
  if (res.D.length === 0) {
    elVectorD.innerHTML = '<p style="color: var(--text-muted); font-size: 0.85rem;">0 GDL libres.</p>';
  } else {
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
  }

  // 2. Fuerzas en extremos {q}
  const es6 = res.barras.length > 0 && res.barras[0].q.length === 6;
  if (es6) {
    tablaQHead.innerHTML = `
      <tr>
        <th>Barra</th>
        <th>N_i (t)</th>
        <th>V_i (t)</th>
        <th>M_i (t·m)</th>
        <th>N_j (t)</th>
        <th>V_j (t)</th>
        <th>M_j (t·m)</th>
      </tr>
    `;
  } else {
    tablaQHead.innerHTML = `
      <tr>
        <th>Barra</th>
        <th>V_i (t)</th>
        <th>M_i (t·m)</th>
        <th>V_j (t)</th>
        <th>M_j (t·m)</th>
      </tr>
    `;
  }

  tablaQBody.innerHTML = '';
  res.barras.forEach(b => {
    const tr = document.createElement('tr');
    let cols = `<td><strong>Barra ${b.id}</strong> (${b.i} → ${b.j})</td>`;
    b.q.forEach(v => {
      cols += `<td class="mono-num">${v.toFixed(4)}</td>`;
    });
    tr.innerHTML = cols;
    tablaQBody.appendChild(tr);
  });

  // 3. Reacciones en apoyos
  tablaReacBody.innerHTML = '';
  Object.keys(res.reacciones).sort((a,b) => Number(a)-Number(b)).forEach(nid => {
    const r = res.reacciones[nid];
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>Nudo ${nid}</strong></td>
      <td class="mono-num">${r[0].toFixed(3)}</td>
      <td class="mono-num">${r[1].toFixed(3)}</td>
      <td class="mono-num">${r[2].toFixed(3)}</td>
    `;
    tablaReacBody.appendChild(tr);
  });

  // 4. Desplazamientos nodales {u}
  tablaUNudosBody.innerHTML = '';
  Object.keys(res.u_nudos).sort((a,b) => Number(a)-Number(b)).forEach(nid => {
    const u = res.u_nudos[nid];
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>Nudo ${nid}</strong></td>
      <td class="mono-num">${u[0].toFixed(6)}</td>
      <td class="mono-num">${u[1].toFixed(6)}</td>
      <td class="mono-num">${u[2].toFixed(6)}</td>
    `;
    tablaUNudosBody.appendChild(tr);
  });

  // 5. Matriz [K] y Vector {R}
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
}

// ----------------------------------------------------------- Hito 3: Renderizar Pasos (informe.py)
function renderizarPasos(html) {
  if (!pasosContenedor) return;
  if (html) {
    pasosContenedor.innerHTML = html;
  } else {
    pasosContenedor.innerHTML = '<p style="color: var(--text-muted);">Sin datos de pasos.</p>';
  }
}

// ----------------------------------------------------------- Hito 4: Diagramas Interactivos con Zoom
let viewBoxState = { x: 0, y: 0, w: 800, h: 500, origX: 0, origY: 0, origW: 800, origH: 500 };

document.querySelectorAll('.diag-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.diag-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    diagramaActual = btn.getAttribute('data-diag');
    actualizarDiagrama();
  });
});

function actualizarDiagrama() {
  if (!ultimoResultado || !ultimoResultado.diagramas_barras) return;
  dibujarDiagramaSVG(diagramaActual);
}

function dibujarDiagramaSVG(tipo) {
  const nudos = modeloActual.nudos;
  if (!nudos || nudos.length === 0) return;

  // 1. Calcular caja envolvente en coordenadas reales
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  nudos.forEach(n => {
    if (n.x < minX) minX = n.x;
    if (n.x > maxX) maxX = n.x;
    if (n.y < minY) minY = n.y;
    if (n.y > maxY) maxY = n.y;
  });

  const spanX = Math.max(maxX - minX, 1.0);
  const spanY = Math.max(maxY - minY, 1.0);
  const spanMax = Math.max(spanX, spanY);

  const W = 800, H = 500;
  const pad = 90;
  const escala = Math.min((W - 2 * pad) / spanX, (H - 2 * pad) / spanY);

  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  const toSvgX = (x) => W / 2 + (x - cx) * escala;
  const toSvgY = (y) => H / 2 - (y - cy) * escala; // Y invertida hacia arriba

  let svgContent = '';

  // Cuadrícula sutil
  svgContent += `<defs>
    <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
      <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.03)" stroke-width="1"/>
    </pattern>
    <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="#38bdf8"/>
    </marker>
    <marker id="arrow-red" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="#f43f5e"/>
    </marker>
  </defs>
  <rect width="100%" height="100%" fill="url(#grid)" />`;

  // Factor de escala para diagramas de esfuerzos
  let valMaxAbs = 1e-12;
  const diagBarras = ultimoResultado.diagramas_barras || [];
  diagBarras.forEach(b => {
    if (tipo === 'DMF') b.M.forEach(v => valMaxAbs = Math.max(valMaxAbs, Math.abs(v)));
    if (tipo === 'DFC') b.V.forEach(v => valMaxAbs = Math.max(valMaxAbs, Math.abs(v)));
    if (tipo === 'DFN') b.N.forEach(v => valMaxAbs = Math.max(valMaxAbs, Math.abs(v)));
    if (tipo === 'def') b.v.forEach(v => valMaxAbs = Math.max(valMaxAbs, Math.abs(v)));
  });

  const escalaEsfuerzo = (0.15 * spanMax) / (valMaxAbs > 0 ? valMaxAbs : 1.0);

  // 2. Dibujar estructura base (ejes de barras)
  diagBarras.forEach(b => {
    const xi = toSvgX(b.xi), yi = toSvgY(b.yi);
    const xj = toSvgX(b.xi + b.L * b.c), yj = toSvgY(b.yi + b.L * b.s);

    // Eje de la barra
    svgContent += `<line x1="${xi}" y1="${yi}" x2="${xj}" y2="${yj}" stroke="#334155" stroke-width="4" stroke-linecap="round"/>`;

    // Brazos rígidos
    if (b.bi > 0) {
      const xbi = toSvgX(b.xi + b.bi * b.c), ybi = toSvgY(b.yi + b.bi * b.s);
      svgContent += `<line x1="${xi}" y1="${yi}" x2="${xbi}" y2="${ybi}" stroke="#0f172a" stroke-width="8" stroke-linecap="square"/>`;
    }
    if (b.bj > 0) {
      const xbj = toSvgX(b.xi + (b.L - b.bj) * b.c), ybj = toSvgY(b.yi + (b.L - b.bj) * b.s);
      svgContent += `<line x1="${xbj}" y1="${ybj}" x2="${xj}" y2="${yj}" stroke="#0f172a" stroke-width="8" stroke-linecap="square"/>`;
    }

    // 3. Dibujar diagramas específicos
    if (tipo === 'def') {
      // Deformada
      let defPath = '';
      for (let k = 0; k < b.xs.length; k++) {
        const x_k = b.xs[k];
        const v_k = b.v[k] * escalaEsfuerzo;
        const u_k = b.u[k] * escalaEsfuerzo;
        const x_def = b.xi + x_k * b.c - v_k * b.s + u_k * b.c;
        const y_def = b.yi + x_k * b.s + v_k * b.c + u_k * b.s;
        const sx = toSvgX(x_def), sy = toSvgY(y_def);
        defPath += (k === 0 ? `M ${sx} ${sy}` : ` L ${sx} ${sy}`);
      }
      svgContent += `<path d="${defPath}" fill="none" stroke="#a855f7" stroke-width="3" stroke-linecap="round"/>`;
    } else if (tipo === 'DMF' || tipo === 'DFC' || tipo === 'DFN') {
      // Diagramas DMF, DFC, DFN con polígonos sombreados
      const valores = tipo === 'DMF' ? b.M : (tipo === 'DFC' ? b.V : b.N);
      const colorTrazo = tipo === 'DMF' ? '#ef4444' : (tipo === 'DFC' ? '#38bdf8' : '#14b8a6');
      const colorRelleno = tipo === 'DMF' ? 'rgba(239, 68, 68, 0.2)' : (tipo === 'DFC' ? 'rgba(56, 189, 248, 0.2)' : 'rgba(20, 184, 166, 0.2)');

      // Perpendicular local: (-s, c)
      // M > 0 tracciona cara -y (lado de tracción)
      const signo = tipo === 'DMF' ? -1 : 1;

      let poligono = `M ${xi} ${yi}`;
      let curvaD = '';
      for (let k = 0; k < b.xs.length; k++) {
        const x_k = b.xs[k];
        const val = valores[k] * escalaEsfuerzo * signo;
        const x_curva = (b.xi + x_k * b.c) + val * (-b.s);
        const y_curva = (b.yi + x_k * b.s) + val * b.c;
        const sx = toSvgX(x_curva), sy = toSvgY(y_curva);
        poligono += ` L ${sx} ${sy}`;
        curvaD += (k === 0 ? `M ${sx} ${sy}` : ` L ${sx} ${sy}`);
      }
      poligono += ` L ${xj} ${yj} Z`;

      svgContent += `<path d="${poligono}" fill="${colorRelleno}" stroke="none"/>`;
      svgContent += `<path d="${curvaD}" fill="none" stroke="${colorTrazo}" stroke-width="2"/>`;

      // Texto de valores en extremos de barra
      const vIni = valores[0], vFin = valores[valores.length - 1];
      if (Math.abs(vIni) > 0.05) {
        const x0 = toSvgX((b.xi) + vIni * escalaEsfuerzo * signo * (-b.s));
        const y0 = toSvgY((b.yi) + vIni * escalaEsfuerzo * signo * b.c);
        svgContent += `<text x="${x0}" y="${y0 - 6}" fill="${colorTrazo}" font-size="11" font-family="JetBrains Mono" font-weight="600" text-anchor="middle">${vIni.toFixed(1)}</text>`;
      }
      if (Math.abs(vFin) > 0.05) {
        const x1 = toSvgX((b.xi + b.L * b.c) + vFin * escalaEsfuerzo * signo * (-b.s));
        const y1 = toSvgY((b.yi + b.L * b.s) + vFin * escalaEsfuerzo * signo * b.c);
        svgContent += `<text x="${x1}" y="${y1 - 6}" fill="${colorTrazo}" font-size="11" font-family="JetBrains Mono" font-weight="600" text-anchor="middle">${vFin.toFixed(1)}</text>`;
      }
    }
  });

  // 4. Dibujar apoyos y nudos
  nudos.forEach(n => {
    const sx = toSvgX(n.x), sy = toSvgY(n.y);
    const ap = n.apoyo;

    // Símbolos de apoyos
    if (ap === 'empotrado') {
      svgContent += `<line x1="${sx - 16}" y1="${sy + 10}" x2="${sx + 16}" y2="${sy + 10}" stroke="#94a3b8" stroke-width="3"/>`;
      for (let dx = -14; dx <= 14; dx += 6) {
        svgContent += `<line x1="${sx + dx}" y1="${sy + 10}" x2="${sx + dx - 6}" y2="${sy + 18}" stroke="#64748b" stroke-width="1.5"/>`;
      }
    } else if (ap === 'articulado') {
      svgContent += `<polygon points="${sx},${sy} ${sx - 10},${sy + 16} ${sx + 10},${sy + 16}" fill="none" stroke="#94a3b8" stroke-width="2"/>`;
      svgContent += `<line x1="${sx - 14}" y1="${sy + 17}" x2="${sx + 14}" y2="${sy + 17}" stroke="#94a3b8" stroke-width="2"/>`;
    } else if (ap.startsWith('rodillo')) {
      svgContent += `<polygon points="${sx},${sy} ${sx - 10},${sy + 13} ${sx + 10},${sy + 13}" fill="none" stroke="#94a3b8" stroke-width="2"/>`;
      svgContent += `<circle cx="${sx - 5}" cy="${sy + 17}" r="3" fill="none" stroke="#94a3b8" stroke-width="1.5"/>`;
      svgContent += `<circle cx="${sx + 5}" cy="${sy + 17}" r="3" fill="none" stroke="#94a3b8" stroke-width="1.5"/>`;
      svgContent += `<line x1="${sx - 14}" y1="${sy + 22}" x2="${sx + 14}" y2="${sy + 22}" stroke="#94a3b8" stroke-width="2"/>`;
    }

    // Reacciones si tipo == 'reacciones'
    if (tipo === 'reacciones' && ultimoResultado.reacciones[n.id]) {
      const r = ultimoResultado.reacciones[n.id];
      const rx = r[0], ry = r[1], mz = r[2];

      if (Math.abs(rx) > 0.01) {
        const dir = rx > 0 ? 1 : -1;
        const x1 = sx - dir * 45, x2 = sx - dir * 6;
        svgContent += `<line x1="${x1}" y1="${sy}" x2="${x2}" y2="${sy}" stroke="#38bdf8" stroke-width="2.5" marker-end="url(#arrow)"/>`;
        svgContent += `<text x="${x1}" y="${sy - 8}" fill="#38bdf8" font-size="11" font-family="JetBrains Mono" font-weight="600">Rx=${rx.toFixed(2)}t</text>`;
      }
      if (Math.abs(ry) > 0.01) {
        const dir = ry > 0 ? 1 : -1;
        const y1 = sy + dir * 45, y2 = sy + dir * 6;
        svgContent += `<line x1="${sx}" y1="${y1}" x2="${sx}" y2="${y2}" stroke="#34d399" stroke-width="2.5" marker-end="url(#arrow)"/>`;
        svgContent += `<text x="${sx + 8}" y="${(y1 + y2) / 2}" fill="#34d399" font-size="11" font-family="JetBrains Mono" font-weight="600">Ry=${ry.toFixed(2)}t</text>`;
      }
      if (Math.abs(mz) > 0.01) {
        svgContent += `<circle cx="${sx}" cy="${sy}" r="18" fill="none" stroke="#fbbf24" stroke-width="2" stroke-dasharray="10 5"/>`;
        svgContent += `<text x="${sx + 20}" y="${sy - 15}" fill="#fbbf24" font-size="11" font-family="JetBrains Mono" font-weight="600">M=${mz.toFixed(2)}</text>`;
      }
    }

    // Círculo del nudo y etiqueta
    svgContent += `<circle cx="${sx}" cy="${sy}" r="5" fill="#38bdf8" stroke="#0b0f19" stroke-width="2"/>`;
    svgContent += `<text x="${sx + 8}" y="${sy - 8}" fill="#cbd5e1" font-size="11" font-family="Inter" font-weight="600">N${n.id}</text>`;
  });

  diagramaSvg.innerHTML = svgContent;

  // Actualizar estado de viewBox
  viewBoxState.origW = W;
  viewBoxState.origH = H;
  viewBoxState.w = W;
  viewBoxState.h = H;
  viewBoxState.x = 0;
  viewBoxState.y = 0;
  diagramaSvg.setAttribute('viewBox', `0 0 ${W} ${H}`);

  const nombres = {
    modelo: "Modelo geométrico y cargas",
    def: "Deformada elástica (flecha magnificada)",
    DMF: "Diagrama de Momentos Flectores [M] (t·m)",
    DFC: "Diagrama de Fuerzas Cortantes [V] (t)",
    DFN: "Diagrama de Fuerzas Normales [N] (t)",
    reacciones: "Reacciones en apoyos (Rx, Ry, Mz)"
  };
  diagramaInfo.textContent = `${nombres[tipo] || tipo} · Zoom: dos dedos o rueda`;
}

// ----------------------------------------------------------- Zoom con dos dedos y Pan Táctil
let touchStartDist = 0;
let isPanning = false;
let startPanX = 0, startPanY = 0;

function updateSvgViewBox() {
  diagramaSvg.setAttribute('viewBox', `${viewBoxState.x} ${viewBoxState.y} ${viewBoxState.w} ${viewBoxState.h}`);
}

diagramaWrapper.addEventListener('touchstart', e => {
  if (e.touches.length === 2) {
    // Inicio de pinch zoom
    touchStartDist = Math.hypot(
      e.touches[0].clientX - e.touches[1].clientX,
      e.touches[0].clientY - e.touches[1].clientY
    );
  } else if (e.touches.length === 1) {
    // Inicio de pan
    isPanning = true;
    startPanX = e.touches[0].clientX;
    startPanY = e.touches[0].clientY;
  }
}, { passive: false });

diagramaWrapper.addEventListener('touchmove', e => {
  if (e.touches.length === 2 && touchStartDist > 0) {
    e.preventDefault();
    const currentDist = Math.hypot(
      e.touches[0].clientX - e.touches[1].clientX,
      e.touches[0].clientY - e.touches[1].clientY
    );
    const factor = touchStartDist / currentDist;
    touchStartDist = currentDist;

    const newW = viewBoxState.w * factor;
    const newH = viewBoxState.h * factor;
    viewBoxState.x += (viewBoxState.w - newW) / 2;
    viewBoxState.y += (viewBoxState.h - newH) / 2;
    viewBoxState.w = newW;
    viewBoxState.h = newH;
    updateSvgViewBox();
  } else if (e.touches.length === 1 && isPanning) {
    e.preventDefault();
    const dx = (e.touches[0].clientX - startPanX) * (viewBoxState.w / 800);
    const dy = (e.touches[0].clientY - startPanY) * (viewBoxState.h / 500);
    viewBoxState.x -= dx;
    viewBoxState.y -= dy;
    startPanX = e.touches[0].clientX;
    startPanY = e.touches[0].clientY;
    updateSvgViewBox();
  }
}, { passive: false });

diagramaWrapper.addEventListener('touchend', () => {
  isPanning = false;
  touchStartDist = 0;
});

// Zoom con rueda de ratón
diagramaWrapper.addEventListener('wheel', e => {
  e.preventDefault();
  const factor = e.deltaY > 0 ? 1.15 : 0.85;
  const newW = viewBoxState.w * factor;
  const newH = viewBoxState.h * factor;
  viewBoxState.x += (viewBoxState.w - newW) / 2;
  viewBoxState.y += (viewBoxState.h - newH) / 2;
  viewBoxState.w = newW;
  viewBoxState.h = newH;
  updateSvgViewBox();
}, { passive: false });

// Botones de zoom
document.getElementById('btn-zoom-in')?.addEventListener('click', () => {
  const newW = viewBoxState.w * 0.8;
  const newH = viewBoxState.h * 0.8;
  viewBoxState.x += (viewBoxState.w - newW) / 2;
  viewBoxState.y += (viewBoxState.h - newH) / 2;
  viewBoxState.w = newW;
  viewBoxState.h = newH;
  updateSvgViewBox();
});

document.getElementById('btn-zoom-out')?.addEventListener('click', () => {
  const newW = viewBoxState.w * 1.25;
  const newH = viewBoxState.h * 1.25;
  viewBoxState.x += (viewBoxState.w - newW) / 2;
  viewBoxState.y += (viewBoxState.h - newH) / 2;
  viewBoxState.w = newW;
  viewBoxState.h = newH;
  updateSvgViewBox();
});

document.getElementById('btn-zoom-reset')?.addEventListener('click', () => {
  viewBoxState.x = 0;
  viewBoxState.y = 0;
  viewBoxState.w = viewBoxState.origW;
  viewBoxState.h = viewBoxState.origH;
  updateSvgViewBox();
});

// ----------------------------------------------------------- Test Automatizado: TODOS los ejemplos
async function ejecutarTestTodos() {
  setStatus('loading', 'Ejecutando suite completa de validación (9 ejemplos)...');
  const resultadosTodos = {};

  for (const nombre of TODOS_LOS_EJEMPLOS) {
    try {
      const resp = await fetch(`ejemplos/${nombre}`);
      const jsonStr = await resp.text();
      const resolverFn = pyodide.globals.get('resolver_modelo_json');
      const resJsonStr = resolverFn(jsonStr);
      resultadosTodos[nombre] = JSON.parse(resJsonStr);
    } catch (err) {
      resultadosTodos[nombre] = { error: err.message };
    }
  }

  try {
    await fetch('/api/resultado', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(resultadosTodos)
    });
    setStatus('success', 'Suite de 9 ejemplos resuelta y enviada');
  } catch (err) {
    setStatus('error', `Error al enviar resultados: ${err.message}`);
  }
}

// Botón de cálculo
btnResolver.addEventListener('click', () => resolver(true));

// Iniciar al cargar el DOM
window.addEventListener('DOMContentLoaded', inicializarPyodide);
