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

    def _prepare_rma_line_from_inv_line(self, line):
        data = super(RmaOrder, self)._prepare_rma_line_from_inv_line(line)
        data['sale_line_id'] = line.sale_line_id