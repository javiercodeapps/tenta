{
    "name": "FreshERP Ventas" ,
    "summary": "Pantalla de Sale Order Personalizada para CAJA",
    "author": "Javier Pepe",
    'website': "https://www.fresherp.com.ar/",
    
    "license": "LGPL-3",
    "category": "Sales",
    "version": "18.0.1.0.0",
    "depends": ["base","sale","account","payment_status_in_sale"],
    'data': [
        "security/ir.model.access.csv",
        "views/sale_order.xml",
        "views/sale_order_menu.xml",
        "views/scan_qr_wizard_views.xml",
        "views/sale_order_views_payment.xml",
        "views/caja_pagos.xml",
        'views/mercadopago_point.xml',
        'views/custom_popup_confirmation.xml',
        'views/sale_order_invoice_status.xml',
        'data/action_server_refacturar.xml',
    ],
    "assets": {
        "web.assets_backend": [
            "fresherp_ventas/static/src/css/button_styles.css",
                "fresherp_ventas/static/src/css/label_fix.css",
        ],
    },
    "installable": True,
    "application": True,
}
