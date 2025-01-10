# -*- coding: utf-8 -*-

from odoo import models, fields, api, Command, _
import locale
from datetime import datetime, timedelta
import base64
from dateutil.relativedelta import relativedelta
import logging
_logger = logging.getLogger(__name__)
import io
import xlsxwriter

class ReportPerceptions(models.TransientModel):
    _name = 'account.tax_custom_report'
    
    perc_account = fields.Many2one('account.account', 
                                   string='Cuenta Percepción',
                                   domain="[('report_type','in',['municipal','iva'])]")

    report_type = fields.Selection(
        selection=[('iva', 'IVA'), ('municipal', 'MUNICIPAL')],
        string='Tipo de Reporte',
        related='perc_account.report_type',
        readonly=True,
    )
    
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
                    ('move_id.state', '=', 'posted'),
                ])
                _logger.warning(move_lines)
                record.perc_line_ids = [Command.clear(), Command.set(move_lines.ids)]
            else:
                 record.perc_line_ids = [Command.clear()]

    
    def export_txt(self):
        if self.report_type == 'iva':
            txt_content = self.format_line()
            txt_content = txt_content.replace('\n', '\r\n')
            # Codificar el contenido en base64
            file_content_base64 = base64.b64encode(txt_content.encode('utf-8')).decode('utf-8')
            # Crear un adjunto en Odoo
            attachment = self.env['ir.attachment'].create({
                'name': f"Percepciones_IVA_{self.get_month_name_or_date_range()}.txt",
                'type': 'binary',
                'datas': file_content_base64,
                'mimetype': 'text/plain',
            })
            return {
                'type': 'ir.actions.act_url',
                'url': '/web/content/%s?download=true' % attachment.id,
                'target': 'self',
            }
        else:
            txt_content = self.format_municipal()
            txt_content = txt_content.replace('\n', '\r\n')
            # Codificar el contenido en base64
            file_content_base64 = base64.b64encode(txt_content.encode('utf-8')).decode('utf-8')
            # Crear un adjunto en Odoo
            attachment = self.env['ir.attachment'].create({
                'name': f"Percepciones_IIBB_{self.get_month_name_or_date_range()}.txt",
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
                comprobante = self.obtenerComprobante(apunte, 2)
                
                # Formatear el CUIT
                cuit = str(apunte.partner_id.vat).zfill(11)
                formatted_cuit = f"{cuit[:2]}-{cuit[2:10]}-{cuit[10:]}"
                
                # Formatear la fecha
                formatted_date = apunte.date.strftime('%d/%m/%Y')
                
                # Formatear número de comprobante
                sequence_prefix = comprobante.sequence_prefix[-5:-1] if comprobante.sequence_prefix else "0000"
                sequence_number = str(comprobante.sequence_number).zfill(8)
                
                # Formatear monto
                monto = '{:.2f}'.format(record.montoRetenido(apunte)).replace('.', ',')
                formatted_monto = monto.zfill(16)
                
                # Crear la línea formateada
                formatted_line = (
                    f"493{formatted_cuit}{formatted_date}0000"
                    f"{sequence_prefix.zfill(4)}{sequence_number.zfill(8)}"
                    f"{formatted_monto}"
                )
                
                formatted_lines.append(formatted_line)
            return "\n".join(formatted_lines)

    def format_municipal(self):
        for record in self:
            formatted_lines = []
            for apunte in record.perc_line_ids:
                comprobante = self.obtenerComprobante(apunte, 2)
                
                # Formatear el CUIT
                cuit = str(apunte.partner_id.vat).zfill(11)
                formatted_cuit = f"{cuit[:2]}-{cuit[2:10]}-{cuit[10:]}"
    
                # Formatear la fecha
                formatted_date = apunte.date.strftime('%d/%m/%Y')
    
                doc_number = comprobante.l10n_latam_document_number if comprobante.l10n_latam_document_number else "0000-00000000"
            
                # Procesar el documento para eliminar solo el primer '0' del bloque inicial
                parts = doc_number.split('-')
                part1 = parts[0].lstrip('0').zfill(4)  # Asegurarse de que sean 4 dígitos después de eliminar el primer '0'
                part2 = parts[1].zfill(8)  # Asegurarse de que el segundo bloque tenga exactamente 8 dígitos
                
                doc_number_cleaned = part1 + part2

                sequence_prefix = comprobante.sequence_prefix[-5:-1] if comprobante.sequence_prefix else "0000"
                sequence_number = str(comprobante.sequence_number).zfill(8)
                formatted_comprobante = f"{sequence_prefix}-{sequence_number}"
                _logger.info(f"Comprobante formateado {formatted_comprobante}")
    
                # Formatear monto
                monto = '{:.2f}'.format(record.montoRetenido(apunte)).replace('.', ',')
                formatted_monto = monto.zfill(11)
    
                # Código prefijo fijo como 902
                code_prefix = "902"
    
                # Código de Tipo de Comprobante
                tax_code = comprobante.l10n_latam_document_type_id.doc_code_prefix[:2] if comprobante.l10n_latam_document_type_id and comprobante.l10n_latam_document_type_id.doc_code_prefix else "FA"
    
                # Crear la línea formateada
                formatted_line = (
                    f"{code_prefix}{formatted_cuit}{formatted_date}"
                    f"{doc_number_cleaned}{tax_code}{formatted_monto}"
                )
                
                formatted_lines.append(formatted_line)
            return "\n".join(formatted_lines)

    
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

    def export_reported_invoices_xlsx(self):
        for record in self:
            # Crear un archivo en memoria
            output = io.BytesIO()
    
            # Crear el archivo XLSX
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            worksheet = workbook.add_worksheet("Facturas Reportadas")
    
            # Formatos
            bold = workbook.add_format({'bold': True})
            currency = workbook.add_format({'num_format': '#,##0.00'})
    
            # Encabezados
            headers = ['Fecha', 'Número de Documento', 'Cliente', 'Monto Total', 'Monto Percepción']
            for col_num, header in enumerate(headers):
                worksheet.write(0, col_num, header, bold)
    
            # Ajustar el ancho de las columnas
            worksheet.set_column(0, 0, 15)  # Fecha
            worksheet.set_column(1, 1, 25)  # Número de Documento
            worksheet.set_column(2, 2, 30)  # Cliente
            worksheet.set_column(3, 3, 15)  # Monto Total
            worksheet.set_column(4, 4, 20)  # Monto Percepción
    
            # Obtener las líneas contables seleccionadas
            move_lines = record.perc_line_ids.mapped('move_id')
            if not move_lines:
                raise UserError(_("No se encontraron facturas reportadas."))
    
            # Escribir datos
            row = 1
            for move in move_lines:
                monto_percepcion = sum(
                    line.debit for line in move.line_ids.filtered(lambda l: l.account_id == record.perc_account)
                )
                worksheet.write(row, 0, move.invoice_date.strftime('%Y/%m/%d') if move.invoice_date else '')
                worksheet.write(row, 1, move.name or '')
                worksheet.write(row, 2, move.partner_id.name or '')
                worksheet.write(row, 3, move.amount_total, currency)
                worksheet.write(row, 4, monto_percepcion, currency)
                row += 1
    
            # Cerrar el archivo XLSX
            workbook.close()
            output.seek(0)
    
            # Convertir contenido a base64
            xlsx_content = base64.b64encode(output.read()).decode('utf-8')
            output.close()
    
            # Crear adjunto en Odoo
            attachment = self.env['ir.attachment'].create({
                'name': f"Facturas_Reportadas_{record.get_month_name_or_date_range()}.xlsx",
                'type': 'binary',
                'datas': xlsx_content,
                'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            })
    
            # Devolver el archivo como descarga
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'self',
            }