import io
import logging
import io 
from collections import defaultdict
import base64
import zipfile
import openpyxl
from openpyxl.utils.exceptions import InvalidFileException

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

SUFFIX_ORDER = ("kg", "u", "p", "b", "k")


def _safe_num(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return None


def _safe_int(v):
    n = _safe_num(v)
    return int(n) if n is not None else None


def _product_code_val(v):
    if v is None:
        return None
    try:
        return str(int(v))
    except (ValueError, TypeError):
        return str(v).strip()


class MercadoImportBatch(models.Model):
    _name = "mercado.import.batch"
    _description = "Mercado Import Batch"
    _order = "create_date desc"

    name = fields.Char(
        string="Referencia",
        required=True,
        default="New",
        readonly=True,
    )
    data_file = fields.Binary("Excel File")
    filename = fields.Char("Filename")
    parent_company_ref = fields.Char(
        "Parent Company Ref",
        default="TENTA",
    )
    cajon_product_id = fields.Many2one(
        "product.product",
        "Cajon Product",
        domain=[("default_code", "like", "CAJON")],
    )
    state = fields.Selection([
        ("draft", "Borrador"),
        ("parsed", "Parseado"),
        ("reviewed", "Revisado"),
        ("done", "Generado"),
    ], default="draft", tracking=True)

    purchase_line_ids = fields.One2many(
        "mercado.import.purchase.line",
        "batch_id",
        string="Lineas de Compra",
    )
    sale_line_ids = fields.One2many(
        "mercado.import.sale.line",
        "batch_id",
        string="Lineas de Venta",
    )

    count_purchase_lines = fields.Integer(
        compute="_compute_counts",
    )
    count_sale_lines = fields.Integer(
        compute="_compute_counts",
    )

    import_log = fields.Text("Import Log", readonly=True)

    purchase_order_ids = fields.One2many(
        "purchase.order",
        "mercado_batch_id",
        string="Purchase Orders",
    )
    sale_order_ids = fields.One2many(
        "sale.order",
        "mercado_batch_id",
        string="Sale Orders",
    )
    internal_purchase_order_ids = fields.One2many(
        "purchase.order",
        "mercado_internal_batch_id",
        string="Internal Purchase Orders",
    )

    info_purchase = fields.Integer("POs Creadas")
    info_sale = fields.Integer("SOs Creadas")
    info_internal = fields.Integer("POs Internas Creadas")

    @api.depends("purchase_line_ids", "sale_line_ids")
    def _compute_counts(self):
        for rec in self:
            rec.count_purchase_lines = len(rec.purchase_line_ids)
            rec.count_sale_lines = len(rec.sale_line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "mercado.import.batch"
                ) or _("New")
        return super().create(vals_list)

    def _get_branch_map(self):
        """Retorna dict {branch_name: {"qty_col": N, "sale_col": N}} desde config."""
        configs = self.env["mercado.import.branch.config"].search([
            ("active", "=", True),
        ])
        result = {}
        for cfg in configs:
            result[cfg.name] = {
                "qty_col": cfg.qty_col,
                "sale_col": cfg.sale_col,
                "company_id": cfg.company_id.id if cfg.company_id else None,
                "partner_id": cfg.partner_id.id if cfg.partner_id else None,
            }
        return result

    def _get_unit_map(self):
        """Retorna dict {code: {"name": ..., "uom_search": ..., "uom_factor": ...}}."""
        configs = self.env["mercado.import.unit.config"].search([
            ("active", "=", True),
        ])
        return {
            cfg.code.lower(): {
                "name": cfg.name,
                "uom_search": cfg.uom_search_term,
                "uom_factor": cfg.uom_factor,
            }
            for cfg in configs
        }

    def _parse_unit(self, pu_str, unit_map):
        if not pu_str:
            return (None, None, None)
        raw = str(pu_str).strip()
        if raw.upper() == "P/U":
            return (None, None, None)
        if " " in raw or (raw.count(",") > 1):
            return (None, raw, "mixto")
        normalized = raw.replace(",", ".")
        for suffix in SUFFIX_ORDER:
            if normalized.lower().endswith(suffix):
                num_str = normalized[:-len(suffix)]
                try:
                    qty = float(num_str)
                except ValueError:
                    return (None, raw, None)
                info = unit_map.get(suffix)
                unit_type = info["name"] if info else suffix
                return (qty, suffix, unit_type)
        return (None, raw, None)

    def _clean_value(self, value):
        """Limpia un valor de celda de Excel para uso en Odoo"""
        if value is None or value == '':
            return None
        # Convertir a string y limpiar espacios
        return str(value).strip()

    def action_parse(self):
        self.ensure_one()
        if not self.data_file:
            raise UserError(_("Seleccione un archivo Excel"))

        branch_map = self._get_branch_map()
        unit_map = self._get_unit_map()

        if not branch_map:
            raise UserError(_(
                "No hay sucursales configuradas. "
                "Vaya a Configuracion > Sucursales y agregue al menos una."
            ))

        file_data = self.data_file
        try:
            wb = openpyxl.load_workbook(filename=io.BytesIO(base64.b64decode(file_data)),data_only=True)
        except (zipfile.BadZipFile, InvalidFileException):
            ext = self.filename and self.filename.split(".")[-1].lower() or None
            if ext in ("xls", "csv", "txt"):
                raise UserError(_(
                    "El archivo debe ser un archivo Excel .xlsx. "
                    "Suba un archivo con formato XLSX válido."
                ))
            raise UserError(_(
                "El archivo no es un Excel válido (.xlsx). "
                "Verifique el archivo e intente de nuevo."
            ))
        ws = wb["GENERAL"]

        self.purchase_line_ids.unlink()
        self.sale_line_ids.unlink()

        purchase_lines = []
        sale_lines = []
        log = []

        for row in ws.iter_rows(min_row=3, max_row=ws.max_row, values_only=True):
            product = (row[2] or "").strip() if row[2] else None
            if not product or product.upper() == "FECHA:":
                continue
            supplier_name = (row[4] or "").strip() if row[4] else None
            if not supplier_name or supplier_name.upper() == "PROOVEDOR":
                continue

            product_code = _product_code_val(row[0])
            supplier_ref = self._clean_value(row[3])
            p_u_raw = self._clean_value(row[7])
            p_u_qty, p_u_code, p_u_type = self._parse_unit(row[7], unit_map)
            has_sena = bool(row[7] and str(row[6]).strip().upper() == "X")
            total_qty = _safe_int(row[1])

            purchase_lines.append({
                "batch_id": self.id,
                "product_code": product_code,
                "product_name": product,
                "supplier_ref": supplier_ref,
                "supplier_name": supplier_name,
                "marca": (row[5] or "").strip() if row[5] else None,
                "tipo": (row[6] or "").strip() if row[6] else None,
                "p_u_raw": p_u_raw,
                "p_u_qty": p_u_qty,
                "p_u_unit_code": p_u_code,
                "p_u_unit_type": p_u_type,
                "has_sena": has_sena,
                "valor_sena": _safe_num(row[8]),
                "costo_unit": _safe_num(row[9]),
                "venta_unit": _safe_num(row[10]),
                "total_qty": total_qty,
                "total": total_qty * _safe_num(row[9])
            })

            for branch_ref, cols in branch_map.items():
                qty = _safe_int(row[cols["qty_col"]])
                sale = _safe_num(row[cols["sale_col"]])
                venta_unit = _safe_num(row[10])
                if qty and qty > 0:
                    sale_lines.append({
                        "batch_id": self.id,
                        "branch_ref": branch_ref,
                        "branch_company_id": cols.get("company_id"),
                        "branch_partner_id": cols.get("partner_id"),
                        "product_code": product_code,
                        "product_name": product,
                        "supplier_ref": supplier_ref,
                        "supplier_name": supplier_name,
                        "qty": qty,
                        "unit_sale": venta_unit,
                        "total_sale": sale,
                        "has_sena": has_sena,
                    })

        if purchase_lines:
            self.env["mercado.import.purchase.line"].create(purchase_lines)
        if sale_lines:
            self.env["mercado.import.sale.line"].create(sale_lines)

        log.append(f"Lineas de compra: {len(purchase_lines)}")
        log.append(f"Lineas de venta: {len(sale_lines)}")
        log.append(f"Sucursales configuradas: {len(branch_map)}")

        no_code_products = [
            l for l in purchase_lines if not l.get("product_code")
        ]
        if no_code_products:
            log.append(
                f"Productos sin codigo ({len(no_code_products)}): "
                + ", ".join(l["product_name"] for l in no_code_products[:10])
            )

        self.write({
            "state": "parsed",
            "import_log": "\n".join(log),
        })

        return {
            "type": "ir.actions.act_window",
            "res_model": "mercado.import.batch",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_review(self):
        self.write({"state": "reviewed"})

    def action_generate(self):
        self.ensure_one()

        missing_purchase_products = self.purchase_line_ids.filtered(
            lambda l: not l.product_id
        )
        if missing_purchase_products:
            raise UserError(_(
                "No se puede generar órdenes porque hay líneas de compra "
                "sin producto asignado. Por favor asigne el código de producto "
                "antes de generar."
            ))

        missing_purchase_suppliers = self.purchase_line_ids.filtered(
            lambda l: not l.supplier_id
            )
        if missing_purchase_suppliers:
            raise UserError(_(
                "No se puede generar órdenes porque hay líneas de compra "
                "sin proveedor asignado o con proveedor no encontrado. "
                "Por favor verifique la referencia del proveedor antes de generar."
            ))

        missing_sale_products = self.sale_line_ids.filtered(
            lambda l: not l.product_id
        )
        if missing_sale_products:
            raise UserError(_(
                "No se puede generar órdenes porque hay líneas de venta "
                "sin producto asignado. Por favor asigne el código de producto "
                "en las líneas de venta antes de generar."
            ))

        parent_company = self.env["res.company"].search(
            [("code", "=", self.parent_company_ref)], limit=1
        )
        if not parent_company:
            raise UserError(_(
                f"No se encontro la empresa con ref='{self.parent_company_ref}'"
            ))

        log = []
        po_created = self._create_purchase_orders(parent_company, log)
        so_created = self._create_sale_orders(parent_company, log)
        int_po_created = self._create_internal_purchase_orders(
            so_created, parent_company, log
        )

        self.write({
            "state": "done",
            "purchase_order_ids": [(6, 0, [o.id for o in po_created])],
            "sale_order_ids": [(6, 0, [o.id for o in so_created])],
            "internal_purchase_order_ids": [(6, 0, [o.id for o in int_po_created])],
            "info_purchase": len(po_created),
            "info_sale": len(so_created),
            "info_internal": len(int_po_created),
            "import_log": self.import_log + "\n\n=== GENERACION ===\n" + "\n".join(log),
        })

    def action_revert_generated_orders(self):
        self.ensure_one()
        purchase_orders = self.purchase_order_ids
        sale_orders = self.sale_order_ids
        internal_orders = self.internal_purchase_order_ids

        if not (purchase_orders or sale_orders or internal_orders):
            self.write({
                "state": "reviewed",
                "purchase_order_ids": [(5, 0, 0)],
                "sale_order_ids": [(5, 0, 0)],
                "internal_purchase_order_ids": [(5, 0, 0)],
                "info_purchase": 0,
                "info_sale": 0,
                "info_internal": 0,
            })
            return True

        # Cancelar órdenes de compra que no estén en draft
        for po in purchase_orders:
            if po.state == "draft":
                try:
                    po.button_cancel()
                except Exception as e:
                    _logger.warning(f"No se pudo cancelar PO {po.name}: {e}")

        # Cancelar órdenes de venta que no estén en draft
        for so in sale_orders:
            if so.state == "draft":
                try:
                    so.action_cancel()
                except Exception as e:
                    _logger.warning(f"No se pudo cancelar SO {so.name}: {e}")

        # Cancelar órdenes internas que no estén en draft
        for ipo in internal_orders:
            if ipo.state == "draft":
                try:
                    ipo.button_cancel()
                except Exception as e:
                    _logger.warning(f"No se pudo cancelar PO-INT {ipo.name}: {e}")

        # Eliminar todas las órdenes
        purchase_orders.unlink()
        sale_orders.unlink()
        internal_orders.unlink()
        self.write({
            "state": "reviewed",
            "purchase_order_ids": [(5, 0, 0)],
            "sale_order_ids": [(5, 0, 0)],
            "internal_purchase_order_ids": [(5, 0, 0)],
            "info_purchase": 0,
            "info_sale": 0,
            "info_internal": 0,
        })
        return True

    def action_confirm_all_orders(self):
        self.ensure_one()
        purchase_orders = self.purchase_order_ids
        sale_orders = self.sale_order_ids
        internal_orders = self.internal_purchase_order_ids

        if not (purchase_orders or sale_orders or internal_orders):
            raise UserError(_("No hay órdenes generadas para confirmar."))

        # Confirmar órdenes de compra
        for po in purchase_orders:
            if po.state == "draft":
                try:
                    po.button_confirm()
                except Exception as e:
                    _logger.warning(f"No se pudo confirmar PO {po.name}: {e}")

        # Confirmar órdenes de venta
        for so in sale_orders:
            if so.state == "draft":
                try:
                    so.action_confirm()
                except Exception as e:
                    _logger.warning(f"No se pudo confirmar SO {so.name}: {e}")

        # Confirmar órdenes internas
        for ipo in internal_orders:
            if ipo.state == "draft":
                try:
                    ipo.button_confirm()
                except Exception as e:
                    _logger.warning(f"No se pudo confirmar PO-INT {ipo.name}: {e}")

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Órdenes confirmadas"),
                "message": _("Se han confirmado todas las órdenes en estado borrador."),
                "type": "success",
                "sticky": False,
            },
        }

    def _create_purchase_orders(self, parent_company, log):
        grouped = defaultdict(list)
        for line in self.purchase_line_ids:
            if line.supplier_ref:
                grouped[line.supplier_ref].append(line)

        created = []
        SupplierInfo = self.env["product.supplierinfo"]

        _logger.info("Grouped purchase lines: %s", {k: len(v) for k, v in grouped.items()})
        for ref, lines in sorted(grouped.items()):
            supplier = lines[0].supplier_id if lines else None

            _logger.info("Processing supplier '%s' with %d lines", supplier.name if supplier else 'N/A', len(lines))
            line_vals = []
            total_sena_value = 0
            sena_count = 0
            
            for line in lines:
                if not line.product_id:
                    log.append(f"  [WARN] {line.product_name}: sin producto asignado")
                    continue
                qty = line.total_qty or 0
                if qty <= 0:
                    continue

                price = line.costo_unit or 0
                uom = line._get_product_uom()

                line_vals.append((0, 0, {
                    "product_id": line.product_id.id,
                    "name": line.product_id.name,
                    "product_qty": qty,
                    "product_uom": uom.id,
                    "price_unit": price,
                    #"taxes_id": [(5, 0, 0)],
                }))
                
                # Sumar valores de señas
                if line.has_sena and line.valor_sena:
                    total_sena_value = line.valor_sena
                    sena_count += line.total_qty

            # Agregar producto CAJON si hay señas
            if total_sena_value > 0:
                cajon_code = f"CAJON{int(total_sena_value)}"
                cajon_product = self.env["product.product"].search([
                    ("default_code", "=", cajon_code),
                ], limit=1)
                if cajon_product:
                    line_vals.append((0, 0, {
                        "product_id": cajon_product.id,
                        "name": cajon_product.name,
                        "product_qty": sena_count,
                        "product_uom": cajon_product.uom_id.id,
                        "price_unit": total_sena_value,
                    }))
                    log.append(f"    [CAJON] {cajon_code} x @ {sena_count} unidades a {total_sena_value} cada una")

            if line_vals:
                _logger.info(line_vals)
                order = self.env["purchase.order"].sudo().with_company(
                    parent_company
                ).create({
                    "partner_id": supplier.id,
                    "company_id": parent_company.id,
                    "currency_id": parent_company.currency_id.id,
                    "origin": f"Mercado {self.name} - ref {ref}",
                    "mercado_batch_id": self.id,
                    "order_line": line_vals,
                })
                #order.button_confirm()
                created.append(order)
                log.append(
                    f"  [PO] {order.name} -> {supplier.name} "
                    f"(ref: {ref}) - {len(order.order_line)} lineas"
                )

        log.append("")
        return created

    def _create_sale_orders(self, parent_company, log):
        grouped = defaultdict(list)
        for line in self.sale_line_ids:
            grouped[line.branch_ref].append(line)

        created = []

        _logger.info("Grouped sale lines: %s", {k: len(v) for k, v in grouped.items()})
        for branch_ref, lines in sorted(grouped.items()):
            _logger.info("Processing branch '%s' with %d lines", branch_ref, lines)

            if not lines:
                continue

            first_line = lines[0]
            company = None
            partner = None

            if first_line.branch_company_id:
                company = first_line.branch_company_id
            else:
                company = self.env["res.company"].search(
                    [("ref", "=", branch_ref)], limit=1
                )

            if first_line.branch_partner_id:
                partner = first_line.branch_partner_id
            else:
                partner = self.env["res.partner"].search([
                    ("ref", "=", branch_ref),
                    ("company_id", "=", company.id if company else False),
                ], limit=1)

            if not company:
                log.append(f"  [SKIP] Sucursal ref='{branch_ref}' no encontrada")
                continue
            if not partner:
                log.append(
                    f"  [SKIP] Partner ref='{branch_ref}' "
                    f"en empresa '{company.name}' no encontrado"
                )
                continue

            line_vals = []
            for line in lines:
                if not line.product_id:
                    continue
                qty = line.qty or 0
                if qty <= 0:
                    continue

                price = line.unit_sale or 0
                line_vals.append((0, 0, {
                    "product_id": line.product_id.id,
                    "name": line.product_id.name,
                    "product_uom_qty": qty,
                    "price_unit": price,
                   #"tax_id": [(5, 0, 0)],
                }))

            if line_vals:
                sale_varios = self.env["sale.order.type"].search([
                    ("name", "ilike", "Varios"),
                    ("company_id", "=", parent_company.id),
                ], limit=1)
                order = self.env["sale.order"].sudo().with_company(
                    parent_company
                ).create({
                    "partner_id": partner.id,
                    "partner_invoice_id": partner.id,
                    "partner_shipping_id": partner.id,
                    "company_id": parent_company.id,
                    "currency_id": parent_company.currency_id.id,
                    "origin": f"Mercado {self.name} - {branch_ref}",
                    "mercado_batch_id": self.id,
                    "type_id": sale_varios.id if sale_varios else None,
                    "order_line": line_vals,
                })
                #order.action_confirm()
                created.append(order)
                log.append(
                    f"  [SO] {order.name} -> {partner.name} "
                    f"({branch_ref}) - {len(order.order_line)} lineas"
                )
                sena_total = 0
                for line in lines:
                    if line.has_sena:
                        sena_total += line.qty

                # Crear orden de venta adicional con CAJON si hay sena_total
                cajon4000_product = self.cajon_product_id
                if cajon4000_product and sena_total > 0:
                    sale_varios = self.env["sale.order.type"].search([
                        ("name", "ilike", "Varios"),
                        ("company_id", "=", parent_company.id),
                    ], limit=1)
                    cajon_order = self.env["sale.order"].sudo().with_company(
                        parent_company
                    ).create({
                        "partner_id": partner.id,
                        "partner_invoice_id": partner.id,
                        "partner_shipping_id": partner.id,
                        "company_id": parent_company.id,
                        "currency_id": parent_company.currency_id.id,
                        "origin": f"Mercado {self.name} - CAJON4000",
                        "mercado_batch_id": self.id,
                        "type_id": sale_varios.id if sale_varios else None,
                        "order_line": [(0, 0, {
                            "product_id": cajon4000_product.id,
                            "name": cajon4000_product.name,
                            "product_uom_qty": sena_total,
                            "price_unit": 4000,
                            #"tax_id": [(5, 0, 0)],
                        })],
                    })
                    created.append(cajon_order)
                    log.append(
                        f"  [SO-CAJON] {cajon_order.name} -> {branch_ref} "
                        f"(CAJON4000) - 1 linea de %s" % sena_total
                    )

        log.append("")
        return created

    def _create_internal_purchase_orders(self, sale_orders, parent_company, log):
        created = []
        laamistad_partner = self.env["res.partner"].search([
            ("company_id", "=", parent_company.id),
        ], limit=1)
        if not laamistad_partner:
            laamistad_partner = parent_company.partner_id

        for so in sale_orders:
            company = self.env["res.company"].search([
                ("partner_id", "=", so.partner_id.id),
            ], limit=1)
            if not company:
                company = so.company_id
            line_vals = []
            for sol in so.order_line:
                line_vals.append((0, 0, {
                    "product_id": sol.product_id.id,
                    "name": sol.name,
                    "product_qty": sol.product_uom_qty,
                    "product_uom": sol.product_uom.id,
                    "price_unit": sol.price_unit,
                    #"taxes_id": [(5, 0, 0)],
                }))

            if line_vals:
                order = self.env["purchase.order"].sudo().with_company(
                    company
                ).create({
                    "partner_id": laamistad_partner.id,
                    "company_id": company.id,
                    "currency_id": company.currency_id.id,
                    "origin": f"Interno desde {so.name}",
                    "mercado_internal_batch_id": self.id,
                    "order_line": line_vals,
                })
                #order.button_confirm()
                created.append(order)
                log.append(
                    f"  [PO-INT] {order.name} ({company.name}) "
                    f"{'<'}- LAAMISTAD - {len(order.order_line)} lineas"
                )

        log.append("")
        return created

    def action_assign_products(self):
        self.ensure_one()
        found_products = 0
        not_found_products = 0
        found_sale_products = 0
        not_found_sale_products = 0
        found_suppliers = 0
        not_found_suppliers = 0

        for line in self.purchase_line_ids:
            # Assign products
            if line.product_code and not line.product_id:
                if line.product_code.isdigit():
                    search_code = '%03d' % int(line.product_code)
                else:
                    search_code = line.product_code
                product = self.env["product.product"].search([
                    ("default_code", "=", search_code),
                ], limit=1)
                if product:
                    line.product_id = product.id
                    found_products += 1
                else:
                    not_found_products += 1

            # Assign suppliers
            if line.supplier_ref and not line.supplier_id:
                supplier = self.env["res.partner"].search([
                    ("ref", "=", line.supplier_ref.upper()),
                ], limit=1)
                if supplier:
                    line.supplier_id = supplier.id
                    found_suppliers += 1
                else:
                    not_found_suppliers += 1

        for line in self.sale_line_ids:
            if line.product_code and not line.product_id:
                if line.product_code.isdigit():
                    search_code = '%03d' % int(line.product_code)
                else:
                    search_code = line.product_code
                product = self.env["product.product"].search([
                    ("default_code", "=", search_code),
                ], limit=1)
                if product:
                    line.product_id = product.id
                    found_sale_products += 1
                else:
                    not_found_sale_products += 1

        self.import_log = (
            f"Productos asignados: {found_products}\n"
            f"Productos no encontrados: {not_found_products}\n"
            f"Productos de venta asignados: {found_sale_products}\n"
            f"Productos de venta no encontrados: {not_found_sale_products}\n"
            f"Proveedores asignados: {found_suppliers}\n"
            f"Proveedores no encontrados: {not_found_suppliers}\n\n"
            + (self.import_log or "")
        )

    def action_load_default_config(self):
        """Carga las sucursales y unidades por defecto."""
        self.env["mercado.import.branch.config"].load_defaults()
        self.env["mercado.import.unit.config"].load_defaults()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Configuracion cargada"),
                "message": _("Sucursales y unidades por defecto cargadas"),
                "type": "success",
                "sticky": False,
            },
        }

    def action_open_purchase_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Lineas de Compra",
            "res_model": "mercado.import.purchase.line",
            "view_mode": "tree,form",
            "domain": [("batch_id", "=", self.id)],
            "context": {"default_batch_id": self.id},
        }

    def action_open_sale_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Lineas de Venta",
            "res_model": "mercado.import.sale.line",
            "view_mode": "tree,form",
            "domain": [("batch_id", "=", self.id)],
            "context": {"default_batch_id": self.id},
        }
