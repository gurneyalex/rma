# -*- coding: utf-8 -*-
# © 2017 Eficent Business and IT Consulting Services S.L.
# © 2015 Eezee-It, MONK Software, Vauxoo
# © 2013 Camptocamp
# © 2009-2013 Akretion,
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

from openerp import api, models, fields


class RmaMakePicking(models.TransientModel):
    _inherit = 'rma_make_picking.wizard'
    _description = 'Wizard to create pickings from rma lines'

    @api.model
    def _get_address(self, line, picking_type, location):
        delivery_address = super(RmaMakePicking, self)._get_address(
            line, picking_type, location)
        if (location != line.rma_id.warehouse_id.lot_rma_id) \
                and not (line.is_dropship and picking_type == 'outgoing') \
                    and not line.rma_id.delivery_address_id:
            seller = line.product_id.seller_ids.filtered(
                lambda p: p.name == line.invoice_line_id.invoice_id.
                    partner_id)
            partner = seller.warranty_return_address
            delivery_address = partner.id
        return delivery_address
