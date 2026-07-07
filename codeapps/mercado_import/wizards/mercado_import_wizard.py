from odoo import fields, models


class MercadoImportWizard(models.TransientModel):
    _name = "mercado.import.wizard"
    _description = "Mercado Import Wizard"

    data_file = fields.Binary("Excel File", required=True)
    filename = fields.Char("Filename")
    parent_company_ref = fields.Char(
        "Parent Company Ref",
        default="LAAMISTAD",
        help="Reference (ref) of the parent company",
    )
    cajon_product_id = fields.Many2one(
        "product.product",
        string="Cajon Product",
        help="Producto para las líneas de cajón cuando se generen señas",
    )

    def action_create_batch(self):
        self.ensure_one()
        batch = self.env["mercado.import.batch"].create({
            "data_file": self.data_file,
            "filename": self.filename,
            "parent_company_ref": self.parent_company_ref,
            "cajon_product_id": self.cajon_product_id.id,
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "mercado.import.batch",
            "res_id": batch.id,
            "view_mode": "form",
            "target": "current",
        }
