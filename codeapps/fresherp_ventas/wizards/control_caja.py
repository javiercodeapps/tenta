from odoo import models, fields, api
from datetime import datetime, timedelta
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)

class CajaControl(models.TransientModel):
    _name = "caja.pagos.control"
    _description = "Control Caja"
    caja = fields.Many2one('account.cashbox.session')
    monto = fields.Float(string='Monto')
    msg = fields.Char(string='Mensaje')
    
    @api.model
    def default_get(self, fields):
        caja = self.env['account.cashbox.session'].search([('state','=','opened')])
        if not caja:
            raise UserError('No se encontro ninguna caja abierta')
        result = super().default_get(fields)
        result.update({'caja': caja[0].id })
        return result


    def control(self):
        max_diff_in_currency = self.caja.cashbox_id.max_diff
        for line in self.caja.line_ids:
            if 'Efectivo' in line.journal_id.name:
                payments = self.env['account.payment'].search([
                                    ('journal_id', '=', line.journal_id.id),
                                    ('create_date', '>', self.caja.opening_date),
                                    ('state', '=', 'posted'),
                                    ('cashbox_session_id', '=', False),
                                    ])
                payments.cashbox_session_id = self.caja
                balance_end = line.balance_end
                _logger.info('%s %s' % (balance_end,line.balance_start) )
                diff = abs(balance_end - self.monto)
                diff_ss = balance_end - self.monto
                if diff > max_diff_in_currency:
                    msg = 'En el diario "%s" el Balance Final Real (%s) excede la máxima diferencia permitida (%s).' % (
                                       line.journal_id.name,
                                       self.monto,
                                       max_diff_in_currency,
                                )
                    view_id = self.env.ref('caja_pagos.view_contol_caja_wizard_msg').id
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'caja.pagos.control',
                        'view_mode': 'form',
                        'target': 'new',
                        'view_id': view_id,
                        'context': {'default_msg': msg},
                    }
                else:
  #                 raise ValidationError("La caja esta correcta")
                    view_id = self.env.ref('caja_pagos.view_contol_caja_wizard_msg').id
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'caja.pagos.control',
                        'view_mode': 'form',
                        'target': 'new',
                        'view_id': view_id,
                        'context': {'default_msg': "La caja esta correcta, la diferencia es: %s" % diff_ss},
                    }

    def compute_amounts(self, record):
        payments_lines = record.env['account.payment'].search([ ('cashbox_session_id', 'in', record.mapped('cashbox_session_id').ids), ('state', '=', 'posted')])
        filtered_lines = payments_lines.filtered( lambda p: p.cashbox_session_id == record.cashbox_session_id and p.journal_id == record.journal_id)
        _logger.info(filtered_lines)
        amount = sum(filtered_lines.mapped('amount_company_currency_signed'))
        balance_end = amount + record.balance_start
        return balance_end


