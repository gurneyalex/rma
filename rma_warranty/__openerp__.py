# -*- coding: utf-8 -*-
# © 2017 Eficent Business and IT Consulting Services S.L.
# © 2015 Eezee-It, MONK Software, Vauxoo
# © 2013 Camptocamp
# © 2009-2013 Akretion,
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)
{
    'name': 'RMA Warranty',
    'version': '9.0.1.0.0',
    'category': 'RMA',
    'summary': """
    Introduces de warranty to the RMA:
    The warranty can be set up in the company or in the product.
    It uses as reference the invoice date. Set the number of warranty months
    to zero and the warranty will be ignored

""",
    'author': 'Eficent',
    'website': 'http://www.github.com/OCA/rma',
    'depends': ['rma', 'product_warranty'],
    'data': ['views/rma_order_view.xml',
             'views/rma_order_line_view.xml'],
    'installable': True,
    'auto_install': False,
}
