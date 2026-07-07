from odoo import api, fields, models


class MercadoImportPurchaseLine(models.Model):
    _name = "mercado.import.purchase.line"
    _description = "Mercado Import Purchase Line"
    _order = "supplier_ref, product_name"

    batch_id = fields.Many2one(
        "mercado.import.batch",
        string="Import Batch",
        required=True,
        ondelete="cascade",
    )

    product_code = fields.Char("Codigo Producto")
    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        domain=[("sale_ok", "=", True)],
    )
    product_name = fields.Char("Nombre Producto")

    supplier_ref = fields.Char("Ref Proveedor")
    supplier_id = fields.Many2one(
        "res.partner",
        string="Proveedor",
        domain=[("supplier_rank", ">", 0)],
    )
    supplier_name = fields.Char("Nombre Proveedor")

    marca = fields.Char("Marca")
    tipo = fields.Char("Tipo (V/F)")

    p_u_raw = fields.Char("P/U Raw")
    p_u_qty = fields.Float("Cantidad P/U")
    p_u_unit_code = fields.Char("Codigo Unidad")
    p_u_unit_type = fields.Char("Tipo Unidad")

    has_sena = fields.Boolean("Senia")
    valor_sena = fields.Float("Valor Senia")

    costo_unit = fields.Float("Costo Unitario")
    venta_unit = fields.Float("Venta Unitario")
    total_qty = fields.Integer("Cantidad Total")

    costo_mercad = fields.Float("Costo Mercaderia")
    costo_vacio = fields.Float("Costo Vacio")
    total = fields.Float("Total")

    @api.onchange("product_code")
    def _onchange_product_code(self):
        if self.product_code:
            product = self.env["product.product"].search([
                ("default_code", "=", self.product_code),
            ], limit=1)
            if product:
                self.product_id = product.id
                if not self.product_name:
                    self.product_name = product.name

    @api.onchange("supplier_ref")
    def _onchange_supplier_ref(self):
        if self.supplier_ref:
            partner = self.env["res.partner"].search([
                ("ref", "=", self.supplier_ref),
            ], limit=1)
            if partner:
                self.supplier_id = partner.id
                if not self.supplier_name:
                    self.supplier_name = partner.name

    def _get_product_uom(self):
        self.ensure_one()
        if not self.product_id:
            return self.env["uom.uom"]

        product = self.product_id
        unit_code = self.p_u_unit_code
        unit_type = self.p_u_unit_type

        if not unit_type:
            return product.uom_id

        unit_config = self.env["mercado.import.unit.config"].search([
            ("code", "=", unit_code.lower()),
            ("active", "=", True),
        ], limit=1) if unit_code else None

        if not unit_config:
            if unit_type in ("kilogramos", "kilos"):
                unit_config = self.env["mercado.import.unit.config"].search([
                    ("name", "in", ("kilogramos", "kilos")),
                    ("active", "=", True),
                ], limit=1)
            elif unit_type == "unidades":
                unit_config = self.env["mercado.import.unit.config"].search([
                    ("name", "=", "unidades"),
                    ("active", "=", True),
                ], limit=1)

        if unit_config:
            search_term = unit_config.uom_search_term
            if search_term:
                uom = self.env["uom.uom"].search([
                    ("category_id", "=", product.uom_id.category_id.id),
                    ("name", "ilike", search_term),
                ], limit=1)
                if uom:
                    return uom

            factor = unit_config.uom_factor
            if factor:
                uom = self.env["uom.uom"].search([
                    ("category_id", "=", product.uom_id.category_id.id),
                    ("factor", "=", factor),
                ], limit=1)
                if uom:
                    return uom

        return product.uom_id

    def action_assign_product(self):
        for line in self:
            if line.product_code:
                product = self.env["product.product"].search([
                    ("default_code", "=", line.product_code),
                ], limit=1)
                if product:
                    line.product_id = product.id
            if line.supplier_ref:
                partner = self.env["res.partner"].search([
                    ("ref", "=", line.supplier_ref),
                ], limit=1)
                if partner:
                    line.supplier_id = partner.id
