from odoo import models, fields, api, Command, _

class AccountAccount(models.Model):
    _inherit = 'account.account'

    report_type = fields.Selection([('iva','IVA'),('municipal','MUNICIPAL')],string="Tipo de reporte", default ="municipal")