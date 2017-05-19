# -*- coding: utf-8 -*-
# © 2017 Eficent Business and IT Consulting Services S.L.
# © 2015 Eezee-It, MONK Software, Vauxoo
# © 2013 Camptocamp
# © 2009-2013 Akretion,
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)
from . import models

from openerp import SUPERUSER_ID
from openerp.api import Environment

def post_init_hook(cr, registry):
    env = Environment(cr, SUPERUSER_ID, {})
    locations = env['stock.location'].search([])
    for location in locations:
        warehouse = env['stock.location'].get_warehouse(location)
        if warehouse:
            location.write({'warehouse_id': warehouse})
