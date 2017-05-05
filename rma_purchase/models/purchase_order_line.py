# -*- coding: utf-8 -*-
# © 2017 Eficent Business and IT Consulting Services S.L.
# © 2015 Eezee-It, MONK Software, Vauxoo
# © 2013 Camptocamp
# © 2009-2013 Akretion,
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)
from openerp import api, fields, models


class PurchaseOrderLine(models.Model):

    _inherit = "purchase.order.line"

    rma_line_id = fields.Many2one('rma.order.line', string='RMA',
                                  ondelete='restrict')

    def _create_stock_moves(self, picking):
        res = super(PurchaseOrderLine, self)._create_stock_moves(picking)
        if self.rma_line_id and self.rma_line_id.id:
            for move in res:
                move.write({'rma_line_id': self.rma_line_id.id})
        return res