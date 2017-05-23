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


class RmaOrderLine(models.Model):
    _name = "rma.order.line"

    @api.model
    def _default_warehouse_id(self):
        company = self.env.user.company_id.id
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', company)], limit=1)
        return warehouse

    @api.model
    def _default_customer_location_id(self):
        return self.env.ref('stock.stock_location_customers') or \
               self.env['stock.location'].search([(
                   'usage', '=', 'customer')], limit=1)

    @api.model
    def _default_supplier_location_id(self):
        return self.env.ref('stock.stock_location_suppliers') or \
               self.env['stock.location'].search([(
                   'usage', '=', 'supplier')], limit=1)

    @api.model
    def _default_location_id(self):
        if self.operation_id:
            if self.operation_id.location_id:
                return self.operation_id.location_id
        elif self.warehouse_id:
            return self.warehouse_id.lot_rma_id
        else:
            return self.env['stock.location'].search([], limit=1)

    @api.model
    def _default_receipt_policy(self):
        if self.operation_id:
            return self.operation_id.receipt_policy or 'no'

    @api.model
    def _default_refund_policy(self):
        if self.operation_id:
            return self.operation_id.refund_policy or 'no'

    @api.model
    def _default_delivery_policy(self):
        if self.operation_id:
            return self.operation_id.delivery_policy or 'no'

    @api.model
    def _default_delivery_address(self):
        partner_id = self.env.context.get('partner_id', False)
        if partner_id:
            return self.env['res.partner'].browse(partner_id)
        return self.env['res.partner'].search([], limit=1)

    @api.model
    def _default_invoice_address(self):
        partner_id = self.env.context.get('partner_id', False)
        if partner_id:
            return self.env['res.partner'].browse(partner_id)
        return self.env['res.partner'].search([], limit=1)

    @api.model
    def _default_in_route_id(self):
        if self.operation_id:
            return self.operation_id.in_route_id
        return self.env['stock.location.route'].search([], limit=1)

    @api.model
    def _default_out_route_id(self):
        if self.operation_id:
            return self.operation_id.out_route_id
        return self.env['stock.location.route'].search([], limit=1)


    @api.model
    def _default_customer_to_supplier(self):
        if self.operation_id:
            return self.operation_id.customer_to_supplier
        else:
            return False
    @api.model
    def _default_supplier_to_customer(self):
        if self.operation_id:
            return self.operation_id.customer_to_supplier
        else:
            return False

    @api.one
    def _compute_in_shipment_count(self):
        picking_ids = []
        suppliers = self.env.ref('stock.stock_location_suppliers')
        customers = self.env.ref('stock.stock_location_customers')
        for line in self:
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
    def _compute_out_shipment_count(self):
        picking_ids = []
        suppliers = self.env.ref('stock.stock_location_suppliers')
        customers = self.env.ref('stock.stock_location_customers')
        for line in self:
            if line.type == 'customer':
                for move in line.move_ids:
                    if move.picking_id.location_id != customers:
                        picking_ids.append(move.picking_id.id)
            else:
                for move in line.move_ids:
                    if move.picking_id.location_id != suppliers:
                        picking_ids.append(move.picking_id.id)
        self.out_shipment_count = len(list(set(picking_ids)))

    @api.multi
    def _get_rma_move_qty(self, states, shipment=False, delivery=False):
        self.ensure_one()
        qty = 0.0
        suppliers = self.env.ref('stock.stock_location_suppliers')
        customers = self.env.ref('stock.stock_location_customers')
        moves = self.env['stock.move'].search(
            [('procurement_id', 'in', self.procurement_ids.ids)])
        for move in moves.filtered(
                lambda m: m.state in states):
            if self.type == 'customer':
                if move.location_id == customers and shipment:
                    qty += move.product_qty
                elif move.location_id != customers and delivery:
                    qty += move.product_qty
            else:
                if move.location_id == suppliers and shipment:
                    qty += move.product_qty
                elif move.location_id != suppliers and delivery:
                    qty += move.product_qty
        return qty

    @api.one
    @api.depends('procurement_ids.state', 'state',
                 'receipt_policy', 'delivery_policy', 'type')
    def _compute_qty_incoming(self):
        qty = self._get_rma_move_qty(
            ('draft', 'confirmed', 'assigned'), True, False)
        self.qty_incoming = qty

    @api.one
    @api.depends('procurement_ids.state', 'state',
                 'receipt_policy', 'product_qty',
                 'delivery_policy', 'type')
    def _compute_qty_to_receive(self):
        if self.receipt_policy == 'no' or (
                self.type == 'supplier' and
                    self.customer_to_supplier):
            self.qty_to_receive = 0.0
        elif self.receipt_policy == 'ordered':
            qty = self._get_rma_move_qty(('done'), True, False)
            self.qty_to_receive = self.product_qty - qty
        elif self.receipt_policy == 'received':
            if self.type == 'customer':
                qty = self._get_rma_move_qty(('done'), True, False)
                self.qty_to_receive = self.qty_received - qty
            else:
                qty = self._get_rma_move_qty(('done'), False, True)
            self.qty_to_receive = qty - self.qty_received
        else:
            self.qty_to_receive = 0.0

    @api.one
    @api.depends('procurement_ids.state', 'state', 'parent_id',
                 'receipt_policy', 'product_qty',
                 'delivery_policy', 'type')
    def _compute_qty_to_deliver(self):
        if self.delivery_policy == 'no' or (
                self.type == 'customer' and
                    self.supplier_to_customer):
            self.qty_to_deliver = 0.0
        elif self.delivery_policy == 'ordered':
            qty = self._get_rma_move_qty(('done'), False, True)
            self.qty_to_deliver = self.product_qty - qty
        elif self.delivery_policy == 'received':
            qty = self._get_rma_move_qty(('done'), False, True)
            if self.parent_id and self.parent_id.id:
                qty_to_deliver = self.parent_id.qty_received - qty
            else:
                qty_to_deliver = self.qty_received - qty
            self.qty_to_deliver = qty_to_deliver
        else:
            self.qty_to_deliver = 0.0

    @api.one
    @api.depends('procurement_ids.state', 'state',
                 'receipt_policy',
                 'delivery_policy', 'type')
    def _compute_qty_received(self):
        qty = self._get_rma_move_qty(('done'), True, False)
        self.qty_received = qty

    @api.one
    @api.depends('procurement_ids.state', 'state',
                 'receipt_policy',
                 'delivery_policy', 'type')
    def _compute_qty_outgoing(self):
        qty = self._get_rma_move_qty(
            ('draft', 'confirmed', 'assigned'), False, True)
        self.qty_outgoing = qty

    @api.one
    @api.depends('procurement_ids.state', 'state',
                 'receipt_policy',
                 'delivery_policy', 'type')
    def _compute_qty_delivered(self):
        qty = self._get_rma_move_qty(('done'), False, True)
        self.qty_delivered = qty

    @api.one
    @api.depends('refund_line_ids.invoice_id.state',
                 'state', 'refund_policy', 'type')
    def _compute_qty_refunded(self):
        qty = 0.0
        if self.refund_policy == 'no':
            self.qty_refunded = qty
        for refund in self.refund_line_ids:
            if refund.invoice_id.state in ('open', 'paid'):
                qty += refund.quantity
        self.qty_refunded = qty

    @api.one
    @api.depends('invoice_line_id', 'state', 'refund_policy', 'type',
                 'refund_line_ids.invoice_id.state')
    def _compute_qty_to_refund(self):
        qty = 0.0
        if self.refund_policy == 'no':
            self.qty_to_refund = qty
        elif self.refund_policy == 'ordered':
            qty = self.product_qty
        elif self.refund_policy == 'received':
            qty = self.qty_received
        if self.refund_line_ids:
            for refund in self.refund_line_ids:
                if refund.invoice_id.state in ('open', 'paid'):
                    qty -= refund.quantity
        self.qty_to_refund = qty

    @api.one
    def _compute_move_count(self):
        move_list = []
        for move in self.move_ids:
            move_list.append(move.id)
        self.move_count = len(list(set(move_list)))

    @api.one
    def _compute_procurement_count(self):
        procurement_list = []
        for procurement in self.procurement_ids.filtered(
                lambda p: p.state == 'exception'):
            procurement_list.append(procurement.id)
        self.procurement_count = len(list(set(procurement_list)))

    @api.one
    def _compute_refund_count(self):
        refund_list = []
        for inv_line in self.refund_line_ids:
            refund_list.append(inv_line.invoice_id.id)
        self.refund_count = len(list(set(refund_list)))

    delivery_address_id = fields.Many2one(
        'res.partner', string='Partner delivery address',
        default=_default_delivery_address,
        help="This address will be used to "
        "deliver repaired or replacement products.")
    invoice_address_id = fields.Many2one(
        'res.partner', string='Partner invoice address',
        default=_default_invoice_address,
        help="Invoice address for current rma order.")
    procurement_count = fields.Integer(compute=_compute_procurement_count,
                                       string='# of Procurements', copy=False,
                                       default=0)
    refund_count = fields.Integer(compute=_compute_refund_count,
                                  string='# of Refunds', copy=False, default=0)
    in_shipment_count = fields.Integer(compute=_compute_in_shipment_count,
                                       string='# of Shipments', copy=False,
                                       default=0)
    out_shipment_count = fields.Integer(compute=_compute_out_shipment_count,
                                       string='# of Deliveries', copy=False,
                                       default=0)
    name = fields.Text(string='Description', required=True)
    origin = fields.Char(string='Source Document',
                         help="Reference of the document that produced "
                              "this rma.")
    state = fields.Selection(related='rma_id.state')
    operation_id = fields.Many2one(
        comodel_name="rma.operation", string="Operation")

    invoice_line_id = fields.Many2one('account.invoice.line',
                                      string='Invoice Line',
                                      ondelete='restrict',
                                      index=True)
    refund_line_ids = fields.One2many(comodel_name='account.invoice.line',
                                      inverse_name='rma_line_id',
                                      string='Refund Lines',
                                      copy=False, index=True, readonly=True)
    invoice_id = fields.Many2one('account.invoice', string='Source',
                                 related='invoice_line_id.invoice_id',
                                 index=True, readonly=True)
    assigned_to = fields.Many2one('res.users', related='rma_id.assigned_to')
    requested_by = fields.Many2one('res.users', related='rma_id.requested_by')
    partner_id = fields.Many2one('res.partner', related='rma_id.partner_id',
                                 store=True)
    sequence = fields.Integer(default=10,
                              help="Gives the sequence of this line "
                              "when displaying the rma.")
    rma_id = fields.Many2one('rma.order', string='RMA',
                             ondelete='cascade')
    uom_id = fields.Many2one('product.uom', string='Unit of Measure')
    product_id = fields.Many2one('product.product', string='Product',
                                 ondelete='restrict')
    price_unit = fields.Monetary(string='Price Unit', readonly=False,
                                 states={'approved': [('readonly', True)],
                                         'done': [('readonly', True)],
                                         'to_approve': [('readonly', True)]})
    move_ids = fields.One2many('stock.move', 'rma_line_id',
                               string='Stock Moves', readonly=True,
                               states={'draft': [('readonly', False)]},
                               copy=False)
    procurement_ids = fields.One2many('procurement.order', 'rma_line_id',
                                      string='Procurements', readonly=True,
                                      states={'draft': [('readonly', False)]},
                                      copy=False)
    currency_id = fields.Many2one('res.currency', string="Currency")
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.user.company_id)
    type = fields.Selection(related='rma_id.type')
    customer_to_supplier= fields.Boolean(
        'The customer will send to the supplier',
        default=_default_customer_to_supplier)
    supplier_to_customer = fields.Boolean(
        'The supplier will send to the customer',
        default=_default_supplier_to_customer)
    refund_policy = fields.Selection([
        ('no', 'No refund'), ('ordered', 'Based on Ordered Quantities'),
        ('received', 'Based on Received Quantities')], string="Refund Policy",
        default=_default_refund_policy, required=True)
    receipt_policy = fields.Selection([
        ('no', 'Not required'), ('ordered', 'Based on Ordered Quantities'),
        ('received', 'Based on Delivered Quantities')],
        default=_default_receipt_policy, required=True,
        string="Receipts Policy")
    delivery_policy = fields.Selection([
        ('no', 'Not required'), ('ordered', 'Based on Ordered Quantities'),
        ('received', 'Based on Received Quantities')],
        default=_default_delivery_policy, required=True,
        string="Delivery Policy")
    in_route_id = fields.Many2one(
        'stock.location.route', string='Inbound Route',
        domain=[('rma_selectable', '=', True)])
    out_route_id = fields.Many2one(
        'stock.location.route', string='Outbound Route',
        domain=[('rma_selectable', '=', True)])
    in_warehouse_id = fields.Many2one('stock.warehouse',
                                      string='Inbound Warehouse',
                                      default=_default_warehouse_id)
    out_warehouse_id = fields.Many2one('stock.warehouse',
                                       string='Outbound Warehouse',
                                       default=_default_warehouse_id)
    location_id = fields.Many2one(
        'stock.location', 'Send To This Company Location')
    parent_id = fields.Many2one(
        'rma.order.line', string='Parent RMA line', ondelete='cascade')
    children_ids = fields.One2many('rma.order.line', 'parent_id')
    partner_address_id = fields.Many2one(
        'res.partner', readonly=True,
        states={'draft': [('readonly', False)]},
        string='Partner Address',
        help="This address of the supplier in case of Customer RMA operation "
             "dropship. The address of the customer in case of Supplier RMA "
             "operation dropship")
    product_qty = fields.Float(
        string='Ordered Qty', copy=False,
        digits=dp.get_precision('Product Unit of Measure'))
    qty_to_receive = fields.Float(
        string='Qty To Receive',
        digits=dp.get_precision('Product Unit of Measure'),
        compute=_compute_qty_to_receive, store=True)
    qty_incoming = fields.Float(
        string='Incoming Qty', copy=False,
        readonly=True, digits=dp.get_precision('Product Unit of Measure'),
        compute=_compute_qty_incoming, store=True)
    qty_received = fields.Float(
        string='Qty Received', copy=False,
        digits=dp.get_precision('Product Unit of Measure'),
        compute=_compute_qty_received,
        store=True)
    qty_to_deliver = fields.Float(
        string='Qty To Deliver', copy=False,
        digits=dp.get_precision('Product Unit of Measure'),
        readonly=True, compute=_compute_qty_to_deliver,
        store=True)
    qty_outgoing = fields.Float(
        string='Outgoing Qty', copy=False,
        readonly=True, digits=dp.get_precision('Product Unit of Measure'),
        compute=_compute_qty_outgoing,
        store=True)
    qty_delivered = fields.Float(
        string='Qty Delivered', copy=False,
        digits=dp.get_precision('Product Unit of Measure'),
        readonly=True, compute=_compute_qty_delivered,
        store=True)
    qty_to_refund = fields.Float(
        string='Qty To Refund', copy=False,
        digits=dp.get_precision('Product Unit of Measure'), readonly=True,
        compute=_compute_qty_to_refund, store=True)
    qty_refunded = fields.Float(
        string='Qty Refunded', copy=False,
        digits=dp.get_precision('Product Unit of Measure'),
        readonly=True, compute=_compute_qty_refunded, store=True)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        self.uom_id = self.product_id.uom_id.id
        self.price_unit = self.product_id.standard_price
        if self.product_id.categ_id.rma_operation_id:
            self.operation_id = self.product_id.rma_operation_id
        else:
            self.operation_id = self.product_id.categ_id.rma_operation_id

    @api.onchange('operation_id')
    def _onchange_operation_id(self):
        self.name = self.operation_id.name
        self.receipt_policy = self.operation_id.receipt_policy
        self.delivery_policy = self.operation_id.delivery_policy
        self.refund_policy = self.operation_id.refund_policy
        self.in_warehouse_id = self.operation_id.in_warehouse_id
        self.out_warehouse_id = self.operation_id.out_warehouse_id
        self.location_id = self.operation_id.location_id or \
                           self.in_warehouse_id.lot_rma_id
        self.customer_to_supplier = self.operation_id.customer_to_supplier
        self.supplier_to_customer = self.operation_id.supplier_to_customer
        self.in_route_id = self.operation_id.in_route_id
        self.out_route_id = self.operation_id.out_route_id

    @api.onchange('invoice_line_id')
    def _onchange_invoice_line_id(self):
        if not self.invoice_line_id:
            return
        self.origin = self.invoice_id.number

    @api.multi
    @api.constrains('invoice_line_id')
    def _check_duplicated_lines(self):
        for line in self:
            matching_inv_lines = self.env['account.invoice.line'].search([(
                'id', '=', line.invoice_line_id.id)])
            if len(matching_inv_lines) > 1:
                    raise UserError(
                        _("There's an rma for the invoice line %s "
                          "and invoice %s" %
                          (line.invoice_line_id,
                           line.invoice_line_id.invoice_id)))
        return {}

    @api.multi
    def action_view_invoice(self):
        action = self.env.ref('account.action_invoice_tree')
        result = action.read()[0]
        res = self.env.ref('account.invoice_form', False)
        result['views'] = [(res and res.id or False, 'form')]
        result['view_id'] = res and res.id or False
        result['res_id'] = self.invoice_line_id.invoice_id.id

        return result

    @api.multi
    def action_view_refunds(self):
        action = self.env.ref('account.action_invoice_tree2')
        result = action.read()[0]
        invoice_ids = []
        for inv_line in self.refund_line_ids:
            invoice_ids.append(inv_line.invoice_id.id)
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
    def action_view_in_shipments(self):
        action = self.env.ref('stock.action_picking_tree_all')
        result = action.read()[0]
        picking_ids = []
        suppliers = self.env.ref('stock.stock_location_suppliers')
        customers = self.env.ref('stock.stock_location_customers')
        for line in self:
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
        for line in self:
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
    def action_view_procurements(self):
        action = self.env.ref('procurement.procurement_order_action_exceptions')
        result = action.read()[0]
        procurements = self.procurement_ids.filtered(
                lambda p: p.state == 'exception').ids
        # choose the view_mode accordingly
        if len(procurements) != 1:
            result['domain'] = "[('id', 'in', " + \
                               str(procurements) + ")]"
        elif len(procurements) == 1:
            res = self.env.ref('procurement.procurement_form_view', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = procurements[0]
        return result
