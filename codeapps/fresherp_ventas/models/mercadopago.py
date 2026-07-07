# -*- coding: utf-8 -*-
import json
import logging
from odoo.tools.float_utils import json_float_round
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import mercadopago

import requests
from requests.structures import CaseInsensitiveDict
_logger = logging.getLogger(__name__)


class Fresherp_ventasMercadopago(models.Model):
    _name = 'fresherp_ventas.mercadopago'
    _description = 'Fresherp_ventasMercadopago'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Name')
     
    payment_provider_id = fields.Many2one('payment.provider', 'Payment Provider')
    terminal_id = fields.Char('Terminal ID')
    platform_id = fields.Char('Platform ID')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    store_id = fields.Char()
    pos_id = fields.Char(copy=False)
    mp_user_id = fields.Char('MP User ID')
    mp_external_store_id = fields.Char('MP External Store ID')
    mp_external_pos_id = fields.Char('MP External POS ID')

    def create_order(self, so):
        mp_token = self.payment_provider_id.mercado_pago_access_token
        sdk = mercadopago.SDK(mp_token)
        mercadopago_items = []
        for line in so.order_line:
            mercadopago_items.append({
                "title": '%s %s' % (line.product_id.name, line.name),
                "quantity": "%s" % line.product_uom_qty,
                "currency_id": 'ARS',
                "unit_price": "%s" % line.price_unit,
            })
        data = {
            "type": "point",
            "external_reference": so.name,
            "expiration_time": "PT16M",
            "description": so.name,
            "transactions": {
                "payments": [
                    {
                        "amount": "%s" % so.amount_total
                    }
                ]
            },
            "config": {
                "point": {
                    "terminal_id": self.terminal_id,
                    "print_on_terminal": "no_ticket",
                    "ticket_number": so.name
                },
            },
            "integration_data": {
                "platform_id": self.platform_id,
            },
        }
        _logger.info("data: %s", data)
        preference_response = sdk.order().create(data)
        _logger.info("preference_response: %s", preference_response)
        preference = preference_response["response"]
        self.env['fresherp_ventas.mercadopago.history'].create({
            'sale_id': so.id,
            'name': so.name,
            'preference': str(preference),
        })
        so.message_post(body='Mercado Pago %s' % preference)
        return preference

    def get_stores(self):
        headers = CaseInsensitiveDict()
        headers["Authorization"]="Bearer %s" % self.payment_provider_id.mercado_pago_access_token
        headers["Content-Type"] = "application/json"
        preference = requests.get(f"https://api.mercadopago.com/users/{self.mp_user_id}/stores/search", headers=headers)
        _logger.info("preference: %s", preference.content)
        self.message_post(body='Stores %s' % preference.content)
        return True

    def get_pos(self):
        self.ensure_one()
        headers = CaseInsensitiveDict()
        headers["Authorization"]="Bearer %s" % self.payment_provider_id.mercado_pago_access_token
        headers["Content-Type"] = "application/json"
        preference = requests.get(f"https://api.mercadopago.com/pos?store_id={self.store_id}", headers=headers)
        _logger.info("preference: %s", preference.content)
        self.message_post(body='Stores %s' % preference.content)
        return True
    def get_user_info(self):
        self.ensure_one()
        provider = self.payment_provider_id
        if not provider:
            raise UserError('No está configurado el proveedor de pago Mercado Pago.')

        token = getattr(provider, 'mercado_pago_access_token', False)
        if not token:
            raise UserError('No se encontró token de Mercado Pago.')

        url = 'https://api.mercadopago.com/users/me'
        headers = {
            'Authorization': 'Bearer %s' % token,
            'Content-Type': 'application/json',
        }
        response = requests.get(url, headers=headers)
        try:
            result = response.json()
        except ValueError:
            raise UserError('Respuesta inválida de Mercado Pago al consultar users/me.')

        body = 'Mercado Pago users/me: %s' % json.dumps(result, ensure_ascii=False)
        self.message_post(body=body)

        if response.status_code != 200:
            raise UserError('Error al consultar users/me: %s' % result)

        return result

    def _use_qr_presentation(self):
        return bool(
            self
            and getattr(self, 'mp_user_id', False)
            and getattr(self, 'mp_external_store_id', False)
            and getattr(self, 'mp_external_pos_id', False)
        )

    def create_order_qr(self, so):
        _logger.info("Creating Mercado Pago QR order for sale order: %s", so.name)
        provider = self.payment_provider_id
        if not provider:
            raise UserError('No está configurado el proveedor de pago Mercado Pago.')

        mp_user_id = self.mp_user_id
        pos_id = self.pos_id
        store_id = self.store_id
        mp_external_store_id = self.mp_external_store_id
        mp_external_pos_id = self.mp_external_pos_id
        token = self.payment_provider_id.mercado_pago_access_token
        if not mp_user_id or not mp_external_store_id or not mp_external_pos_id:
            raise UserError('El proveedor no tiene configurado el POS QR presencial (mp_user_id, mp_external_store_id, mp_external_pos_id).')
        if not token:
            raise UserError('No se encontró token de Mercado Pago para crear la orden QR presencial.')

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        if base_url.endswith('/'):
            base_url = base_url[:-1]

        data = {
            "title": so.name,
            "notification_url": f"{base_url}/mercadopago_qr_payment/ipn/{so.id}" if base_url else None,
            "description": self.company_id.display_name,
            "total_amount": json_float_round(so.amount_total, 2),
            "items": [
                {
                    "sku_number": _("0001"),
                    "category": _("general"),
                    "title": so.name + " sale",
                    "description": _("odoo sale"),
                    "unit_price": json_float_round(so.amount_total, 2),
                    "quantity": 1,
                    "unit_measure": "unit",
                    "total_amount": json_float_round(so.amount_total, 2),
                }
            ],
            "external_reference": so.name,
        }

        url = (
            f"https://api.mercadopago.com/instore/qr/seller/collectors/{mp_user_id}"
            f"/stores/{mp_external_store_id}/pos/{mp_external_pos_id}/orders"
        )
        headers = {
            "Authorization": "Bearer %s" % token,
            "Content-Type": "application/json",
        }
        _logger.info("Creating Mercado Pago QR order: %s %s", url, data)
        response = requests.put(url, headers=headers, json=data)
        _logger.info("Response from Mercado Pago QR order creation: %s", response.content)
        if response.status_code not in (200, 201, 204):
            raise UserError('Error al crear orden QR presencial: %s' % preference)
        _logger.info("MP QR status: %s", response.status_code)
        _logger.info("MP QR headers: %s", response.headers)
        _logger.info("MP QR text: %s", response.text)
        so.message_post(body='Mercado Pago QR presencial' )
        return 'OK'

    def get_order_status(self,so):
        self.ensure_one()
        headers = CaseInsensitiveDict()
        headers["Authorization"]="Bearer %s" % self.payment_provider_id.mercado_pago_access_token
        headers["Content-Type"] = "application/json"
        preference = self.env['fresherp_ventas.mercadopago.history'].search([('sale_id', '=', so.id), ('preference', 'ilike', 'merchant_order') ],order='create_date desc', limit=1)
        _logger.info("preference: %s", preference.preference)
        pref = eval('%s' % preference.preference)
        response = requests.get(f"https://api.mercadopago.com/merchant_orders/{pref['id']}", headers=headers)
        _logger.info("preference: %s", response.content)
        pref = response.json()
        so.message_post(body='Status MP %s' % pref)
        self.env['fresherp_ventas.mercadopago.history'].create({
            'sale_id': so.id,
            'name': so.name,
            'preference': str(pref),
        })
        return pref['status']

    def set_terminal_pdv(self):
        headers = CaseInsensitiveDict()
        headers["Authorization"]="Bearer %s" % self.payment_provider_id.mercado_pago_access_token
        headers["Content-Type"] = "application/json"
        terminals = {'terminals' : [{'id': self.terminal_id,'operating_mode':'PDV'}] }
        preference = requests.patch("https://api.mercadopago.com/terminals/v1/setup", headers=headers, data=terminals)
        _logger.info("preference: %s", terminals)
        _logger.info("preference: %s", preference.content)
        import subprocess
        subprocess.Popen(['curl', '-X', 'PATCH', 'https://api.mercadopago.com/terminals/v1/setup', '-H', 'Authorization: Bearer %s' % self.payment_provider_id.mercado_pago_access_token,'-H', 'Content-Type: application/json', '-d', '{"terminals": [{"id": "%s", "operating_mode": "PDV"}]}' % self.terminal_id])
        self.get_terminals()
        return True
    def set_terminal_manual(self):
        headers = CaseInsensitiveDict()
        headers["Authorization"]="Bearer %s" % self.payment_provider_id.mercado_pago_access_token
        _logger.info("headers: %s", headers)
        headers["Content-Type"] = "application/json"
        terminals = {'terminals' : [{'id': self.terminal_id,'operating_mode':'STANDALONE'}] }
        preference = requests.patch("https://api.mercadopago.com/terminals/v1/setup", headers=headers, data=terminals)
        import subprocess
        subprocess.Popen(['curl', '-X', 'PATCH', 'https://api.mercadopago.com/terminals/v1/setup', '-H', 'Authorization: Bearer %s' % self.payment_provider_id.mercado_pago_access_token,'-H', 'Content-Type: application/json', '-d', '{"terminals": [{"id": "%s", "operating_mode": "STANDALONE"}]}' % self.terminal_id])
        _logger.info("terminals: %s", terminals)
        _logger.info("preference: %s", preference.content)
        self.get_terminals()
        return True
    def get_terminals(self):
        headers = CaseInsensitiveDict()
        headers["Authorization"]="Bearer %s" % self.payment_provider_id.mercado_pago_access_token
        headers["Content-Type"] = "application/json"
        preference = requests.get("https://api.mercadopago.com/terminals/v1/list", headers=headers)
        _logger.info("preference: %s", preference.content)
        self.message_post(body='Terminales %s' % preference.content)
        return True

class Fresherp_ventasMercadopagoHistory(models.Model):
    _name = 'fresherp_ventas.mercadopago.history'
    _description = 'Fresherp_ventasMercadopagoHistory'

    sale_id = fields.Many2one('sale.order', 'Sale Order')
    name = fields.Char('Name')
    preference = fields.Char('Preference')
    date = fields.Datetime('Date', default=fields.Datetime.now)

    def get_id(self,so):
        preference = self.env['fresherp_ventas.mercadopago.history'].search([('sale_id', '=', so.id)],order='date desc', limit=1)
        pref = eval(preference.preference)
        return pref['id']
