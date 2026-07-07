{
    "name": "Mercado Import",
    "version": "18.0.1.0.0",
    "category": "Inventory/Purchase",
    "summary": "Import mercado.xlsx and generate purchase/sale orders",
    "description": """
Mercado Import
==============
Loads the mercado.xlsx spreadsheet and automatically generates:
1. Purchase orders from LAAMISTAD to each supplier
2. Sale orders from LAAMISTAD to partners in each branch company
3. Internal purchase orders within each branch company (LAAMISTAD as supplier)

Workflow:
1. Create a batch and upload the Excel file
2. Parse the file -> purchase and sale lines are created
3. Review and correct data in editable tree views
4. Assign products automatically or manually
5. Mark as reviewed
6. Generate orders
""",
    "author": "Custom",
    "website": "",
    "license": "LGPL-3",
    "depends": [
        "purchase",
        "sale_management",
        "account",
    ],
    "external_dependencies": {
        "python": ["openpyxl"],
    },
    "data": [
        "security/ir.model.access.csv",
        "security/mercado_import_security.xml",
        "data/mercado_import_sequence.xml",
        "views/mercado_import_views.xml",
        "views/mercado_import_wizard_views.xml",
        "views/mercado_import_menus.xml",
    ],
    "images": ["static/description/icon.png"],
    "installable": True,
    "application": True,
}
