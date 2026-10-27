"""Método de rigidez sistematizado (notación del curso):

  {d} = [A]{D}      [K]e = [A]ᵀ[k][A]      [K] = Σ[K]e
  {R} = Σ[A]ᵀ{r}    {F} = {Q} − {R}        {D} = [K]⁻¹{F}
  {q} = [k]{d} + {r}

Convención global: X → +, Y ↑ +, giro antihorario +.
Convención local: x de i a j; y = x girado 90° antihorario.
{r} = fuerzas que el empotramiento ejerce sobre la barra [N_i, V_i, M_i, N_j, V_j, M_j].

Con EA = ∞ las barras no cambian de longitud: los desplazamientos de los nudos
quedan ligados y se eligen GDL independientes (como D1 = desplazamiento lateral).
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np

from .modelo import Modelo, APOYOS

TOL = 1e-10


class ErrorAnalisis(Exception):
    pass


# ---------------------------------------------------------------- geometría
@dataclass
class Geo:
    xi: float
    yi: float
    L: float
    c: float
    s: float

    @property
    def t(self):
        return np.array([self.c, self.s])

    @property
    def n(self):
        return np.array([-self.s, self.c])


def geometria(m: Modelo, b) -> Geo:
    ni, nj = m.nudo(b.i), m.nudo(b.j)
    dx, dy = nj.x - ni.x, nj.y - ni.y
    L = float(np.hypot(dx, dy))
    if L < 1e-9:
        raise ErrorAnalisis(f"La barra {b.id} tiene longitud cero")
    return Geo(ni.x, ni.y, L, dx / L, dy / L)


def matriz_rotacion(g: Geo) -> np.ndarray:
    """[λ] 6×6: desplazamientos globales del elemento → locales."""
    r = np.array([[g.c, g.s, 0], [-g.s, g.c, 0], [0, 0, 1]])
    T = np.zeros((6, 6))
    T[:3, :3] = r
    T[3:, 3:] = r
    return T


def k_local6(EI, EA, L):
    a, b, c, d = 12 * EI / L**3, 6 * EI / L**2, 4 * EI / L, 2 * EI / L
    e = EA / L
    return np.array([
        [e, 0, 0, -e, 0, 0],
        [0, a, b, 0, -a, b],
        [0, b, c, 0, -b, d],
        [-e, 0, 0, e, 0, 0],
        [0, -a, -b, 0, a, -b],
        [0, b, d, 0, -b, c]])


def k_local4(EI, L):
    return k_local6(EI, 0.0, L)[np.ix_([1, 2, 4, 5], [1, 2, 4, 5])]


def matriz_brazos(bi: float, bj: float) -> np.ndarray:
    """[H] 6×6: desplazamientos locales de los nudos → extremos de la parte flexible.
    v'_i = v_i + b_i·θ_i ;  v'_j = v_j − b_j·θ_j  (brazos rígidos)."""
    H = np.eye(6)
    H[1, 2] = bi
    H[4, 5] = -bj
    return H


def liberados(b, n=6):
    """Índices locales con momento liberado (rótulas) para [k] de 6 ó 4 filas."""
    ii, jj = (2, 5) if n == 6 else (1, 3)
    return ([ii] if b.rot_i else []) + ([jj] if b.rot_j else [])


def condensar(k, r, lib):
    """Condensación estática: los GDL liberados (rótulas) tienen fuerza nula.
    [k]c = k_aa − k_ab·k_bb⁻¹·k_ba ;  {r}c = r_a − k_ab·k_bb⁻¹·r_b (filas liberadas = 0)."""
    if not lib:
        return k.copy(), r.copy()
    n = k.shape[0]
    a = [i for i in range(n) if i not in lib]
    kbb = np.linalg.inv(k[np.ix_(lib, lib)])
    kc = np.zeros_like(k)
    rc = np.zeros_like(r)
    kc[np.ix_(a, a)] = k[np.ix_(a, a)] - k[np.ix_(a, lib)] @ kbb @ k[np.ix_(lib, a)]
    rc[a] = r[a] - k[np.ix_(a, lib)] @ kbb @ r[lib]
    kc[np.abs(kc) < 1e-12 * max(np.max(np.abs(k)), 1)] = 0.0
    return kc, rc


def recuperar_giros(EI, Lf, d6, r6, lib6):
    """Giro de la barra en los extremos con rótula: k_bb·d_b = −(k_ba·d_a + r_b)."""
    if not lib6:
        return d6
    k = k_local6(EI, 1.0, Lf)
    a = [i for i in range(6) if i not in lib6]
    d = d6.copy()
    d[lib6] = -np.linalg.solve(k[np.ix_(lib6, lib6)], k[np.ix_(lib6, a)] @ d6[a] + r6[lib6])
    return d


# ------------------------------------------------------- cargas en barras
_GX, _GW = np.polynomial.legendre.leggauss(5)


def componentes_locales(direccion: str, valor: float, g: Geo):
    """Devuelve (px, py) en ejes locales para una carga de valor dado."""
    if direccion.startswith("perpendicular"):
        return 0.0, valor
    if direccion.startswith("axial"):
        return valor, 0.0
    if direccion == "global X":
        gx, gy = valor, 0.0
    elif direccion == "global Y":
        gx, gy = 0.0, valor
    else:
        raise ErrorAnalisis(f"Dirección desconocida: {direccion}")
    return g.c * gx + g.s * gy, -g.s * gx + g.c * gy


def tramo_repartida(cr, L):
    a = float(cr.a or 0.0)
    b = L if (cr.b is None or cr.b == 0) else float(cr.b)
    w2 = cr.w if cr.w2 is None else cr.w2
    return a, b, w2


def cargas_locales(m: Modelo, b, g: Geo):
    """Cargas de la barra en ejes locales; x desde el nudo i (longitud total L).
    ('w', px1, py1, px2, py2, a, b)  repartida lineal de a a b
    ('P', Px, Py, a)                 puntual"""
    L = g.L
    out = []
    for cr in m.cargas_repartidas:
        if cr.barra != b.id:
            continue
        a, bb, w2 = tramo_repartida(cr, L)
        if not (-1e-9 <= a < bb <= L + 1e-9):
            raise ErrorAnalisis(f"Repartida en barra {b.id}: tramo {a:g}…{bb:g} fuera de 0…{L:.3f}")
        cx, cy = componentes_locales(cr.direccion, 1.0, g)
        out.append(("w", cx * cr.w, cy * cr.w, cx * w2, cy * w2, max(a, 0.0), min(bb, L)))
    for cp in m.cargas_puntuales:
        if cp.barra != b.id:
            continue
        if not (-1e-9 <= cp.a <= L + 1e-9):
            raise ErrorAnalisis(f"Carga puntual en barra {b.id}: a = {cp.a} fuera de 0…{L:.3f}")
        Px, Py = componentes_locales(cp.direccion, cp.P, g)
        out.append(("P", Px, Py, min(max(cp.a, 0.0), L)))
    return out


def _forma(xi, L):
    """Funciones de forma (axial lineal, flexión Hermite) en orden [N, V, M, N, V, M]."""
    s = xi / L
    return np.array([1 - s, 1 - 3 * s**2 + 2 * s**3, L * (s - 2 * s**2 + s**3),
                     s, 3 * s**2 - 2 * s**3, L * (-s**2 + s**3)])


def _puntos_repartida(c, lo, hi):
    """Puntos de Gauss (x, peso, px, py) de la repartida c en el subtramo [lo, hi]."""
    _, px1, py1, px2, py2, a, b = c
    xs = (lo + hi) / 2 + (hi - lo) / 2 * _GX
    ws = (hi - lo) / 2 * _GW
    t = (xs - a) / (b - a)
    return xs, ws, px1 + (px2 - px1) * t, py1 + (py2 - py1) * t


def fuerzas_fijacion_flexible(cargas, x0, Lf):
    """{r} 6×1 de la parte flexible (empotrada en x0 y x0+Lf).
    {r} = −∫[N]ᵀ p dx (exacto para cargas lineales: equivale a las fórmulas de tablas)."""
    r = np.zeros(6)
    x1 = x0 + Lf
    for c in cargas:
        if c[0] == "P":
            _, Px, Py, a = c
            if x0 - 1e-9 <= a <= x1 + 1e-9:
                xi = min(max(a - x0, 0.0), Lf)
                r -= _forma(xi, Lf) * np.array([Px, Py, Py, Px, Py, Py])
        else:
            lo, hi = max(c[5], x0), min(c[6], x1)
            if hi - lo <= 1e-12:
                continue
            for xk, wk, pxk, pyk in zip(*_puntos_repartida(c, lo, hi)):
                r -= wk * _forma(xk - x0, Lf) * np.array([pxk, pyk, pyk, pxk, pyk, pyk])
    return r


def fuerzas_brazos(cargas, L, bi, bj):
    """{r} 6×1 en los nudos por las cargas aplicadas sobre los brazos rígidos
    (el brazo es parte del nudo: la carga pasa directo, con su momento)."""
    r = np.zeros(6)
    for lo, hi, xref, base in ((0.0, bi, 0.0, 0), (L - bj, L, L, 3)):
        if hi - lo <= 1e-12:
            continue
        F = np.zeros(3)
        for c in cargas:
            if c[0] == "P":
                _, Px, Py, a = c
                dentro = a < hi - 1e-9 if base == 0 else a > lo + 1e-9
                if dentro:
                    F += [Px, Py, Py * (a - xref)]
            else:
                l2, h2 = max(c[5], lo), min(c[6], hi)
                if h2 - l2 <= 1e-12:
                    continue
                xs, ws, px, py = _puntos_repartida(c, l2, h2)
                F += [np.sum(ws * px), np.sum(ws * py), np.sum(ws * py * (xs - xref))]
        r[base:base + 3] = -F
    return r


def fuerzas_fijacion(m: Modelo, b, g: Geo):
    """Compatibilidad v0.1: {r} local 6×1 (sin rótulas ni brazos) y cargas."""
    cargas = cargas_locales(m, b, g)
    return fuerzas_fijacion_flexible(cargas, 0.0, g.L), cargas


# ------------------------------------------------------------ GDL globales
def _rref(Mx, tol=1e-9):
    A = Mx.astype(float).copy()
    rows, cols = A.shape
    piv = []
    r = 0
    for c in range(cols):
        if r >= rows:
            break
        p = r + int(np.argmax(np.abs(A[r:, c])))
        if abs(A[p, c]) < tol:
            continue
        A[[r, p]] = A[[p, r]]
        A[r] /= A[r, c]
        for k in range(rows):
            if k != r:
                A[k] -= A[k, c] * A[r]
        piv.append(c)
        r += 1
    return A[:r], piv


@dataclass
class GDL:
    libres: list            # índices (3*k + comp) de GDL de nudo no restringidos
    T: np.ndarray           # u_libres = T · D
    etiquetas: list         # descripción de cada D
    nombres_dof: list       # nombre de cada GDL de nudo libre
    dependientes: list      # textos "v2 = −0.75·D1"


def giros_inactivos(m: Modelo) -> set:
    """Nudos cuyo giro no tiene rigidez: todas las barras que llegan tienen rótula en ese
    extremo (p. ej. nudos de armadura). Ese giro no es GDL."""
    inact = set()
    for n in m.nudos:
        if APOYOS[n.apoyo][2]:
            continue
        llegan = [(b.rot_i if b.i == n.id else b.rot_j) for b in m.barras if n.id in (b.i, b.j)]
        if all(llegan):
            inact.add(n.id)
    return inact


def libres_nudo(m: Modelo):
    """Lista de (nudo, componente) libres, sin los giros inactivos."""
    inact = giros_inactivos(m)
    return [(n.id, c) for n in m.nudos for c in range(3)
            if not APOYOS[n.apoyo][c] and not (c == 2 and n.id in inact)]


def gdl_globales(m: Modelo) -> GDL:
    idx = {n.id: k for k, n in enumerate(m.nudos)}
    inact = giros_inactivos(m)
    for c in m.cargas_nudo:
        if c.nudo in inact and abs(c.M) > 0:
            raise ErrorAnalisis(f"Momento aplicado en el nudo {c.nudo}, pero todas sus barras "
                                "tienen rótula ahí (el giro no tiene rigidez)")
    libres, nombres = [], []
    for nid, c in libres_nudo(m):
        libres.append(3 * idx[nid] + c)
        nombres.append((nid, c))
    pos = {g: k for k, g in enumerate(libres)}
    nl = len(libres)
    if nl == 0:
        raise ErrorAnalisis("No hay grados de libertad libres")

    tras = [k for k, g in enumerate(libres) if g % 3 != 2]
    rots = [k for k, g in enumerate(libres) if g % 3 == 2]
    indep = []
    dep_expr = {}
    if m.ea_infinito and tras:
        filas = []
        for b in m.barras:
            g = geometria(m, b)
            fila = np.zeros(nl)
            for sign, nid in ((-1, b.i), (1, b.j)):
                base = 3 * idx[nid]
                for c, coef in ((0, g.c), (1, g.s)):
                    if base + c in pos:
                        fila[pos[base + c]] += sign * coef
            if np.any(np.abs(fila) > TOL):
                filas.append(fila)
        # orden de columnas: primero verticales, luego horizontales
        # (las que quedan libres al final del RREF serán los D de traslación)
        verticales = [k for k in tras if libres[k] % 3 == 1]
        horizontales = [k for k in tras if libres[k] % 3 == 0]
        orden = verticales + horizontales[::-1]
        if filas:
            C = np.array(filas)[:, orden]
            R, piv = _rref(C)
            piv_cols = [orden[p] for p in piv]
            libres_tras = [orden[c] for c in range(len(orden)) if c not in piv]
            # expresión de cada dependiente en función de las libres
            for fila_r, p in zip(R, piv):
                dep_expr[orden[p]] = {orden[c]: -fila_r[c] for c in range(len(orden))
                                      if c not in piv and abs(fila_r[c]) > TOL}
            indep_tras = libres_tras
        else:
            indep_tras = tras
    else:
        indep_tras = tras
    # Regla del curso: primero los desplazamientos en X, luego en Y y al final los giros;
    # dentro de cada grupo, por número de nudo.
    orden_gdl = lambda k: (libres[k] % 3, nombres[k][0])
    indep = sorted(indep_tras, key=orden_gdl) + sorted(rots, key=orden_gdl)
    nD = len(indep)
    T = np.zeros((nl, nD))
    for j, k in enumerate(indep):
        T[k, j] = 1.0
    for k, expr in dep_expr.items():
        for kk, coef in expr.items():
            T[k, indep.index(kk)] = coef
    T[np.abs(T) < TOL] = 0.0

    def nombre(k):
        nid, c = nombres[k]
        return f"{['u', 'v', 'θ'][c]}{nid}"

    etiquetas = []
    for j, k in enumerate(indep):
        nid, c = nombres[k]
        txt = {0: f"desplazamiento X del nudo {nid}", 1: f"desplazamiento Y del nudo {nid}",
               2: f"giro del nudo {nid}"}[c]
        iguales = [nombre(kk) for kk in range(nl) if kk != k and abs(T[kk, j] - 1) < 1e-9
                   and np.count_nonzero(T[kk]) == 1]
        if iguales:
            txt += " (= " + ", ".join(iguales) + ")"
        etiquetas.append(txt)
    dependientes = []
    for k in range(nl):
        if k in indep:
            continue
        terms = [(T[k, j], j) for j in range(nD) if abs(T[k, j]) > TOL]
        if not terms:
            expr = "0"
        else:
            partes = []
            for n_, (v, j) in enumerate(terms):
                sg = ("" if v >= 0 else "−") if n_ == 0 else (" + " if v >= 0 else " − ")
                coef = "" if abs(abs(v) - 1) < 1e-12 else f"{abs(v):.4g}·"
                partes.append(f"{sg}{coef}D{j + 1}")
            expr = "".join(partes)
        dependientes.append(f"{nombre(k)} = {expr}")
    return GDL(libres, T, etiquetas, [nombre(k) for k in range(nl)], dependientes)


# ------------------------------------------------------------- resultados
@dataclass
class ResBarra:
    id: int
    i: int
    j: int
    geo: Geo
    EI: float
    EA: float
    filas: list              # nombres de GDL locales usados
    A: np.ndarray            # [A] (4 ó 6 × nD)
    A6: np.ndarray           # [A] completa 6 × nD
    k: np.ndarray            # [k] local (4×4 ó 6×6)
    Kg: np.ndarray           # [A]ᵀ[k][A]
    r: np.ndarray            # {r} con las mismas filas que [A]
    r6: np.ndarray
    Re: np.ndarray           # [A6]ᵀ{r6}
    usa_axial_en_R: bool
    d: np.ndarray = None
    qc: np.ndarray = None
    q: np.ndarray = None
    q6: np.ndarray = None    # fuerzas finales 6×1 (N del análisis completo si EA=∞)
    d6: np.ndarray = None    # desplazamientos locales 6×1
    cargas: list = field(default_factory=list)
    dn6: np.ndarray = None   # desplazamientos locales de los nudos 6×1
    q6n: np.ndarray = None   # fuerzas en los nudos 6×1 (incluye brazos rígidos)
    bi: float = 0.0
    bj: float = 0.0
    Lf: float = 0.0          # longitud flexible = L − bi − bj
    H: np.ndarray = None
    r_brazos: np.ndarray = None
    rot_i: bool = False
    rot_j: bool = False


@dataclass
class Resultado:
    modelo: Modelo
    gdl: GDL
    barras: list
    K: np.ndarray
    R: np.ndarray
    Q: np.ndarray
    F: np.ndarray
    D: np.ndarray
    u_nudos: dict            # nid -> (ux, uy, θ)
    reacciones: dict         # nid -> (Rx, Ry, M)
    avisos: list
    Rs: np.ndarray = None    # Σ[A]ᵀ{r} (sin las cargas en nudos)


def elemento(m: Modelo, b, idx, EA=None):
    """Datos de una barra: geometría, [λ], [H] (brazos), [k] 6×6 condensada (rótulas),
    {r} de la parte flexible (condensada) y {r} de los brazos."""
    g = geometria(m, b)
    if b.bi < 0 or b.bj < 0:
        raise ErrorAnalisis(f"Barra {b.id}: los brazos rígidos no pueden ser negativos")
    Lf = g.L - b.bi - b.bj
    if Lf <= 1e-6 * g.L:
        raise ErrorAnalisis(f"Barra {b.id}: los brazos rígidos ocupan toda la barra")
    cargas = cargas_locales(m, b, g)
    r6f = fuerzas_fijacion_flexible(cargas, b.bi, Lf)
    k6, r6 = condensar(k_local6(b.EI, b.EA if EA is None else EA, Lf), r6f, liberados(b, 6))
    dofs = [3 * idx[b.i] + c for c in range(3)] + [3 * idx[b.j] + c for c in range(3)]
    return dict(g=g, Lf=Lf, lam=matriz_rotacion(g), H=matriz_brazos(b.bi, b.bj), k6=k6, r6=r6,
                r6f=r6f, rb=fuerzas_brazos(cargas, g.L, b.bi, b.bj), cargas=cargas, dofs=dofs)


def analizar(m: Modelo) -> Resultado:
    """Resuelve el modelo. Aplica las reglas del curso sobre una copia:
    barras orientadas de menor a mayor nudo (SR local) y GDL en orden X, Y, giro."""
    import copy
    m = copy.deepcopy(m)
    invertidas = m.orientar_barras()
    if len(m.nudos) < 2 or not m.barras:
        raise ErrorAnalisis("El modelo necesita al menos 2 nudos y 1 barra")
    idx = {n.id: k for k, n in enumerate(m.nudos)}
    nn = len(m.nudos)
    gdl = gdl_globales(m)
    nl = len(gdl.libres)
    S = np.zeros((3 * nn, nl))
    for k, g in enumerate(gdl.libres):
        S[g, k] = 1.0
    ST = S @ gdl.T                       # u_completo = ST · D
    nD = gdl.T.shape[1]

    barras = []
    K = np.zeros((nD, nD))
    R = np.zeros(nD)
    for b in m.barras:
        eb = elemento(m, b, idx)
        An6 = eb["lam"] @ ST[eb["dofs"], :]          # nudos (ejes locales)
        A6 = eb["H"] @ An6                            # extremos de la parte flexible
        A6[np.abs(A6) < TOL] = 0.0
        r6 = eb["r6"]
        if m.ea_infinito:
            sel = [1, 2, 4, 5]
            filas = ["v_i", "θ_i", "v_j", "θ_j"]
            A = A6[sel, :]
            k, _ = condensar(k_local4(b.EI, eb["Lf"]), np.zeros(4), liberados(b, 4))
            r = r6[sel]
        else:
            filas = ["u_i", "v_i", "θ_i", "u_j", "v_j", "θ_j"]
            A = A6
            k = eb["k6"]
            r = r6
        Kg = A.T @ k @ A
        Re = A6.T @ r6 + An6.T @ eb["rb"]
        usa_axial = m.ea_infinito and (abs(r6[0]) > TOL or abs(r6[3]) > TOL) \
            and np.any(np.abs(A6[[0, 3], :]) > TOL)
        K += Kg
        R += Re
        rb = ResBarra(b.id, b.i, b.j, eb["g"], b.EI, b.EA, filas, A, A6, k, Kg, r, r6,
                      Re, usa_axial, cargas=eb["cargas"])
        rb.bi, rb.bj, rb.Lf, rb.H, rb.r_brazos = b.bi, b.bj, eb["Lf"], eb["H"], eb["rb"]
        rb.rot_i, rb.rot_j = b.rot_i, b.rot_j
        barras.append(rb)

    # cargas en nudos
    P = np.zeros(3 * nn)
    for c in m.cargas_nudo:
        base = 3 * idx[c.nudo]
        P[base:base + 3] += [c.Fx, c.Fy, c.M]
    # Como el profesor: {R} = Σ[A]ᵀ{r} − {fuerzas aplicadas directamente en los nudos} ; {F} = −{R}
    Rs = R.copy()
    Q = ST.T @ P
    R = Rs - Q
    F = -R
    avisos = []
    if invertidas:
        avisos.append("Barras invertidas para que x local vaya de menor a mayor nudo: "
                      + ", ".join(str(b) for b in invertidas))
    if nD == 0:
        raise ErrorAnalisis("La estructura no tiene GDL independientes")
    cond = np.linalg.cond(K)
    if not np.isfinite(cond) or cond > 1e12:
        raise ErrorAnalisis("[K] es singular: la estructura es un mecanismo o le faltan apoyos")
    D = np.linalg.solve(K, F)

    for rb in barras:
        rb.d = rb.A @ D
        rb.qc = rb.k @ rb.d
        rb.q = rb.qc + rb.r

    # análisis completo (para N con EA=∞, reacciones y deformada)
    u_full, reac, q6s = _analisis_completo(m, idx)
    u_red = ST @ D
    for rb in barras:
        b = m.barra(rb.id)
        lam = matriz_rotacion(rb.geo)
        dofs = [3 * idx[b.i] + c for c in range(3)] + [3 * idx[b.j] + c for c in range(3)]
        rb.dn6 = lam @ u_red[dofs]
        eb = elemento(m, b, idx)
        rb.d6 = recuperar_giros(b.EI, rb.Lf, rb.H @ rb.dn6, eb["r6f"], liberados(b, 6))
        if m.ea_infinito:
            q6 = q6s[rb.id].copy()
            q6[[1, 2, 4, 5]] = rb.q        # V y M exactos del método
            rb.q6 = q6
        else:
            rb.q6 = rb.q.copy()
        rb.q6n = rb.H.T @ rb.q6 + rb.r_brazos     # fuerzas en los nudos (con brazos)
    dif = np.max(np.abs(u_full - u_red)) / max(np.max(np.abs(u_red)), 1e-12)
    if dif > 1e-3:
        avisos.append(f"Aviso: el análisis completo difiere {dif:.1e} del reducido")
    u_nudos = {n.id: tuple(u_red[3 * idx[n.id]:3 * idx[n.id] + 3]) for n in m.nudos}
    res = Resultado(m, gdl, barras, K, R, Q, F, D, u_nudos, reac, avisos)
    res.Rs = Rs
    return res


def _analisis_completo(m: Modelo, idx):
    """3 GDL por nudo. Si EA = ∞ usa un EA muy grande (penalización)."""
    nn = len(m.nudos)
    Kf = np.zeros((3 * nn, 3 * nn))
    Pf = np.zeros(3 * nn)
    info = {}
    EImax = max(b.EI for b in m.barras)
    for b in m.barras:
        g = geometria(m, b)
        EA = 1e9 * max(EImax, 1.0) / g.L**2 if m.ea_infinito else None
        eb = elemento(m, b, idx, EA)
        HL = eb["H"] @ eb["lam"]
        dofs = eb["dofs"]
        Kf[np.ix_(dofs, dofs)] += HL.T @ eb["k6"] @ HL
        Pf[dofs] -= HL.T @ eb["r6"] + eb["lam"].T @ eb["rb"]
        info[b.id] = (HL, eb["k6"], eb["r6"], dofs)
    for c in m.cargas_nudo:
        base = 3 * idx[c.nudo]
        Pf[base:base + 3] += [c.Fx, c.Fy, c.M]
    libres = [3 * idx[nid] + c for nid, c in libres_nudo(m)]
    u = np.zeros(3 * nn)
    Kll = Kf[np.ix_(libres, libres)]
    u[libres] = np.linalg.solve(Kll, Pf[libres])
    q6s = {bid: k6 @ (HL @ u[dofs]) + r6 for bid, (HL, k6, r6, dofs) in info.items()}
    fuerzas = Kf @ u - Pf
    reac = {}
    for n in m.nudos:
        rest = APOYOS[n.apoyo]
        if any(rest):
            base = 3 * idx[n.id]
            reac[n.id] = tuple(fuerzas[base + c] if rest[c] else 0.0 for c in range(3))
    return u, reac, q6s


# ------------------------------------------------- funciones a lo largo de x
def esfuerzos(rb: ResBarra, npts: int = 201):
    """x, N(x), V(x), M(x), v(x) local (flecha), u(x) local, a lo largo de toda la barra
    (x desde el nudo i, incluye brazos rígidos).
    M(x) = −M_i + V_i·x − (cargas): M > 0 tracciona la cara −y local."""
    L = rb.geo.L
    bi, bj = rb.bi, rb.bj
    xs = np.linspace(0, L, npts)
    extra = [bi, L - bj]
    for c in rb.cargas:
        if c[0] == "P":
            a = c[3]
            extra += [max(a - 1e-9, 0), a, min(a + 1e-9, L)]
        else:
            extra += [c[5], c[6]]
    xs = np.union1d(xs, np.clip(extra, 0, L))
    Ni, Vi, Mi = rb.q6n[0], rb.q6n[1], rb.q6n[2]
    N = -Ni * np.ones_like(xs)
    V = Vi * np.ones_like(xs)
    M = -Mi + Vi * xs
    for c in rb.cargas:
        if c[0] == "P":
            _, Px, Py, a = c
            h = xs > a
            N += np.where(h, -Px, 0.0)
            V += np.where(h, Py, 0.0)
            M += np.where(h, Py * (xs - a), 0.0)
        else:
            a = c[5]
            s_ = np.clip(xs, a, c[6])
            for k, x in enumerate(xs):
                if s_[k] - a <= 1e-12:
                    continue
                xg, wg, px, py = _puntos_repartida(c, a, s_[k])
                N[k] -= np.sum(wg * px)
                V[k] += np.sum(wg * py)
                M[k] += np.sum(wg * py * (x - xg))
    # flecha en la parte flexible: v'' = M/EI desde el extremo i' (giro de la barra);
    # corrección lineal para cerrar en v_j'. Brazos: rectos con el giro del nudo.
    d6, dn = rb.d6, rb.dn6
    v = np.zeros_like(xs)
    fx = (xs >= bi - 1e-12) & (xs <= L - bj + 1e-12)
    xf = xs[fx]
    curv = M[fx] / rb.EI
    th = d6[2] + np.concatenate([[0], np.cumsum((curv[1:] + curv[:-1]) / 2 * np.diff(xf))])
    vf = d6[1] + np.concatenate([[0], np.cumsum((th[1:] + th[:-1]) / 2 * np.diff(xf))])
    vf += (d6[4] - vf[-1]) * (xf - xf[0]) / max(xf[-1] - xf[0], 1e-12)
    v[fx] = vf
    izq, der = xs < bi - 1e-12, xs > L - bj + 1e-12
    v[izq] = dn[1] + dn[2] * xs[izq]
    v[der] = dn[4] - dn[5] * (L - xs[der])
    u = dn[0] + (dn[3] - dn[0]) * xs / L
    return xs, N, V, M, v, u
