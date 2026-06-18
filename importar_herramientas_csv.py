"""
Importa herramientas y salidas desde CSV o Excel.

Inventario (CSV/Excel hoja INVENTARIO):
  tipo, nombre, responsable, existencia, activo, observaciones

Salidas (CSV/Excel hoja SALIDAS):
  fecha_salida, tipo, nombre, cantidad, responsable, quien_se_llevo, comentario
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

ROOT = Path(__file__).resolve().parent
DEFAULT_INVENTARIO = ROOT / "herramientas_inventario.csv"
DEFAULT_SALIDAS = ROOT / "herramientas_salidas.csv"


def _norm(text) -> str:
    if text is None or (isinstance(text, float) and math.isnan(text)):
        return ""
    s = str(text).strip().upper()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s+", " ", s)
    return s


def _norm_col(name: str) -> str:
    return _norm(name).replace("_", " ")


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


def _pick_col(df: pd.DataFrame, *cands: str) -> str | None:
    colmap = {}
    for c in df.columns:
        key = _norm_col(str(c))
        if key and key not in colmap:
            colmap[key] = c
    for cand in cands:
        key = _norm_col(cand)
        if key in colmap:
            return colmap[key]
    return None


def _buscar_herramienta(items, nombre: str, tipo: str = ""):
    nombre_n = _norm(nombre)
    tipo_n = _norm(tipo)
    if not nombre_n:
        return None
    for h in items:
        if _norm(h.nombre) == nombre_n and (not tipo_n or _norm(h.tipo) == tipo_n):
            return h
    for h in items:
        if _norm(h.nombre) == nombre_n:
            return h
    for h in items:
        hn = _norm(h.nombre)
        if nombre_n in hn or hn in nombre_n:
            return h
    return None


def _leer_hoja(path: Path, sheet: str | None = None) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path, sheet_name=sheet or 0)
    return pd.read_csv(path)


def importar_inventario_df(df: pd.DataFrame, reemplazar: bool = False) -> dict:
    from app import db, HerramientaLimpieza, SalidaHerramienta

    col_tipo = _pick_col(df, "TIPO")
    col_nombre = _pick_col(df, "NOMBRE")
    col_resp = _pick_col(df, "RESPONSABLE", "RESPONSAB")
    col_stock = _pick_col(df, "EXISTENCIA", "STOCK ACTUAL", "STOCK")
    col_activo = _pick_col(df, "ACTIVO")
    col_obs = _pick_col(df, "OBSERVACIONES", "OBSERVACION")

    if not col_nombre:
        raise RuntimeError("Falta columna NOMBRE en inventario.")

    if reemplazar:
        SalidaHerramienta.query.delete()
        HerramientaLimpieza.query.delete()
        db.session.commit()

    items = HerramientaLimpieza.query.all()
    creados = actualizados = saltados = 0

    for _, row in df.iterrows():
        nombre = str(row.get(col_nombre, "")).strip()
        if not nombre or nombre.lower() == "nan":
            saltados += 1
            continue

        tipo = _norm(row.get(col_tipo, "HERRAMIENTA")) if col_tipo else "HERRAMIENTA"
        if tipo not in {"HERRAMIENTA", "LIMPIEZA"}:
            tipo = "HERRAMIENTA"

        responsable = str(row.get(col_resp, "")).strip() if col_resp else ""
        if tipo == "LIMPIEZA":
            responsable = "AREA DE RECURSOS MATERIALES"
        elif not responsable:
            responsable = "RECURSOS MATERIALES"

        stock = max(0, _to_int(row.get(col_stock), default=1)) if col_stock else 1
        obs = str(row.get(col_obs, "")).strip() if col_obs else ""
        obs = obs if obs and obs.lower() != "nan" else None

        activo = True
        if col_activo:
            val = _norm(row.get(col_activo))
            activo = val in {"SI", "S", "1", "TRUE", "ACTIVO", "YES"}

        item = _buscar_herramienta(items, nombre, tipo)
        if item:
            item.nombre = nombre
            item.tipo = tipo
            item.responsable = responsable
            item.stock_actual = stock
            item.activo = activo
            item.observaciones = obs
            actualizados += 1
        else:
            item = HerramientaLimpieza(
                nombre=nombre,
                tipo=tipo,
                responsable=responsable,
                stock_actual=stock,
                activo=activo,
                observaciones=obs,
            )
            db.session.add(item)
            items.append(item)
            creados += 1

    db.session.commit()
    return {"creados": creados, "actualizados": actualizados, "saltados": saltados}


def importar_salidas_df(
    df: pd.DataFrame,
    actualizar_stock: bool = False,
    reemplazar: bool = False,
) -> dict:
    from app import db, HerramientaLimpieza, SalidaHerramienta

    col_fecha = _pick_col(df, "FECHA SALIDA", "FECHA_SALIDA", "FECHA")
    col_tipo = _pick_col(df, "TIPO")
    col_nombre = _pick_col(df, "NOMBRE")
    col_cant = _pick_col(df, "CANTIDAD")
    col_resp = _pick_col(df, "RESPONSABLE", "RESPONSAB")
    col_quien = _pick_col(df, "QUIEN SE LLEVO", "QUIEN_SE_LLEVO", "QUIEN RECOGE")
    col_com = _pick_col(df, "COMENTARIO")

    if not col_nombre or not col_fecha:
        raise RuntimeError("Faltan columnas NOMBRE y FECHA_SALIDA en salidas.")

    if reemplazar:
        SalidaHerramienta.query.delete()
        db.session.commit()

    items = HerramientaLimpieza.query.all()
    existentes = {
        (
            s.fecha_se_llevo.strftime("%Y-%m-%d %H:%M:%S"),
            s.herramienta_id,
            s.cantidad,
            _norm(s.quien_se_lleva),
        )
        for s in SalidaHerramienta.query.all()
    }

    creados = omitidos = errores = 0
    errores_lista = []

    for idx, row in df.iterrows():
        nombre = str(row.get(col_nombre, "")).strip()
        fecha = _parse_fecha(row.get(col_fecha))
        if not nombre or nombre.lower() == "nan":
            continue
        if not fecha:
            errores_lista.append(f"Fila {idx + 2}: fecha inválida ({row.get(col_fecha)})")
            errores += 1
            continue

        tipo = str(row.get(col_tipo, "")).strip() if col_tipo else ""
        herramienta = _buscar_herramienta(items, nombre, tipo)
        if not herramienta:
            errores_lista.append(f"Fila {idx + 2}: herramienta no encontrada ({nombre})")
            errores += 1
            continue

        cantidad = max(1, _to_int(row.get(col_cant), default=1)) if col_cant else 1
        responsable = str(row.get(col_resp, "")).strip() if col_resp else ""
        if not responsable:
            responsable = herramienta.responsable

        quien = str(row.get(col_quien, "")).strip() if col_quien else ""
        if not quien:
            errores_lista.append(f"Fila {idx + 2}: falta quien_se_llevo ({nombre})")
            errores += 1
            continue

        comentario = str(row.get(col_com, "")).strip() if col_com else ""
        comentario = comentario if comentario and comentario.lower() != "nan" else None

        clave = (
            fecha.strftime("%Y-%m-%d %H:%M:%S"),
            herramienta.id,
            cantidad,
            _norm(quien),
        )
        if clave in existentes:
            omitidos += 1
            continue

        salida = SalidaHerramienta(
            herramienta_id=herramienta.id,
            cantidad=cantidad,
            responsable=responsable,
            quien_se_lleva=quien,
            fecha_se_llevo=fecha,
            comentario=comentario,
        )
        db.session.add(salida)

        if actualizar_stock:
            herramienta.stock_actual = max(0, herramienta.stock_actual - cantidad)

        existentes.add(clave)
        creados += 1

    db.session.commit()
    return {
        "creados": creados,
        "omitidos": omitidos,
        "errores": errores,
        "errores_lista": errores_lista,
    }


def importar_archivos(
    inventario_path: Path | None,
    salidas_path: Path | None,
    actualizar_stock: bool = False,
    reemplazar: bool = False,
) -> None:
    from app import app

    with app.app_context():
        if inventario_path and inventario_path.exists():
            df = _leer_hoja(inventario_path, "INVENTARIO")
            stats = importar_inventario_df(df, reemplazar=reemplazar)
            print(f"[OK] Inventario: {stats}")
        elif inventario_path:
            print(f"[SKIP] No existe inventario: {inventario_path}")

        if salidas_path and salidas_path.exists():
            df = _leer_hoja(salidas_path, "SALIDAS")
            stats = importar_salidas_df(
                df,
                actualizar_stock=actualizar_stock,
                reemplazar=reemplazar and not inventario_path,
            )
            print(f"[OK] Salidas: {stats}")
            if stats.get("errores_lista"):
                for e in stats["errores_lista"][:10]:
                    print("  -", e)
        elif salidas_path:
            print(f"[SKIP] No existe salidas: {salidas_path}")


def importar_excel_completo(path: Path, actualizar_stock: bool = False, reemplazar: bool = False) -> dict:
    from app import app

    with app.app_context():
        xls = pd.ExcelFile(path)
        hojas = {_norm(h): h for h in xls.sheet_names}
        result = {}

        inv_name = (
            hojas.get("INVENTARIO")
            or hojas.get("HERRAMIENTAS")
            or hojas.get("HERRAMIENTA")
        )
        if inv_name:
            result["inventario"] = importar_inventario_df(
                pd.read_excel(path, sheet_name=inv_name),
                reemplazar=reemplazar,
            )
        elif len(xls.sheet_names) == 1:
            result["inventario"] = importar_inventario_df(
                pd.read_excel(path, sheet_name=0),
                reemplazar=reemplazar,
            )

        sal_name = hojas.get("SALIDAS")
        if sal_name:
            result["salidas"] = importar_salidas_df(
                pd.read_excel(path, sheet_name=sal_name),
                actualizar_stock=actualizar_stock,
                reemplazar=reemplazar and "inventario" not in result,
            )

        if not result:
            raise RuntimeError(
                "El Excel debe tener hoja INVENTARIO, HERRAMIENTAS o una sola hoja con datos."
            )
        return result


def main():
    parser = argparse.ArgumentParser(description="Importa herramientas y salidas.")
    parser.add_argument("--inventario", default=str(DEFAULT_INVENTARIO))
    parser.add_argument("--salidas", default=str(DEFAULT_SALIDAS))
    parser.add_argument("--excel", help="Excel con hojas INVENTARIO y SALIDAS")
    parser.add_argument("--actualizar-stock", action="store_true")
    parser.add_argument("--reemplazar", action="store_true")
    args = parser.parse_args()

    if not os.environ.get("DATABASE_URL", "").strip():
        print("Usando SQLite local. Para Supabase define DATABASE_URL.")
    else:
        print("Destino: PostgreSQL (DATABASE_URL)")

    if args.excel:
        importar_excel_completo(
            Path(args.excel),
            actualizar_stock=args.actualizar_stock,
            reemplazar=args.reemplazar,
        )
        print("Importación desde Excel terminada.")
        return

    importar_archivos(
        Path(args.inventario) if args.inventario else None,
        Path(args.salidas) if args.salidas else None,
        actualizar_stock=args.actualizar_stock,
        reemplazar=args.reemplazar,
    )
    print("Importación terminada.")


if __name__ == "__main__":
    main()
