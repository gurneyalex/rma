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
from datetime import datetime


class RmaOrder(models.Model):
    _name = "rma.order"
    _inherit = ['mail.thread']

    @api.model
    def _compute_rule_id(self):
        if self.company_id and self.company_id.id:
            if self.company_id.rma_rule_id and self.company_id.rma_rule_id.id:
                self.rule_id = self.company_id.rma_rule_id

    @api.model
    def _get_default_type(self):
        if 'supplier' in self.env.context:
            return "supplier"
        else:
            return "customer"

    name = fields.Char(string='Order Number', index=True,
                       readonly=True,
                       states={'progress': [('readonly', False)]},
                       copy=False)
    type = fields.Selection(
        [('customer', 'Customer'), ('supplier', 'Supplier')],
        string="Type", required=True, default=_get_default_type, readonly=True)
    reference = fields.Char(string='Reference',
                            help="The partner reference of this RMA order.")

    comment = fields.Text('Additional Information', readonly=True, states={
        'draft': [('readonly', False)]})
    add_invoice_id = fields.Many2one('account.invoice', string='Add Invoice',
                                     ondelete='set null', readonly=True,
                                     states={'draft': [('readonly', False)]})
    state = fields.Selection([('draft', 'Draft'), ('to_approve', 'To Approve'),
                              ('approved', 'Approved'),
                              ('done', 'Done')], string='State', index=True,
                              default='draft')
    date_rma = fields.Datetime(string='Order Date', index=True, copy=False)
    partner_id = fields.Many2one('res.partner', string='Partner',
                                 required=True, readonly=True,
                                 states={'draft': [('readonly', False)]})
    assigned_to = fields.Many2one('res.users', 'Assigned to',
                                  track_visibility='onchange')
    requested_by = fields.Many2one('res.users', 'Requested by',
                                   track_visibility='onchange',
                                   default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self:
                                 self.env.user.company_id)
    rule_id = fields.Many2one('rma.rule', string='Approval Criteria',
                              compute=_compute_rule_id)
    rma_line_ids = fields.One2many('rma.order.line', 'rma_id',
                                   string='RMA lines')

    @api.model
    def create(self, vals):
        if self.env.context.get('supplier'):
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'rma.order.supplier')
        else:
            vals['name'] = self.env['ir.sequence'].next_by_code('rma.order')
        return super(RmaOrder, self).create(vals)

    @api.one
    def _compute_invoice_refund_count(self):
        invoice_list = []
        for line in self.rma_line_ids:
            for refund in line.refund_line_ids:
                invoice_list.append(refund.invoice_id.id)
        self.invoice_refund_count = len(list(set(invoice_list)))

    @api.one
    def _compute_in_shipment_count(self):
        picking_ids = []
        suppliers = self.env.ref('stock.stock_location_suppliers')
        customers = self.env.ref('stock.stock_location_customers')
        for line in self.rma_line_ids:
            if line.type == 'customer':
                for move in line.move_ids:
                    if move.picking_id.location_id == customers:
                        picking_ids.append(move.picking_id.id)
            else:
                for move in line.move_ids:
                    if move.picking_id.location_id == suppliers:
                        picking_ids.append(move.picking_id.id)
        self.in_shipment_count = len(list(set(picking_ids)))

    @api.one
    def _compute_invoice_count(self):
        invoice_list = []
        for line in self.rma_line_ids:
            if line.invoice_line_id and line.invoice_line_id.id:
                invoice_list.append(line.invoice_line_id.invoice_id.id)
        self.invoice_count = len(list(set(invoice_list)))

    @api.one
    def _compute_out_shipment_count(self):
        picking_ids = []
        suppliers = self.env.ref('stock.stock_location_suppliers')
        customers = self.env.ref('stock.stock_location_customers')
        for line in self.rma_line_ids:
            if line.type == 'customer':
                for move in line.move_ids:
                    if move.picking_id.location_id != customers:
                        picking_ids.append(move.picking_id.id)
            else:
                for move in line.move_ids:
                    if move.picking_id.location_id != suppliers:
                        picking_ids.append(move.picking_id.id)
        self.out_shipment_count = len(list(set(picking_ids)))

    @api.one
    def _compute_supplier_line_count(self):
        lines = self.rma_line_ids.filtered(
            lambda r: r.children_ids)
        related_lines = [line.id for line in lines.children_ids]
        self.supplier_line_count = len(related_lines)

    @api.one
    def _compute_line_count(self):
        self.line_count = len(self._get_valid_lines())

    invoice_refund_count = fields.Integer(
        compute=_compute_invoice_refund_count,
        string='# of Refunds',
        copy=False)
    invoice_count = fields.Integer(compute=_compute_invoice_count,
                                   string='# of Incoming Shipments',
                                   copy=False)
    in_shipment_count = fields.Integer(compute=_compute_in_shipment_count,
                                       string='# of Invoices', copy=False)
    out_shipment_count = fields.Integer(compute=_compute_out_shipment_count,
                                        string='# of Outgoing Shipments',
                                        copy=False)
    line_count = fields.Integer(compute=_compute_line_count,
                                string='# of Outgoing Shipments',
                                copy=False)
    supplier_line_count = fields.Integer(compute=_compute_supplier_line_count,
                                         string='# of Outgoing Shipments',
                                         copy=False)

    def _prepare_rma_line_from_inv_line(self, line):
        operation = line.product_id.rma_operation_id and \
                    line.product_id.rma_operation_id.id or False
        if not operation:
            operation = line.product_id.categ_id.rma_operation_id and \
                        line.product_id.categ_id.rma_operation_id.id or False
        data = {
            'invoice_line_id': line.id,
            'product_id': line.product_id.id,
            'name': line.name,
            'origin': line.invoice_id.number,
            'uom_id': line.uom_id.id,
            'operation_id': operation,
            'product_qty': line.quantity,
            'price_unit': line.invoice_id.currency_id.compute(
                line.price_unit, line.currency_id, round=False),
            'rma_id': self._origin.id
        }
        return data

    @api.onchange('add_invoice_id')
    def on_change_invoice(self):
        if not self.add_invoice_id:
            return {}
        if not self.partner_id:
            self.partner_id = self.add_invoice_id.partner_id.id
        new_lines = self.env['rma.order.line']
        for line in self.add_invoice_id.invoice_line_ids:
            # Load a PO line only once
            if line in self.rma_line_ids.mapped('invoice_line_id'):
                continue
            data = self._prepare_rma_line_from_inv_line(line)
            new_line = new_lines.new(data)
            new_lines += new_line

        self.rma_line_ids += new_lines
        self.date_rma = fields.Datetime.now()
        self.delivery_address_id = self.add_invoice_id.partner_id.id
        self.invoice_address_id = self.add_invoice_id.partner_id.id
        self.add_invoice_id = False
        return {}

    @api.multi
    def action_view_invoice_refund(self):
        """
        This function returns an action that display existing vendor refund
        bills of given purchase order id.
        When only one found, show the vendor bill immediately.
        """
        action = self.env.ref('account.action_invoice_tree2')
        result = action.read()[0]
        invoice_list = []
        for line in self.rma_line_ids:
            for refund in line.refund_line_ids:
                invoice_list.append(refund.invoice_id.id)
        invoice_ids = list(set(invoice_list))
        # choose the view_mode accordingly
        if len(invoice_ids) != 1:
            result['domain'] = "[('id', 'in', " + \
                               str(invoice_ids) + ")]"
        elif len(invoice_ids) == 1:
            res = self.env.ref('account.invoice_supplier_form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = invoice_ids[0]
        return result

    @api.multi
    def action_view_invoice(self):
        if self.type == "supplier":
            action = self.env.ref('account.action_invoice_tree2')
        else:
            action = self.env.ref('account.action_invoice_tree')
        result = action.read()[0]
        invoice_list = []
        for line in self.rma_line_ids:
            invoice_list.append(line.invoice_id.id)
        invoice_ids = list(set(invoice_list))
        # choose the view_mode accordingly
        if len(invoice_ids) != 1:
            result['domain'] = "[('id', 'in', " + \
                               str(invoice_ids) + ")]"
        elif len(invoice_ids) == 1:
            if self.type == "supplier":
                res = self.env.ref('account.invoice_supplier_form', False)
            else:
                res = self.env.ref('account.invoice_form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = invoice_ids[0]
        return result

    @api.multi
    def action_view_in_shipments(self):
        action = self.env.ref('stock.action_picking_tree_all')
        result = action.read()[0]
        picking_ids = []
        suppliers = self.env.ref('stock.stock_location_suppliers')
        customers = self.env.ref('stock.stock_location_customers')
        for line in self.rma_line_ids:
            if line.type == 'customer':
                for move in line.move_ids:
                    if move.picking_id.location_id == customers:
                        picking_ids.append(move.picking_id.id)
            else:
                for move in line.move_ids:
                    if move.picking_id.location_id == suppliers:
                        picking_ids.append(move.picking_id.id)
        shipments = list(set(picking_ids))
        # choose the view_mode accordingly
        if len(shipments) != 1:
            result['domain'] = "[('id', 'in', " + \
                               str(shipments) + ")]"
        elif len(shipments) == 1:
            res = self.env.ref('stock.view_picking_form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = shipments[0]
        return result

    @api.multi
    def action_view_out_shipments(self):
        action = self.env.ref('stock.action_picking_tree_all')
        result = action.read()[0]
        picking_ids = []
        suppliers = self.env.ref('stock.stock_location_suppliers')
        customers = self.env.ref('stock.stock_location_customers')
        for line in self.rma_line_ids:
            if line.type == 'customer':
                for move in line.move_ids:
                    if move.picking_id.location_id != customers:
                        picking_ids.append(move.picking_id.id)
            else:
                for move in line.move_ids:
                    if move.picking_id.location_id != suppliers:
                        picking_ids.append(move.picking_id.id)
        shipments = list(set(picking_ids))
        # choose the view_mode accordingly
        if len(shipments) != 1:
            result['domain'] = "[('id', 'in', " + \
                               str(shipments) + ")]"
        elif len(shipments) == 1:
            res = self.env.ref('stock.view_picking_form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = shipments[0]
        return result

    @api.multi
    def action_rma_to_approve(self):
        for rec in self:
            rec.state = 'to_approve'
            if rec.rule_id and rec.rule_id.id:
                if rec.rule_id.approval_policy == 'always':
                    rec.assigned_to = self.env.uid
                    rec.action_rma_approve()
        return True

    @api.multi
    def action_rma_draft(self):
        for rec in self:
            rec.state = 'draft'
        return True

    @api.model
    def _get_line_domain(self, rma_id, line):
        return [('rma_id', '=', rma_id.id),
             ('type', '=', 'supplier'),
             ('invoice_line_id', '=', line.invoice_line_id.id)]

    @api.model
    def _get_existing_lines(self, rma_id, line):
        domain = self._get_line_domain(rma_id, line)
        existing_lines = self.env['rma.order.line'].search(domain)
        return existing_lines

    @api.model
    def _create_supplier_rma(self, origin_rma, lines):
        partners = lines.mapped('partner_address_id')
        for partner in partners:
            existing_rmas = self.env['rma.order'].search(
                [('partner_id', '=', partner.id),
                 ('state', '=', 'draft'),
                 ('type', '=', 'supplier')])
            if not len(existing_rmas):
                rma_values = {'partner_id': partner.id,
                              'delivery_address_id': partner.id,
                              'invoice_address_id': partner.id,
                              'type': 'supplier',
                              'assigned_to': origin_rma.assigned_to.id,
                              'requested_by': origin_rma.requested_by.id,
                              'date_rma': origin_rma.date_rma}
                self = self.with_context(supplier=True)
                rma_id = self.env['rma.order'].create(rma_values)
            else:
                rma_id = existing_rmas[-1]
            for line in lines.filtered(
                    lambda p: p.partner_address_id == partner):
                # existing_lines = self._get_existing_lines(rma_id, line)
                # if existing_lines:
                #     continue
                if line.children_ids and line.children_ids.ids:
                    for child_id in line.children_ids:
                        if child_id.parent_id and child_id.parent_id.id:
                            if child_id.parent_id.id != line.id:
                                line_values = {
                                    'origin': origin_rma.name,
                                    'name': line.name,
                                    'partner_address_id':
                                        origin_rma.delivery_address_id.id,
                                    'product_id': line.product_id.id,
                                    'parent_id': line.id,
                                    'product_qty': line.product_qty,
                                    'rma_id': rma_id.id}
                                self.env['rma.order.line'].create(line_values)
        return True

    @api.multi
    def action_rma_approve(self):
        # pass the supplier address in case this is a customer RMA
        for rec in self:
            rec.state = 'approved'
            # Only customer RMA can create supplier RMA
            if rec.type == 'customer':
                lines = rec.rma_line_ids.filtered(lambda p: p.is_dropship)
                if lines:
                    self._create_supplier_rma(rec, lines)
        return True

    @api.multi
    def action_rma_done(self):
        for rec in self:
            rec.state = 'done'
            return True

    @api.multi
    def _get_valid_lines(self):
        self.ensure_one()
        return self.rma_line_ids

    @api.multi
    def action_view_lines(self):
        if self.type == 'customer':
            action = self.env.ref('rma.action_rma_customer_lines')
        else:
            action = self.env.ref('rma.action_rma_supplier_lines')
        result = action.read()[0]
        lines = self._get_valid_lines()
        # choose the view_mode accordingly
        if len(lines) != 1:
            result['domain'] = "[('id', 'in', " + \
                               str(lines.ids) + ")]"
        elif len(lines) == 1:
            if self.type == 'customer':
                res = self.env.ref('rma.view_rma_line_form', False)
            else:
                res = self.env.ref('rma.view_rma_line_supplier_form', False)

            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = lines.id
        return result

    @api.multi
    def action_view_supplier_lines(self):
        action = self.env.ref('rma.action_rma_supplier_lines')
        result = action.read()[0]
        lines = self.rma_line_ids
        related_lines = [line.id for line in lines.children_ids]
        # choose the view_mode accordingly
        if len(lines) != 1:
            result['domain'] = "[('id', 'in', " + \
                               str(related_lines) + ")]"
        elif len(lines) == 1:
            res = self.env.ref('rma.view_rma_line_supplier_form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = related_lines[0]
        return result
