from app import app, db, Articulo


# Formato recomendado para Code-128 (lectores lo leen como texto tal cual).
# Ejemplo: PAP-000241
PREFIJO = "PAP"
LARGO_NUM = 6


def generar_codigo(articulo: Articulo) -> str:
    # Si ya tiene código interno tipo P001, úsalo tal cual para que te sea familiar.
    if articulo.codigo_interno:
        return str(articulo.codigo_interno).strip()
    return f"{PREFIJO}-{articulo.id:0{LARGO_NUM}d}"


def main():
    with app.app_context():
        total = 0
        asignados = 0

        articulos = Articulo.query.order_by(Articulo.id).all()
        for a in articulos:
            total += 1
            if a.codigo_barras:
                continue

            codigo = generar_codigo(a)

            # Evitar duplicados
            existe = Articulo.query.filter(Articulo.codigo_barras == codigo, Articulo.id != a.id).first()
            if existe:
                # Si choca, cae al formato PAP-000001
                codigo = f"{PREFIJO}-{a.id:0{LARGO_NUM}d}"

            a.codigo_barras = codigo
            asignados += 1

        db.session.commit()
        print(f"Artículos totales: {total}")
        print(f"Códigos de barras asignados: {asignados}")


if __name__ == "__main__":
    main()

