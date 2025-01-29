# -*- coding: utf-8 -*-
{
    'name': "tax_custom_reports",

    'summary': """
        Permite exportar reporte txt con formato de percepciones """,

    'description': """
        ermite exportar reporte txt con formato de percepciones
    """,

    'author': "OutsourceArg",
    'website': "http://www.outsourcearg.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '1.0',

    # any module necessary for this one to work correctly
    'depends': ['account'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/tax_custom_report_views.xml',
        'views/account_tag.xml',
    ],

}