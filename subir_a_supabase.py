"""
Crea tablas en Supabase/PostgreSQL y copia los datos desde SQLite local.

Uso:
  set DATABASE_URL=postgresql://usuario:pass@host:5432/postgres
  python subir_a_supabase.py

O con la URL directa:
  python subir_a_supabase.py --pg-url "postgresql://..."
"""
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent
DEFAULT_SQLITE = ROOT / "instance" / "inventario.db"


def crear_tablas(pg_url: str) -> None:
    os.environ["DATABASE_URL"] = pg_url
    from app import app, db, _ensure_schema_updates

    with app.app_context():
        db.create_all()
        _ensure_schema_updates()
    print("[OK] Tablas creadas/actualizadas en PostgreSQL.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sube inventario local (SQLite) a Supabase/PostgreSQL."
    )
    parser.add_argument(
        "--sqlite-path",
        default=str(DEFAULT_SQLITE),
        help="Ruta de inventario.db local",
    )
    parser.add_argument(
        "--pg-url",
        default=os.environ.get("DATABASE_URL", "").strip(),
        help="URI de Supabase (o define DATABASE_URL)",
    )
    args = parser.parse_args()

    if not args.pg_url:
        print(
            "Falta la URL de Supabase.\n"
            "1. En Supabase: Project Settings -> Database -> Connection string (URI)\n"
            "2. Usa modo 'Session' o 'Direct' y reemplaza [YOUR-PASSWORD]\n"
            "3. Ejecuta:\n"
            '   python subir_a_supabase.py --pg-url "postgresql://..."'
        )
        sys.exit(1)

    sqlite_path = Path(args.sqlite_path)
    if not sqlite_path.exists():
        print(f"No existe la base local: {sqlite_path}")
        sys.exit(1)

    print(f"SQLite: {sqlite_path}")
    print("Destino: PostgreSQL (Supabase)")
    crear_tablas(args.pg_url)

    from migrar_sqlite_a_render import migrate

    migrate(sqlite_path, args.pg_url)
    print("\nListo. Reinicia tu app en Render y verifica que DATABASE_URL apunte a Supabase.")


if __name__ == "__main__":
    main()
