"""
PAYROLL PDF SERVICE — Generador de documentos oficiales en PDF (Orden ESS/2098/2014, Finiquito y Despido).
"""

from pathlib import Path
from typing import Dict, Any
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from app.config import settings
from app.domain.services.payroll_engine import PayrollEngine

import io
import base64
from reportlab.lib.utils import ImageReader
from app.domain.services.document_customization_service import DocumentCustomizationService
from app.adapters.document_customization import SqliteDocumentCustomizationAdapter

DOCS_DIR = Path(__file__).resolve().parents[3] / "data" / "documentos_laborales"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

def _get_font_name(family: str, style: str = "Regular") -> str:
    """Resuelve el nombre de la tipografía estándar según ReportLab."""
    if family == "Times-Roman":
        if style in ("Bold", "bold"):
            return "Times-Bold"
        elif style in ("Italic", "italic", "Oblique", "oblique"):
            return "Times-Italic"
        elif style in ("BoldItalic", "BoldOblique"):
            return "Times-BoldItalic"
        return "Times-Roman"
    elif family == "Courier":
        if style in ("Bold", "bold"):
            return "Courier-Bold"
        elif style in ("Italic", "italic", "Oblique", "oblique"):
            return "Courier-Oblique"
        elif style in ("BoldItalic", "BoldOblique"):
            return "Courier-BoldOblique"
        return "Courier"
    else: # Helvetica por defecto
        if style in ("Bold", "bold"):
            return "Helvetica-Bold"
        elif style in ("Italic", "italic", "Oblique", "oblique"):
            return "Helvetica-Oblique"
        elif style in ("BoldItalic", "BoldOblique"):
            return "Helvetica-BoldOblique"
        return "Helvetica"

def _apply_pdf_customization(c, canvas_height: float = 841.89) -> dict:
    """
    Carga la personalización y dibuja el logo en el canvas.
    Retorna un diccionario con los colores y la tipografía a aplicar.
    """
    try:
        from app.adapters.memory.memory import tenant_context
        cid = tenant_context.get() or "default"
        service = DocumentCustomizationService(SqliteDocumentCustomizationAdapter())
        custom = service.get_customization(cid)
        
        # Dibujar logo si existe
        if custom.get("logo_base64"):
            try:
                logo_data = base64.b64decode(custom["logo_base64"])
                logo_img = ImageReader(io.BytesIO(logo_data))
                l_width = custom.get("logo_width", 110)
                l_height = l_width * 40.0 / 110.0
                # Dibujar logo arriba a la derecha con ancho dinámico
                c.drawImage(logo_img, 550 - l_width, canvas_height - l_height - 35, width=l_width, height=l_height, mask='auto')
            except Exception:
                pass
                
        return {
            "primary_rgb": service.hex_to_rgb(custom.get("primary_color")),
            "secondary_rgb": service.hex_to_rgb(custom.get("secondary_color")),
            "font_family": custom.get("font_family", "Helvetica"),
            "layout_template": custom.get("layout_template", "classic")
        }
    except Exception:
        return {
            "primary_rgb": (0.12, 0.23, 0.35),
            "secondary_rgb": (0.39, 0.45, 0.53),
            "font_family": "Helvetica",
            "layout_template": "classic"
        }



class PayrollPdfService:

    @classmethod
    def generate_payroll_pdf(cls, payroll: Dict[str, Any], employee: Dict[str, Any], output_path: str = None) -> str:
        """
        Genera el Recibo Individual de Salarios oficial conforme a la Orden ESS/2098/2014.
        """
        if not output_path:
            filename = f"Nomina_{payroll['employee_id']}_{payroll['year']}_{str(payroll['month']).zfill(2)}.pdf"
            output_path = str(DOCS_DIR / filename)

        c = canvas.Canvas(output_path, pagesize=A4)
        w, h = A4
        cust = _apply_pdf_customization(c, canvas_height=h)
        p_rgb = cust["primary_rgb"]
        s_rgb = cust["secondary_rgb"]
        font = cust["font_family"]
        template = cust["layout_template"]
        
        orig_setFont = c.setFont
        def custom_setFont(font_name, size, *args, **kwargs):
            if font_name.startswith("Helvetica"):
                style = font_name.replace("Helvetica", "").lstrip("-")
                resolved = _get_font_name(font, style or "Regular")
                orig_setFont(resolved, size, *args, **kwargs)
            else:
                orig_setFont(font_name, size, *args, **kwargs)
        c.setFont = custom_setFont
        
        # Aplicar colores corporativos al trazado de líneas y cajas
        c.setStrokeColorRGB(*s_rgb)


        # 1. Cabecera
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, h - 45, "RECIBO INDIVIDUAL DE JUSTIFICANTE DE PAGO DE SALARIOS")
        c.setFont("Helvetica", 8)
        c.drawString(40, h - 58, "Conforme a la Orden ESS/2098/2014 y Art. 29.1 del Estatuto de los Trabajadores")

        # 2. Datos Empresa y Trabajador
        c.rect(40, h - 130, w - 80, 65)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(50, h - 75, "EMPRESA (EMPLEADOR):")
        c.drawString(320, h - 75, "TRABAJADOR:")

        c.setFont("Helvetica", 9)
        c.drawString(50, h - 90, f"Nombre / Razón Social: {settings.ALFONSO_USER_NAME}")
        c.drawString(50, h - 105, f"NIF / CIF: {settings.ALFONSO_USER_NIF}")
        c.drawString(50, h - 120, "C.C.C.: 28/12345678901")

        c.drawString(320, h - 90, f"Nombre: {employee['full_name']}")
        c.drawString(320, h - 105, f"NIF/NIE: {employee['nif']}")
        c.drawString(320, h - 120, f"Nº Afiliación SS: {employee['nss']}  | Grupo: {employee.get('contribution_group', 1)}")

        # 3. Período de Liquidación
        c.setFont("Helvetica-Bold", 9)
        c.drawString(40, h - 145, f"PERÍODO DE LIQUIDACIÓN: Mes {payroll['month']}/{payroll['year']} (30 días)")
        c.line(40, h - 150, w - 40, h - 150)

        # 4. Devengos
        y = h - 170
        c.setFont("Helvetica-Bold", 10)
        c.drawString(40, y, "I. DEVENGOS (PERCEPCIONES SALARIALES)")
        c.drawString(480, y, "TOTALES")

        y -= 20
        c.setFont("Helvetica", 9)
        c.drawString(50, y, "1. Salario Base")
        c.drawString(480, y, f"{payroll['salary_base']:,.2f} €")

        if payroll.get("extra_pay_prorata", 0) > 0:
            y -= 15
            c.drawString(50, y, "2. Prorrata Pagas Extraordinarias")
            c.drawString(480, y, f"{payroll['extra_pay_prorata']:,.2f} €")

        y -= 20
        c.setFont("Helvetica-Bold", 9)
        c.drawString(50, y, "A. TOTAL DEVENGADO (SALARIO BRUTO)")
        c.drawString(480, y, f"{payroll['gross_total']:,.2f} €")

        # 5. Deducciones
        y -= 30
        c.setFont("Helvetica-Bold", 10)
        c.drawString(40, y, "II. DEDUCCIONES Y APORTACIONES DEL TRABAJADOR")
        c.drawString(480, y, "TOTALES")

        y -= 18
        c.setFont("Helvetica", 9)
        c.drawString(50, y, f"1. Contingencias Comunes ({PayrollEngine.WORKER_CC_RATE}%)")
        c.drawString(480, y, f"{payroll['ss_worker_cc']:,.2f} €")

        y -= 15
        c.drawString(50, y, f"2. Desempleo ({PayrollEngine.WORKER_UNEMPLOYMENT_RATE}%)")
        c.drawString(480, y, f"{payroll['ss_worker_unemployment']:,.2f} €")

        y -= 15
        c.drawString(50, y, f"3. Formación Profesional ({PayrollEngine.WORKER_FP_RATE}%)")
        c.drawString(480, y, f"{payroll['ss_worker_fp']:,.2f} €")

        y -= 15
        c.drawString(50, y, f"4. MEI - Equidad Intergeneracional ({PayrollEngine.WORKER_MEI_RATE}%)")
        c.drawString(480, y, f"{payroll['ss_worker_mei']:,.2f} €")

        y -= 18
        c.drawString(50, y, f"5. Retención I.R.P.F. ({payroll['irpf_rate']:.1f}%)")
        c.drawString(480, y, f"{payroll['irpf_amount']:,.2f} €")

        y -= 20
        c.setFont("Helvetica-Bold", 9)
        c.drawString(50, y, "B. TOTAL A DEDUCIR")
        total_ded = payroll['ss_worker_total'] + payroll['irpf_amount']
        c.drawString(480, y, f"{total_ded:,.2f} €")

        # 6. Líquido Total
        y -= 30
        c.rect(40, y - 10, w - 80, 25, fill=0)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y - 2, "LÍQUIDO TOTAL A PERCIBIR (NETO EN CUENTA):")
        c.drawString(480, y - 2, f"{payroll['net_salary']:,.2f} €")

        # 7. Cuadro Obligatorio de Aportaciones de la Empresa a la Seguridad Social (Orden ESS/2098/2014)
        y -= 50
        c.rect(40, y - 65, w - 80, 75)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(45, y - 5, "DETERMINACIÓN DE LAS BASES DE COTIZACIÓN Y APORTACIÓN EMPRESARIAL (OBLIGATORIO)")
        c.setFont("Helvetica", 7.5)
        c.drawString(45, y - 20, f"Base Contingencias Comunes (BCCC): {payroll['bccc']:,.2f} €  | Aportación Empresa ({PayrollEngine.EMPLOYER_CC_RATE}%): {payroll['ss_employer_cc']:,.2f} €")
        c.drawString(45, y - 32, f"Base Contingencias Prof. (BCCP): {payroll['bccp']:,.2f} €  | Desempleo ({PayrollEngine.EMPLOYER_UNEMPLOYMENT_RATE}%): {payroll['ss_employer_unemployment']:,.2f} €  | FOGASA: {payroll['ss_employer_fogasa']:,.2f} €")
        c.drawString(45, y - 44, f"Formación Profesional: {payroll['ss_employer_fp']:,.2f} €  | MEI Empresa: {payroll['ss_employer_mei']:,.2f} €  | AT/EP: {payroll['ss_employer_atep']:,.2f} €")
        c.setFont("Helvetica-Bold", 8)
        c.drawString(45, y - 58, f"TOTAL APORTACIÓN EMPRESARIAL A LA SEGURIDAD SOCIAL: {payroll['ss_employer_total']:,.2f} €")

        # Firmas
        c.setFont("Helvetica", 8)
        c.drawString(50, 45, "Firma del Empleador (Alfonso Autónomo SIF)")
        c.drawString(350, 45, "Firma / Recibí del Trabajador")

        c.save()
        return output_path

    @classmethod
    def generate_settlement_pdf(cls, settlement: Dict[str, Any], employee: Dict[str, Any], output_path: str = None) -> str:
        """
        Genera el Documento Oficial de Liquidación, Saldo y Finiquito.
        """
        if not output_path:
            filename = f"Finiquito_{settlement['employee_id']}_{settlement['termination_date'][:10]}.pdf"
            output_path = str(DOCS_DIR / filename)

        c = canvas.Canvas(output_path, pagesize=A4)
        w, h = A4
        cust = _apply_pdf_customization(c, canvas_height=h)
        p_rgb = cust["primary_rgb"]
        s_rgb = cust["secondary_rgb"]
        font = cust["font_family"]
        template = cust["layout_template"]
        
        orig_setFont = c.setFont
        def custom_setFont(font_name, size, *args, **kwargs):
            if font_name.startswith("Helvetica"):
                style = font_name.replace("Helvetica", "").lstrip("-")
                resolved = _get_font_name(font, style or "Regular")
                orig_setFont(resolved, size, *args, **kwargs)
            else:
                orig_setFont(font_name, size, *args, **kwargs)
        c.setFont = custom_setFont
        
        # Aplicar colores corporativos al trazado de líneas y cajas
        c.setStrokeColorRGB(*s_rgb)

        # Cabecera
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, h - 45, "DOCUMENTO DE LIQUIDACIÓN, SALDO Y FINIQUITO")
        c.setFont("Helvetica", 9)
        c.drawString(40, h - 60, f"Fecha de Extinción Contractual: {settlement['termination_date']}")

        # Datos Partes
        c.rect(40, h - 130, w - 80, 60)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(50, h - 80, "EMPLEADOR:")
        c.drawString(320, h - 80, "TRABAJADOR:")
        c.setFont("Helvetica", 9)
        c.drawString(50, h - 95, f"{settings.ALFONSO_USER_NAME} (NIF: {settings.ALFONSO_USER_NIF})")
        c.drawString(50, h - 110, f"Causa: {settlement['termination_type']}")
        c.drawString(320, h - 95, f"{employee['full_name']} (NIF: {employee['nif']})")
        c.drawString(320, h - 110, f"Antigüedad: {settlement['seniority_years']} años ({settlement['seniority_months']} meses)")

        # Desglose de Haberes
        y = h - 165
        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, y, "PROPUESTA Y DESGLOSE DE LIQUIDACIÓN")
        c.line(40, y - 5, w - 40, y - 5)

        y -= 25
        c.setFont("Helvetica", 9)
        c.drawString(50, y, f"1. Salarios pendientes del mes en curso ({settlement['worked_days_month']} días):")
        c.drawString(480, y, f"{settlement['worked_days_amount']:,.2f} €")

        y -= 20
        c.drawString(50, y, "2. Parte proporcional de pagas extraordinarias devengadas:")
        c.drawString(480, y, f"{settlement['extra_pays_pending']:,.2f} €")

        y -= 20
        c.drawString(50, y, f"3. Vacaciones devengadas y no disfrutadas ({settlement['vacation_pending_days']} días):")
        c.drawString(480, y, f"{settlement['vacation_pending_amount']:,.2f} €")

        y -= 20
        c.drawString(50, y, f"4. Indemnización por extinción contractual ({settlement['indemnity_days_total']} días):")
        c.drawString(480, y, f"{settlement['indemnity_amount']:,.2f} €")

        # Total Finiquito
        y -= 30
        c.rect(40, y - 10, w - 80, 25, fill=0)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y - 2, "TOTAL SALDO Y FINIQUITO A ABONAR:")
        c.drawString(480, y - 2, f"{settlement['total_settlement']:,.2f} €")

        # Cláusula de finiquito
        y -= 45
        c.setFont("Helvetica-Oblique", 8)
        text_clause = (
            "Con el percibo de la citada cantidad, el trabajador queda totalmente saldado y finiquitado por todos los conceptos "
            "salariales e indemnizatorios dimanantes de la relación laboral que unía a ambas partes, manifestando no tener nada más que pedir ni reclamar."
        )
        c.drawString(40, y, text_clause[:110])
        c.drawString(40, y - 12, text_clause[110:])

        # Firmas
        c.setFont("Helvetica", 8)
        c.drawString(50, 60, "Firma del Empleador")
        c.drawString(350, 60, "Firma del Trabajador (Conforme)")

        c.save()
        return output_path

    @classmethod
    def generate_dismissal_letter_pdf(cls, settlement: Dict[str, Any], employee: Dict[str, Any], motive: str = "Causas económicas y organizativas (Art. 52.c ET)", output_path: str = None) -> str:
        """
        Genera la Carta Formal de Comunicación de Despido Objetivo (Art. 53.1.a Estatuto de los Trabajadores).
        """
        if not output_path:
            filename = f"Carta_Despido_{settlement['employee_id']}_{settlement['termination_date'][:10]}.pdf"
            output_path = str(DOCS_DIR / filename)

        c = canvas.Canvas(output_path, pagesize=A4)
        w, h = A4
        cust = _apply_pdf_customization(c, canvas_height=h)
        p_rgb = cust["primary_rgb"]
        s_rgb = cust["secondary_rgb"]
        font = cust["font_family"]
        template = cust["layout_template"]
        
        orig_setFont = c.setFont
        def custom_setFont(font_name, size, *args, **kwargs):
            if font_name.startswith("Helvetica"):
                style = font_name.replace("Helvetica", "").lstrip("-")
                resolved = _get_font_name(font, style or "Regular")
                orig_setFont(resolved, size, *args, **kwargs)
            else:
                orig_setFont(font_name, size, *args, **kwargs)
        c.setFont = custom_setFont
        
        # Aplicar colores corporativos al trazado de líneas y cajas
        c.setStrokeColorRGB(*s_rgb)

        # Cabecera
        c.setFont("Helvetica-Bold", 13)
        c.drawString(40, h - 45, "COMUNICACIÓN DE EXTINCIÓN DE CONTRATO DE TRABAJO")
        c.setFont("Helvetica", 9)
        c.drawString(40, h - 60, "Por causas objetivas (Artículos 52 y 53 del Estatuto de los Trabajadores)")

        # Destinatario
        c.setFont("Helvetica", 9)
        c.drawString(40, h - 90, f"A la atención de: D./Dña. {employee['full_name']}")
        c.drawString(40, h - 105, f"NIF / NIE: {employee['nif']}")
        c.drawString(40, h - 120, f"Fecha de notificación: {settlement['termination_date']}")

        # Cuerpo de la carta
        c.setFont("Helvetica", 9)
        y = h - 150
        c.drawString(40, y, "Muy señor/a nuestro/a:")
        y -= 20
        c.drawString(40, y, f"Por medio de la presente, la dirección de la empresa le comunica formalmente la decisión de proceder a la")
        y -= 15
        c.drawString(40, y, f"extinción de su contrato de trabajo por causas objetivas, con fecha de efectos a partir de {settlement['termination_date']}.")

        y -= 25
        c.setFont("Helvetica-Bold", 9)
        c.drawString(40, y, "1. MOTIVACIÓN LEGAL Y FÁCTICA:")
        c.setFont("Helvetica", 9)
        y -= 15
        c.drawString(40, y, f"La presente extinción se fundamenta en: {motive}.")

        y -= 25
        c.setFont("Helvetica-Bold", 9)
        c.drawString(40, y, "2. PUESTA A DISPOSICIÓN DE LA INDEMNIZACIÓN LEGAL (Art. 53.1.b ET):")
        c.setFont("Helvetica", 9)
        y -= 15
        c.drawString(40, y, f"Simultáneamente a la entrega de esta comunicación, se pone a su disposición la indemnización legal correspondiente")
        y -= 15
        c.drawString(40, y, f"a razón de 20 días por año de servicio ({settlement['indemnity_days_total']} días), por un importe total de:")
        y -= 20
        c.setFont("Helvetica-Bold", 10)
        c.drawString(40, y, f"IMPORTE INDEMNIZACIÓN LEGAL: {settlement['indemnity_amount']:,.2f} € (Exenta de IRPF)")

        y -= 30
        c.setFont("Helvetica", 9)
        c.drawString(40, y, "Asimismo, se acompaña la liquidación de haberes y finiquito devengado hasta la fecha de extinción.")

        # Firmas
        c.drawString(50, 70, "Por la Empresa (Firma)")
        c.drawString(350, 70, "El Trabajador (Recibí y Fecha)")

        c.save()
        return output_path
