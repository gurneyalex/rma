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

    add_sale_id = fields.Many2one('sale.order', string='Add Sale Order',
                                  ondelete='set null', readonly=True,
                                  states={'draft': [('readonly', False)]})

    @api.model
    def _get_line_domain(self, rma_id, line):
        if line.sale_line_id and line.sale_line_id.id:
            domain = [('rma_id', '=', rma_id.id),
                      ('type', '=', 'supplier'),
                      ('sale_line_id', '=', line.sale_line_id.id)]
        else:
            domain = super(RmaOrder, self)._get_line_domain(rma_id, line)
        return domain


    def _prepare_rma_line_from_sale_order_line(self, line):
        operation = line.product_id.rma_operation_id and \
                    line.product_id.rma_operation_id.id or False
        if not operation:
            operation = line.product_id.categ_id.rma_operation_id and \
                        line.product_id.categ_id.rma_operation_id.id or False
        data = {
            'sale_line_id': line.id,
            'product_id': line.product_id.id,
            'name': line.name,
            'origin': line.order_id.name,
            'uom_id': line.product_uom.id,
            'operation_id': operation,
            'product_qty': line.product_uom_qty,
            'price_unit': line.currency_id.compute(
                line.price_unit, line.currency_id, round=False),
            'rma_id': self._origin.id
        }
        return data

    @api.onchange('add_sale_id')
    def on_change_sale_id(self):
        if not self.add_sale_id:
            return {}
        if not self.partner_id:
            self.partner_id = self.add_sale_id.partner_id.id
        new_lines = self.env['rma.order.line']
        for line in self.add_sale_id.order_line:
            # TODO: avoid duplicated lines
            # if line in self.rma_line_ids.mapped('sale_line_id'):
            #     continue
            data = self._prepare_rma_line_from_sale_order_line(line)
            new_line = new_lines.create(data)
            new_lines += new_line

        self.rma_line_ids += new_lines
        self.date_rma = fields.Datetime.now()
        self.delivery_address_id = self.add_sale_id.partner_id.id
        self.invoice_address_id = self.add_sale_id.partner_id.id
        self.add_sale_id = False
        return {}
