{
    "name": "FreshERP Discount" ,
    "summary": "Descuento a aplicar en los ventas",
    "author": "Javier Pepe",
    
    "license": "LGPL-3",
    "category": "Sales",
    "version": "18.0.1.0.0",
    "depends": ["base","sale","sale_order_type"],
    "data": [
        "security/ir.model.access.csv",
        "views/sale_order_discount.xml",
        "data/weekdays.xml",
    ],
    "installable": True,
    "application": True,
}
