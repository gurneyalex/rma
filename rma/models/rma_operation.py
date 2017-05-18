# -*- coding: utf-8 -*-
# © 2017 Eficent Business and IT Consulting Services S.L.
# © 2015 Eezee-It, MONK Software, Vauxoo
# © 2013 Camptocamp
# © 2009-2013 Akretion,
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)
from openerp import _, api, fields, models


class RmaOperation(models.Model):
    _name = 'rma.operation'
    _description = 'RMA Operation'

    name = fields.Char('Description', required=True)
    code = fields.Char('Code', required=True)
    refund_policy = fields.Selection([
        ('no', 'No refund'), ('ordered', 'Based on Ordered Quantities'),
        ('received', 'Based on Received Quantities')], string="Refund Policy",
        default='no')
    receipt_policy = fields.Selection([
        ('no', 'Not required'), ('ordered', 'Based on Ordered Quantities'),
        ('received', 'Based on Delivered Quantities')],
        string="Receipts Policy", default='no')
    delivery_policy = fields.Selection([
        ('no', 'Not required'), ('ordered', 'Based on Ordered Quantities'),
        ('received', 'Based on Received Quantities')],
        string="Delivery Policy", default='no')
    route_id = fields.Many2one(
        'stock.location.route', string='Route',
        domain=[('rma_selectable', '=', True)])
    is_dropship = fields.Boolean('Dropship', default=False)
    location_id = fields.Many2one('stock.location', 'Sent To This Location')
    type = fields.Selection([
        ('customer', 'Customer'), ('supplier', 'Supplier')],
        string="Used in RMA of this type", required=True, default='customer')
    rma_line_ids = fields.One2many('rma.order.line', 'operation_id',
                                   'RMA lines')
