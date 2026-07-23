"""Generador de PDF de la consulta clínica.

Usa EXCLUSIVAMENTE reportlab.platypus (flujo de contenido con Frames) en
lugar de coordenadas fijas (canvas.drawString). Esto permite que el texto
largo del SOAPE fluya y salte de página automáticamente sin cortarse.
"""

from __future__ import annotations

from datetime import date, datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Paleta de diseño (coherente con el frontend: azul/blanco, gris claro)
PRIMARY = colors.HexColor("#1d4ed8")   # Azul principal
DARK = colors.HexColor("#1e293b")      # Texto oscuro
MUTED = colors.HexColor("#64748b")     # Texto secundario
LIGHT_GRAY = colors.HexColor("#f1f5f9")  # Fondo de tablas
BORDER = colors.HexColor("#e2e8f0")    # Bordes suaves


def _calculate_age(date_of_birth) -> str:
    """Edad en años a partir de la fecha de nacimiento."""
    if not date_of_birth:
        return "—"
    if isinstance(date_of_birth, datetime):
        date_of_birth = date_of_birth.date()
    today = date.today()
    years = (
        today.year
        - date_of_birth.year
        - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))
    )
    return f"{years} años"


def _format_date(value) -> str:
    if not value:
        return "—"
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    return str(value)


def _build_styles() -> dict:
    """Estilos de párrafo reutilizables."""
    base = getSampleStyleSheet()
    styles: dict = {}

    styles["title"] = ParagraphStyle(
        "AuraTitle",
        parent=base["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        textColor=PRIMARY,
        spaceAfter=0,
        leading=24,
    )
    styles["subtitle"] = ParagraphStyle(
        "AuraSubtitle",
        parent=base["Normal"],
        fontSize=9,
        textColor=MUTED,
        leading=12,
    )
    styles["doctor"] = ParagraphStyle(
        "AuraDoctor",
        parent=base["Normal"],
        fontSize=9,
        textColor=DARK,
        alignment=TA_RIGHT,
        leading=13,
    )
    styles["section"] = ParagraphStyle(
        "AuraSection",
        parent=base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=PRIMARY,
        spaceBefore=6,
        spaceAfter=4,
        leading=15,
    )
    styles["field_title"] = ParagraphStyle(
        "AuraFieldTitle",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=DARK,
        spaceAfter=2,
        leading=13,
    )
    styles["body"] = ParagraphStyle(
        "AuraBody",
        parent=base["Normal"],
        fontSize=10,
        textColor=DARK,
        leading=14,
        spaceAfter=6,
    )
    styles["cell"] = ParagraphStyle(
        "AuraCell",
        parent=base["Normal"],
        fontSize=9,
        textColor=DARK,
        leading=12,
    )
    styles["cell_head"] = ParagraphStyle(
        "AuraCellHead",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=colors.white,
        leading=12,
    )
    styles["signature"] = ParagraphStyle(
        "AuraSignature",
        parent=base["Normal"],
        fontSize=10,
        textColor=DARK,
        alignment=TA_CENTER,
        leading=14,
    )
    return styles


def _header(patient, doctor, styles) -> Table:
    """Encabezado: título a la izquierda y datos del doctor a la derecha."""
    title_block = [
        Paragraph("Aura Clinical Copilot", styles["title"]),
        Paragraph("Reporte de consulta clínica", styles["subtitle"]),
    ]

    if doctor is not None:
        doctor_lines = [
            f"<b>{doctor.full_name or '—'}</b>",
            doctor.specialty or "",
            f"Cédula: {doctor.license_number}" if doctor.license_number else "",
        ]
    else:
        doctor_lines = ["<b>Médico no asignado</b>"]
    doctor_html = "<br/>".join(line for line in doctor_lines if line)
    doctor_block = [Paragraph(doctor_html, styles["doctor"])]

    header = Table(
        [[title_block, doctor_block]],
        colWidths=[100 * mm, 70 * mm],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LINEBELOW", (0, 0), (-1, -1), 1.2, PRIMARY),
            ]
        )
    )
    return header


def _patient_table(consultation, patient, styles) -> Table:
    """Tabla estilizada (fondo gris claro) con los datos del paciente."""
    nombre = "—"
    sexo = "—"
    edad = "—"
    if patient is not None:
        nombre = f"{patient.first_name or ''} {patient.last_name or ''}".strip() or "—"
        sexo = patient.gender or "—"
        edad = _calculate_age(patient.date_of_birth)

    folio = getattr(consultation, "folio", None) or "—"
    fecha = _format_date(getattr(consultation, "date", None))

    def _pair(label, value):
        return Paragraph(f"<b>{label}:</b> {value}", styles["cell"])

    data = [
        [_pair("Paciente", nombre), _pair("Edad", edad), _pair("Sexo", sexo)],
        [_pair("Folio", folio), _pair("Fecha", fecha), Paragraph("", styles["cell"])],
    ]

    table = Table(data, colWidths=[80 * mm, 45 * mm, 45 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GRAY),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("SPAN", (1, 1), (2, 1)),
            ]
        )
    )
    return table


def _clinical_section(title, text, styles) -> KeepTogether:
    """Bloque de cuerpo clínico. KeepTogether evita títulos huérfanos."""
    body = (text or "").strip() or "Sin información."
    return KeepTogether(
        [
            Paragraph(title, styles["field_title"]),
            Paragraph(body.replace("\n", "<br/>"), styles["body"]),
        ]
    )


def _prescription_table(prescriptions, styles) -> Table:
    """Tabla de receta con encabezados."""
    header_row = [
        Paragraph("Medicamento", styles["cell_head"]),
        Paragraph("Dosis", styles["cell_head"]),
        Paragraph("Frecuencia", styles["cell_head"]),
        Paragraph("Duración", styles["cell_head"]),
    ]
    rows = [header_row]
    for p in prescriptions or []:
        rows.append(
            [
                Paragraph(p.medication or "—", styles["cell"]),
                Paragraph(p.dose or "—", styles["cell"]),
                Paragraph(p.frequency or "—", styles["cell"]),
                Paragraph(p.duration or "—", styles["cell"]),
            ]
        )

    table = Table(
        rows,
        colWidths=[65 * mm, 35 * mm, 40 * mm, 30 * mm],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def generate_consultation_pdf(
    consultation,
    patient,
    doctor,
    note,
    prescriptions,
    diagnostics,
) -> BytesIO:
    """Genera el PDF de la consulta y devuelve un buffer de bytes en memoria.

    Todo el contenido se agrega a una lista de "flowables" que
    SimpleDocTemplate pagina automáticamente.
    """
    styles = _build_styles()
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Consulta {getattr(consultation, 'folio', '') or ''}".strip(),
    )

    story: list = []

    # 1. Encabezado (título + doctor)
    story.append(_header(patient, doctor, styles))
    story.append(Spacer(1, 10))

    # 2. Datos del paciente
    story.append(_patient_table(consultation, patient, styles))
    story.append(Spacer(1, 12))

    # 3. Cuerpo clínico (SOAPE). Los párrafos largos saltan de página solos.
    story.append(Paragraph("Nota clínica (SOAPE)", styles["section"]))
    if note is not None:
        story.append(_clinical_section("SUBJETIVO", note.subjective, styles))
        story.append(_clinical_section("OBJETIVO", note.objective, styles))
        story.append(_clinical_section("ANÁLISIS", note.analysis, styles))
        story.append(_clinical_section("PLAN", note.plan, styles))
    else:
        story.append(Paragraph("Sin nota clínica registrada.", styles["body"]))
    story.append(Spacer(1, 8))

    # 4. Diagnósticos (código CIE-11 + descripción + probabilidad)
    story.append(Paragraph("Diagnósticos (CIE-11)", styles["section"]))
    dx_list = list(diagnostics or [])
    if dx_list:
        for dx in dx_list:
            codigo = (getattr(dx, "codigo", None) or "").strip() or "[Sin Código]"
            desc = (getattr(dx, "description", None) or "").strip() or "—"
            prob = (getattr(dx, "probabilidad", None) or "").strip()
            prefix = f"<b>[{codigo}]</b> "
            suffix = f" <font color='#64748b'>({prob})</font>" if prob else ""
            story.append(Paragraph(f"{prefix}{desc}{suffix}", styles["body"]))
    else:
        story.append(Paragraph("Sin diagnósticos sugeridos.", styles["body"]))
    story.append(Spacer(1, 8))

    # 5. Receta
    story.append(Paragraph("Receta", styles["section"]))
    if prescriptions:
        story.append(_prescription_table(prescriptions, styles))
    else:
        story.append(Paragraph("Sin medicamentos prescritos.", styles["body"]))
    story.append(Spacer(1, 26))

    # 6. Firma (bloque centrado). KeepTogether evita que se separe la línea.
    signature_line = Table(
        [[""]],
        colWidths=[80 * mm],
        style=TableStyle([("LINEABOVE", (0, 0), (-1, -1), 0.8, DARK)]),
    )
    signature_line.hAlign = "CENTER"
    signature = KeepTogether(
        [
            signature_line,
            Spacer(1, 4),
            Paragraph("Firma del Médico Titular", styles["signature"]),
            Paragraph(
                doctor.full_name if doctor is not None else "",
                styles["signature"],
            ),
        ]
    )
    story.append(signature)

    doc.build(story)
    buffer.seek(0)
    return buffer
