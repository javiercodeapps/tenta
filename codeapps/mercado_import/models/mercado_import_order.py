from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    mercado_batch_id = fields.Many2one(
        "mercado.import.batch",
        string="Mercado Batch",
        readonly=True,
    )
    mercado_internal_batch_id = fields.Many2one(
        "mercado.import.batch",
        string="Mercado Internal Batch",
        readonly=True,
    )


class SaleOrder(models.Model):
    _inherit = "sale.order"

    mercado_batch_id = fields.Many2one(
        "mercado.import.batch",
        string="Mercado Batch",
        readonly=True,
    )
