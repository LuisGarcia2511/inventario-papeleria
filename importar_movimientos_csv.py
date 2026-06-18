"""
Importa movimientos históricos desde CSV (ej. movimientos_supabase.csv de ChatGPT).

Columnas esperadas:
  fecha, tipo, nombre_articulo, codigo, area, quien_recoge, inventario_existente

Por defecto NO modifica el stock actual (solo agrega historial).
"""
import argparse
import math
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

DEFAULT_CSV = Path(__file__).resolve().parent / "movimientos_supabase.csv"


def _norm(text: str | None) -> str:
    if text is None or (isinstance(text, float) and math.isnan(text)):
        return ""
    s = str(text).strip().upper()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s+", " ", s)
    return s


def _parse_fecha(value) -> datetime | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def _to_int(value, default: int = 0) -> int:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _buscar_articulo(articulos, codigo: str, nombre: str):
    codigo_n = _norm(codigo)
    nombre_n = _norm(nombre)

    if codigo_n:
        for a in articulos:
            if _norm(a.codigo_interno) == codigo_n:
                return a

    if nombre_n:
        for a in articulos:
            if _norm(a.nombre) == nombre_n:
                return a
        for a in articulos:
            if nombre_n in _norm(a.nombre) or _norm(a.nombre) in nombre_n:
                return a
    return None


def _buscar_maestro(maestros, area: str, quien_recoge: str):
    area_n = _norm(area)
    quien_n = _norm(quien_recoge)

    if quien_n:
        for m in maestros:
            if _norm(m.nombre) == quien_n:
                return m
        for m in maestros:
            mn = _norm(m.nombre)
            if quien_n in mn or mn in quien_n:
                return m
        partes = quien_n.split()
        if len(partes) >= 2:
            for m in maestros:
                mn = _norm(m.nombre)
                if partes[0] in mn and partes[-1] in mn:
                    return m

    if area_n:
        candidatos = [m for m in maestros if _norm(m.area) == area_n]
        if len(candidatos) == 1:
            return candidatos[0]
        if candidatos:
            return candidatos[0]
    return None


def importar(csv_path: Path, actualizar_stock: bool, reemplazar: bool) -> None:
    if not csv_path.exists():
        raise FileNotFoundError(f"No existe el CSV: {csv_path}")

    from app import app, db, Articulo, Maestro, Movimiento

    df = pd.read_csv(csv_path)
    df.columns = [c.strip().lower() for c in df.columns]

    requeridas = {"fecha", "tipo", "inventario_existente"}
    faltan = requeridas - set(df.columns)
    if faltan:
        raise RuntimeError(f"Faltan columnas en el CSV: {', '.join(sorted(faltan))}")

    with app.app_context():
        if reemplazar:
            Movimiento.query.delete()
            db.session.commit()
            print("[OK] Movimientos anteriores borrados.")

        articulos = Articulo.query.all()
        maestros = Maestro.query.all()
        existentes = {
            (
                m.fecha.strftime("%Y-%m-%d %H:%M:%S"),
                m.tipo,
                m.articulo_id,
                m.cantidad,
            )
            for m in Movimiento.query.all()
        }

        creados = 0
        omitidos = 0
        errores = []

        filas = df.sort_values("fecha")
        for idx, row in filas.iterrows():
            tipo = _norm(row.get("tipo"))
            if tipo not in ("ENTRADA", "SALIDA"):
                errores.append(f"Fila {idx + 2}: tipo inválido '{row.get('tipo')}'")
                continue

            fecha = _parse_fecha(row.get("fecha"))
            if not fecha:
                errores.append(f"Fila {idx + 2}: fecha inválida")
                continue

            cantidad = _to_int(row.get("inventario_existente"))
            if cantidad <= 0:
                errores.append(f"Fila {idx + 2}: cantidad inválida ({row.get('inventario_existente')})")
                continue

            codigo = row.get("codigo", "")
            nombre_art = row.get("nombre_articulo", "")
            articulo = _buscar_articulo(articulos, codigo, nombre_art)
            if not articulo:
                errores.append(
                    f"Fila {idx + 2}: artículo no encontrado "
                    f"({codigo or nombre_art})"
                )
                continue

            area = row.get("area", "")
            quien = row.get("quien_recoge", "")
            maestro = _buscar_maestro(maestros, area, quien) if tipo == "SALIDA" else None

            clave = (
                fecha.strftime("%Y-%m-%d %H:%M:%S"),
                tipo,
                articulo.id,
                cantidad,
            )
            if clave in existentes:
                omitidos += 1
                continue

            mov = Movimiento(
                tipo=tipo,
                cantidad=cantidad,
                fecha=fecha,
                articulo_id=articulo.id,
                maestro_id=maestro.id if maestro else None,
                persona_recibe=str(quien).strip() if quien and not (isinstance(quien, float) and math.isnan(quien)) else None,
                comentario=str(area).strip() if area and not (isinstance(area, float) and math.isnan(area)) else None,
            )
            db.session.add(mov)

            if actualizar_stock:
                if tipo == "ENTRADA":
                    articulo.stock_actual += cantidad
                else:
                    articulo.stock_actual -= cantidad

            existentes.add(clave)
            creados += 1

        db.session.commit()
        print(f"[OK] Movimientos importados: {creados}")
        if omitidos:
            print(f"[INFO] Duplicados omitidos: {omitidos}")
        if errores:
            print(f"[AVISO] {len(errores)} filas con problema:")
            for e in errores[:15]:
                print("  -", e)
            if len(errores) > 15:
                print(f"  ... y {len(errores) - 15} más")


def main():
    parser = argparse.ArgumentParser(description="Importa movimientos desde CSV.")
    parser.add_argument(
        "--csv",
        default=str(DEFAULT_CSV),
        help="Ruta del archivo CSV",
    )
    parser.add_argument(
        "--actualizar-stock",
        action="store_true",
        help="También recalcula stock (por defecto solo importa historial)",
    )
    parser.add_argument(
        "--reemplazar",
        action="store_true",
        help="Borra movimientos existentes antes de importar",
    )
    args = parser.parse_args()

    if not os.environ.get("DATABASE_URL", "").strip():
        print("Usando SQLite local (sin DATABASE_URL).")
        print("Para Supabase, define DATABASE_URL antes de ejecutar.")
    else:
        print("Destino: PostgreSQL (DATABASE_URL)")

    importar(Path(args.csv), args.actualizar_stock, args.reemplazar)


if __name__ == "__main__":
    main()
