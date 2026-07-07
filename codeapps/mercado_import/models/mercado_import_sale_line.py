from odoo import api, fields, models


class MercadoImportSaleLine(models.Model):
    _name = "mercado.import.sale.line"
    _description = "Mercado Import Sale Line"
    _order = "branch_ref, product_name"

    batch_id = fields.Many2one(
        "mercado.import.batch",
        string="Import Batch",
        required=True,
        ondelete="cascade",
    )

    branch_ref = fields.Char("Sucursal")
    branch_company_id = fields.Many2one(
        "res.company",
        string="Empresa Sucursal",
    )
    branch_partner_id = fields.Many2one(
        "res.partner",
        string="Cliente Sucursal",
    )

    product_code = fields.Char("Codigo Producto")
    product_id = fields.Many2one(
        "product.product",
        string="Producto",
    )
    product_name = fields.Char("Nombre Producto")

    supplier_ref = fields.Char("Ref Proveedor")
    supplier_name = fields.Char("Proveedor")

    qty = fields.Integer("Cantidad")
    unit_sale = fields.Float("Precio Venta Unitario")
    total_sale = fields.Float("Total Venta")

    has_sena = fields.Boolean("Senia")

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

    @api.onchange("branch_ref")
    def _onchange_branch_ref(self):
        if self.branch_ref:
            branch_cfg = self.env["mercado.import.branch.config"].search([
                ("name", "=", self.branch_ref),
                ("active", "=", True),
            ], limit=1)
            if branch_cfg:
                self.branch_company_id = branch_cfg.company_id.id
                self.branch_partner_id = branch_cfg.partner_id.id
            else:
                company = self.env["res.company"].search([
                    ("ref", "=", self.branch_ref),
                ], limit=1)
                if company:
                    self.branch_company_id = company.id
                partner = self.env["res.partner"].search([
                    ("ref", "=", self.branch_ref),
                    ("company_id", "=", company.id if company else False),
                ], limit=1)
                if partner:
                    self.branch_partner_id = partner.id

    def action_assign_all(self):
        for line in self:
            if line.product_code:
                product = self.env["product.product"].search([
                    ("default_code", "=", line.product_code),
                ], limit=1)
                if product:
                    line.product_id = product.id
            if line.branch_ref:
                branch_cfg = self.env["mercado.import.branch.config"].search([
                    ("name", "=", line.branch_ref),
                    ("active", "=", True),
                ], limit=1)
                if branch_cfg:
                    line.branch_company_id = branch_cfg.company_id.id
                    line.branch_partner_id = branch_cfg.partner_id.id
                else:
                    company = self.env["res.company"].search([
                        ("ref", "=", line.branch_ref),
                    ], limit=1)
                    if company:
                        line.branch_company_id = company.id
                    partner = self.env["res.partner"].search([
                        ("ref", "=", line.branch_ref),
                        ("company_id", "=", company.id if company else False),
                    ], limit=1)
                    if partner:
                        line.branch_partner_id = partner.id
