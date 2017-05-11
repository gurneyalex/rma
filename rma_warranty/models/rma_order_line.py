# -*- coding: utf-8 -*-
# © 2017 Eficent Business and IT Consulting Services S.L.
# © 2015 Eezee-It, MONK Software, Vauxoo
# © 2013 Camptocamp
# © 2009-2013 Akretion,
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)
from openerp import _, api, fields, models
from openerp.addons import decimal_precision as dp
from openerp.exceptions import UserError
from dateutil.relativedelta import relativedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
import math
from datetime import datetime
import calendar


class RmaOrderLine(models.Model):
    _inherit = "rma.order.line"

    @api.one
    @api.depends('invoice_line_id')
    def _compute_warranty(self):
        limit = False
        state = "undefined"
        line = self.invoice_line_id
        invoice_date = line.invoice_id.date_invoice
        if self.type == 'supplier':
            seller = line.product_id.seller_ids.filtered(
                lambda p: p.name == line.invoice_id.partner_id)
            warranty = seller.warranty_duration or False
        else:
            warranty = line.product_id.warranty

        if warranty and invoice_date:
            limit = datetime.strptime(
                invoice_date, DEFAULT_SERVER_DATE_FORMAT) + relativedelta(
                months=int(warranty))
        if limit and warranty > 0:
            if limit < datetime.now():
                state = 'expired'
            else:
                state = 'valid'
        if limit:
            self.limit = datetime.strftime(limit, DEFAULT_SERVER_DATE_FORMAT)
        self.warranty_state = state

    limit = fields.Date('Warranty Expiry Date', compute=_compute_warranty)
    warranty_state = fields.Selection([('valid', _("Valid")),
                                       ('expired', _("Expired")),
                                       ('undefined', _("Undefined"))],
                                      string='Warranty',
                                      compute=_compute_warranty)