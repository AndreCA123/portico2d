#!/bin/bash
# ==============================================================================
# construir.sh: Copia los módulos originales de portico2d a web/py/ para Pyodide
# Regla de oro: un solo motor de cálculo. No editar las copias generadas.
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
P2D_DIR="$(cd "$DIR/.." && pwd)"

echo "==> Copiando módulos de portico2d a web/py/portico2d/..."
mkdir -p "$DIR/py/portico2d"
cp -v "$P2D_DIR/portico2d/__init__.py" "$DIR/py/portico2d/"
cp -v "$P2D_DIR/portico2d/modelo.py" "$DIR/py/portico2d/"
cp -v "$P2D_DIR/portico2d/solver.py" "$DIR/py/portico2d/"
cp -v "$P2D_DIR/portico2d/informe.py" "$DIR/py/portico2d/"
cp -v "$P2D_DIR/portico2d/dibujo.py" "$DIR/py/portico2d/"
cp -v "$P2D_DIR/portico2d/figuras.py" "$DIR/py/portico2d/"

echo "==> Copiando ejemplos a web/ejemplos/..."
mkdir -p "$DIR/ejemplos"
cp -v "$P2D_DIR/ejemplos/"*.json "$DIR/ejemplos/"

echo "==> Construcción exitosa. Módulos listos para Pyodide."
