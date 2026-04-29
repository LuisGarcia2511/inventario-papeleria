import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).parent / "instance" / "inventario.db"


def col_exists(cur: sqlite3.Cursor, table: str, col: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1] == col for r in cur.fetchall())


def add_col(cur: sqlite3.Cursor, table: str, col: str, col_type: str):
    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
    print(f"OK: agregada columna {table}.{col}")


def main():
    if not DB_PATH.exists():
        print(f"No existe la BD aún: {DB_PATH}")
        print("Primero ejecuta: python app.py (para crearla) y luego vuelve a correr este script.")
        return

    con = sqlite3.connect(str(DB_PATH))
    try:
        cur = con.cursor()

        # Solo migramos si existe la tabla
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='articulo'")
        if not cur.fetchone():
            print("No existe la tabla 'articulo'. Primero importa o crea algún artículo.")
            return

        if not col_exists(cur, "articulo", "categoria"):
            add_col(cur, "articulo", "categoria", "VARCHAR(80)")
        if not col_exists(cur, "articulo", "marca"):
            add_col(cur, "articulo", "marca", "VARCHAR(80)")

        # Maestro.area
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='maestro'")
        if cur.fetchone():
            if not col_exists(cur, "maestro", "area"):
                add_col(cur, "maestro", "area", "VARCHAR(120)")

        # Movimiento.fecha_editado
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='movimiento'")
        if cur.fetchone():
            if not col_exists(cur, "movimiento", "fecha_editado"):
                add_col(cur, "movimiento", "fecha_editado", "DATETIME")
            if not col_exists(cur, "movimiento", "original_tipo"):
                add_col(cur, "movimiento", "original_tipo", "VARCHAR(10)")
            if not col_exists(cur, "movimiento", "original_cantidad"):
                add_col(cur, "movimiento", "original_cantidad", "INTEGER")
            if not col_exists(cur, "movimiento", "original_fecha"):
                add_col(cur, "movimiento", "original_fecha", "DATETIME")
            if not col_exists(cur, "movimiento", "original_comentario"):
                add_col(cur, "movimiento", "original_comentario", "VARCHAR(255)")
            if not col_exists(cur, "movimiento", "original_articulo_id"):
                add_col(cur, "movimiento", "original_articulo_id", "INTEGER")
            if not col_exists(cur, "movimiento", "original_maestro_id"):
                add_col(cur, "movimiento", "original_maestro_id", "INTEGER")
            if not col_exists(cur, "movimiento", "original_articulo_nombre"):
                add_col(cur, "movimiento", "original_articulo_nombre", "VARCHAR(150)")
            if not col_exists(cur, "movimiento", "original_maestro_nombre"):
                add_col(cur, "movimiento", "original_maestro_nombre", "VARCHAR(120)")
            if not col_exists(cur, "movimiento", "original_maestro_area"):
                add_col(cur, "movimiento", "original_maestro_area", "VARCHAR(120)")

        con.commit()
        print("Migración lista.")
    finally:
        con.close()


if __name__ == "__main__":
    main()

