# -*- coding: utf-8 -*-

from odoo import models, fields, api, Command, _
import locale
from datetime import datetime, timedelta
import base64
from dateutil.relativedelta import relativedelta
import logging
_logger = logging.getLogger(__name__)
class ReportPerceptions(models.TransientModel):
    _name = 'account.tax_custom_report'
    
    perc_account = fields.Many2one('account.account', string='Cuenta Percepción')
    
    date_start = fields.Date(
        string='Fecha Inicio', 
        required=True,
        default=lambda self: fields.Date.to_string(
            datetime.now().replace(day=1) - relativedelta(months=1)
        )
    )
    
    date_end = fields.Date(
        string='Fecha Fin', 
        required=True,
        default=lambda self: fields.Date.to_string(
            datetime.now().replace(day=1) - timedelta(days=1)
        )
    )
    
    perc_line_ids = fields.Many2many(
        comodel_name='account.move.line',
        relation='account_tax_csutom_report_line_rel',
        column1='account_tax_custom_id',
        column2='move_line_id',
        string='Apuntes Contables',
        compute='_compute_perc_line_ids')
    
    @api.depends('date_end','date_start','perc_account')
    def _compute_perc_line_ids(self):
        for record in self:
            _logger.warning('computing')
            if record.date_start and record.date_end and record.perc_account:
                # Búsqueda de los apuntes contables entre las fechas y con la cuenta seleccionada
                move_lines = self.env['account.move.line'].search([
                    ('date', '>=', record.date_start),
                    ('date', '<=', record.date_end),
                    ('account_id', '=', record.perc_account.id),
                ])
                _logger.warning(move_lines)
                record.perc_line_ids = [Command.clear(), Command.set(move_lines.ids)]
            else:
                 record.perc_line_ids = [Command.clear()]

    
    def export_txt(self):
        txt_content = self.format_line()
        txt_content = txt_content.replace('\n', '\r\n')
        # Codificar el contenido en base64
        file_content_base64 = base64.b64encode(txt_content.encode('utf-8')).decode('utf-8')
        # Crear un adjunto en Odoo
        attachment = self.env['ir.attachment'].create({
            'name': f"Percepciones_{self.get_month_name_or_date_range()}.txt",
            'type': 'binary',
            'datas': file_content_base64,
            'mimetype': 'text/plain',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }
    
    def format_line(self):
        for record in self:
            formatted_lines = []
            for apunte in record.perc_line_ids:
                comprobante = self.obtenerComprobante(apunte,2)
                formatted_line = '493'                                          #Código de norma
                formatted_line += str(apunte.partner_id.vat).rjust(11,'0')
                formatted_line += str(apunte.date.strftime('%d/%m/%Y')).rjust(10)   #Fecha de Retención/Percepción
                formatted_line += '    '
                formatted_line += str(comprobante.sequence_prefix[-5:-1])
                formatted_line += str(comprobante.sequence_number).rjust(8,'0')
                formatted_line += '{:.2f}'.format(record.montoRetenido(apunte)).replace('.', ',').rjust(16, ' ')
                 
                formatted_lines.append(formatted_line)
            formatted_lines_reversed = list(reversed(formatted_lines))
            formatted_lines.append('')
            return "\n".join(formatted_lines_reversed)

    
    def get_month_name_or_date_range(self):
        self.ensure_one()
        if not self.date_start or not self.date_end:
            return ''

        # Convertir a objetos datetime para comparar
        start_date = fields.Date.from_string(self.date_start)
        end_date = fields.Date.from_string(self.date_end)

        # Guardar la localización actual
        current_locale = locale.getlocale(locale.LC_TIME)
        try:
            # Cambiar temporalmente la localización a español
            locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')  # Ajusta según la localización disponible en tu servidor

            # Comparar si están en el mismo mes y año
            if start_date.month == end_date.month and start_date.year == end_date.year:
                # Devolver el nombre del mes en español
                result = start_date.strftime('%B %Y').capitalize()  # Ejemplo: 'Marzo 2024'
            else:
                # Devolver el rango de fechas en español
                result = f"{start_date.strftime('%d %b %Y')} - {end_date.strftime('%d %b %Y')}"
        finally:
            # Restaurar la localización original
            locale.setlocale(locale.LC_TIME, current_locale)

        return result

    def obtenerComprobante(self,apunte,tipo_operacion):
        if tipo_operacion == 1:
            return apunte.move_id.payment_id
        else:
            return apunte.move_id

    def montoRetenido(self,apunte):
            if apunte.credit > 0:
                return apunte.credit
            elif apunte.debit > 0:
                return apunte.debit