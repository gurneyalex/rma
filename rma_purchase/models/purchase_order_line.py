# -*- coding: utf-8 -*-
# © 2017 Eficent Business and IT Consulting Services S.L.
# © 2015 Eezee-It, MONK Software, Vauxoo
# © 2013 Camptocamp
# © 2009-2013 Akretion,
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)
from openerp import api, fields, models


class PurchaseOrderLine(models.Model):

    _inherit = "purchase.order.line"

    rma_line_ids = fields.Many2many(
        'purchase.order.line', 'purchase_line_rma_line_rel',
        'purchase_order_line_id', 'rma_order_line_id',
        string='RMA Order Lines', copy=False)
