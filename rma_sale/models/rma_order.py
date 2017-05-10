# -*- coding: utf-8 -*-
# © 2017 Eficent Business and IT Consulting Services S.L.
# © 2015 Eezee-It, MONK Software, Vauxoo
# © 2013 Camptocamp
# © 2009-2013 Akretion,
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)
from openerp import _, api, fields, models
from openerp.addons import decimal_precision as dp


class RmaOrder(models.Model):
    _inherit = "rma.order"

    @api.model
    def _get_line_domain(self, rma_id, line):
        if line.sale_line_id and line.sale_line_id.id:
            domain = [('rma_id', '=', rma_id.id),
                      ('type', '=', 'supplier'),
                      ('sale_line_id', '=', line.sale_line_id.id)]
        else:
            domain = super(RmaOrder, self)._get_line_domain(rma_id, line)
        return domain
