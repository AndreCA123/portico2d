"""Dibujo del modelo y de los diagramas sobre un Axes de matplotlib."""
from __future__ import annotations
import numpy as np
from matplotlib.patches import FancyArrowPatch, Arc, Polygon, Circle

from .modelo import Modelo, APOYOS
from .solver import geometria, componentes_locales, esfuerzos, Resultado, tramo_repartida

C_BARRA = "#1d2b53"
C_CARGA = "#d62828"
C_APOYO = "#3a3a3a"
C_SEL = "#f77f00"
COLOR_DIAG = {"DMF": "#c1121f", "DFC": "#1f6fb2", "DFN": "#2a9d8f", "def": "#7b2cbf"}


def _tam(m: Modelo):
    xs = [n.x for n in m.nudos] or [0, 1]
    ys = [n.y for n in m.nudos] or [0, 1]
    return max(max(xs) - min(xs), max(ys) - min(ys), 1.0)


def _flecha(ax, a, b, color, lw=1.5, ms=12, z=5):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=ms, color=color,
                                 lw=lw, shrinkA=0, shrinkB=0, zorder=z))


def dibujar_apoyo(ax, x, y, tipo, s):
    if tipo == "libre":
        return
    h = 0.06 * s
    if tipo in ("empotrado", "guía (fija X y giro)", "guía (fija Y y giro)"):
        ax.plot([x - h, x + h], [y, y], color=C_APOYO, lw=2.2, zorder=4)
        for k in np.linspace(-h, h, 6):
            ax.plot([x + k, x + k - h * 0.4], [y, y - h * 0.5], color=C_APOYO, lw=1, zorder=4)
    elif tipo == "articulado":
        ax.add_patch(Polygon([[x, y], [x - h * 0.8, y - h * 1.2], [x + h * 0.8, y - h * 1.2]],
                             closed=True, fill=False, ec=C_APOYO, lw=1.6, zorder=4))
        ax.plot([x - h, x + h], [y - h * 1.2, y - h * 1.2], color=C_APOYO, lw=1.6)
    elif tipo.startswith("rodillo (fija Y"):
        ax.add_patch(Polygon([[x, y], [x - h * 0.8, y - h * 1.0], [x + h * 0.8, y - h * 1.0]],
                             closed=True, fill=False, ec=C_APOYO, lw=1.6, zorder=4))
        for dx in (-0.45, 0.45):
            ax.add_patch(Circle((x + dx * h, y - h * 1.2), h * 0.18, fill=False, ec=C_APOYO))
        ax.plot([x - h, x + h], [y - h * 1.42, y - h * 1.42], color=C_APOYO, lw=1.6)
    elif tipo.startswith("rodillo (fija X"):
        ax.add_patch(Polygon([[x, y], [x - h * 1.0, y - h * 0.8], [x - h * 1.0, y + h * 0.8]],
                             closed=True, fill=False, ec=C_APOYO, lw=1.6, zorder=4))
        for dy in (-0.45, 0.45):
            ax.add_patch(Circle((x - h * 1.2, y + dy * h), h * 0.18, fill=False, ec=C_APOYO))
        ax.plot([x - h * 1.42, x - h * 1.42], [y - h, y + h], color=C_APOYO, lw=1.6)
    if tipo.startswith("guía"):
        ax.text(x, y - h * 1.1, "guía", ha="center", va="top", fontsize=7, color=C_APOYO)


def dibujar_estructura(ax, m: Modelo, seleccion=None, etiquetas=True, gris=False, lw=2.6):
    s = _tam(m)
    col = "#9aa3b5" if gris else C_BARRA
    for b in m.barras:
        try:
            ni, nj = m.nudo(b.i), m.nudo(b.j)
        except KeyError:
            continue
        c = C_SEL if seleccion == ("barra", b.id) else col
        ax.plot([ni.x, nj.x], [ni.y, nj.y], color=c, lw=lw, solid_capstyle="round", zorder=3)
        dibujar_detalles_barra(ax, m, b, s, c, lw)
        if etiquetas and not gris:
            xm, ym = (ni.x + nj.x) / 2, (ni.y + nj.y) / 2
            try:
                g = geometria(m, b)
            except Exception:
                continue
            p = np.array([xm, ym]) - g.n * 0.045 * s
            ax.text(*p, str(b.id), ha="center", va="center", fontsize=9, color=C_BARRA,
                    bbox=dict(boxstyle="square,pad=0.15", fc="white", ec=C_BARRA, lw=0.8), zorder=6)
    for n in m.nudos:
        dibujar_apoyo(ax, n.x, n.y, n.apoyo, s)
        c = C_SEL if seleccion == ("nudo", n.id) else col
        ax.plot(n.x, n.y, "o", color=c, ms=5, zorder=5)
        if etiquetas and not gris:
            ax.text(n.x + 0.03 * s, n.y + 0.03 * s, str(n.id), fontsize=9, color=C_BARRA,
                    bbox=dict(boxstyle="circle,pad=0.15", fc="white", ec=C_BARRA, lw=0.8), zorder=6)


def dibujar_detalles_barra(ax, m: Modelo, b, s, col, lw):
    """Brazos rígidos (trazo grueso) y rótulas (círculo hueco) de una barra."""
    try:
        g = geometria(m, b)
    except Exception:
        return
    p0, t = np.array([g.xi, g.yi]), g.t
    bi, bj = getattr(b, "bi", 0.0) or 0.0, getattr(b, "bj", 0.0) or 0.0
    for a0, a1 in ((0.0, bi), (g.L - bj, g.L)):
        if a1 - a0 > 1e-9:
            q0, q1 = p0 + t * a0, p0 + t * a1
            ax.plot([q0[0], q1[0]], [q0[1], q1[1]], color="black", lw=lw * 2.4,
                    solid_capstyle="butt", zorder=3.5)
    r = 0.014 * s
    for rot, x in ((getattr(b, "rot_i", False), bi + 1.6 * r), (getattr(b, "rot_j", False), g.L - bj - 1.6 * r)):
        if rot:
            ax.add_patch(Circle(p0 + t * x, r, fc="white", ec=col, lw=1.4, zorder=6))


def dibujar_ejes_locales(ax, m: Modelo):
    """Flechas x (a lo largo de la barra, de nudo menor a mayor) e y (mano derecha) en cada barra."""
    s = _tam(m)
    lx = 0.07 * s
    for b in m.barras:
        try:
            g = geometria(m, b)
        except Exception:
            continue
        p = np.array([g.xi, g.yi]) + g.t * g.L * 0.3
        _flecha(ax, p, p + g.t * lx, "#2a9d8f", lw=1.1, ms=8, z=6)
        _flecha(ax, p, p + g.n * lx * 0.75, "#2a9d8f", lw=1.1, ms=8, z=6)
        ax.text(*(p + g.t * lx * 1.25 + g.n * 0.025 * s), "x", color="#2a9d8f", fontsize=8, ha="center", va="center")
        ax.text(*(p + g.n * lx * 1.0), "y", color="#2a9d8f", fontsize=8, ha="center", va="center")


def dibujar_cargas(ax, m: Modelo):
    s = _tam(m)
    Lf = 0.12 * s
    for c in m.cargas_nudo:
        try:
            n = m.nudo(c.nudo)
        except KeyError:
            continue
        p = np.array([n.x, n.y])
        if abs(c.Fx) > 0:
            d = np.array([np.sign(c.Fx), 0])
            _flecha(ax, p - d * Lf, p - d * 0.01 * s, C_CARGA)
            ax.text(*(p - d * Lf * 1.05), f"{abs(c.Fx):g} t", color=C_CARGA, fontsize=8,
                    ha="right" if c.Fx > 0 else "left", va="bottom")
        if abs(c.Fy) > 0:
            d = np.array([0, np.sign(c.Fy)])
            _flecha(ax, p - d * Lf, p - d * 0.01 * s, C_CARGA)
            ax.text(*(p - d * Lf * 1.05), f"{abs(c.Fy):g} t", color=C_CARGA, fontsize=8, ha="left")
        if abs(c.M) > 0:
            r = 0.05 * s
            ax.add_patch(Arc(p, 2 * r, 2 * r, theta1=30, theta2=300, color=C_CARGA, lw=1.4))
            ang = np.radians(300 if c.M > 0 else 30)
            tip = p + r * np.array([np.cos(ang), np.sin(ang)])
            tang = np.array([-np.sin(ang), np.cos(ang)]) * (1 if c.M > 0 else -1)
            _flecha(ax, tip - tang * 0.01 * s, tip + tang * 0.012 * s, C_CARGA, ms=9)
            ax.text(p[0] + r, p[1] + r, f"{abs(c.M):g} t·m", color=C_CARGA, fontsize=8)
    for cr in m.cargas_repartidas:
        try:
            b = m.barra(cr.barra)
            g = geometria(m, b)
        except Exception:
            continue
        p0 = np.array([g.xi, g.yi])
        a, bb, w2 = tramo_repartida(cr, g.L)
        bb = min(bb, g.L)
        wref = cr.w if abs(cr.w) >= abs(w2) else w2
        if cr.direccion.startswith("perpendicular"):
            d = g.n * np.sign(wref)
        elif cr.direccion.startswith("axial"):
            d = g.t * np.sign(wref)
        elif cr.direccion == "global X":
            d = np.array([np.sign(wref), 0.0])
        else:
            d = np.array([0.0, np.sign(wref)])
        wmax = max(abs(cr.w), abs(w2), 1e-12)
        h = 0.07 * s
        xs = np.linspace(a, bb, max(4, int((bb - a) / s * 14) + 2))
        alt = [h * abs(cr.w + (w2 - cr.w) * (x - a) / max(bb - a, 1e-12)) / wmax for x in xs]
        for x, hx in zip(xs, alt):
            p = p0 + g.t * x
            if hx > 0.12 * h:
                _flecha(ax, p - d * hx, p - d * 0.005 * s, C_CARGA, lw=0.9, ms=7)
        tope = np.array([p0 + g.t * x - d * hx for x, hx in zip(xs, alt)])
        ax.plot(tope[:, 0], tope[:, 1], color=C_CARGA, lw=0.9)
        if abs(w2 - cr.w) < 1e-12:
            pm = p0 + g.t * (a + bb) / 2 - d * h * 1.35
            ax.text(*pm, f"{abs(cr.w):g} t/m", color=C_CARGA, fontsize=8, ha="center", va="center")
        else:
            for x, w, hx in ((a, cr.w, alt[0]), (bb, w2, alt[-1])):
                if abs(w) > 1e-12:
                    ax.text(*(p0 + g.t * x - d * (hx + 0.03 * s)), f"{abs(w):g} t/m", color=C_CARGA,
                            fontsize=8, ha="center", va="center")
    for cp in m.cargas_puntuales:
        try:
            b = m.barra(cp.barra)
            g = geometria(m, b)
        except Exception:
            continue
        p = np.array([g.xi, g.yi]) + g.t * cp.a
        if cp.direccion.startswith("perpendicular"):
            d = g.n * np.sign(cp.P)
        elif cp.direccion.startswith("axial"):
            d = g.t * np.sign(cp.P)
        elif cp.direccion == "global X":
            d = np.array([np.sign(cp.P), 0.0])
        else:
            d = np.array([0.0, np.sign(cp.P)])
        _flecha(ax, p - d * Lf, p - d * 0.008 * s, C_CARGA)
        ax.text(*(p - d * Lf * 1.08), f"{abs(cp.P):g} t", color=C_CARGA, fontsize=8,
                ha="center", va="center")


def dibujar_gdl(ax, res: Resultado):
    """Flechas de los D independientes."""
    m = res.modelo
    s = _tam(m)
    for j, et in enumerate(res.gdl.etiquetas):
        col = np.nonzero(res.gdl.T[:, j])[0]
        k = [kk for kk in col if res.gdl.T[kk, j] == 1.0]
        k = k[0] if k else col[0]
        g = res.gdl.libres[k]
        n = m.nudos[g // 3]
        p = np.array([n.x, n.y])
        comp = g % 3
        if comp == 2:
            r = 0.045 * s
            ax.add_patch(Arc(p, 2 * r, 2 * r, theta1=200, theta2=340, color="#7b2cbf", lw=1.4))
            ax.text(p[0] + r * 0.2, p[1] - r * 1.9, f"D{j + 1}", color="#7b2cbf", fontsize=9)
        else:
            d = np.array([1.0, 0.0]) if comp == 0 else np.array([0.0, 1.0])
            off = np.array([0.0, 0.09 * s]) if comp == 0 else np.array([0.08 * s, 0.0])
            _flecha(ax, p + off, p + off + d * 0.1 * s, "#7b2cbf", lw=1.4, ms=10)
            ax.text(*(p + off + d * 0.11 * s), f"D{j + 1}", color="#7b2cbf", fontsize=9)


def _escala(res: Resultado, valores, frac=0.12):
    vmax = max((np.max(np.abs(v)) for v in valores), default=0.0)
    return 0.0 if vmax < 1e-9 else frac * _tam(res.modelo) / vmax


def dibujar_diagrama(ax, res: Resultado, tipo: str, lado_traccion=True, decimales=2):
    """tipo: 'DMF', 'DFC', 'DFN' o 'def'."""
    m = res.modelo
    dibujar_estructura(ax, m, etiquetas=False, gris=True, lw=1.6)
    datos = [(rb, *esfuerzos(rb)) for rb in res.barras]
    col = COLOR_DIAG[tipo]
    if tipo == "def":
        umax = max((max(np.max(np.abs(v)), np.max(np.abs(u))) for _, _, _, _, _, v, u in datos), default=0)
        esc = 0.0 if umax < 1e-12 else 0.08 * _tam(m) / umax
        for rb, xs, N, V, M, v, u in datos:
            g = rb.geo
            p0 = np.array([g.xi, g.yi])
            pts = p0[None] + np.outer(xs + u * esc, g.t) + np.outer(v * esc, g.n)
            ax.plot(pts[:, 0], pts[:, 1], color=col, lw=2, zorder=4)
        for n in m.nudos:
            ux, uy, th = res.u_nudos[n.id]
            if abs(ux) + abs(uy) + abs(th) < 1e-14:
                continue
            ax.text(n.x + ux * esc, n.y + uy * esc,
                    f" u={ux:.5f}\n v={uy:.5f}\n θ={th:.5f}", fontsize=7.5, color=col, va="bottom")
        ax.set_title(f"Deformada (amplificada ×{esc:.0f}) – u, v en m; θ en rad", fontsize=10)
        return
    idx = {"DFN": 2, "DFC": 3, "DMF": 4}[tipo]
    vals = [d[idx] for d in datos]
    esc = _escala(res, vals)
    usados = []
    for (rb, xs, N, V, M, v, u), val in zip(datos, vals):
        g = rb.geo
        p0 = np.array([g.xi, g.yi])
        d = -g.n if (tipo == "DMF" and lado_traccion) else g.n
        base = p0[None] + np.outer(xs, g.t)
        pts = base + np.outer(val * esc, d)
        ax.fill(np.r_[base[:, 0], pts[::-1, 0]], np.r_[base[:, 1], pts[::-1, 1]],
                color=col, alpha=0.18, lw=0, zorder=2)
        ax.plot(pts[:, 0], pts[:, 1], color=col, lw=1.5, zorder=3)
        ax.plot([base[0, 0], pts[0, 0]], [base[0, 1], pts[0, 1]], color=col, lw=1, zorder=3)
        ax.plot([base[-1, 0], pts[-1, 0]], [base[-1, 1], pts[-1, 1]], color=col, lw=1, zorder=3)
        # índices a etiquetar: extremos, bajo cargas puntuales y extremo interior
        marcar = {0, len(xs) - 1}
        corr = {}
        for c in rb.cargas:
            if c[0] == "P":
                k = int(np.argmin(np.abs(xs - c[3])))
                k1, k2 = max(k - 1, 0), min(k + 1, len(xs) - 1)
                marcar.update({k1, k2})
                corr[k1], corr[k2] = -0.05, 0.05
        kint = int(np.argmax(np.abs(val)))
        if 0 < kint < len(xs) - 1:
            marcar.add(kint)
        if tipo == "DMF":
            for c in rb.cargas:
                if c[0] == "w":
                    dV = np.where(np.diff(np.sign(V)) != 0)[0]
                    for k in dV:
                        marcar.add(int(k))
        for k in sorted(marcar):
            if abs(val[k]) < 10 ** -decimales / 2:
                continue
            p = pts[k] + d * np.sign(val[k]) * 0.035 * _tam(m) + g.t * corr.get(k, 0) * _tam(m)
            if any(np.hypot(*(p - q)) < 0.1 * _tam(m) and abs(vv - val[k]) < 0.01 for q, vv in usados):
                continue
            usados.append((p, val[k]))
            ax.text(*p, f"{val[k]:.{decimales}f}", fontsize=8, color=col, ha="center",
                    va="center", fontweight="bold", zorder=7)
        if tipo == "DMF" and 0 < kint < len(xs) - 1 and any(c[0] == "w" for c in rb.cargas):
            ax.text(*(pts[kint] + d * np.sign(val[kint]) * 0.07 * _tam(m)),
                    f"x={xs[kint]:.2f} m", fontsize=7, color=col, ha="center", zorder=7)
    titulos = {"DMF": "Diagrama de Momento Flector (t·m)" + (" – lado de la tracción" if lado_traccion else ""),
               "DFC": "Diagrama de Fuerza Cortante (t)", "DFN": "Diagrama de Fuerza Normal (t)  (− compresión)"}
    ax.set_title(titulos[tipo], fontsize=10)


def dibujar_reacciones(ax, res: Resultado):
    m = res.modelo
    dibujar_estructura(ax, m, etiquetas=True)
    s = _tam(m)
    for nid, (Rx, Ry, Mz) in res.reacciones.items():
        n = m.nudo(nid)
        p = np.array([n.x, n.y])
        txt = []
        if abs(Rx) > 1e-6:
            d = np.array([np.sign(Rx), 0])
            _flecha(ax, p - d * 0.12 * s - [0, 0.04 * s], p - [0, 0.04 * s], "#2a9d8f")
            txt.append(f"Rx = {Rx:.2f} t")
        if abs(Ry) > 1e-6:
            d = np.array([0, np.sign(Ry)])
            _flecha(ax, p - d * 0.12 * s - [0.03 * s, 0], p - [0.03 * s, 0], "#2a9d8f")
            txt.append(f"Ry = {Ry:.2f} t")
        if abs(Mz) > 1e-6:
            txt.append(f"M = {Mz:.2f} t·m {'↺' if Mz > 0 else '↻'}")
        ax.text(p[0] + 0.04 * s, p[1] - 0.16 * s, "\n".join(txt), fontsize=8, color="#2a9d8f", va="top")
    ax.set_title("Reacciones (X →+, Y ↑+, antihorario +)", fontsize=10)


def ajustar_vista(ax, m: Modelo, margen=0.25):
    xs = [n.x for n in m.nudos] or [0, 1]
    ys = [n.y for n in m.nudos] or [0, 1]
    s = _tam(m)
    ax.set_xlim(min(xs) - margen * s, max(xs) + margen * s)
    ax.set_ylim(min(ys) - margen * s, max(ys) + margen * s)
    ax.set_aspect("equal", adjustable="box")
