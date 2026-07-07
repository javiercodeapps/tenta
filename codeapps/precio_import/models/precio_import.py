from odoo import models, fields, api
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class PrecioExport(models.Model):
    _name = 'precio.export'
    _description = 'Exportacion de Precios iTegra'
    _order = 'create_date desc'

    name = fields.Char('Referencia', default='Exportacion', readonly=True)
    fecha = fields.Date('Fecha Generacion', default=fields.Date.today, readonly=True)
    archivo_txt = fields.Text('Contenido TXT', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Exportacion') == 'Exportacion':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'precio.export'
                ) or 'Exportacion'
        return super().create(vals_list)

    def action_generate(self):
        self.ensure_one()
        codigos = []
        ProductTemplate = self.env['product.template']
        products = ProductTemplate.search([])
        for rec in products:
            if rec.default_code and rec.barcode:
                if rec.barcode[0] == '2':
                    t = 'P'
                else:
                    t = 'N'
                if float(rec.list_price) > 0:
                    codigos.append('%05d%06d%-26s%07.1f%s\n' % (
                        int(rec.default_code),
                        int(rec.default_code),
                        rec.name[:25],
                        float(rec.list_price),
                        t
                    ))
        self.write({
            'fecha': fields.Date.today(),
            'archivo_txt': ''.join(codigos),
        })
        return {
            'type': 'ir.actions.act_url',
            'name': 'Descargar',
            'url': '/precio_export/download/%s' % self.id,
            'target': 'new',
        }
