from odoo import api, fields, models


class MercadoImportUnitConfig(models.Model):
    _name = "mercado.import.unit.config"
    _description = "Mercado Import Unit Configuration"
    _order = "code"

    code = fields.Char(
        "Codigo",
        required=True,
        help="Sufijo en la columna P/U (ej: kg, u, p, b)",
    )
    name = fields.Char(
        "Tipo Unidad",
        required=True,
        help="Descripcion legible (ej: kilogramos, unidades, paquetes)",
    )
    uom_search_term = fields.Char(
        "Buscar UoM",
        help="Termino para buscar la UoM de Odoo (ej: 'kg', 'Unit')",
    )
    uom_factor = fields.Float(
        "Factor UoM",
        default=1.0,
        help="Factor de referencia para identificar la UoM base",
    )
    active = fields.Boolean("Activo", default=True)

    _sql_constraints = [
        ("unit_code_unique", "UNIQUE(code)", "El codigo de unidad debe ser unico"),
    ]

    def load_defaults(self):
        defaults = [
            ("kg", "kilogramos", "kg", 0.0),
            ("k",  "kilos",      "kg", 0.0),
            ("u",  "unidades",   "",   1.0),
            ("p",  "paquetes",   "",   1.0),
            ("b",  "bultos",     "",   1.0),
        ]
        existing = {r.code for r in self.search([])}
        to_create = []
        for code, name, search, factor in defaults:
            if code not in existing:
                to_create.append({
                    "code": code,
                    "name": name,
                    "uom_search_term": search,
                    "uom_factor": factor,
                })
        if to_create:
            self.create(to_create)
