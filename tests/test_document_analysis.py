import pytest

from app.services.document_analysis import DocumentAnalyzerService


def _service_without_init():
    return DocumentAnalyzerService.__new__(DocumentAnalyzerService)


@pytest.mark.parametrize(
    ("label", "text", "expected"),
    [
        (
            "cliente",
            "Cliente: Juan Perez Av. Siempre Viva 123, Buenos Aires Proveedor: X Corp",
            {"nombre": "Juan Perez", "direccion": "Av. Siempre Viva 123, Buenos Aires"},
        ),
        (
            "cliente",
            "Cliente: Ana López Calle Falsa 456 Lima Peru Fecha: 01/01/2024",
            {"nombre": "Ana López", "direccion": "Calle Falsa 456 Lima Peru"},
        ),
        (
            "cliente",
            "Cliente: Industrias Ñu\nRuta 8 KM 45, Montevideo\nNúmero de factura: 123",
            {"nombre": "Industrias Ñu", "direccion": "Ruta 8 KM 45, Montevideo"},
        ),
        (
            "cliente",
            "Cliente: Solo Nombre\nProveedor: Otro",
            {"nombre": "Solo Nombre", "direccion": None},
        ),
        (
            "proveedor",
            "Cliente: A B Calle 1 100\nProveedor: COMERCIAL SA Boulevard Central 99 Santiago, Chile",
            {"nombre": "COMERCIAL SA", "direccion": "Boulevard Central 99 Santiago, Chile"},
        ),
        (
            "proveedor",
            "Proveedor: Servicios S.A. Cl 50 #123 Medellín Descripción:",
            {"nombre": "Servicios S.A.", "direccion": "Cl 50 #123 Medellín"},
        ),
        (
            "cliente",
            "cliente: Maria Gomez, Montevideo Uruguay",
            {"nombre": "Maria Gomez", "direccion": "Montevideo Uruguay"},
        ),
        (
            "cliente",
            "PROVEEDOR: X Corp\nCliente: Org XYZ Carrera 7 77-01 Bogotá Total: 10",
            {"nombre": "Org XYZ", "direccion": "Carrera 7 77-01 Bogotá"},
        ),
        (
            "cliente",
            "Cliente: Innovaciones SAS Avenida Colón 500 Córdoba Numero:",
            {"nombre": "Innovaciones SAS", "direccion": "Avenida Colón 500 Córdoba"},
        ),
        (
            "proveedor",
            "Cliente: Foo\nProveedor: NoAddress\nFecha: 04/04/24",
            {"nombre": "NoAddress", "direccion": None},
        ),
        (
            "cliente",
            "Proveedor: ACME\nFecha: 01/02/2024",
            None,
        ),
    ],
)
def test_extract_party_block_cases(label, text, expected):
    result = DocumentAnalyzerService._extract_party_block(text, label)
    assert result == expected


PRODUCT_TEMPLATE = """
Cantidad Producto Precio Unitario Total
{line}
Total de la factura: 1
"""


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("2 Laptop Lenovo $500.00 $1,000.00", {"cantidad": 2, "nombre": "Laptop Lenovo", "precio": 500.0, "total": 1000.0}),
        ("1 Mouse Logitech $20.50 $20.50", {"cantidad": 1, "nombre": "Mouse Logitech", "precio": 20.5, "total": 20.5}),
        ("10 Cable HDMI $5 $50", {"cantidad": 10, "nombre": "Cable HDMI", "precio": 5.0, "total": 50.0}),
        ("3 Monitor 24 $300,00 $900,00", {"cantidad": 3, "nombre": "Monitor 24", "precio": 300.0, "total": 900.0}),
        ("7 Disco SSD $120.99 $846.93", {"cantidad": 7, "nombre": "Disco SSD", "precio": 120.99, "total": 846.93}),
        ("5 Teclado-Mecánico $89.5 $447.5", {"cantidad": 5, "nombre": "Teclado-Mecánico", "precio": 89.5, "total": 447.5}),
        ("4 Cámara Ágil $150 $600", {"cantidad": 4, "nombre": "Cámara Ágil", "precio": 150.0, "total": 600.0}),
        ("9 UPS PRO $250.00 $2,250.00", {"cantidad": 9, "nombre": "UPS PRO", "precio": 250.0, "total": 2250.0}),
        ("6 Router AX $135,75 $814,50", {"cantidad": 6, "nombre": "Router AX", "precio": 135.75, "total": 814.5}),
        ("8 Cable RJ45 $3.25 $26.00", {"cantidad": 8, "nombre": "Cable RJ45", "precio": 3.25, "total": 26.0}),
    ],
)
def test_extract_products_cases(line, expected):
    analyzer = _service_without_init()
    items = analyzer._extract_products(PRODUCT_TEMPLATE.format(line=line))
    assert len(items) >= 1
    first = items[0]
    assert first.cantidad == expected["cantidad"]
    assert first.nombre == expected["nombre"]
    assert first.precio_unitario == pytest.approx(expected["precio"])
    assert first.total == pytest.approx(expected["total"])

