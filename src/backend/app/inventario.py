"""
El inventario, sobre un CSV. Es el sistema que las tools del agente manipulan.

Un CSV y no una base de datos a propósito: el asistente puede abrirlo con
cualquier cosa, verlo cambiar mientras el agente trabaja, y entender de un
vistazo qué pasó. Una base de datos esconde justo lo que queremos mostrar.

    datos/inventario.semilla.csv   el estado inicial. SE VERSIONA.
    datos/inventario.csv           el estado vivo. NO se versiona.

El archivo vivo se crea desde la semilla la primera vez, y `/api/admin/reiniciar`
lo vuelve a crear. Durante el taller eso se usa más de lo que parece: entre
práctica y práctica, y después de cada demo de falla del bloque 5.

Sobre los verbos: GET lee, POST crea, PUT actualiza y **DELETE borra**. Ese
último es el que justifica el guardrail del paso 4 — una acción que de verdad
duele deshacer. Sin algo así, la confirmación humana se siente como un
requisito inventado y nadie se la cree.
"""

import csv
import os
import shutil
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

# Dentro del contenedor, /datos es el bind mount de la carpeta datos/ del repo.
# Fuera (si alguien corre el backend a mano), se busca relativo al archivo.
DIR = Path("/datos") if Path("/datos").is_dir() else Path(__file__).resolve().parents[3] / "datos"
VIVO = DIR / "inventario.csv"
SEMILLA = DIR / "inventario.semilla.csv"

COLUMNAS = ["sku", "nombre", "existencias", "precio", "categoria"]

# Un CSV no tiene transacciones. Con un solo asistente por backend esto es mas
# que suficiente, y es mucho menos codigo que explicar un motor de base de datos
# que no es el tema del taller.
_candado = threading.Lock()


class Producto(BaseModel):
    sku: str = Field(..., min_length=1, max_length=40)
    nombre: str = Field(..., min_length=1, max_length=80)
    existencias: int = Field(..., ge=0)
    precio: float = Field(..., ge=0)
    categoria: str = "general"


class ProductoParcial(BaseModel):
    """Para el PUT: todo opcional, se actualiza solo lo que venga."""
    nombre: str | None = Field(None, min_length=1, max_length=80)
    existencias: int | None = Field(None, ge=0)
    precio: float | None = Field(None, ge=0)
    categoria: str | None = None


# ---------------------------------------------------------------------------
# Lectura y escritura del archivo
# ---------------------------------------------------------------------------
def _asegurar_archivo():
    if not VIVO.exists():
        if not SEMILLA.exists():
            raise HTTPException(500, f"No existe la semilla en {SEMILLA}")
        VIVO.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(SEMILLA, VIVO)


def _leer() -> list[dict]:
    _asegurar_archivo()
    with open(VIVO, encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
    for r in filas:
        # El CSV guarda texto; el agente espera numeros.
        r["existencias"] = int(r["existencias"])
        r["precio"] = float(r["precio"])
    return filas


def _limpiar(valor):
    """
    180.0 se escribe como 180.

    Suena a detalle y no lo es: este archivo esta hecho para que el asistente
    lo abra y lo lea de un vistazo mientras el agente trabaja. Una columna de
    precios con .0 en todo distrae.
    """
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    return valor


def _escribir(filas: list[dict]):
    # Escribimos a un temporal y renombramos: si algo falla a mitad, el archivo
    # bueno queda intacto en lugar de truncado.
    tmp = VIVO.with_suffix(".csv.tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader()
        w.writerows([{c: _limpiar(r[c]) for c in COLUMNAS} for r in filas])
    os.replace(tmp, VIVO)


def reiniciar_desde_semilla():
    """La llama /api/admin/reiniciar."""
    with _candado:
        if VIVO.exists():
            VIVO.unlink()
        _asegurar_archivo()
    return len(_leer())


# ---------------------------------------------------------------------------
# GET — leer
# ---------------------------------------------------------------------------
@router.get("/api/inventario")
def listar(categoria: str | None = None, con_existencias: bool | None = None):
    """
    Todo el inventario. `categoria` y `con_existencias` filtran.

    Los filtros existen para el paso 5: le dan al agente de inventario algo que
    decidir —cuál de las dos consultas usar— en vez de un solo endpoint que
    devuelve todo siempre.
    """
    filas = _leer()
    if categoria:
        filas = [r for r in filas if r["categoria"].lower() == categoria.lower()]
    if con_existencias is not None:
        filas = [r for r in filas if (r["existencias"] > 0) == con_existencias]
    return {"productos": filas, "total": len(filas)}


@router.get("/api/inventario/{sku}")
def obtener(sku: str):
    for r in _leer():
        if r["sku"].upper() == sku.upper():
            return r
    # 404 con la lista de SKU validos: cuando esto le vuelve al modelo como
    # resultado de una tool, puede corregirse solo. Un "no encontrado" a secas
    # lo deja adivinando.
    raise HTTPException(404, {
        "error": f"no existe el producto '{sku}'",
        "disponibles": [r["sku"] for r in _leer()],
    })


# ---------------------------------------------------------------------------
# POST — crear
# ---------------------------------------------------------------------------
@router.post("/api/inventario", status_code=201)
def crear(p: Producto):
    with _candado:
        filas = _leer()
        if any(r["sku"].upper() == p.sku.upper() for r in filas):
            raise HTTPException(409, f"el producto '{p.sku}' ya existe")
        filas.append(p.model_dump())
        _escribir(filas)
    return p.model_dump()


# ---------------------------------------------------------------------------
# PUT — actualizar
# ---------------------------------------------------------------------------
@router.put("/api/inventario/{sku}")
def actualizar(sku: str, cambios: ProductoParcial):
    with _candado:
        filas = _leer()
        for r in filas:
            if r["sku"].upper() == sku.upper():
                for campo, valor in cambios.model_dump(exclude_none=True).items():
                    r[campo] = valor
                _escribir(filas)
                return r
    raise HTTPException(404, f"no existe el producto '{sku}'")


# ---------------------------------------------------------------------------
# DELETE — borrar. El endpoint destructivo del taller.
# ---------------------------------------------------------------------------
@router.delete("/api/inventario/{sku}")
def borrar(sku: str):
    """
    Borra un producto. **No hay papelera.**

    Esta es la acción que el paso 4 protege con confirmación humana, y la que
    la demo de falla 4 ejecuta sin red para mostrar qué pasa. Que duela es el
    punto: un guardrail sobre algo reversible no enseña nada.
    """
    with _candado:
        filas = _leer()
        quedan = [r for r in filas if r["sku"].upper() != sku.upper()]
        if len(quedan) == len(filas):
            raise HTTPException(404, f"no existe el producto '{sku}'")
        _escribir(quedan)
    return {"borrado": sku, "quedan": len(quedan)}
