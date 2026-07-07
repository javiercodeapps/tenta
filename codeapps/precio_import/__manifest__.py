{
    "name": "Precio Import",
    "version": "18.0.1.0.0",
    "category": "Sales",
    "summary": "Importar/Exportar precios desde Excel y TXT",
    "description": """
Precio Import
=============
Permite importar precios desde un archivo Excel (codigo, descripcion, precio)
y exportar precios al formato TXT de iTegra.
    """,
    "author": "Custom",
    "license": "LGPL-3",
    "depends": [
        "sale",
        "product",
    ],
    "external_dependencies": {
        "python": ["openpyxl"],
    },
    "data": [
        "security/ir.model.access.csv",
        "views/precio_import_views.xml",
    ],
    "images": ["static/description/icon.png"],
    "installable": True,
    "application": True,
}
