# -*- coding: utf-8 -*-
# © 2017 Eficent Business and IT Consulting Services S.L.
# © 2015 Eezee-It, MONK Software, Vauxoo
# © 2013 Camptocamp
# © 2009-2013 Akretion,
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)
from openerp import _, api, fields, models


class RmaOrder(models.Model):
    _inherit = "rma.order"

    @api.multi
    def _get_valid_lines(self):
        for rec in self:
            lines = rec.rma_line_ids.filtered(
                lambda p: p.warranty_state != 'expired')
        return lines
