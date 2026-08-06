"""Generadores de PDF clínicos (ReportLab platypus).

Dos salidas independientes por consulta:
- Nota clínica (expediente interno: SOAPE + CIE-11).
- Receta + resumen del paciente (para paciente / farmacia).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.db.models import MEXICO_TZ
from app.modules.clinical_ai.patient_summary import (
    coerce_patient_summary,
    summary_has_content,
)

# Isotipo Aura (PNG generado desde el SVG del frontend)
_LOGO_PATH = Path(__file__).resolve().parents[2] / "assets" / "logo.png"

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
    """Solo fecha (dd/mm/yyyy) en America/Mexico_City — sin hora."""
    if not value:
        return "—"
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(MEXICO_TZ)
        return dt.strftime("%d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
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


def _brand_block(styles, subtitle: str) -> Table:
    """Logo + nombre del producto para el encabezado del PDF."""
    title_col = [
        Paragraph("Aura Clinical Copilot", styles["title"]),
        Paragraph(subtitle, styles["subtitle"]),
    ]

    if _LOGO_PATH.is_file():
        logo = Image(str(_LOGO_PATH), width=12 * mm, height=12.6 * mm)
        brand = Table(
            [[logo, title_col]],
            colWidths=[14 * mm, 86 * mm],
        )
        brand.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (0, 0), 3),
                    ("RIGHTPADDING", (1, 0), (1, 0), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("ALIGN", (1, 0), (1, 0), "LEFT"),
                ]
            )
        )
        return brand

    return Table([[title_col]], colWidths=[100 * mm])


def _doctor_lines_compact(doctor) -> list[str]:
    """Líneas breves del médico (nota clínica)."""
    if doctor is None:
        return ["<b>Médico no asignado</b>"]
    lines = [
        f"<b>{doctor.full_name or '—'}</b>",
        doctor.specialty or "",
        f"Cédula: {doctor.license_number}" if doctor.license_number else "",
    ]
    return [line for line in lines if line]


def _doctor_lines_full(doctor) -> list[str]:
    """Líneas ampliadas del médico (receta)."""
    if doctor is None:
        return ["<b>Médico no asignado</b>"]
    lines = [
        f"<b>{doctor.full_name or '—'}</b>",
        doctor.specialty or "",
        f"Cédula: {doctor.license_number}" if doctor.license_number else "",
        doctor.university or "",
        doctor.clinic_address or "",
    ]
    contact_bits = []
    if doctor.phone:
        contact_bits.append(doctor.phone)
    if doctor.email:
        contact_bits.append(doctor.email)
    if contact_bits:
        lines.append(" · ".join(contact_bits))
    return [line for line in lines if line]


def _header(doctor, styles, *, subtitle: str, full_doctor: bool = False) -> Table:
    """Encabezado: logo + título a la izquierda y datos del doctor a la derecha."""
    brand_block = _brand_block(styles, subtitle)
    doctor_lines = (
        _doctor_lines_full(doctor) if full_doctor else _doctor_lines_compact(doctor)
    )
    doctor_html = "<br/>".join(doctor_lines)
    doctor_block = [Paragraph(doctor_html, styles["doctor"])]

    header = Table(
        [[brand_block, doctor_block]],
        colWidths=[100 * mm, 70 * mm],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 0), (-1, -1), 1.2, PRIMARY),
            ]
        )
    )
    return header


def _patient_table(consultation, patient, styles, *, allergies_text: str | None = None) -> Table:
    """Tabla estilizada con datos del paciente (alergias opcionales para receta)."""
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

    if allergies_text is not None:
        data = [
            [_pair("Paciente", nombre), _pair("Edad", edad), _pair("Sexo", sexo)],
            [_pair("Folio", folio), _pair("Fecha", fecha), Paragraph("", styles["cell"])],
            [
                Paragraph(
                    f"<b>Alergias:</b> {allergies_text or 'Ninguna registrada'}",
                    styles["cell"],
                ),
                "",
                "",
            ],
        ]
        table = Table(data, colWidths=[80 * mm, 45 * mm, 45 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GRAY),
                    ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                    ("INNERGRID", (0, 0), (-1, 1), 0.5, BORDER),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("SPAN", (1, 1), (2, 1)),
                    ("SPAN", (0, 2), (2, 2)),
                ]
            )
        )
        return table

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
    """Tabla de receta: denominación genérica primero (normativa mexicana)."""
    header_row = [
        Paragraph("Denominación genérica", styles["cell_head"]),
        Paragraph("Dosis", styles["cell_head"]),
        Paragraph("Frecuencia", styles["cell_head"]),
        Paragraph("Duración", styles["cell_head"]),
    ]
    rows = [header_row]
    for p in prescriptions or []:
        generic = (getattr(p, "active_ingredient", None) or "").strip()
        commercial = (p.medication or "").strip()

        # Genérico como dato principal; comercial en segunda línea (complementario)
        if generic:
            main = generic
            secondary_bits = []
            if commercial and commercial.lower() != generic.lower():
                secondary_bits.append(f"Comercial: {commercial}")
        else:
            main = commercial or "—"
            secondary_bits = []

        indications = (getattr(p, "indications", None) or "").strip()
        if indications:
            secondary_bits.append(indications)

        med_html = f"<b>{main}</b>"
        if secondary_bits:
            detail = "<br/>".join(secondary_bits)
            med_html += f"<br/><font color='#64748b' size='8'>{detail}</font>"

        rows.append(
            [
                Paragraph(med_html, styles["cell"]),
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


def _signature_block(doctor, styles) -> KeepTogether:
    signature_line = Table(
        [[""]],
        colWidths=[80 * mm],
        style=TableStyle([("LINEABOVE", (0, 0), (-1, -1), 0.8, DARK)]),
    )
    signature_line.hAlign = "CENTER"
    return KeepTogether(
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


def _new_doc(buffer: BytesIO, title: str) -> SimpleDocTemplate:
    return SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=title,
    )


def _format_allergies(allergies) -> str:
    items = []
    for a in allergies or []:
        allergen = (getattr(a, "allergen", None) or "").strip()
        if not allergen:
            continue
        severity = (getattr(a, "severity", None) or "").strip()
        items.append(f"{allergen} ({severity})" if severity else allergen)
    return ", ".join(items) if items else "Ninguna registrada"


def generate_clinical_note_pdf(
    consultation,
    patient,
    doctor,
    note,
    diagnostics,
) -> BytesIO:
    """PDF interno: SOAPE + diagnósticos CIE-11. Sin receta ni resumen al paciente."""
    styles = _build_styles()
    buffer = BytesIO()
    folio = getattr(consultation, "folio", "") or ""
    doc = _new_doc(buffer, f"Nota clínica {folio}".strip())

    story: list = []
    story.append(
        _header(
            doctor,
            styles,
            subtitle="Nota clínica — expediente interno",
            full_doctor=False,
        )
    )
    story.append(Spacer(1, 10))
    story.append(_patient_table(consultation, patient, styles))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Nota clínica (SOAPE)", styles["section"]))
    if note is not None:
        story.append(_clinical_section("SUBJETIVO", note.subjective, styles))
        story.append(_clinical_section("OBJETIVO", note.objective, styles))
        story.append(_clinical_section("ANÁLISIS", note.analysis, styles))
        story.append(_clinical_section("PLAN", note.plan, styles))
        if getattr(note, "evaluation", None):
            story.append(_clinical_section("EVALUACIÓN", note.evaluation, styles))
    else:
        story.append(Paragraph("Sin nota clínica registrada.", styles["body"]))
    story.append(Spacer(1, 8))

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
        story.append(Paragraph("Sin diagnósticos registrados.", styles["body"]))

    story.append(Spacer(1, 26))
    story.append(_signature_block(doctor, styles))

    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_prescription_pdf(
    consultation,
    patient,
    doctor,
    prescriptions,
    *,
    allergies=None,
    patient_summary: str | None = None,
) -> BytesIO:
    """PDF para paciente/farmacia: receta + resumen amigable. Sin SOAPE."""
    styles = _build_styles()
    buffer = BytesIO()
    folio = getattr(consultation, "folio", "") or ""
    doc = _new_doc(buffer, f"Receta médica {folio}".strip())

    story: list = []
    story.append(
        _header(
            doctor,
            styles,
            subtitle="Receta médica y resumen para el paciente",
            full_doctor=True,
        )
    )
    story.append(Spacer(1, 10))
    story.append(
        _patient_table(
            consultation,
            patient,
            styles,
            allergies_text=_format_allergies(allergies),
        )
    )
    story.append(Spacer(1, 12))

    story.append(Paragraph("Receta médica", styles["section"]))
    if prescriptions:
        story.append(_prescription_table(prescriptions, styles))
    else:
        story.append(Paragraph("Sin medicamentos prescritos.", styles["body"]))
    story.append(Spacer(1, 10))

    summary = coerce_patient_summary(patient_summary)
    story.append(Paragraph("Indicaciones y cuidados", styles["section"]))
    sections = (
        ("Qué le diagnosticaron", summary["diagnostico_simple"]),
        ("Cómo tomar sus medicinas", summary["instrucciones_medicinas"]),
        ("Cuidados en casa", summary["cuidados_casa"]),
        ("Señales de alarma", summary["senales_alarma"]),
    )
    if summary_has_content(summary):
        for title, text in sections:
            if not (text or "").strip():
                continue
            story.append(_clinical_section(title, text, styles))
    else:
        story.append(
            Paragraph(
                "Siga las indicaciones de su médico. Ante síntomas de alarma, "
                "acuda a valoración médica.",
                styles["body"],
            )
        )

    story.append(Spacer(1, 26))
    story.append(_signature_block(doctor, styles))

    doc.build(story)
    buffer.seek(0)
    return buffer
