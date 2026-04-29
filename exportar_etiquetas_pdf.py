from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import code39

from app import app, Articulo


OUT_PATH = Path(r"C:\Users\ASUS\OneDrive\Documentos\basededatos\etiquetas_papeleria.pdf")

# Diseño de etiqueta (A4)
PAGE_W, PAGE_H = A4

# 2 columnas x 4 filas (que llene la hoja, como antes)
COLS = 2
ROWS = 4

# Márgenes y separación (para que se vea “a hoja llena”)
MARGIN_X = 15 * mm
MARGIN_Y = 20 * mm
GAP_X = 6 * mm
GAP_Y = 8 * mm

# Tamaño de cada etiqueta calculado para ocupar la hoja
LABEL_W = (PAGE_W - 2 * MARGIN_X - (COLS - 1) * GAP_X) / COLS
LABEL_H = (PAGE_H - 2 * MARGIN_Y - (ROWS - 1) * GAP_Y) / ROWS

# Tamaño del código de barras (lo que pediste)
BAR_W = 45 * mm
BAR_H = 40 * mm


def trunc(texto: str, n: int) -> str:
    texto = (texto or "").strip()
    if len(texto) <= n:
        return texto
    return texto[: max(0, n - 2)] + "…"


def draw_label(c: canvas.Canvas, x: float, y: float, a: Articulo):
    # Marco suave (opcional)
    c.setLineWidth(0.2)
    c.setStrokeGray(0.75)
    c.rect(x, y, LABEL_W, LABEL_H, stroke=1, fill=0)

    nombre = trunc(a.nombre, 30)
    codigo = (a.codigo_barras or a.codigo_interno or "").strip()

    c.setFillGray(0.05)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(x + 5 * mm, y + LABEL_H - 7 * mm, nombre)

    if a.categoria or a.marca:
        meta = " · ".join([p for p in [a.categoria, a.marca] if p])
        c.setFont("Helvetica", 9)
        c.setFillGray(0.25)
        c.drawString(x + 5 * mm, y + LABEL_H - 13 * mm, trunc(meta, 42))

    # Código de barras (Code39, muy compatible con LS2208)
    if codigo:
        safe_code = codigo.strip().upper()
        bc = code39.Standard39(
            safe_code,
            # El alto real total incluye el texto; dejamos el alto de barras un poco menor
            barHeight=(BAR_H - 8 * mm),
            stop=1,
            checksum=0,
            humanReadable=True,
        )
        bw = bc.width
        # Escalamos SOLO en X para que quede exactamente en 45mm de ancho.
        sx = BAR_W / bw if bw else 1.0
        bx = x + (LABEL_W - BAR_W) / 2
        by = y + 6 * mm
        c.saveState()
        c.translate(bx, by)
        c.scale(sx, 1)
        bc.drawOn(c, 0, 0)
        c.restoreState()
    else:
        c.setFont("Helvetica", 7.5)
        c.setFillGray(0.4)
        c.drawString(x + 3 * mm, y + 4 * mm, "SIN CÓDIGO DE BARRAS")


def main():
    with app.app_context():
        articulos = Articulo.query.order_by(Articulo.nombre).all()

        c = canvas.Canvas(str(OUT_PATH), pagesize=A4)
        c.setTitle("Etiquetas - Inventario Papelería")

        i = 0
        for a in articulos:
            col = i % COLS
            row = (i // COLS) % ROWS

            if i > 0 and (i % (COLS * ROWS) == 0):
                c.showPage()

            x = MARGIN_X + col * (LABEL_W + GAP_X)
            y = PAGE_H - MARGIN_Y - (row + 1) * LABEL_H - row * GAP_Y

            draw_label(c, x, y, a)
            i += 1

        c.save()
        print(f"PDF generado en: {OUT_PATH}")
        print(f"Etiquetas: {len(articulos)}")


if __name__ == "__main__":
    main()

