import argparse
import os
import sqlite3
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values


TABLES = [
    "maestro",
    "articulo",
    "herramienta_limpieza",
    "cupo_departamento",
    "movimiento",
    "salida_herramienta",
]


def normalize_pg_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def sqlite_tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {r[0] for r in rows}


def sqlite_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [r[1] for r in rows]


def pg_columns(cur, table: str) -> list[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position
        """,
        (table,),
    )
    return [r[0] for r in cur.fetchall()]


def pg_column_types(cur, table: str) -> dict[str, str]:
    cur.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        """,
        (table,),
    )
    return {name: dtype for name, dtype in cur.fetchall()}


def fetch_sqlite_rows(conn: sqlite3.Connection, table: str, cols: list[str]) -> list[tuple]:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(f"SELECT {', '.join(cols)} FROM {table}")
    rows = cur.fetchall()
    return [tuple(r[c] for c in cols) for r in rows]


def normalize_rows_for_pg(rows: list[tuple], cols: list[str], col_types: dict[str, str]) -> list[tuple]:
    out = []
    for row in rows:
        values = list(row)
        for i, col in enumerate(cols):
            if values[i] is None:
                continue
            if col_types.get(col) == "boolean":
                # SQLite often stores booleans as 0/1 integers.
                values[i] = bool(values[i])
        out.append(tuple(values))
    return out


def reset_sequence(cur, table: str):
    cur.execute(
        """
        SELECT pg_get_serial_sequence(%s, 'id')
        """,
        (f"public.{table}",),
    )
    seq = cur.fetchone()[0]
    if not seq:
        return
    cur.execute(
        f"""
        SELECT setval(%s, COALESCE((SELECT MAX(id) FROM {table}), 1), true)
        """,
        (seq,),
    )


def migrate(sqlite_path: Path, pg_url: str):
    if not sqlite_path.exists():
        raise FileNotFoundError(f"No existe SQLite: {sqlite_path}")

    pg_url = normalize_pg_url(pg_url)
    sqlite_conn = sqlite3.connect(str(sqlite_path))
    pg_conn = psycopg2.connect(pg_url)

    try:
        pg_conn.autocommit = False
        pg_cur = pg_conn.cursor()

        existing_sqlite = sqlite_tables(sqlite_conn)
        tables_to_copy = [t for t in TABLES if t in existing_sqlite]
        if not tables_to_copy:
            raise RuntimeError("No se encontraron tablas para copiar en SQLite.")

        # Limpieza destino en orden inverso por dependencias
        for table in reversed(tables_to_copy):
            pg_cur.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")

        for table in tables_to_copy:
            s_cols = sqlite_columns(sqlite_conn, table)
            p_cols = pg_columns(pg_cur, table)
            p_col_types = pg_column_types(pg_cur, table)
            cols = [c for c in s_cols if c in p_cols]
            if not cols:
                print(f"[SKIP] {table}: no hay columnas compatibles")
                continue

            rows = fetch_sqlite_rows(sqlite_conn, table, cols)
            if not rows:
                print(f"[OK] {table}: 0 filas")
                continue
            rows = normalize_rows_for_pg(rows, cols, p_col_types)

            insert_sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES %s"
            execute_values(pg_cur, insert_sql, rows, page_size=500)
            print(f"[OK] {table}: {len(rows)} filas")

            if "id" in cols:
                reset_sequence(pg_cur, table)

        pg_conn.commit()
        print("Migracion terminada correctamente.")
    except Exception:
        pg_conn.rollback()
        raise
    finally:
        sqlite_conn.close()
        pg_conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Migra datos de SQLite local a PostgreSQL (Render)."
    )
    parser.add_argument(
        "--sqlite-path",
        default=str(Path("instance") / "inventario.db"),
        help="Ruta de la base SQLite local",
    )
    parser.add_argument(
        "--pg-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="URL de PostgreSQL destino (si no, usa DATABASE_URL)",
    )
    args = parser.parse_args()

    if not args.pg_url.strip():
        raise RuntimeError("Falta PostgreSQL URL. Usa --pg-url o define DATABASE_URL.")

    migrate(Path(args.sqlite_path), args.pg_url.strip())


if __name__ == "__main__":
    main()

