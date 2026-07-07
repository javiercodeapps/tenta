from odoo import models, fields, api
from datetime import datetime, timedelta
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)

class SaleOrderQR(models.Model):
    _inherit = "sale.order"
    # Agrego campos para que carguen el efecto y calcular el vuelto
    efectivo = fields.Monetary(string='Efectivo',copy=False)
    vuelto = fields.Monetary(string='Vuelto',copy=False)
    redondeo = fields.Monetary(string='Redondeo',copy=False)
    total_calculado = fields.Monetary(string='Total',copy=False)
    is_admin = fields.Boolean(default=False, compute='check_group', store=True,tracking=True)
    mercado_pago_link = fields.Char('Link MP')
    mercado_pago = fields.Many2one('fresherp_ventas.mercadopago', 'Mercado Pago')
    sale_line_count = fields.Integer(string="Cantidad de Productos", compute="_compute_sale_line_count", store=True)

    @api.depends('order_line', 'order_line.product_id')
    def _compute_sale_line_count(self):
        for order in self:
            # Filtramos las líneas que son productos reales (no son descuentos ni redondeo)
            valid_lines = order.order_line.filtered(lambda l: 
                l.product_id and 
                not l.display_type and 
                l.product_id.default_code != 'REDONDEO' and 
                not (l.product_id.name or "").startswith('DESCUENTO')
            )
            order.sale_line_count = len(valid_lines)

       
    def _action_cancel(self):
        for record in self:
            if self.state == 'draft':
                self.state = 'cancel'
                return True
            if not record.is_admin:
                raise UserError('El pedido solo puede ser cancelado por el encargado')
            # Busco facturas
            _logger.info('Rever %s ' % self.invoice_ids)
            for invoice in self.invoice_ids:
                for payment in invoice.payment_group_ids:
                    payment.action_draft()
                    payment.cancel()
            if self.invoice_ids:
                self.create_reverse(self.invoice_ids)
            return self.write({'state': 'cancel'})
        return True

    def create_reverse(self,move):
        move_reversal = self.env['account.move.reversal']\
            .with_context(active_model='account.move', active_ids=move.ids)\
            .create({'reason': 'no reason',
                     'refund_method': 'cancel',
                     'journal_id': move.journal_id.id,
                     })
        reversal = move_reversal.reverse_moves()
        reverse_move = self.env['account.move'].browse(reversal['res_id'])
        try:
            reverse_move.action_post()
            (move + reverse_move).line_ids\
                   .filtered(lambda line: line.account_type in ('asset_receivable', 'liability_payable'))\
                   .reconcile()
        except:
            return True


    def check_group(self):
#       if self.user_has_groups('account_cashbox.cashbox_view_access'):
#           self.is_admin = True
#       else:
            self.is_admin = False

    def set_admin(self):
        if self.is_admin:
            self.is_admin = False
        else:
            self.is_admin = True

    def autorizo(self,clave=None):
        _logger.info('CLAVE %s' % clave)
        _logger.info('CLAVE %s' % self.env['ir.config_parameter'].sudo().get_param('autorizacioncaja'))
        if clave == self.env['ir.config_parameter'].sudo().get_param('autorizacioncaja'):
            self.is_admin = True
        else:
            raise UserError('La clave ingresada es incorrecta')

    def modifico(self):
        if self.is_admin == True:
            self.is_admin = False
            return True
        popup = self.env['paimon.popup.confirmation']
        action = popup.show_aut(self, 'Ingrese la clave de autorizacion x', 'autorizo')
        return action

    @api.onchange('vuelto')
    def _compute_total_calculado_vuelto(self):
        for record in self:
            if self.efectivo ==0:
                return {}
            total = record.get_total()
            record.redondeo = 0
            if record.efectivo == 0:
                record.vuelto = 0
            redondeo = total  - ( record.efectivo - record.vuelto)
            if abs(redondeo) > 1000:
                raise ValidationError('No puede aplicar un redondeo mayor a 1.000 (%s) ' % redondeo)
            record.redondeo = redondeo
            record.total_calculado = total - self.redondeo 


    @api.onchange('efectivo')
    def _compute_total_efectivo(self):
        for record in self:
            total = record.get_total()
            record.redondeo = 0
            record.vuelto = 0
            if record.vuelto == 0:
                record._compute_vuelto()
            if record.vuelto >= 0 and record.efectivo > 0:
                redondeo = total  - ( record.efectivo - record.vuelto)
                record.redondeo = redondeo
            record.total_calculado = total - self.redondeo 

    @api.onchange('sale_discount','amount_total','sale_with_discount')
    def _compute_total_calculado(self):
        for record in self:
            record.efectivo = 0
            record.vuelto = 0
            total = record.get_total()
            record.redondeo = 0
            if record.vuelto == 0:
                record._compute_vuelto()
            if record.vuelto >= 0 and record.efectivo > 0:
                redondeo = total  - ( record.efectivo - record.vuelto)
                record.redondeo = redondeo
            record.total_calculado = total - self.redondeo 

    #@api.onchange('efectivo')
    def _compute_vuelto(self):
        for record in self:
            total = record.get_total()
            if record.efectivo > total:
                record.vuelto = record.efectivo - total
                if record.vuelto < 0:
                    record.vuelto = 0
                

    #@api.onchange('vuelto')
    def _compute_vuelto_efectivo(self):
        for record in self:
            total = record.get_total()
            _logger.info('REDONDEO  %s ' %  total)
            redondeo = total  - ( record.efectivo - record.vuelto)
            if abs(redondeo) > 1000:
                raise ValidationError('No puede aplicar un redondeo mayor a 1.000 (%s) ' % redondeo)
            self.redondeo = redondeo

    def get_total(self):
        self.ensure_one()
        if 'sale_with_discount' in self._fields and self.sale_with_discount > 0:
            return self.sale_with_discount
        return self.amount_total

    def pay_mp_link(self,efectivo=0):
        import mercadopago
        provider = self.env["payment.provider"].sudo().search([('name','=','MP QR'),('company_id.id','=',self.company_id.id)],limit=1)
        mercadopago_key ='%s' %  provider.mercado_pago_qr_access_token
        sdk = mercadopago.SDK(mercadopago_key)
        preference_data = self.prepare_payment_mp_link(efectivo)
        _logger.info('DATA %s' % preference_data)
        preference_response = sdk.preference().create(preference_data)
        preference = preference_response["response"]
        
        mercadopago_link = preference.get('init_point')
        _logger.info('MP LINK %s' % mercadopago_link)
        _logger.info('RESPONSE %s' % preference)
        #self.mercado_pago_link = mercadopago_link

        return mercadopago_link
