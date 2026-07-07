from odoo import http
from odoo.http import request
from werkzeug.wrappers import Response


class PrecioExportController(http.Controller):

    @http.route(
        '/precio_export/download/<int:export_id>',
        type='http', auth='user', csrf=False
    )
    def download_txt(self, export_id):
        export = request.env['precio.export'].sudo().browse(export_id)
        if not export.exists() or not export.archivo_txt:
            return Response('No encontrado', status=404)

        content = export.archivo_txt.encode('utf-8')
        return Response(
            content,
            headers=[
                ('Content-Type', 'text/plain; charset=utf-8'),
                ('Content-Disposition',
                 'attachment; filename="CODIGOS_PLU_ODOO.TXT"'),
            ],
        )
