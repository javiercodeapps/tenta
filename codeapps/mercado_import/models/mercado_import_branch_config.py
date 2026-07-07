from odoo import api, fields, models


class MercadoImportBranchConfig(models.Model):
    _name = "mercado.import.branch.config"
    _description = "Mercado Import Branch Configuration"
    _order = "name"

    name = fields.Char("Sucursal", required=True)
    company_id = fields.Many2one(
        "res.company",
        string="Empresa",
        help="Empresa asociada a esta sucursal",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        help="Partner cliente de esta sucursal",
    )
    qty_col = fields.Integer(
        "Columna Cantidad",
        required=True,
        help="Numero de columna en el Excel (1-based, A=1)",
    )
    sale_col = fields.Integer(
        "Columna Venta",
        required=True,
        help="Numero de columna en el Excel (1-based, A=1)",
    )
    active = fields.Boolean("Activo", default=True)

    _sql_constraints = [
        ("branch_name_unique", "UNIQUE(name)", "El nombre de sucursal debe ser unico"),
    ]

    def load_defaults(self):
        defaults = [
            ("CERVIÑO",    13, 14),
            ("LAFINUR",    15, 16),
            ("LACROZE",    17, 18),
            ("CABILDO",    19, 20),
            ("ECHEVERRIA", 21, 22),
            ("JURADO",     23, 24),
            ("OLLEROS",    25, 26),
            ("VTE_LOPEZ",  27, 28),
            ("MARTINEZ",   29, 30),
            ("SAN_ISIDRO", 31, 32),
            ("LIBERTAD",   33, 34),
            ("OTROS",      35, 36),
        ]
        existing = {r.name for r in self.search([])}
        to_create = []
        for name, qty, sale in defaults:
            if name not in existing:
                to_create.append({
                    "name": name,
                    "qty_col": qty,
                    "sale_col": sale,
                })
        if to_create:
            self.create(to_create)
