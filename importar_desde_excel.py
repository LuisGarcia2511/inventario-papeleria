from pathlib import Path
import math
import pandas as pd

from app import app, db, Articulo


CSV_PATH = Path(r"C:\Users\ASUS\OneDrive\Documentos\basededatos\papeleria.csv")

# En tu hoja se ven estos encabezados: NP, CODIGO, CATEGORIA, ARTICULO, Columna1, INVENTARIO
# Aquí ponemos candidatos por si el CSV trae espacios/variantes.
CANDIDATOS_NOMBRE = ["ARTICULO", "ARTÍCULO"]
CANDIDATOS_CODIGO_INTERNO = ["CODIGO", "CÓDIGO", "CODIGC_", "CODIGC"]
CANDIDATOS_EXISTENCIA = ["INVENTARIO", "EXISTENCIA", "STOCK"]
CANDIDATOS_CATEGORIA = ["CATEGORIA", "CATEGORÍA"]
CANDIDATOS_MARCA = ["MARCA"]
CANDIDATOS_UNIDAD = ["UNIDAD DE MEDIDA", "UNIDAD", "UM"]


def _valor_str(celda):
    if isinstance(celda, str):
        texto = celda.strip()
        return texto if texto else None
    if celda is None or (isinstance(celda, float) and math.isnan(celda)):
        return None
    return str(celda).strip() or None


def _valor_int(celda, default=0):
    if celda is None or (isinstance(celda, float) and math.isnan(celda)):
        return default
    try:
        return int(celda)
    except (TypeError, ValueError):
        return default


def _norm(x):
    return str(x).strip().upper()


def importar():
    if not CSV_PATH.exists():
        print(f"No se encontró el archivo: {CSV_PATH}")
        return

    # Si el archivo empieza con "PK", NO es CSV: es un XLSX (zip) renombrado.
    with open(CSV_PATH, "rb") as f:
        magic = f.read(4)

    if magic.startswith(b"PK\x03\x04"):
        print("Detecté que el archivo NO es CSV (parece XLSX renombrado).")
        print("Leyendo como Excel (hoja: PAPELERIA)...")
        raw = pd.read_excel(
            CSV_PATH,
            sheet_name="PAPELERIA",
            dtype=str,
            header=None,  # leemos sin encabezado para poder detectar la fila real
        )
    else:
        # CSV exportado desde Excel a veces trae:
        # - filas arriba del encabezado (título / vacías)
        # - codificación latin1
        # - separadores mezclados o líneas "rotas"
        #
        # Leemos primero SIN encabezado y detectamos en qué fila están las columnas reales.
        raw = pd.read_csv(
            CSV_PATH,
            encoding="latin1",
            sep=None,
            engine="python",
            on_bad_lines="skip",
            dtype=str,
            encoding_errors="replace",
            header=None,
        )

    # Detectar encabezado real (NP, CODIGO, ARTICULO, INVENTARIO, etc.)
    requeridas = {
        _norm(CANDIDATOS_NOMBRE[0]),
        _norm(CANDIDATOS_CODIGO_INTERNO[0]),
        _norm(CANDIDATOS_EXISTENCIA[0]),
    }
    header_row_idx = None
    for i in range(min(len(raw), 80)):  # buscamos en las primeras 80 filas
        fila = {
            _norm(v)
            for v in raw.iloc[i].tolist()
            if v is not None and str(v).strip() != "" and str(v).strip().lower() != "nan"
        }
        if requeridas.issubset(fila):
            header_row_idx = i
            break

    if header_row_idx is None:
        print("No pude detectar automáticamente el encabezado.")
        print("Voy a asumir que la primera fila es el encabezado (fila 1).")
        header_row_idx = 0

    headers = [
        str(v).strip() if v is not None else "" for v in raw.iloc[header_row_idx].tolist()
    ]
    df = raw.iloc[header_row_idx + 1 :].copy()
    df.columns = headers

    # Mapa de columnas normalizadas -> columna real
    colmap = {}
    for c in df.columns:
        nc = _norm(c)
        if nc and nc not in colmap:
            colmap[nc] = c

    def _pick_col(candidatos):
        for cand in candidatos:
            key = _norm(cand)
            if key in colmap:
                return colmap[key]
        return None

    col_nombre = _pick_col(CANDIDATOS_NOMBRE)
    col_codigo = _pick_col(CANDIDATOS_CODIGO_INTERNO)
    col_exist = _pick_col(CANDIDATOS_EXISTENCIA)
    col_categoria = _pick_col(CANDIDATOS_CATEGORIA)
    col_marca = _pick_col(CANDIDATOS_MARCA)
    col_unidad = _pick_col(CANDIDATOS_UNIDAD)

    print(f"Encabezado detectado en la fila: {header_row_idx + 1}")
    print("Columnas detectadas:")
    print(list(df.columns))
    print("Columnas a usar:")
    print(
        {
            "nombre": col_nombre,
            "codigo": col_codigo,
            "existencia": col_exist,
            "categoria": col_categoria,
            "marca": col_marca,
            "unidad": col_unidad,
        }
    )

    if not col_nombre or not col_exist:
        print("No encontré columnas mínimas (ARTICULO/INVENTARIO). Revisa el CSV.")
        return

    with app.app_context():
        creados = 0
        actualizados = 0

        for _, row in df.iterrows():
            nombre = _valor_str(row.get(col_nombre))
            if not nombre:
                continue

            codigo_interno = _valor_str(row.get(col_codigo)) if col_codigo else None
            existencia = _valor_int(row.get(col_exist), default=0)
            categoria = _valor_str(row.get(col_categoria)) if col_categoria else None
            marca = _valor_str(row.get(col_marca)) if col_marca else None
            unidad = _valor_str(row.get(col_unidad)) if col_unidad else None

            articulo = None
            if codigo_interno:
                articulo = Articulo.query.filter_by(
                    codigo_interno=codigo_interno
                ).first()
            if not articulo:
                articulo = Articulo.query.filter_by(nombre=nombre).first()

            if articulo:
                articulo.codigo_interno = articulo.codigo_interno or codigo_interno
                articulo.stock_actual = existencia
                articulo.categoria = articulo.categoria or categoria
                articulo.marca = articulo.marca or marca
                articulo.unidad = articulo.unidad or unidad
                actualizados += 1
            else:
                articulo = Articulo(
                    nombre=nombre,
                    codigo_interno=codigo_interno,
                    stock_actual=existencia,
                    categoria=categoria,
                    marca=marca,
                    unidad=unidad,
                )
                db.session.add(articulo)
                creados += 1

        db.session.commit()
        print(f"Artículos creados: {creados}")
        print(f"Artículos actualizados: {actualizados}")
        if creados == 0 and actualizados == 0:
            print("TIP: Si esto sale en 0, probablemente los nombres de columnas no coinciden.")
            print(
                f"Busco: nombre={CANDIDATOS_NOMBRE}, codigo={CANDIDATOS_CODIGO_INTERNO}, existencia={CANDIDATOS_EXISTENCIA}"
            )


if __name__ == "__main__":
    importar()
