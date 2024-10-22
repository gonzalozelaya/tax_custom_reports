# -*- coding: utf-8 -*-

from odoo import models, fields, api
import locale
from datetime import datetime, date, timedelta
import base64
from dateutil.relativedelta import relativedelta


class ReportPerceptions(models.Model):
    _name = 'account.tax_custom_report'
    
    perc_account = fields.Many2one('account.account', string='Cuenta Contable')
    
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
        compute='_compute_apunte_ids')
    
    @api.depends('date_end','date_start','perc_account')
    def _compute_apunte_ids(self):
        for record in self:
            if record.date_start and record.date_end and record.perc_account:
                # Búsqueda de los apuntes contables entre las fechas y con la cuenta seleccionada
                move_lines = self.env['account.move.line'].search([
                    ('date', '>=', record.date_start),
                    ('date', '<=', record.date_end),
                    ('account_id', '=', record.perc_account.id),
                ])
                # Asignar los apuntes contables encontrados
                record.perc_line_ids = move_lines
            else:
                record.perc_line_ids = False
        
    
    def export_txt(self):
        txt_content = self.format_line(self.record)
        txt_content = txt_content.replace('\n', '\r\n')
        # Codificar el contenido en base64
        file_content_base64 = base64.b64encode(txt_content.encode('utf-8')).decode('utf-8')
        # Crear un adjunto en Odoo
        attachment = self.record.env['ir.attachment'].create({
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
    
    def format_line(self, record):
        formatted_lines = []
        for apunte in record.apunte_ids:
            tipo_operacion = self.tipoOperacion(apunte)
            comprobante = self.obtenerComprobante(apunte,tipo_operacion)
            formatted_line = str(tipo_operacion)                                                #Tipo de Operación 1:Retencion/2:Percepción
            formatted_line += '029'                                             #Código de norma
            formatted_line += str(apunte.date.strftime('%d/%m/%Y')).rjust(10)   #Fecha de Retención/Percepción
            formatted_line += str(self.tipoComprobanteOrigen(tipo_operacion,apunte)).rjust(2,'0') #Tipo comprobante de Origen
            formatted_line += str(self.tipoFactura(apunte,tipo_operacion)).rjust(1)                                               #Tipo de operación
            formatted_line += self.AgipSequenceNumber(comprobante,tipo_operacion)
            #formatted_line += str(comprobante.sequence_number).rjust(16,'0')    #Número de comprobante
            formatted_line += str(comprobante.date.strftime('%d/%m/%Y')).rjust(10,'0')           #Fecha de comprobante
            formatted_line += '{:.2f}'.format(self.montoComprobante(comprobante,tipo_operacion)).replace('.', ',').rjust(16, '0')      #Monto de comprobante
            formatted_line += str(self.buscarNroCertificado(comprobante,record.tax_group_id_ret_agip,tipo_operacion)).split('-')[-1].ljust(16,' ')     #Nro de certificado propio
            formatted_line += str(self.tipodeIdentificacion(apunte.partner_id))   #Tipo de identificacion 1:CDI/2:CUIL/3:CUIT
            formatted_line += str(self.nrodeIdentificacion(apunte.partner_id)).rjust(11,'0')    #Nro de identificacion
            formatted_line += str(self.situacionIb(apunte.partner_id))         #Situacion IB
            formatted_line += str(self.nroIb(apunte.partner_id)).rjust(11,'0')  #Nro IB
            formatted_line += str(self.situacionIva(apunte.partner_id))        #Situacion IVA
            formatted_line += (str(self.razonSocial(apunte.partner_id))[:30] if len(str(self.razonSocial(apunte.partner_id))) > 30 else str(self.razonSocial(apunte.partner_id))).ljust(30, ' ') #Razon social
            formatted_line += '{:.2f}'.format(self.importeOtrosConceptos(apunte,tipo_operacion,comprobante,self.record.tax_group_id_ret_agip)).replace('.', ',').rjust(16,'0') #Importe otros conceptos 
            formatted_line += '{:.2f}'.format(self.ImporteIva(apunte,comprobante,tipo_operacion,self.record.tax_group_id_ret_agip)).replace('.', ',').rjust(16,'0') #Importe IVA 
            formatted_line += '{:.2f}'.format(self.montoSujetoARetencion(comprobante,self.record.tax_group_id_ret_agip,tipo_operacion)).replace('.', ',').rjust(16, '0') #Monto sujeto a retención (Neto) 
            formatted_line += '{:.2f}'.format(self.porcentajeAlicuota(comprobante,self.record.tax_group_id_ret_agip,self.record.tax_group_id_perc_agip,tipo_operacion)).replace('.', ',').rjust(5, '0') #Alicuota
            formatted_line += '{:.2f}'.format(self.montoRetenido(apunte,comprobante,self.record.tax_group_id_ret_agip,tipo_operacion)).replace('.', ',').rjust(16, '0')
            formatted_line += '{:.2f}'.format(self.montoRetenido(apunte,comprobante,self.record.tax_group_id_ret_agip,tipo_operacion)).replace('.', ',').rjust(16, '0')
             
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