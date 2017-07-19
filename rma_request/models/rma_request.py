# -*- coding: utf-8 -*-
# © 2017 Eficent Business and IT Consulting Services S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)
from openerp import _, api, fields, models
from openerp.addons import decimal_precision as dp


class RmaRequest(models.Model):
    _name = "rma.request"

    @api.model
    def _default_warehouse_id(self):
        rma_id = self.env.context.get('default_rma_id', False)
        warehouse = self.env['stock.warehouse']
        if rma_id:
            rma = self.env['rma.order'].browse(rma_id)
            warehouse = self.env['stock.warehouse'].search(
                [('company_id', '=', rma.company_id.id)], limit=1)
        return warehouse

    @api.model
    def _get_default_requested_by(self):
        return self.env.user

    @api.model
    def _get_rma_qty(self):
        return sum(self.supplier_rma_line_ids.filtered(
            lambda r: r.state != 'cancel').mapped(
            'product_qty'))

    @api.multi
    @api.depends('rma_line_ids','rma_line_ids.rma_id.state')
    def _compute_qty_rma(self):
        for rec in self:
            qty_in_rma = 0.0
            for rma_line in rec.rma_line_ids.filtered(lambda r: r.state !=
                    'cancel'):
                qty_in_rma += self.env['product.product']._compute_qty_obj(
                    rma_line.uom_id, rma_line.product_qty,
                    rec.uom_id)
            rec.qty_in_rma = qty_in_rma
            rec.qty_to_rma = rec.product_qty - rec.qty_in_rma

    @api.multi
    def _compute_rma_count(self):
        for rec in self:
            valid_lines = rec.rma_line_ids.filtered(
                lambda s: s.state != 'cancel')
            rec.rma_line_count = len(valid_lines)
            rec.rma_count = len(valid_lines.mapped('rma_id'))

    name = fields.Char(
        default="/", required=True,
        readonly=True, states={'draft': [('readonly', False)]})
    description = fields.Text(string='Description',
                              readonly=True,
                              states={'draft': [('readonly', False)]})
    origin = fields.Char(
        string='Source Document',
        readonly=True, states={'draft': [('readonly', False)]})
    state = fields.Selection(
        selection=[('draft', 'Draft'),
                   ('to_approve', 'To approve'),
                   ('approved', 'Approved'),
                   ('done', 'Done'),
                   ('cancel', 'Cancel')], string='State', required=True)
    type = fields.Selection(selection=[('customer', 'Customer'),
                                       ('supplier', 'Supplier')], required=True)
    requested_by = fields.Many2one(
        comodel_name='res.users', string='Requested by',
        default=_get_default_requested_by,
        required=True, track_visibility='onchange',
        readonly=True, states={'draft': [('readonly', False)]})
    requested_on = fields.Date(string='Requested on', required=True)
    assigned_to = fields.Many2one(
        comodel_name='res.users', string='Approver',
        track_visibility='onchange',
        readonly=True, states={'draft': [('readonly', False)]})
    partner_id = fields.Many2one('res.partner', string='Partner')
    product_id = fields.Many2one('product.product', string='Product',
                                 ondelete='restrict', required=True)
    uom_id = fields.Many2one('product.uom', string='Unit of Measure',
                             required=True)
    product_qty = fields.Float(
        string='Ordered Qty', copy=False,
        digits=dp.get_precision('Product Unit of Measure'), required=True)

    qty_to_rma = fields.Float(
        string='Qty to RMA',
        digits=dp.get_precision('Product Unit of Measure'),
        readonly=True, compute=_compute_qty_rma,
        store=True)
    qty_in_rma = fields.Float(
        string='Qty in RMA',
        digits=dp.get_precision('Product Unit of Measure'),
        readonly=True, compute=_compute_qty_rma,
        store=True)
    rma_count = fields.Integer(
        string='# of RMA',
        readonly=True, compute=_compute_rma_count)
    rma_line_count = fields.Integer(
        string='# of RMA Lines',
        readonly=True, compute=_compute_rma_count)
    warehouse_id = fields.Many2one('stock.warehouse',
                                   string='Warehouse',
                                   required=True,
                                   default=_default_warehouse_id)
    rma_line_ids = fields.One2many(comodel_name='rma.order.line',
                                   inverse_name='rma_request_id',
                                   copy=False, string='RMA Lines')
    company_id = fields.Many2one('res.company', string='Company',
                                 required=True, default=lambda self:
                                 self.env.user.company_id)

    @api.multi
    def _subscribe_assigned_user(self, vals):
        self.ensure_one()
        if vals.get('assigned_to'):
            self.message_subscribe_users(user_ids=[self.assigned_to.id])

    @api.model
    def _create_sequence(self, vals):
        if not vals.get('name') or vals.get('name') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'rma.request') or '/'
        return vals

    @api.model
    def create(self, vals):
        """Add sequence if name is not defined and subscribe to the thread
        the user assigned to the request."""
        vals = self._create_sequence(vals)
        res = super(RmaRequest, self).create(vals)
        res._subscribe_assigned_user(vals)
        return res

    @api.multi
    def write(self, vals):
        res = super(RmaRequest, self).write(vals)
        for request in self:
            request._subscribe_assigned_user(vals)
        return res

    @api.onchange('product_id')
    def _onchange_product_id(self):
        self.uom_id = self.product_id.uom_id

    @api.multi
    def action_view_rma(self):
        self.ensure_one()
        if self.type == 'customer':
            action = self.env.ref('rma.action_rma_customer', False)
            view = self.env.ref('rma.view_rma_form', False)
        else:
            action = self.env.ref('rma.action_rma_supplier', False)
            view = self.env.ref('rma.view_rma_supplier_form', False)
        result = action.read()[0]
        rmas = self.rma_line_ids.mapped('rma_id')
        # choose the view_mode accordingly
        if len(rmas) != 1:
            result['domain'] = "[('id', 'in', " + \
                               str(rmas) + ")]"
        elif len(rmas) == 1:
            res = view
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = rmas[0]
        return result

    @api.multi
    def action_view_rma_lines(self):
        self.ensure_one()
        if self.type == 'customer':
            action = self.env.ref('rma.action_rma_customer_lines', False)
            view = self.env.ref('rma.view_rma_line_form', False)
        else:
            action = self.env.ref('rma.action_rma_supplier_lines', False)
            view = self.env.ref('rma.view_rma_line_supplier_form', False)
        result = action.read()[0]
        # choose the view_mode accordingly
        if len(self.rma_line_ids) != 1:
            result['domain'] = "[('id', 'in', " + \
                               str(self.rma_line_ids) + ")]"
        elif len(self.rma_line_ids) == 1:
            res = view
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = rmas[0]
        return result
