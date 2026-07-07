from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class MercadopagoQrPaymemnt(http.Controller):
    @http.route("/mercadopago_qr_payment/ipn/<int:so_id>", auth="public", type="json")
    def ipn(self, so_id, **kw):
        params = request.httprequest.full_path.split("?")[1].split("&")
        data = {}
        # TODO esto es feo pero por ahora resuelvo asi
        # el problema envian variables por GET
        # mediante un POST de JSON
        for p in params:
            i = p.split("=")
            data[i[0]] = i[1]
        _logger.info("MercadoPago IPN data: %s", data)
        so = request.env['sale.order'].sudo().browse(so_id)
        so.message_post(body='Mercado Pago QR presencial IPN: %s' % data)
        request.env['fresherp_ventas.mercadopago.history'].sudo().create({
            'sale_id': so.id,
            'name': so.name,
            'preference': str(data),
        })
        return ""

    @http.route('/mercadopago/success', type='http', auth='public', csrf=False, methods=['POST','GET'])
    def mp_success(self, **kwargs):
        params = request.httprequest.full_path.split("?")[1].split("&")
        _logger.info(" MercadoPago SUCCESS: %s", kwargs)
        _logger.info(" MercadoPago SUCCESS: %s", kwargs.get('preference_id') )
        return "Payment Successful"

    @http.route('/mercadopago/failure', type='http', auth='public', csrf=False)
    def mp_failure(self, **kwargs):
        _logger.warning(" MercadoPago FAILURE: %s", kwargs)
        return "Payment Failed"

    @http.route('/mercadopago/pending', type='http', auth='public', csrf=False)
    def mp_pending(self, **kwargs):
        _logger.info(" MercadoPago PENDING: %s", kwargs)
        return "Payment Pending"
