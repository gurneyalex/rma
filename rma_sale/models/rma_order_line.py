# -*- coding: utf-8 -*-
# © 2017 Eficent Business and IT Consulting Services S.L.
# © 2015 Eezee-It, MONK Software, Vauxoo
# © 2013 Camptocamp
# © 2009-2013 Akretion,
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)
from openerp import _, api, fields, models
from openerp.addons import decimal_precision as dp


class RmaOrderLine(models.Model):
    _inherit = "rma.order.line"

    @api.one
    @api.depends('sale_line_ids', 'operation_id', 'operation_id.sale_type',
                 'product_id', 'product_qty')
    def _compute_qty_to_sell(self):
        if self.operation_id.sale_type == 'no':
            self.qty_to_sell = 0.0
        elif self.operation_id.sale_type == 'ordered':
            qty = self._get_rma_sold_qty()
            self.qty_to_sell = self.product_qty - qty
        elif self.operation_id.sale_type == 'received':
            qty = self._get_rma_sold_qty()
            self.qty_to_sell = self.qty_received - qty
        else:
            self.qty_to_sell = 0.0

    @api.one
    @api.depends('sale_line_ids')
    def _compute_qty_sold(self):
        self.qty_sold = self._get_rma_sold_qty()

    sale_line_ids = fields.One2many('sale.order.line', 'rma_line_id',
                                    string='Sales Order Lines', readonly=True,
                                    states={'draft': [('readonly', False)]},
                                    copy=False)
    qty_to_sell = fields.Float(
        string='Qty To Sell', copy=False,
        digits=dp.get_precision('Product Unit of Measure'),
        readonly=True, compute=_compute_qty_to_sell,
        store=True)

    qty_sold = fields.Float(
        string='Qty Sold', copy=False,
        digits=dp.get_precision('Product Unit of Measure'),
        readonly=True, compute=_compute_qty_sold,
        store=True)

    @api.multi
    def action_view_sale_order(self):
        action = self.env.ref('sale.action_quotations')
        result = action.read()[0]
        order_ids = []
        for sale_line in self.sale_line_ids:
            order_ids.append(sale_line.order_id.id)
        result['domain'] = [('id', 'in', order_ids)]
        return result

    @api.multi
    def _get_rma_sold_qty(self):
        self.ensure_one()
        qty = 0.0
        for sale_line in self.sale_line_ids:
            if self.type == 'customer':
                qty += sale_line.product_uom_qty

            else:
                qty = 0.0

        return qty
