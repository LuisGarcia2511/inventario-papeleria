from datetime import datetime
from io import BytesIO
from collections import defaultdict

from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
import pandas as pd


app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-secret-key"
import os
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


MAESTROS_BASE = [
    ("DR. INOCENTE MELITON GARCIA", "DIRECCION"),
    ("DRA. MARIANA LOPEZ VICTORIANO", "SUBDIRECCION ACADEMICA"),
    ("MTRO. BELIB ANGEL ANGELES REYES", "SUBDIRECCION ADMINISTRATIVA"),
    ("LIC. YADIRA ALMANZA GONZALEZ", "UPSE"),
    ("DRA. FABIOLA LIZBETH ARIAS HINOJOSA", "CONTROL ESCOLAR"),
    ("MTRO. ELADIO CEDILLO GONZALEZ", "RECURSOS MATERIALES"),
    ("DRA. EMMA GARCIA PEDROZA", "RECURSOS HUMANOS"),
    ("MTRO. SERGIO GONZALEZ ISIDRO", "POSGRADO"),
    ("MTRA. ROSA LIDIA MERCADO TELLEZ", "PROMOCION Y DIVULGACION CULTURAL"),
    ("MTRO. PAVEL ALEXIS SIERRA TAPIA", "FORMACION INICIAL"),
    ("MTRO. CARLOS FERNANDO TELLEZ CALDERON", "SAF"),
    ("MTRA. AURORA ESTEFANIA AVILA BRAVO", "SEGUIMIENTO A PLANES Y PROGRAMAS DE ESTUDIOS"),
    ("MTRO. ISRAEL CRUZ MARTINEZ", "CONTROL ESCOLAR"),
    ("MTRO. ALAN JOSSUE GARCIA ACUNA", "RECURSOS MATERIALES"),
    ("LIC. SERGIO GARCIA CORRAL", "RECURSOS MATERIALES"),
    ("DR. ALEJANDRO GARCIA OAXACA", "INVESTIGACION E INNOVACION"),
    ("DR. JANUARIO VICTOR MANUEL GARDUNO BASTIDA", "INVESTIGACION E INNOVACION"),
    ("LIC. JORGE GIL CONTRERAS", "RECURSOS HUMANOS"),
    ("LIC. PEDRO GOMEZ GONZUELO", "FORMACION INICIAL"),
    ("MTRO. ABRAHAM GONZAGA VALENCIA", "PROMOCION Y DIVULGACION CULTURAL"),
    ("MTRA. CITLALLI LOPEZ CRUZ", "RECURSOS FINANCIEROS"),
    ("MTRO. MARCO ANTONIO LOPEZ OCTAVIANO", "VINCULACION"),
    ("MTRA. ALICIA ESTHELA MELCHOR DURAN", "UPSE"),
    ("MTRA. MARIA DEL CARMEN MONDRAGON FLORES", "SEGUIMIENTO A PLANES Y PROGRAMAS DE ESTUDIOS"),
    ("LIC. ISABEL MONROY PLATA", "DESARROLLO DOCENTE"),
    ("MTRA. JACQUELINE SALAZAR GARCIA", "FORMACION INICIAL"),
    ("MTRO. JULIO CESAR TOVAR HERNANDEZ", "PROMOCION Y DIVULGACION CULTURAL"),
    ("LIC. KARINA VANESSA VELAZQUEZ RODRIGUEZ", "UPSE"),
    ("MTRA. JANNETH LOZANO REYES", "FORMACION INICIAL"),
    ("LIC. CARLOS GUSTAVO CORTES QUIJADA", "RECURSOS HUMANOS"),
    ("MTRA. YASLIN YATSIDI FLORES ORDONEZ", "HORAS CLASE"),
    ("DR. EDGAR MATINEZ GARDUNO", "HORAS CLASE"),
    ("MTRO. RAFAEL MIRANDA SALGADO", "HORAS CLASE"),
    ("MTRO. OMAR NAVARRETE MONTES DE OCA", "VINCULACION"),
    ("LIC. JESSIA TAVIRA ORTIZ", "PROMOCION Y DIVULGACION CULTURAL"),
    ("MTRA. MARIA FERNANDA ZARATE HENDERSON", "PROMOCION Y DIVULGACION CULTURAL"),
    ("LIC. GLORIA IVONNE ALBARRAN ENCISO", "POSGRADO"),
    ("LIC. ANAYELI AMBROCIO GARCIA", "RECURSOS FINANCIEROS"),
    ("LIC. MAYCA SURISADDAY CARDENAS DE LA LUZ", "HORAS CLASE"),
    ("DR. LUIS JAVIER DIAZ CASTILLO", "HORAS CLASE"),
    ("MTRA. SARAI FELISA DIONICIO GARCIA", "HORAS CLASE"),
    ("LIC. ELIBERTH RUTH FLORES MERCADO", "HORAS CLASE"),
    ("MTRO. MANUEL ANTONIO FLORES MERCADO", "HORAS CLASE"),
    ("MTRA. FELIPA GALVAN JUAREZ", "ARCHIVO"),
    ("DRA. ELIZABETH FAGRIAS SUAREZ", "HORAS CLASE"),
    ("LIC. IRMA LIZETH GUERRA GONZALEZ", "HORAS CLASE"),
    ("MTR. SARAHI HERNANDEZ FLORES", "HORAS CLASE"),
    ("MTRA. IVONNE ITZEL HERNANDEZ MARTINEZ", "HORAS CLASE"),
    ("LIC. AMANCIO LOPEZ IBARRA", "HORAS CLASE"),
    ("LIC. DANIELA YURIDIANA MEJIA CORTES", "HORAS CLASE"),
    ("LIC. GERARDO DE JESUS RODRIGUEZ MARTINEZ", "HORAS CLASE"),
    ("LIC. JAZMIN RODRIGUEZ ORTUNO", "HORAS CLASE"),
    ("LIC. JAQUELINE SANCHEZ VICTORIA", "HORAS CLASE"),
    ("ISAURA LOPEZ OCTAVIANO", "AREA SECRETARIAL"),
    ("MA. DEL CARMEN VENTURA MENDOZA", "AREA SECRETARIAL"),
    ("RUTH HELENA ALVAREZ BAYONA", "AREA SECRETARIAL"),
    ("DOLORES SANDOVAL MARTINEZ", "AREA SECRETARIAL"),
    ("ROSA GONZALEZ GONZALEZ", "RECURSOS MATERIALES"),
    ("OMAR BASTIDA OVANDO", "RECURSOS MATERIALES"),
    ("JORGE FLORES OVANDO", "RECURSOS MATERIALES"),
    ("MARCOS JHOAN GALVEZ GUADARRAMA", "RECURSOS MATERIALES"),
    ("ALEJANDRO GARCIA HERNANDEZ", "RECURSOS MATERIALES"),
    ("JESUS ROMERO OJEDA", "RECURSOS MATERIALES"),
    ("VICTOR MANUEL MARTINEZ RAMIREZ", "RECURSOS MATERIALES"),
    ("RUFINA OVANDO VALDEZ", "RECURSOS MATERIALES"),
]


DEPARTAMENTOS_BASE = sorted({area for _, area in MAESTROS_BASE})


def _norm_col(s: str) -> str:
    return (s or "").strip().upper()


def _to_int(val, default=0) -> int:
    try:
        if pd.isna(val):
            return default
    except Exception:
        pass
    try:
        return int(float(str(val).strip()))
    except Exception:
        return default


class Maestro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    clave = db.Column(db.String(50), unique=True, nullable=True)
    area = db.Column(db.String(120), nullable=True)

    movimientos = db.relationship("Movimiento", backref="maestro", lazy=True)

    def __repr__(self) -> str:
        return f"<Maestro {self.nombre}>"


class Articulo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    codigo_interno = db.Column(db.String(50), unique=True, nullable=True)
    codigo_barras = db.Column(db.String(80), unique=True, nullable=True)
    unidad = db.Column(db.String(30), nullable=True)
    categoria = db.Column(db.String(80), nullable=True)
    marca = db.Column(db.String(80), nullable=True)

    stock_actual = db.Column(db.Integer, default=0, nullable=False)

    movimientos = db.relationship("Movimiento", backref="articulo", lazy=True)

    def __repr__(self) -> str:
        return f"<Articulo {self.nombre}>"


class Movimiento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(10), nullable=False)  # "ENTRADA" o "SALIDA"
    cantidad = db.Column(db.Integer, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    fecha_editado = db.Column(db.DateTime, nullable=True)
    comentario = db.Column(db.String(255), nullable=True)
    persona_recibe = db.Column(db.String(150), nullable=True)

    articulo_id = db.Column(db.Integer, db.ForeignKey("articulo.id"), nullable=False)
    maestro_id = db.Column(db.Integer, db.ForeignKey("maestro.id"), nullable=True)

    # Snapshot del movimiento original (se llena en la primera edición)
    original_tipo = db.Column(db.String(10), nullable=True)
    original_cantidad = db.Column(db.Integer, nullable=True)
    original_fecha = db.Column(db.DateTime, nullable=True)
    original_comentario = db.Column(db.String(255), nullable=True)
    original_articulo_id = db.Column(db.Integer, nullable=True)
    original_maestro_id = db.Column(db.Integer, nullable=True)
    original_articulo_nombre = db.Column(db.String(150), nullable=True)
    original_maestro_nombre = db.Column(db.String(120), nullable=True)
    original_maestro_area = db.Column(db.String(120), nullable=True)

    def __repr__(self) -> str:
        return f"<Movimiento {self.tipo} {self.cantidad}>"


class CupoDepartamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    anio = db.Column(db.Integer, nullable=False)
    area = db.Column(db.String(120), nullable=False)
    articulo_id = db.Column(db.Integer, db.ForeignKey("articulo.id"), nullable=False)
    cantidad_maxima = db.Column(db.Integer, nullable=False, default=0)

    articulo = db.relationship("Articulo", lazy=True)

    __table_args__ = (
        db.UniqueConstraint("anio", "area", "articulo_id", name="uq_cupo_depto_articulo_anio"),
    )

    def __repr__(self) -> str:
        return f"<Cupo {self.area} {self.anio} articulo={self.articulo_id}>"


def _apply_movimiento_to_stock(articulo: Articulo, tipo: str, cantidad: int):
    if tipo == "ENTRADA":
        articulo.stock_actual += cantidad
    elif tipo == "SALIDA":
        articulo.stock_actual -= cantidad


def _revert_movimiento_from_stock(articulo: Articulo, tipo: str, cantidad: int):
    # Revertir es aplicar lo contrario
    if tipo == "ENTRADA":
        articulo.stock_actual -= cantidad
    elif tipo == "SALIDA":
        articulo.stock_actual += cantidad


def _year_expr():
    return db.func.strftime("%Y", Movimiento.fecha)


def _catalogo_departamentos():
    departamentos = set(DEPARTAMENTOS_BASE)
    departamentos_db = (
        db.session.query(Maestro.area)
        .filter(Maestro.area.isnot(None), Maestro.area != "")
        .distinct()
        .all()
    )
    for (area,) in departamentos_db:
        if area:
            departamentos.add(area)
    return sorted(departamentos)


def _ensure_schema_updates():
    # Ajustes ligeros de esquema para instalaciones existentes de SQLite
    cols = {
        row[1]
        for row in db.session.execute(db.text("PRAGMA table_info(movimiento)")).fetchall()
    }
    if "persona_recibe" not in cols:
        db.session.execute(
            db.text("ALTER TABLE movimiento ADD COLUMN persona_recibe VARCHAR(150)")
        )
        db.session.commit()


def _obtener_consumo_departamento(anio: int, area: str, articulo_id: int, excluir_movimiento_id=None) -> int:
    query = (
        db.session.query(db.func.coalesce(db.func.sum(Movimiento.cantidad), 0))
        .join(Maestro, Maestro.id == Movimiento.maestro_id)
        .filter(
            Movimiento.tipo == "SALIDA",
            Movimiento.articulo_id == articulo_id,
            Maestro.area == area,
            _year_expr() == str(anio),
        )
    )
    if excluir_movimiento_id is not None:
        query = query.filter(Movimiento.id != excluir_movimiento_id)
    return int(query.scalar() or 0)


def _validar_cupo_departamento(tipo: str, maestro: Maestro, articulo_id: int, cantidad: int, excluir_movimiento_id=None):
    if tipo != "SALIDA" or not maestro or not maestro.area:
        return True, None

    anio_actual = datetime.utcnow().year
    cupo = CupoDepartamento.query.filter_by(
        anio=anio_actual,
        area=maestro.area,
        articulo_id=articulo_id,
    ).first()
    if not cupo:
        return True, None

    consumido = _obtener_consumo_departamento(
        anio=anio_actual,
        area=maestro.area,
        articulo_id=articulo_id,
        excluir_movimiento_id=excluir_movimiento_id,
    )
    disponible = cupo.cantidad_maxima - consumido
    if cantidad > disponible:
        return (
            False,
            f"El departamento '{maestro.area}' ya no tiene cupo suficiente para este artículo. Disponible: {max(disponible, 0)} de {cupo.cantidad_maxima} en {anio_actual}.",
        )
    return True, None


@app.route("/")
def index():
    total_articulos = Articulo.query.count()
    total_maestros = Maestro.query.count()
    total_entradas = (
        db.session.query(db.func.coalesce(db.func.sum(Movimiento.cantidad), 0))
        .filter(Movimiento.tipo == "ENTRADA")
        .scalar()
    )
    total_salida = (
        db.session.query(db.func.coalesce(db.func.sum(Movimiento.cantidad), 0))
        .filter(Movimiento.tipo == "SALIDA")
        .scalar()
    )

    orden_fecha = db.func.coalesce(Movimiento.fecha_editado, Movimiento.fecha)
    ultimos_movimientos = Movimiento.query.order_by(orden_fecha.desc()).limit(10).all()

    return render_template(
        "index.html",
        total_articulos=total_articulos,
        total_maestros=total_maestros,
        total_entradas=total_entradas,
        total_salida=total_salida,
        ultimos_movimientos=ultimos_movimientos,
    )


@app.route("/export/inventario.xlsx")
def export_inventario():
    articulos = Articulo.query.order_by(Articulo.nombre).all()
    rows = []
    for a in articulos:
        rows.append(
            {
                "CODIGO": a.codigo_interno,
                "CODIGO_BARRAS": a.codigo_barras,
                "ARTICULO": a.nombre,
                "CATEGORIA": a.categoria,
                "MARCA": a.marca,
                "UNIDAD": a.unidad,
                "STOCK": a.stock_actual,
            }
        )

    df = pd.DataFrame(rows)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="INVENTARIO")
    output.seek(0)

    nombre = f"inventario_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(
        output,
        as_attachment=True,
        download_name=nombre,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/export/movimientos.xlsx")
def export_movimientos():
    movimientos = Movimiento.query.order_by(Movimiento.fecha.desc()).all()
    rows = []
    for m in movimientos:
        rows.append(
            {
                "FECHA": m.fecha.strftime("%Y-%m-%d %H:%M:%S"),
                "FECHA_EDITADO": m.fecha_editado.strftime("%Y-%m-%d %H:%M:%S") if m.fecha_editado else None,
                "ORIGINAL_FECHA": m.original_fecha.strftime("%Y-%m-%d %H:%M:%S") if m.original_fecha else None,
                "ORIGINAL_TIPO": m.original_tipo,
                "ORIGINAL_CANTIDAD": m.original_cantidad,
                "ORIGINAL_ARTICULO_ID": m.original_articulo_id,
                "ORIGINAL_MAESTRO_ID": m.original_maestro_id,
                "ORIGINAL_COMENTARIO": m.original_comentario,
                "ORIGINAL_ARTICULO": m.original_articulo_nombre,
                "ORIGINAL_MAESTRO": m.original_maestro_nombre,
                "ORIGINAL_AREA": m.original_maestro_area,
                "TIPO": m.tipo,
                "ARTICULO": m.articulo.nombre if m.articulo else None,
                "CODIGO": m.articulo.codigo_interno if m.articulo else None,
                "CODIGO_BARRAS": m.articulo.codigo_barras if m.articulo else None,
                "MAESTRO": m.maestro.nombre if m.maestro else None,
                "AREA": m.maestro.area if m.maestro else None,
                "QUIEN_RECOGE": m.persona_recibe,
                "CANTIDAD": m.cantidad,
                "COMENTARIO": m.comentario,
            }
        )

    df = pd.DataFrame(rows)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="MOVIMIENTOS")
    output.seek(0)

    nombre = f"movimientos_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(
        output,
        as_attachment=True,
        download_name=nombre,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/import/articulos", methods=["GET", "POST"])
def importar_articulos_excel():
    if request.method == "POST":
        f = request.files.get("archivo")
        if not f:
            flash("No se recibió ningún archivo.", "danger")
            return redirect(url_for("importar_articulos_excel"))

        try:
            df = pd.read_excel(f, dtype=str, header=0)
        except Exception as e:
            flash(f"No pude leer el Excel. Error: {e}", "danger")
            return redirect(url_for("importar_articulos_excel"))

        # Mapear columnas por nombre (ignorando mayúsculas/espacios)
        colmap = {}
        for c in df.columns:
            nc = _norm_col(str(c))
            if nc and nc not in colmap:
                colmap[nc] = c

        def pick(*cands):
            for cand in cands:
                key = _norm_col(cand)
                if key in colmap:
                    return colmap[key]
            return None

        col_codigo = pick("CODIGO", "CÓDIGO")
        col_nombre = pick("NOMBRE DEL ARTICULO", "NOMBRE DEL ARTÍCULO", "ARTICULO", "ARTÍCULO")
        col_cat = pick("CATEGORIA", "CATEGORÍA")
        col_marca = pick("MARCA")
        col_unidad = pick("UNIDAD DE MEDIDA", "UNIDAD")
        col_stock = pick("INVENTARIO EXISTENTE", "INVENTARIO", "STOCK")

        if not col_nombre or not col_stock:
            flash(
                "No encontré columnas mínimas. Necesito al menos 'NOMBRE DEL ARTICULO' y 'INVENTARIO EXISTENTE'.",
                "danger",
            )
            return redirect(url_for("importar_articulos_excel"))

        creados = 0
        actualizados = 0
        saltados = 0

        for _, row in df.iterrows():
            nombre = (row.get(col_nombre) or "").strip()
            if not nombre:
                saltados += 1
                continue

            codigo = (row.get(col_codigo) or "").strip() if col_codigo else ""
            categoria = (row.get(col_cat) or "").strip() if col_cat else ""
            marca = (row.get(col_marca) or "").strip() if col_marca else ""
            unidad = (row.get(col_unidad) or "").strip() if col_unidad else ""
            stock = _to_int(row.get(col_stock), default=0)

            articulo = None
            if codigo:
                articulo = Articulo.query.filter_by(codigo_interno=codigo).first()
            if not articulo:
                articulo = Articulo.query.filter_by(nombre=nombre).first()

            if articulo:
                articulo.nombre = nombre
                if codigo and not articulo.codigo_interno:
                    articulo.codigo_interno = codigo
                articulo.categoria = articulo.categoria or (categoria or None)
                articulo.marca = articulo.marca or (marca or None)
                articulo.unidad = articulo.unidad or (unidad or None)
                articulo.stock_actual = stock
                actualizados += 1
            else:
                articulo = Articulo(
                    nombre=nombre,
                    codigo_interno=(codigo or None),
                    categoria=(categoria or None),
                    marca=(marca or None),
                    unidad=(unidad or None),
                    stock_actual=stock,
                )
                db.session.add(articulo)
                creados += 1

        db.session.commit()
        flash(
            f"Importación lista. Creados: {creados}, actualizados: {actualizados}, saltados: {saltados}.",
            "success",
        )
        return redirect(url_for("listar_articulos"))

    return render_template("importar_articulos.html")


@app.route("/articulos")
def listar_articulos():
    q = request.args.get("q", "").strip()
    if q:
        termino = f"%{q}%"
        articulos = Articulo.query.filter(
            db.or_(
                Articulo.nombre.ilike(termino),
                Articulo.codigo_interno.ilike(termino),
                Articulo.codigo_barras.ilike(termino),
            )
        ).all()
    else:
        articulos = Articulo.query.order_by(Articulo.nombre).all()
    return render_template("articulos.html", articulos=articulos, q=q)


@app.route("/articulos/nuevo", methods=["GET", "POST"])
def nuevo_articulo():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        codigo_interno = request.form.get("codigo_interno", "").strip() or None
        codigo_barras = request.form.get("codigo_barras", "").strip() or None
        unidad = request.form.get("unidad", "").strip() or None
        categoria = request.form.get("categoria", "").strip() or None
        marca = request.form.get("marca", "").strip() or None

        if not nombre:
            flash("El nombre del artículo es obligatorio.", "danger")
            return redirect(url_for("nuevo_articulo"))

        articulo = Articulo(
            nombre=nombre,
            codigo_interno=codigo_interno,
            codigo_barras=codigo_barras,
            unidad=unidad,
            categoria=categoria,
            marca=marca,
        )
        db.session.add(articulo)
        db.session.commit()
        flash("Artículo creado correctamente.", "success")
        return redirect(url_for("listar_articulos"))

    return render_template("articulo_form.html", articulo=None)


@app.route("/articulos/<int:articulo_id>/editar", methods=["GET", "POST"])
def editar_articulo(articulo_id):
    articulo = Articulo.query.get_or_404(articulo_id)

    if request.method == "POST":
        articulo.nombre = request.form.get("nombre", "").strip()
        articulo.codigo_interno = (
            request.form.get("codigo_interno", "").strip() or None
        )
        articulo.codigo_barras = (
            request.form.get("codigo_barras", "").strip() or None
        )
        articulo.unidad = request.form.get("unidad", "").strip() or None
        articulo.categoria = request.form.get("categoria", "").strip() or None
        articulo.marca = request.form.get("marca", "").strip() or None

        if not articulo.nombre:
            flash("El nombre del artículo es obligatorio.", "danger")
            return redirect(url_for("editar_articulo", articulo_id=articulo.id))

        db.session.commit()
        flash("Artículo actualizado correctamente.", "success")
        return redirect(url_for("listar_articulos"))

    return render_template("articulo_form.html", articulo=articulo)


@app.route("/maestros")
def listar_maestros():
    maestros = Maestro.query.order_by(Maestro.area.asc(), Maestro.nombre.asc()).all()
    maestros_por_area = defaultdict(list)
    for maestro in maestros:
        maestros_por_area[maestro.area or "SIN DEPARTAMENTO"].append(maestro)
    return render_template(
        "maestros.html",
        maestros=maestros,
        maestros_por_area=maestros_por_area,
    )


@app.route("/maestros/nuevo", methods=["GET", "POST"])
def nuevo_maestro():
    departamentos = _catalogo_departamentos()
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        clave = request.form.get("clave", "").strip() or None
        area = request.form.get("area", "").strip() or None

        if not nombre:
            flash("El nombre del maestro es obligatorio.", "danger")
            return redirect(url_for("nuevo_maestro"))

        maestro = Maestro(nombre=nombre, clave=clave, area=area)
        db.session.add(maestro)
        db.session.commit()
        flash("Maestro creado correctamente.", "success")
        return redirect(url_for("listar_maestros"))

    return render_template("maestro_form.html", maestro=None, departamentos=departamentos)


@app.route("/maestros/<int:maestro_id>/editar", methods=["GET", "POST"])
def editar_maestro(maestro_id):
    maestro = Maestro.query.get_or_404(maestro_id)
    departamentos = _catalogo_departamentos()

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        clave = request.form.get("clave", "").strip() or None
        area = request.form.get("area", "").strip() or None

        if not nombre:
            flash("El nombre del maestro es obligatorio.", "danger")
            return redirect(url_for("editar_maestro", maestro_id=maestro.id))

        maestro.nombre = nombre
        maestro.clave = clave
        maestro.area = area
        db.session.commit()
        flash("Maestro actualizado correctamente.", "success")
        return redirect(url_for("listar_maestros"))

    return render_template(
        "maestro_form.html",
        maestro=maestro,
        departamentos=departamentos,
    )


@app.route("/maestros/cargar-base", methods=["POST"])
def cargar_maestros_base():
    creados = 0
    existentes = 0

    for nombre, area in MAESTROS_BASE:
        ya_existe = Maestro.query.filter_by(nombre=nombre).first()
        if ya_existe:
            existentes += 1
            if not ya_existe.area:
                ya_existe.area = area
            continue
        db.session.add(Maestro(nombre=nombre, area=area))
        creados += 1

    db.session.commit()
    flash(
        f"Carga terminada. Nuevos: {creados}. Ya existentes: {existentes}.",
        "success",
    )
    return redirect(url_for("listar_maestros"))


@app.route("/movimientos/nuevo", methods=["GET", "POST"])
def nuevo_movimiento():
    articulos = Articulo.query.order_by(Articulo.nombre).all()
    maestros = Maestro.query.order_by(Maestro.nombre).all()

    if request.method == "POST":
        tipo = request.form.get("tipo")
        articulo_id = request.form.get("articulo_id")
        codigo_barras = request.form.get("codigo_barras", "").strip() or None
        maestro_id = request.form.get("maestro_id") or None
        cantidad = request.form.get("cantidad")
        comentario = request.form.get("comentario", "").strip() or None
        persona_recibe = request.form.get("persona_recibe", "").strip() or None

        try:
            cantidad_int = int(cantidad)
        except (TypeError, ValueError):
            flash("La cantidad debe ser un número entero.", "danger")
            return redirect(url_for("nuevo_movimiento"))

        if cantidad_int <= 0:
            flash("La cantidad debe ser mayor que cero.", "danger")
            return redirect(url_for("nuevo_movimiento"))

        articulo = None

        # 1) Si se escaneó un código, buscar primero por código de barras,
        # luego por código interno y, como último recurso, por nombre exacto.
        if codigo_barras:
            articulo = Articulo.query.filter(
                db.or_(
                    Articulo.codigo_barras == codigo_barras,
                    Articulo.codigo_interno == codigo_barras,
                    Articulo.nombre == codigo_barras,
                )
            ).first()
            if not articulo:
                flash(
                    f"No encontré ningún artículo con el código escaneado: {codigo_barras}",
                    "danger",
                )
                return redirect(url_for("nuevo_movimiento"))

        # 2) Si no hay código o no se encontró, usar el select manual.
        if not articulo:
            if not articulo_id:
                flash(
                    "Debes seleccionar un artículo o escanear un código de barras.",
                    "danger",
                )
                return redirect(url_for("nuevo_movimiento"))
            articulo = Articulo.query.get_or_404(articulo_id)

        if tipo == "SALIDA" and articulo.stock_actual - cantidad_int < 0:
            flash(
                f"No hay suficiente stock para esta salida de '{articulo.nombre}'.",
                "danger",
            )
            return redirect(url_for("nuevo_movimiento"))

        maestro = Maestro.query.get(maestro_id) if maestro_id else None
        if tipo == "SALIDA" and not maestro:
            flash("Para registrar una salida debes seleccionar un docente.", "danger")
            return redirect(url_for("nuevo_movimiento"))
        if tipo == "SALIDA" and not persona_recibe:
            flash("Para salidas indica quién vino a recoger el artículo.", "danger")
            return redirect(url_for("nuevo_movimiento"))

        es_valido, mensaje = _validar_cupo_departamento(
            tipo=tipo,
            maestro=maestro,
            articulo_id=articulo.id,
            cantidad=cantidad_int,
        )
        if not es_valido:
            flash(mensaje, "danger")
            return redirect(url_for("nuevo_movimiento"))

        movimiento = Movimiento(
            tipo=tipo,
            cantidad=cantidad_int,
            articulo_id=articulo.id,
            maestro_id=maestro_id,
            comentario=comentario,
            persona_recibe=persona_recibe,
        )
        db.session.add(movimiento)

        _apply_movimiento_to_stock(articulo, tipo, cantidad_int)

        db.session.commit()
        flash("Movimiento registrado correctamente.", "success")
        return redirect(url_for("index"))

    return render_template(
        "movimiento_form.html", articulos=articulos, maestros=maestros
    )


@app.route("/movimientos/<int:movimiento_id>/editar", methods=["GET", "POST"])
def editar_movimiento(movimiento_id):
    movimiento = Movimiento.query.get_or_404(movimiento_id)
    articulos = Articulo.query.order_by(Articulo.nombre).all()
    maestros = Maestro.query.order_by(Maestro.nombre).all()

    if request.method == "POST":
        # Guardar snapshot del "antes" SOLO la primera vez que se edita
        if movimiento.original_fecha is None:
            movimiento.original_fecha = movimiento.fecha
            movimiento.original_tipo = movimiento.tipo
            movimiento.original_cantidad = movimiento.cantidad
            movimiento.original_articulo_id = movimiento.articulo_id
            movimiento.original_maestro_id = movimiento.maestro_id
            movimiento.original_comentario = movimiento.comentario
            movimiento.original_articulo_nombre = (
                movimiento.articulo.nombre if movimiento.articulo else None
            )
            movimiento.original_maestro_nombre = (
                movimiento.maestro.nombre if movimiento.maestro else None
            )
            movimiento.original_maestro_area = (
                movimiento.maestro.area if movimiento.maestro else None
            )

        tipo = request.form.get("tipo")
        articulo_id = request.form.get("articulo_id")
        codigo_barras = request.form.get("codigo_barras", "").strip() or None
        maestro_id = request.form.get("maestro_id") or None
        cantidad = request.form.get("cantidad")
        comentario = request.form.get("comentario", "").strip() or None
        persona_recibe = request.form.get("persona_recibe", "").strip() or None

        try:
            cantidad_int = int(cantidad)
        except (TypeError, ValueError):
            flash("La cantidad debe ser un número entero.", "danger")
            return redirect(url_for("editar_movimiento", movimiento_id=movimiento.id))

        if cantidad_int <= 0:
            flash("La cantidad debe ser mayor que cero.", "danger")
            return redirect(url_for("editar_movimiento", movimiento_id=movimiento.id))

        articulo_nuevo = None
        if codigo_barras:
            articulo_nuevo = Articulo.query.filter(
                db.or_(
                    Articulo.codigo_barras == codigo_barras,
                    Articulo.codigo_interno == codigo_barras,
                    Articulo.nombre == codigo_barras,
                )
            ).first()
            if not articulo_nuevo:
                flash(
                    f"No encontré ningún artículo con el código escaneado: {codigo_barras}",
                    "danger",
                )
                return redirect(url_for("editar_movimiento", movimiento_id=movimiento.id))

        if not articulo_nuevo:
            if not articulo_id:
                flash(
                    "Debes seleccionar un artículo o escanear un código de barras.",
                    "danger",
                )
                return redirect(url_for("editar_movimiento", movimiento_id=movimiento.id))
            articulo_nuevo = Articulo.query.get_or_404(articulo_id)

        maestro_nuevo = Maestro.query.get(maestro_id) if maestro_id else None
        if tipo == "SALIDA" and not maestro_nuevo:
            flash("Para registrar una salida debes seleccionar un docente.", "danger")
            return redirect(url_for("editar_movimiento", movimiento_id=movimiento.id))
        if tipo == "SALIDA" and not persona_recibe:
            flash("Para salidas indica quién vino a recoger el artículo.", "danger")
            return redirect(url_for("editar_movimiento", movimiento_id=movimiento.id))

        articulo_viejo = movimiento.articulo

        # Revertir el impacto anterior
        _revert_movimiento_from_stock(articulo_viejo, movimiento.tipo, movimiento.cantidad)

        # Validar stock con el nuevo movimiento
        if tipo == "SALIDA" and articulo_nuevo.stock_actual - cantidad_int < 0:
            # Volver a aplicar el movimiento viejo antes de salir
            _apply_movimiento_to_stock(articulo_viejo, movimiento.tipo, movimiento.cantidad)
            flash(
                f"No hay suficiente stock para esta salida de '{articulo_nuevo.nombre}'.",
                "danger",
            )
            db.session.rollback()
            return redirect(url_for("editar_movimiento", movimiento_id=movimiento.id))

        es_valido, mensaje = _validar_cupo_departamento(
            tipo=tipo,
            maestro=maestro_nuevo,
            articulo_id=articulo_nuevo.id,
            cantidad=cantidad_int,
            excluir_movimiento_id=movimiento.id,
        )
        if not es_valido:
            _apply_movimiento_to_stock(articulo_viejo, movimiento.tipo, movimiento.cantidad)
            flash(mensaje, "danger")
            db.session.rollback()
            return redirect(url_for("editar_movimiento", movimiento_id=movimiento.id))

        # Aplicar nuevo impacto
        _apply_movimiento_to_stock(articulo_nuevo, tipo, cantidad_int)

        movimiento.tipo = tipo
        movimiento.cantidad = cantidad_int
        movimiento.articulo_id = articulo_nuevo.id
        movimiento.maestro_id = maestro_id
        movimiento.comentario = comentario
        movimiento.persona_recibe = persona_recibe
        movimiento.fecha_editado = datetime.utcnow()

        db.session.commit()
        flash("Movimiento actualizado correctamente.", "success")
        return redirect(url_for("index"))

    return render_template(
        "movimiento_form.html",
        articulos=articulos,
        maestros=maestros,
        movimiento=movimiento,
    )


@app.route("/movimientos/<int:movimiento_id>/borrar", methods=["POST"])
def borrar_movimiento(movimiento_id):
    movimiento = Movimiento.query.get_or_404(movimiento_id)
    articulo = movimiento.articulo

    _revert_movimiento_from_stock(articulo, movimiento.tipo, movimiento.cantidad)
    db.session.delete(movimiento)
    db.session.commit()

    flash("Movimiento borrado correctamente.", "success")
    return redirect(url_for("index"))


@app.route("/control/departamentos", methods=["GET", "POST"])
def control_departamentos():
    anio = _to_int(request.args.get("anio"), default=datetime.utcnow().year)
    departamentos = _catalogo_departamentos()

    if request.method == "POST":
        anio_form = _to_int(request.form.get("anio"), default=datetime.utcnow().year)
        area = request.form.get("area", "").strip()
        articulo_id = _to_int(request.form.get("articulo_id"), default=0)
        cantidad_maxima = _to_int(request.form.get("cantidad_maxima"), default=-1)

        if not area:
            flash("El departamento o edificio es obligatorio.", "danger")
            return redirect(url_for("control_departamentos", anio=anio_form))
        if articulo_id <= 0:
            flash("Debes seleccionar un artículo para configurar el cupo.", "danger")
            return redirect(url_for("control_departamentos", anio=anio_form))
        if cantidad_maxima < 0:
            flash("El cupo anual debe ser 0 o mayor.", "danger")
            return redirect(url_for("control_departamentos", anio=anio_form))

        cupo = CupoDepartamento.query.filter_by(
            anio=anio_form,
            area=area,
            articulo_id=articulo_id,
        ).first()
        if cupo:
            cupo.cantidad_maxima = cantidad_maxima
            flash("Cupo anual actualizado.", "success")
        else:
            cupo = CupoDepartamento(
                anio=anio_form,
                area=area,
                articulo_id=articulo_id,
                cantidad_maxima=cantidad_maxima,
            )
            db.session.add(cupo)
            flash("Cupo anual creado.", "success")

        db.session.commit()
        return redirect(url_for("control_departamentos", anio=anio_form))

    articulos = Articulo.query.order_by(Articulo.nombre).all()

    cupos = (
        CupoDepartamento.query.filter_by(anio=anio)
        .order_by(CupoDepartamento.area, CupoDepartamento.articulo_id)
        .all()
    )
    cupos_resumen = []
    for c in cupos:
        consumido = _obtener_consumo_departamento(anio, c.area, c.articulo_id)
        cupos_resumen.append(
            {
                "id": c.id,
                "anio": c.anio,
                "area": c.area,
                "articulo": c.articulo.nombre if c.articulo else "-",
                "maximo": c.cantidad_maxima,
                "consumido": consumido,
                "disponible": c.cantidad_maxima - consumido,
            }
        )

    resumen_departamentos = (
        db.session.query(
            Maestro.area.label("area"),
            db.func.coalesce(
                db.func.sum(db.case((Movimiento.tipo == "ENTRADA", Movimiento.cantidad), else_=0)),
                0,
            ).label("entradas"),
            db.func.coalesce(
                db.func.sum(db.case((Movimiento.tipo == "SALIDA", Movimiento.cantidad), else_=0)),
                0,
            ).label("salidas"),
        )
        .join(Movimiento, Movimiento.maestro_id == Maestro.id)
        .filter(Maestro.area.isnot(None), _year_expr() == str(anio))
        .group_by(Maestro.area)
        .order_by(Maestro.area)
        .all()
    )

    resumen_docentes = (
        db.session.query(
            Maestro.nombre.label("docente"),
            Maestro.area.label("area"),
            db.func.coalesce(
                db.func.sum(db.case((Movimiento.tipo == "ENTRADA", Movimiento.cantidad), else_=0)),
                0,
            ).label("entradas"),
            db.func.coalesce(
                db.func.sum(db.case((Movimiento.tipo == "SALIDA", Movimiento.cantidad), else_=0)),
                0,
            ).label("salidas"),
        )
        .join(Movimiento, Movimiento.maestro_id == Maestro.id)
        .filter(_year_expr() == str(anio))
        .group_by(Maestro.id, Maestro.nombre, Maestro.area)
        .order_by(Maestro.nombre)
        .all()
    )

    return render_template(
        "control_departamentos.html",
        anio=anio,
        articulos=articulos,
        departamentos=departamentos,
        cupos_resumen=cupos_resumen,
        resumen_departamentos=resumen_departamentos,
        resumen_docentes=resumen_docentes,
    )
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        _ensure_schema_updates()
    app.run(debug=True)
