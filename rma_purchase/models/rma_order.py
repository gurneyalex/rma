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
        for rec in self:
            purchase_list = []
            for line in rec.rma_line_ids:
                for procurement_id in line.procurement_ids:
                    if procurement_id.purchase_id and procurement_id.purchase_id.id:
                        purchase_list.append(procurement_id.purchase_id.id)
            rec.po_line_count = len(list(set(purchase_list)))

    po_line_count = fields.Integer(compute=_compute_po_line_count,
                                   string='# of PO lines',
                                   copy=False, default=0)

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
