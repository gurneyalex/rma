# -*- coding: utf-8 -*-
# © 2017 Eficent Business and IT Consulting Services S.L.
# © 2015 Eezee-It, MONK Software, Vauxoo
# © 2013 Camptocamp
# © 2009-2013 Akretion,
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)
from openerp import models, fields, exceptions, api, _
import openerp.addons.decimal_precision as dp


class RmaRefund(models.TransientModel):
    _name = "rma.refund"

    @api.model
    def _get_reason(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', False)
        if active_ids:
            rma_lines = self.env['rma.order.line'].browse(active_ids[0])
            return rma_lines.rma_id.name
        return ''

    @api.returns('rma.order.line')
    def _prepare_item(self, line):
        values = {'product_id': line.product_id.id,
                  'name': line.name,
                  'product_qty': line.product_qty,
                  'uom_id': line.uom_id.id,
                  'qty_to_refund': line.qty_to_refund,
                  'line_id': line.id,
                  'wiz_id': self.env.context['active_id']}
        return values

    @api.model
    def default_get(self, fields):
        """Default values for wizard, if there is more than one supplier on
        lines the supplier field is empty otherwise is the unique line
        supplier.
        """
        res = super(RmaRefund, self).default_get(
            fields)
        rma_line_obj = self.env['rma.order.line']
        rma_line_ids = self.env.context['active_ids'] or []
        active_model = self.env.context['active_model']

        if not rma_line_ids:
            return res
        assert active_model == 'rma.order.line', \
            'Bad context propagation'

        items = []
        lines = rma_line_obj.browse(rma_line_ids)
        for line in lines:
            items.append([0, 0, self._prepare_item(line)])
        res['item_ids'] = items
        return res

    date_invoice = fields.Date(string='Refund Date',
                               default=fields.Date.context_today,
                               required=True)
    date = fields.Date(string='Accounting Date')
    description = fields.Char(string='Reason', required=True,
                              default=_get_reason)
    item_ids = fields.One2many(
        'rma.refund.item',
        'wiz_id', string='Items')

    @api.multi
    def compute_refund(self):
        for wizard in self:
            values = self._prepare_refund(wizard, self.item_ids[0].rma_id)
            new_refund = self.env['account.invoice'].create(values)
            for item in self.item_ids:
                line = item.line_id
                refund_line_values = self.prepare_refund_line(line, new_refund)
                self.env['account.invoice.line'].create(
                    refund_line_values)
            # Put the reason in the chatter
            subject = _("Invoice refund")
            body = self.item_ids[0].rma_id.name
            new_refund.message_post(body=body, subject=subject)
            return new_refund

    @api.multi
    def invoice_refund(self):
        rma_line_ids = self.env['rma.order.line'].browse(
            self.env.context['active_ids'])
        for line in rma_line_ids:
            if line.operation_id.refund_policy == 'no':
                raise exceptions.Warning(
                    _('The operation is not refund for at least one line'))
            if line.state != 'approved':
                raise exceptions.Warning(
                    _('RMA %s is not approved') %
                    line.rma_id.name)
        new_invoice = self.compute_refund()
        action = 'action_invoice_tree1' if (
            new_invoice.type in ['out_refund', 'out_invoice']) \
            else 'action_invoice_tree2'
        result = self.env.ref('account.%s' % action).read()[0]
        invoice_domain = eval(result['domain'])
        invoice_domain.append(('id', '=', new_invoice.id))
        result['domain'] = invoice_domain
        return result

    # @api.model
    # def _get_invoice_line(self, line):
    #     if line.invoice_line_id and line.invoice_line_id.id:
    #         return line.invoice_line_id
    #     return False

    # @api.model
    # def _get_invoice(self, order):
    #     invoices = ""
    #     invoice_list = []
    #     for line in order.rma_line_ids:
    #         invoice_list.append(line.invoice_id.id)
    #     invoice_ids = list(set(invoice_list))
    #     for inv in invoice_ids:
    #         invoices += inv.number
    #     return invoices

    @api.model
    def prepare_refund_line(self, item, refund):
        values = {
            'name': item.rma_id.name,
            'origin': item.rma_id.name,
            'account_id': refund.account_id.id,
            'price_unit': item.price_unit,
            'uom_id': item.uom_id.id,
            'product_id': item.product_id.id,
            'rma_line_id': item.id,
            'quantity': item.qty_to_refund,
            'invoice_id': refund.id
        }
        return values

    @api.model
    def _prepare_refund(self, wizard, order):
        # origin_invoices = self._get_invoice(order)
        values = {
            'name': order.name,
            'origin': order.name,
            'reference': False,
            'account_id': order.partner_id.property_account_receivable_id.id,
            'partner_id': order.partner_id.id,
            'currency_id': order.partner_id.company_id.currency_id.id,
            'payment_term_id': False,
            'fiscal_position_id':
                order.partner_id.property_account_position_id.id,
        }
        team_ids = self.env['crm.team'].search(
            ['|', ('user_id', '=', self.env.uid),
             ('member_ids', '=', self.env.uid)], limit=1)
        team_id = team_ids[0] if team_ids else False
        if team_id:
            values['team_id'] = team_id.id
        if len(order.delivery_address_id):
            values['partner_id'] = order.invoice_address_id.id
        else:
            values['partner_id'] = order.partner_id.id
        if order.type == 'customer':
            values['type'] = 'out_refund'
        else:
            values['type'] = 'in_refund'
        values['state'] = 'draft'
        values['number'] = False
        values['date'] = wizard.date_invoice
        values['date_invoice'] = wizard.date or wizard.date_invoice
        return values


class RmaRefundItem(models.TransientModel):
    _name = "rma.refund.item"
    _description = "RMA Lines to refund"

    wiz_id = fields.Many2one(
        'rma.refund',
        string='Wizard', required=True)
    line_id = fields.Many2one('rma.order.line',
                              string='RMA order Line',
                              required=True,
                              readonly=True,
                              ondelete='cascade')
    rma_id = fields.Many2one('rma.order',
                             related='line_id.rma_id',
                             string='RMA',
                             readonly=True)
    product_id = fields.Many2one('product.product', string='Product',
                                 readonly=True)
    name = fields.Char(string='Description', required=True)
    product_qty = fields.Float(
        string='Quantity Ordered', copy=False,
        digits=dp.get_precision('Product Unit of Measure'),
        readonly=True)
    qty_to_refund = fields.Float(
        string='Quantity To Refund',
        digits=dp.get_precision('Product Unit of Measure'))
    uom_id = fields.Many2one('product.uom', string='Unit of Measure',
                             readonly=True)
