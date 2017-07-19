# -*- coding: utf-8 -*-
# Copyright 2016 Eficent Business and IT Consulting Services S.L.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl-3.0).

import openerp.addons.decimal_precision as dp
from openerp import api, fields, models, _
from openerp.exceptions import UserError


class PurchaseRequestLineMakePurchaseOrder(models.TransientModel):
    _name = "qc.issue.make.rma"

    rma_id = fields.Many2one(
        comodel_name="rma.order", string="Existing RMA")
    rma_type = fields.Selection(
        [('customer', 'Customer'), ('supplier', 'Supplier')],
        string="RMA Type")
    partner_id = fields.Many2one(
        comodel_name="res.partner", string="Partner")
    # TODO: restrict partner_id domain?
    qc_issue_id = fields.Many2one(
        comodel_name="qc.issue", string="Quality Control Issue", required=True,
        readonly=True)
    new_or_update = fields.Selection(
        [('new', 'Create a new RMA'), ('update', 'Add to existing RMA')],
        string="Action", required=True, default='new')

    @api.model
    def _prepare_rma_order_context(self):
        """**Technical note:** This context has to be passed to the lines in
        the rma.view_rma_form and rma.view_rma_supplier_form view. (See
        views/rma_order_view.xml in this same module."""
        return {
            'default_type': self.rma_type,
            'default_partner_id': self.partner_id.id,
            'default_product_id': self.qc_issue_id.product_id.id,
            'default_origin': self.qc_issue_id.name,
            'default_product_qty': self.qc_issue_id.product_qty,
            'default_location_id': self.qc_issue_id.location_id.id,
            'default_qc_issue_id': self.qc_issue_id.id,
        }

    @api.multi
    def create_new_rma(self):
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Create RMA'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'rma.order',
            'context': self._prepare_rma_order_context(),
        }
        return action

    @api.multi
    def update_existing_rma(self):
        context = self._prepare_rma_order_context()
        context.pop('default_type', None)
        context.update({'default_rma_id': self.rma_id.id})
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Create RMA line'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'rma.order.line',
            'context': context,
        }
        return action
