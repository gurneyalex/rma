# -*- coding: utf-8 -*-
# © 2017 Eficent Business and IT Consulting Services S.L.
# © 2015 Eezee-It, MONK Software, Vauxoo
# © 2013 Camptocamp
# © 2009-2013 Akretion,
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)
from openerp import api, fields, models
from openerp.addons import decimal_precision as dp
from random import randint
from datetime import datetime


class RmaOrder(models.Model):
    _inherit = "rma.order"

    @api.depends('rma_line_ids', 'rma_line_ids.procurement_ids')
    @api.multi
    def _compute_po_line_count(self):
        purchase_list = []
        for line in self.rma_line_ids:
            for procurement_id in line.procurement_ids:
                if procurement_id.purchase_id and procurement_id.purchase_id.id:
                    purchase_list.append(procurement_id.purchase_id.id)
        self.po_line_count = len(list(set(purchase_list)))

    add_purchase_id = fields.Many2one(comodel_name='purchase.order',
                                      string='Add Purchase Order',
                                      ondelete='set null')
    po_line_count = fields.Integer(compute=_compute_po_line_count,
                                   string='# of PO lines',
                                   copy=False, default=0)

    def _prepare_rma_line_from_po_line(self, line):
        operation = line.product_id.rma_operation_id and \
                    line.product_id.rma_operation_id.id or False
        if not operation:
            operation = line.product_id.categ_id.rma_operation_id and \
                        line.product_id.categ_id.rma_operation_id.id or False
        data = {
            'purchase_order_line_id': line.id,
            'product_id': line.product_id.id,
            'name': line.name,
            'origin': line.order_id.name,
            'uom_id': line.product_uom.id,
            'operation_id': operation,
            'product_qty': line.product_qty,
            'price_unit': line.currency_id.compute(
                line.price_unit, line.currency_id, round=False),
            'rma_id': self._origin.id
        }
        return data

    @api.onchange('add_purchase_id')
    def on_change_purchase(self):
        if not self.add_purchase_id:
            return {}
        if not self.partner_id:
            self.partner_id = self.add_purchase_id.partner_id.id

        new_lines = self.env['rma.order.line']
        for line in self.add_purchase_id.order_line:
            # TODO: Load a PO line only once
            # if line in self.rma_line_ids.mapped('purchase_order_line_id'):
            #     continue
            data = self._prepare_rma_line_from_po_line(line)
            new_line = new_lines.new(data)
            new_lines += new_line
        self.rma_line_ids += new_lines
        self.date_rma = fields.Datetime.now()
        self.delivery_address_id = self.add_purchase_id.partner_id.id
        self.invoice_address_id = self.add_purchase_id.partner_id.id
        self.add_purchase_id = False
        return {}

    @api.multi
    def action_view_purchase_order(self):
        action = self.env.ref('purchase.purchase_rfq')
        result = action.read()[0]
        order_ids = []
        for line in self.rma_line_ids:
            for procurement_id in line.procurement_ids:
                order_ids.append(procurement_id.purchase_id.id)
        result['domain'] = [('id', 'in', order_ids)]
        return result
