{
    "name": "Caja Pagos" ,
    "summary": "Pagos y transferencias automaticas",
    "author": "Javier Pepe",
    
    "license": "LGPL-3",
    "category": "Sales",
    "version": "18.0.1.0.0",
    "depends": ["base","sale","account","account_cashbox"],
    "data": [
        "security/ir.model.access.csv",
        "views/control_caja.xml",
        "views/control_caja_msg.xml",
        "views/caja_pagos.xml",
        "views/res_partner.xml",
    ],
    "installable": True,
    "application": True,
}
