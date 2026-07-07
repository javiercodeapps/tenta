import logging
from odoo import models

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = "account.move"

    sale_order_lines = fields.Char(
        string='Cantidad de productois',
        compute='_get_sale_order_sale_order_lines',
        store=True  # Opcional: almacenar en BD para búsquedas
    )
    @api.depends('invoice_origin')
    def _get_sale_order_sale_order_lines(self):
        for move in self:
            if move.invoice_origin:
                # Buscar pedido por nombre
                sale_order = self.env['sale.order'].search([
                    ('name', '=', move.invoice_origin)
                ], limit=1)
                if sale_order:
                    # Acceder al campo que necesitas
                    move.sale_order_lines = sale_order.sale_line_count
                else:
                    move.sale_order_lines = False
            else:
                move.sale_order_lines = False

    def action_post(self):
        # Confirm the invoice
        res = super().action_post()
        for move in self:
            # Check if the invoice is an "out_invoice" or "out_refund" (customer invoices & refunds)
            if move.move_type in ["out_invoice", "out_refund"]:
                # Ensure the invoice was NOT manually created (i.e., it was created by another process)
                if not move.env.context.get('manual_creation', False):
                    _logger.info('printed')  # This logs 'printed' when report is generated
                    return move.env['ir.actions.report'].search(
                        [('report_name', '=', 'account.report_invoice')], limit=1
                    ).report_action(move)

            return res

