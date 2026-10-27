"""Modelo de datos: nudos, barras, apoyos y cargas. Unidades: t, m, rad."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import json

APOYOS = {  # restricciones (ux, uy, rz)
    "libre": (False, False, False),
    "empotrado": (True, True, True),
    "articulado": (True, True, False),
    "rodillo (fija Y)": (False, True, False),
    "rodillo (fija X)": (True, False, False),
    "guía (fija X y giro)": (True, False, True),
    "guía (fija Y y giro)": (False, True, True),
}
EXTREMOS = {  # (rótula i, rótula j)
    "rígido–rígido": (False, False),
    "rótula en i": (True, False),
    "rótula en j": (False, True),
    "rótula i y j (armadura)": (True, True),
}
EXTREMOS_INV = {v: k for k, v in EXTREMOS.items()}
DIRECCIONES = ["perpendicular (y local)", "axial (x local)", "global X", "global Y"]


@dataclass
class Nudo:
    id: int
    x: float
    y: float
    apoyo: str = "libre"


@dataclass
class Barra:
    id: int
    i: int
    j: int
    EI: float = 3000.0
    EA: float = 1e8
    rot_i: bool = False     # rótula en el extremo i (M = 0)
    rot_j: bool = False     # rótula en el extremo j (M = 0)
    bi: float = 0.0         # brazo rígido en i (m, medido desde el nudo i)
    bj: float = 0.0         # brazo rígido en j (m, medido desde el nudo j)

    @property
    def extremos(self) -> str:
        return EXTREMOS_INV[(bool(self.rot_i), bool(self.rot_j))]


@dataclass
class CargaNudo:
    nudo: int
    Fx: float = 0.0
    Fy: float = 0.0
    M: float = 0.0          # antihorario +


@dataclass
class CargaRepartida:
    """Repartida lineal (uniforme, triangular o trapezoidal), por metro de barra.
    Va de w (en x = a) a w2 (en x = b); x se mide desde el nudo i.
    w2 = None → uniforme; b = None ó 0 → hasta el nudo j."""
    barra: int
    w: float                # t/m en x = a
    direccion: str = "global Y"
    w2: float | None = None  # t/m en x = b
    a: float = 0.0
    b: float | None = None


@dataclass
class CargaPuntual:
    barra: int
    P: float                # t
    a: float                # m, medido desde el nudo i de la barra
    direccion: str = "global Y"


@dataclass
class Modelo:
    titulo: str = "Nuevo modelo"
    nudos: list[Nudo] = field(default_factory=list)
    barras: list[Barra] = field(default_factory=list)
    cargas_nudo: list[CargaNudo] = field(default_factory=list)
    cargas_repartidas: list[CargaRepartida] = field(default_factory=list)
    cargas_puntuales: list[CargaPuntual] = field(default_factory=list)
    ea_infinito: bool = True

    # ---------- utilidades ----------
    def nudo(self, nid: int) -> Nudo:
        for n in self.nudos:
            if n.id == nid:
                return n
        raise KeyError(f"No existe el nudo {nid}")

    def barra(self, bid: int) -> Barra:
        for b in self.barras:
            if b.id == bid:
                return b
        raise KeyError(f"No existe la barra {bid}")

    def siguiente_id_nudo(self) -> int:
        return max((n.id for n in self.nudos), default=0) + 1

    def siguiente_id_barra(self) -> int:
        return max((b.id for b in self.barras), default=0) + 1

    # ---------- reglas del curso ----------
    def orientar_barras(self) -> list[int]:
        """Regla del SR local: x va del nudo de MENOR número al de MAYOR número.
        Invierte las barras que no la cumplen (y sus cargas, rótulas y brazos).
        Devuelve los números de las barras invertidas."""
        cambiadas = []
        for b in self.barras:
            if b.i <= b.j:
                continue
            try:
                ni, nj = self.nudo(b.i), self.nudo(b.j)
            except KeyError:
                continue
            L = ((nj.x - ni.x) ** 2 + (nj.y - ni.y) ** 2) ** 0.5
            b.i, b.j = b.j, b.i
            b.rot_i, b.rot_j = b.rot_j, b.rot_i
            b.bi, b.bj = b.bj, b.bi
            for c in self.cargas_puntuales:
                if c.barra == b.id:
                    c.a = L - c.a
                    if not c.direccion.startswith("global"):
                        c.P = -c.P      # x e y locales cambian de sentido
            for c in self.cargas_repartidas:
                if c.barra == b.id:
                    a = c.a or 0.0
                    bb = L if (c.b is None or c.b == 0) else c.b
                    w1, w2 = c.w, (c.w if c.w2 is None else c.w2)
                    c.a, c.b = L - bb, (None if a == 0 else L - a)
                    c.w, c.w2 = w2, w1
                    if not c.direccion.startswith("global"):
                        c.w, c.w2 = -c.w, -c.w2
            cambiadas.append(b.id)
        return cambiadas

    def renumerar_nudos(self, mapa: dict[int, int]) -> list[int]:
        """Cambia los números de los nudos según mapa {actual: nuevo}; actualiza barras y
        cargas y vuelve a orientar las barras (de menor a mayor)."""
        nuevos = [mapa.get(n.id, n.id) for n in self.nudos]
        if len(set(nuevos)) != len(nuevos):
            raise ValueError("Los números de nudo nuevos se repiten")
        if any(v <= 0 for v in nuevos):
            raise ValueError("Los números de nudo deben ser enteros positivos")
        for n in self.nudos:
            n.id = mapa.get(n.id, n.id)
        for b in self.barras:
            b.i, b.j = mapa.get(b.i, b.i), mapa.get(b.j, b.j)
        for c in self.cargas_nudo:
            c.nudo = mapa.get(c.nudo, c.nudo)
        self.nudos.sort(key=lambda n: n.id)
        return self.orientar_barras()

    def renumerar_barras(self, mapa: dict[int, int]) -> None:
        """Cambia los números de las barras según mapa {actual: nuevo}; actualiza las cargas
        repartidas y puntuales que apuntan a cada barra."""
        nuevos = [mapa.get(b.id, b.id) for b in self.barras]
        if len(set(nuevos)) != len(nuevos):
            raise ValueError("Los números de barra nuevos se repiten")
        if any(v <= 0 for v in nuevos):
            raise ValueError("Los números de barra deben ser enteros positivos")
        for b in self.barras:
            b.id = mapa.get(b.id, b.id)
        for c in self.cargas_repartidas:
            c.barra = mapa.get(c.barra, c.barra)
        for c in self.cargas_puntuales:
            c.barra = mapa.get(c.barra, c.barra)
        self.barras.sort(key=lambda b: b.id)

    # ---------- archivo ----------
    def a_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def de_dict(d: dict) -> "Modelo":
        return Modelo(
            titulo=d.get("titulo", "Modelo"),
            nudos=[Nudo(**n) for n in d.get("nudos", [])],
            barras=[Barra(**b) for b in d.get("barras", [])],
            cargas_nudo=[CargaNudo(**c) for c in d.get("cargas_nudo", [])],
            cargas_repartidas=[CargaRepartida(**c) for c in d.get("cargas_repartidas", [])],
            cargas_puntuales=[CargaPuntual(**c) for c in d.get("cargas_puntuales", [])],
            ea_infinito=d.get("ea_infinito", True),
        )

    def guardar(self, ruta: str) -> None:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(self.a_dict(), f, indent=2, ensure_ascii=False)

    @staticmethod
    def abrir(ruta: str) -> "Modelo":
        with open(ruta, encoding="utf-8") as f:
            return Modelo.de_dict(json.load(f))
