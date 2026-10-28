"""Figuras explicativas del método (como en las soluciones del profesor):

1. Numeración: nudos, barras y GDL globales; abajo, cada barra separada con su SR local
   y sus GDL locales numerados.
2. Configuraciones deformadas: D_j = 1 y los demás D = 0 (sirven para armar [A]).
3. Cargas de fijación {r}: cada barra cargada, empotrada en sus extremos, con sus reacciones.
"""
from __future__ import annotations
import os
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.patches import FancyArrowPatch, Arc

from .modelo import APOYOS
from .solver import (Resultado, geometria, matriz_rotacion, matriz_brazos, recuperar_giros,
                     liberados, _forma)
from . import dibujo as DB

C_GDL = "#7b2cbf"
C_LOC = "#2a9d8f"
C_DEF = "#1d2b53"


def _flecha(ax, a, b, color, lw=1.3, ms=10):
    ax.add_patch(FancyArrowPatch(tuple(a), tuple(b), arrowstyle="-|>", mutation_scale=ms, color=color,
                                 lw=lw, shrinkA=0, shrinkB=0, zorder=7))


def _giro(ax, p, r, color, antihorario=True, lw=1.2, centro=-90.0):
    """Flecha curva de giro alrededor de p (arco centrado en la dirección `centro`, en grados)."""
    t1, t2 = (centro - 70, centro + 70) if antihorario else (centro + 70, centro - 70)
    a1, a2 = np.radians(t1), np.radians(t2)
    ax.add_patch(FancyArrowPatch(tuple(p + r * np.array([np.cos(a1), np.sin(a1)])),
                                 tuple(p + r * np.array([np.cos(a2), np.sin(a2)])),
                                 arrowstyle="-|>", mutation_scale=9, color=color, lw=lw, zorder=7,
                                 connectionstyle=f"arc3,rad={0.9 if antihorario else -0.9}"))


def _ejes_globales(ax, m, s):
    x0 = min(n.x for n in m.nudos) - 0.22 * s
    y0 = min(n.y for n in m.nudos)
    _flecha(ax, (x0, y0), (x0 + 0.1 * s, y0), "#333333")
    _flecha(ax, (x0, y0), (x0, y0 + 0.1 * s), "#333333")
    ax.text(x0 + 0.11 * s, y0, "X", fontsize=9, va="center")
    ax.text(x0, y0 + 0.115 * s, "Y", fontsize=9, ha="center")


def _gdl_global(res: Resultado, j):
    """(nudo, componente) que representa a D_j."""
    T = res.gdl.T
    col = np.nonzero(T[:, j])[0]
    k = [kk for kk in col if abs(T[kk, j] - 1.0) < 1e-12]
    k = k[0] if k else col[0]
    g = res.gdl.libres[k]
    return res.modelo.nudos[g // 3], g % 3


def _guardar(fig, ruta, dpi):
    FigureCanvasAgg(fig)
    fig.savefig(ruta, dpi=dpi, bbox_inches="tight", facecolor="white")
    return ruta


# ------------------------------------------------------------------ 1. numeración
def figura_numeracion(res: Resultado, ruta: str, dpi=150):
    m = res.modelo
    s = DB._tam(m)
    fig = Figure(figsize=(9, 9.5))
    ax1, ax2 = fig.add_subplot(2, 1, 1), fig.add_subplot(2, 1, 2)
    # arriba: estructura con nudos, barras y GDL globales
    DB.dibujar_estructura(ax1, m, etiquetas=True)
    DB.dibujar_gdl(ax1, res)
    _ejes_globales(ax1, m, s)
    DB.ajustar_vista(ax1, m, margen=0.3)
    ax1.set_title("Nudos (○), barras (□) y GDL globales D (orden: X → Y → giros)", fontsize=10)
    ax1.axis("off")
    # abajo: barras separadas con SR local y GDL locales numerados
    c = np.mean([[n.x, n.y] for n in m.nudos], axis=0)
    k = 0
    xs, ys = [], []
    for rb in res.barras:
        b = m.barra(rb.id)
        g = rb.geo
        pi, pj = np.array([g.xi, g.yi]), np.array([g.xi, g.yi]) + g.t * g.L
        mid = (pi + pj) / 2
        off = (mid - c) * 0.45
        qi, qj = mid + off + (pi - mid) * 0.8, mid + off + (pj - mid) * 0.8
        ax2.plot(*zip(qi, qj), color=DB.C_BARRA, lw=2.2, zorder=3)
        xs += [qi[0], qj[0]]; ys += [qi[1], qj[1]]
        pm = (qi + qj) / 2
        ax2.text(*(pm - g.n * 0.045 * s), str(rb.id), fontsize=9, ha="center", va="center", color=DB.C_BARRA,
                 bbox=dict(boxstyle="square,pad=0.15", fc="white", ec=DB.C_BARRA, lw=0.8), zorder=8)
        for q, nid in ((qi, b.i), (qj, b.j)):
            DB.dibujar_apoyo(ax2, q[0], q[1], m.nudo(nid).apoyo, s * 0.8)
        # SR local
        o = qi + g.t * 0.22 * (qj - qi).dot(g.t) - g.n * 0.12 * s
        _flecha(ax2, o, o + g.t * 0.07 * s, C_LOC, lw=1, ms=8)
        _flecha(ax2, o, o + g.n * 0.07 * s, C_LOC, lw=1, ms=8)
        ax2.text(*(o + g.t * 0.085 * s), "x", color=C_LOC, fontsize=8, ha="center", va="center")
        ax2.text(*(o + g.n * 0.085 * s), "y", color=C_LOC, fontsize=8, ha="center", va="center")
        # GDL locales (mismo orden que las filas de [A])
        for nombre in rb.filas:
            k += 1
            q = qi if nombre.endswith("_i") else qj
            if nombre.startswith("u"):
                _flecha(ax2, q, q + g.t * 0.06 * s * (1 if nombre.endswith("_i") else -1) * -1, C_GDL, lw=1, ms=8)
                ax2.text(*(q - g.t * 0.08 * s * (1 if nombre.endswith("_i") else -1) - g.n * 0.02 * s),
                         str(k), color=C_GDL, fontsize=9, ha="center", va="center")
            elif nombre.startswith("v"):
                _flecha(ax2, q - g.n * 0.07 * s, q, C_GDL, lw=1, ms=8)
                ax2.text(*(q - g.n * 0.085 * s + g.t * 0.02 * s), str(k), color=C_GDL, fontsize=9,
                         ha="center", va="center")
            else:
                afuera = -g.t if nombre.endswith("_i") else g.t
                _giro(ax2, q, 0.035 * s, C_GDL, centro=np.degrees(np.arctan2(afuera[1], afuera[0])))
                ax2.text(*(q + afuera * 0.07 * s + g.n * 0.035 * s), str(k),
                         color=C_GDL, fontsize=9, ha="center", va="center")
    ax2.set_xlim(min(xs) - 0.2 * s, max(xs) + 0.2 * s)
    ax2.set_ylim(min(ys) - 0.2 * s, max(ys) + 0.15 * s)
    ax2.set_aspect("equal", adjustable="box")
    ax2.set_title("SR locales (x de nudo menor a mayor, y por la mano derecha) y GDL locales numerados",
                  fontsize=10)
    ax2.axis("off")
    fig.tight_layout()
    return _guardar(fig, ruta, dpi)


# ------------------------------------------------------- 2. configuraciones deformadas
def _forma_unitaria(res: Resultado, u):
    """Puntos (base, desplazamiento) de cada barra para el vector de nudos u."""
    m = res.modelo
    idx = {n.id: k for k, n in enumerate(m.nudos)}
    out = []
    for rb in res.barras:
        b = m.barra(rb.id)
        g = rb.geo
        dofs = [3 * idx[b.i] + c for c in range(3)] + [3 * idx[b.j] + c for c in range(3)]
        dn = matriz_rotacion(g) @ u[dofs]
        Lf = rb.Lf or g.L
        d = recuperar_giros(b.EI, Lf, matriz_brazos(b.bi, b.bj) @ dn, np.zeros(6), liberados(b, 6))
        p0 = np.array([g.xi, g.yi])
        tramos = []
        if b.bi > 0:
            x = np.linspace(0, b.bi, 5)
            tramos.append((x, dn[0] + 0 * x, dn[1] + dn[2] * x))
        xf = np.linspace(0, Lf, 60)
        N = np.array([_forma(x, Lf) for x in xf])
        tramos.append((b.bi + xf, N[:, 0] * d[0] + N[:, 3] * d[3],
                       N[:, 1] * d[1] + N[:, 2] * d[2] + N[:, 4] * d[4] + N[:, 5] * d[5]))
        if b.bj > 0:
            x = np.linspace(g.L - b.bj, g.L, 5)
            tramos.append((x, dn[3] + 0 * x, dn[4] - dn[5] * (g.L - x)))
        x = np.concatenate([t[0] for t in tramos])
        ua = np.concatenate([t[1] for t in tramos])
        v = np.concatenate([t[2] for t in tramos])
        base = p0[None] + np.outer(x, g.t)
        out.append((base, np.outer(ua, g.t) + np.outer(v, g.n)))
    return out


def figura_configuracion(res: Resultado, j: int, ruta: str, dpi=130):
    m = res.modelo
    s = DB._tam(m)
    nD = res.gdl.T.shape[1]
    u = np.zeros(3 * len(m.nudos))
    u[res.gdl.libres] = res.gdl.T[:, j]
    formas = _forma_unitaria(res, u)
    dmax = max(np.max(np.hypot(*d.T)) for _, d in formas)
    esc = 0.12 * s / dmax if dmax > 1e-12 else 0.0
    fig = Figure(figsize=(8, 4.6))
    ax = fig.add_subplot(111)
    DB.dibujar_estructura(ax, m, etiquetas=False, lw=1.6)
    for base, d in formas:
        p = base + d * esc
        ax.plot(p[:, 0], p[:, 1], color=C_DEF, lw=1.3, ls="--", zorder=4)
    n, comp = _gdl_global(res, j)
    p = np.array([n.x, n.y])
    if comp == 2:
        _giro(ax, p, 0.06 * s, "#2a9d2a", lw=1.4)
        ax.text(*(p + np.array([0.0, 0.085 * s])), "1", color="#2a9d2a", fontsize=10, ha="center")
    else:
        dvec = np.array([1.0, 0.0]) if comp == 0 else np.array([0.0, 1.0])
        lado = np.array([0.0, 0.07 * s]) if comp == 0 else np.array([0.07 * s, 0.0])
        a, b = p + lado, p + lado + dvec * esc
        ax.annotate("", b, a, arrowprops=dict(arrowstyle="|-|", color="#2a9d2a", lw=1.2, mutation_scale=4))
        ax.text(*((a + b) / 2 + lado * 0.4), "1", color="#2a9d2a", fontsize=10, ha="center", va="center")
    otros = [f"D{k + 1}" for k in range(nD) if k != j]
    ax.set_title(f"D{j + 1} = 1" + (", " + " = ".join(otros) + " = 0" if otros else ""), fontsize=11, loc="left")
    DB.ajustar_vista(ax, m, margen=0.22)
    ax.axis("off")
    fig.tight_layout()
    return _guardar(fig, ruta, dpi)


# ------------------------------------------------------- 3. cargas de fijación
def _momento(ax, x, valor, lado, r=0.38, color="#1d2b53"):
    """Momento de empotramiento en el extremo (lado −1 = i, +1 = j). valor > 0 = antihorario."""
    ccw = valor > 0
    y1, y2 = (r, -r) if (ccw and lado < 0) or (not ccw and lado > 0) else (-r, r)
    f = lado * 0.8 * np.sign(y2 - y1)
    ax.add_patch(FancyArrowPatch((x, y1), (x, y2), arrowstyle="-|>", mutation_scale=9, color=color, lw=1.1,
                                 connectionstyle=f"arc3,rad={f}", zorder=6))


def figura_fijacion(res: Resultado, ruta: str, dpi=150):
    """Cada barra cargada, empotrada, con sus cargas y su {r} (ejes locales)."""
    cargadas = [rb for rb in res.barras if rb.cargas]
    if not cargadas:
        return None
    nc = min(3, len(cargadas))
    nf = int(np.ceil(len(cargadas) / nc))
    fig = Figure(figsize=(3.6 * nc, 2.5 * nf))
    LD = 4.0
    for k, rb in enumerate(cargadas):
        ax = fig.add_subplot(nf, nc, k + 1)
        L = rb.geo.L
        e = LD / L
        ax.plot([0, LD], [0, 0], color=DB.C_BARRA, lw=2.4)
        for x0 in (0, LD):
            ax.plot([x0, x0], [-0.25, 0.25], color="#888888", lw=0.8)
        pymax = max([abs(c[2]) for c in rb.cargas if c[0] == "w"] + [abs(c[4]) for c in rb.cargas if c[0] == "w"]
                    + [1e-12])
        for c in rb.cargas:
            if c[0] == "w":
                _, px1, py1, px2, py2, a, b = c
                if abs(py1) + abs(py2) > 1e-12:
                    sg = np.sign(py1 if abs(py1) >= abs(py2) else py2)
                    xs = np.linspace(a * e, b * e, 8)
                    hs = [0.9 * abs(py1 + (py2 - py1) * (x / e - a) / max(b - a, 1e-12)) / pymax for x in xs]
                    for x, h in zip(xs, hs):
                        if h > 0.08:
                            _flecha(ax, (x, -sg * h), (x, -sg * 0.03), DB.C_CARGA, lw=0.9, ms=7)
                    ax.plot(xs, [-sg * h for h in hs], color=DB.C_CARGA, lw=0.9)
                    txt = f"{abs(py1):g}" if abs(py1 - py2) < 1e-12 else f"{abs(py1):g}→{abs(py2):g}"
                    ax.text((a + 0.25 * (b - a)) * e, -sg * 1.15, f"{txt} t/m", color=DB.C_CARGA, fontsize=8, ha="center",
                            va="center")
                if abs(px1) + abs(px2) > 1e-12:
                    ax.text((a + b) / 2 * e, 0.12, f"axial {px1:g} t/m", color=DB.C_CARGA, fontsize=7, ha="center")
            else:
                _, Px, Py, a = c
                if abs(Py) > 1e-12:
                    sg = np.sign(Py)
                    _flecha(ax, (a * e, -sg * 1.35), (a * e, -sg * 0.03), DB.C_CARGA, lw=1.4, ms=10)
                    ax.text(a * e + 0.1, -sg * 1.4, f"{abs(Py):.4g} t", color=DB.C_CARGA, fontsize=8,
                            va="center")
                if abs(Px) > 1e-12:
                    _flecha(ax, (a * e - 0.6 * np.sign(Px), 0.15), (a * e, 0.15), DB.C_CARGA, lw=1.2, ms=9)
                    ax.text(a * e, 0.3, f"{abs(Px):.4g} t", color=DB.C_CARGA, fontsize=8, ha="center")
        r = rb.r6
        for x0, (N, V, M), lado in ((0, r[0:3], -1), (LD, r[3:6], 1)):
            if abs(V) > 1e-9:
                sg = np.sign(V)
                _flecha(ax, (x0, -sg * 1.0), (x0, -sg * 0.03), "#1d2b53", lw=1.1, ms=8)
                ax.text(x0 + 0.1 * (-lado), -sg * 0.85, f"{abs(V):.2f}", fontsize=8, color="#1d2b53",
                        ha="right" if lado > 0 else "left")
            if abs(M) > 1e-9:
                _momento(ax, x0, M, lado)
                ax.text(x0 + lado * 0.55, 0.45, f"{abs(M):.2f}", fontsize=8, color="#1d2b53",
                        ha="left" if lado > 0 else "right")
            if abs(N) > 1e-9:
                sg = np.sign(N)
                _flecha(ax, (x0 - sg * 0.6, -0.12), (x0, -0.12), "#1d2b53", lw=1, ms=8)
                ax.text(x0 - sg * 0.3, -0.35, f"{abs(N):.3g}", fontsize=7, color="#1d2b53", ha="center")
        # ejes locales
        _flecha(ax, (-0.9, -1.25), (-0.4, -1.25), C_LOC, lw=0.9, ms=7)
        _flecha(ax, (-0.9, -1.25), (-0.9, -0.75), C_LOC, lw=0.9, ms=7)
        ax.text(-0.33, -1.3, "x", color=C_LOC, fontsize=7)
        ax.text(-1.05, -0.75, "y", color=C_LOC, fontsize=7)
        ax.set_title(f"Barra {rb.id} ({rb.i}→{rb.j}), L = {L:.4g} m", fontsize=9)
        ax.set_xlim(-1.2, LD + 1.2)
        ax.set_ylim(-1.6, 1.6)
        ax.set_aspect("equal")
        ax.axis("off")
    fig.suptitle("Cargas de fijación {r} en ejes locales (barra empotrada en sus dos extremos)", fontsize=10)
    fig.tight_layout()
    return _guardar(fig, ruta, dpi)


def generar(res: Resultado, carpeta: str, dpi=130) -> dict:
    """Crea todas las figuras del método y devuelve sus rutas."""
    os.makedirs(carpeta, exist_ok=True)
    out = {"numeracion": figura_numeracion(res, os.path.join(carpeta, "fig_numeracion.png"), dpi),
           "configuraciones": [figura_configuracion(res, j, os.path.join(carpeta, f"fig_D{j + 1}.png"), dpi)
                               for j in range(res.gdl.T.shape[1])],
           "fijacion": figura_fijacion(res, os.path.join(carpeta, "fig_fijacion.png"), dpi)}
    return out
