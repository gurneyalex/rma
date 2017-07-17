# -*- coding: utf-8 -*-
# © 2017 Eficent Business and IT Consulting Services S.L.
# © 2015 Eezee-It, MONK Software, Vauxoo
# © 2013 Camptocamp
# © 2009-2013 Akretion,
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)
from openerp import _, api, fields, models
from openerp.addons import decimal_precision as dp
import operator
ops = {'=': operator.eq,
       '!=': operator.ne}


class RmaOrderLine(models.Model):
    _name = "rma.order.line"
    _rec_name = "rma_id"

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
    def _default_location_id(self):
        wh = self._default_warehouse_id()
        return wh.lot_rma_id

    @api.model
    def _default_delivery_address(self):
        partner_id = self.env.context.get('partner_id', False)
        if partner_id:
            return self.env['res.partner'].browse(partner_id)
        return self.env['res.partner'].search([], limit=1)

    @api.multi
    def _compute_in_shipment_count(self):
        for line in self:
            moves = line.procurement_ids.mapped('move_ids').filtered(
                lambda m: m.location_dest_id.usage == 'internal')
            pickings = moves.mapped('picking_id')
            line.in_shipment_count = len(pickings)

    @api.multi
    def _compute_out_shipment_count(self):
        for line in self:
            moves = line.procurement_ids.mapped('move_ids').filtered(
                lambda m: m.location_dest_id.usage != 'internal')
            pickings = moves.mapped('picking_id')
            line.out_shipment_count = len(pickings)

    @api.multi
    def _get_rma_move_qty(self, states, direction='in'):
        self.ensure_one()
        product_obj = self.env['product.uom']
        qty = 0.0
        if direction == 'in':
            op = ops['=']
        else:
            op = ops['!=']
        for move in self.procurement_ids.mapped('move_ids').filtered(
                lambda m: m.state in states and op(m.location_id.usage,
                                                   self.type)):
            qty += product_obj._compute_qty_obj(
                move.product_uom, move.product_uom_qty,
                self.uom_id)
        return qty

    @api.multi
    @api.depends('move_ids', 'move_ids.state', 'qty_received',
                 'receipt_policy', 'product_qty', 'type')
    def _compute_qty_to_receive(self):
        for rec in self:
            rec.qty_to_receive = 0.0
            if rec.receipt_policy == 'ordered':
                rec.qty_to_receive = rec.product_qty - rec.qty_received
            elif self.receipt_policy == 'delivered':
                self.qty_to_receive = rec.qty_delivered - rec.qty_received

    @api.multi
    @api.depends('move_ids', 'move_ids.state',
                 'delivery_policy', 'product_qty', 'type', 'qty_delivered',
                 'qty_received')
    def _compute_qty_to_deliver(self):
        for rec in self:
            rec.qty_to_deliver = 0.0
            if rec.delivery_policy == 'ordered':
                rec.qty_to_deliver = rec.product_qty - rec.qty_delivered
            elif self.delivery_policy == 'received':
                self.qty_to_deliver = rec.qty_received - rec.qty_delivered

    @api.multi
    @api.depends('move_ids', 'move_ids.state', 'type')
    def _compute_qty_incoming(self):
        for rec in self:
            qty = rec._get_rma_move_qty(
                ('draft', 'confirmed', 'assigned'), direction='in')
            rec.qty_incoming = qty

    @api.multi
    @api.depends('move_ids', 'move_ids.state', 'type')
    def _compute_qty_received(self):
        for rec in self:
            qty = rec._get_rma_move_qty('done', direction='in')
            rec.qty_received = qty

    @api.multi
    @api.depends('move_ids', 'move_ids.state', 'type')
    def _compute_qty_outgoing(self):
        for rec in self:
            qty = rec._get_rma_move_qty(
                ('draft', 'confirmed', 'assigned'), direction='out')
            rec.qty_outgoing = qty

    @api.multi
    @api.depends('move_ids', 'move_ids.state', 'type')
    def _compute_qty_delivered(self):
        for rec in self:
            qty = rec._get_rma_move_qty('done', direction='out')
            rec.qty_delivered = qty

    @api.multi
    def _compute_procurement_count(self):
        self.ensure_one()
        procurement_list = []
        for procurement in self.procurement_ids.filtered(
                lambda p: p.state == 'exception'):
            procurement_list.append(procurement.id)
        self.procurement_count = len(list(set(procurement_list)))

    delivery_address_id = fields.Many2one(
        'res.partner', string='Partner delivery address',
        default=_default_delivery_address,
        help="This address will be used to "
        "deliver repaired or replacement products.")

    procurement_count = fields.Integer(compute=_compute_procurement_count,
                                       string='# of Procurements', copy=False,
                                       default=0)
    in_shipment_count = fields.Integer(compute=_compute_in_shipment_count,
                                       string='# of Shipments', default=0)
    out_shipment_count = fields.Integer(compute=_compute_out_shipment_count,
                                        string='# of Deliveries', default=0)
    name = fields.Text(string='Description', required=True)
    origin = fields.Char(string='Source Document',
                         help="Reference of the document that produced "
                              "this rma.")
    state = fields.Selection(related='rma_id.state')
    operation_id = fields.Many2one(
        comodel_name="rma.operation", string="Operation")

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
                               string='Stock Moves', readonly=True
                               , copy=False)
    reference_move_id = fields.Many2one(comodel_name='stock.move',
                                        string='Originating stock move',
                                        readonly=True, copy=False)
    procurement_ids = fields.One2many('procurement.order', 'rma_line_id',
                                      string='Procurements', readonly=True,
                                      states={'draft': [('readonly', False)]},
                                      copy=False)
    currency_id = fields.Many2one('res.currency', string="Currency")
    company_id = fields.Many2one('res.company', string='Company',
                                 relation='rma_id.company_id', store=True)
    type = fields.Selection(related='rma_id.type')
    customer_to_supplier= fields.Boolean(
        'The customer will send to the supplier')
    supplier_to_customer = fields.Boolean(
        'The supplier will send to the customer')
    receipt_policy = fields.Selection([
        ('no', 'Not required'), ('ordered', 'Based on Ordered Quantities'),
        ('delivered', 'Based on Delivered Quantities')],
        required=True, string="Receipts Policy")
    delivery_policy = fields.Selection([
        ('no', 'Not required'), ('ordered', 'Based on Ordered Quantities'),
        ('received', 'Based on Received Quantities')], required=True,
        string="Delivery Policy")
    in_route_id = fields.Many2one(
        'stock.location.route', string='Inbound Route',
        required=True,
        domain=[('rma_selectable', '=', True)])
    out_route_id = fields.Many2one(
        'stock.location.route', string='Outbound Route',
        required=True,
        domain=[('rma_selectable', '=', True)])
    in_warehouse_id = fields.Many2one('stock.warehouse',
                                      string='Inbound Warehouse',
                                      required=True,
                                      default=_default_warehouse_id)
    out_warehouse_id = fields.Many2one('stock.warehouse',
                                       string='Outbound Warehouse',
                                       required=True,
                                       default=_default_warehouse_id)
    location_id = fields.Many2one(
        'stock.location', 'Send To This Company Location', required=True,
        default=_default_location_id)
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

    @api.model
    def _get_product_name(self):
        name = False
        if self.product_id:
            name = self.product_id.name
            if self.product_id.code:
                name = '[%s] %s' % (name, self.product_id.code)
        return name

    @api.onchange('product_id')
    def _onchange_product_id(self):
        result = {}
        if not self.product_id:
            return result
        self.name = self._get_product_name()
        self.product_qty = 1
        self.uom_id = self.product_id.uom_id.id
        self.price_unit = self.product_id.standard_price
        if self.product_id.categ_id.rma_operation_id:
            self.operation_id = self.product_id.rma_operation_id
        else:
            self.operation_id = self.product_id.categ_id.rma_operation_id
        return result

    @api.onchange('operation_id')
    def _onchange_operation_id(self):
        result = {}
        if not self.operation_id:
            return result
        self.receipt_policy = self.operation_id.receipt_policy
        self.delivery_policy = self.operation_id.delivery_policy
        self.in_warehouse_id = self.operation_id.in_warehouse_id
        self.out_warehouse_id = self.operation_id.out_warehouse_id
        self.location_id = self.operation_id.location_id or \
            self.in_warehouse_id.lot_rma_id
        self.customer_to_supplier = self.operation_id.customer_to_supplier
        self.supplier_to_customer = self.operation_id.supplier_to_customer
        self.in_route_id = self.operation_id.in_route_id
        self.out_route_id = self.operation_id.out_route_id
        return result

    @api.onchange('customer_to_supplier', 'type')
    def _onchange_receipt_policy(self):
        if self.type == 'supplier' and self.customer_to_supplier:
            self.receipt_policy = 'no'
        elif self.type == 'customer' and self.supplier_to_customer:
            self.delivery_policy = 'no'

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
