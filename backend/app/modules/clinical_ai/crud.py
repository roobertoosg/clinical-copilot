from loguru import logger
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import (
    ClinicalAlert,
    ClinicalNote,
    Consultation,
    Diagnostic,
    Prescription,
    now_mx,
)
from .schemas import AIClinicalOutput, ConsultationInput


def _generate_folio(db: Session) -> str:
    """Genera un folio único del día con formato CON-YYYYMMDD-NNNN."""
    today = now_mx()
    prefix = f"CON-{today.strftime('%Y%m%d')}"
    # Correlativo: cantidad de consultas ya creadas hoy + 1
    start_of_day = today.replace(hour=0, minute=0, second=0, microsecond=0)
    count_today = (
        db.query(func.count(Consultation.id))
        .filter(Consultation.date >= start_of_day)
        .scalar()
        or 0
    )
    return f"{prefix}-{count_today + 1:04d}"


def save_consultation_results(
    db: Session,
    patient_id: int,
    input_data: ConsultationInput,
    ai_output: AIClinicalOutput,
    ai_accuracy_score: float | None = None,
) -> Consultation:
    """Persiste el resultado de una consulta clínica en una única transacción.

    Crea la Consultation y sus registros asociados (ClinicalNote, Prescription,
    ClinicalAlert). Si algo falla se hace rollback completo para no dejar datos
    parciales en la base de datos.

    Args:
        ai_accuracy_score: Similitud SOAPE IA vs. médico (0.0–1.0), opcional.
    """
    logger.info(
        "Iniciando persistencia clínica en la base de datos para paciente ID: {id}.",
        id=patient_id,
    )
    try:
        # 1. Registro principal de la consulta (con folio único autogenerado)
        #    doctor_id=1 es temporal: se asigna al doctor de prueba sembrado por
        #    reset_db.py hasta que exista el módulo de Login/autenticación.
        consultation = Consultation(
            folio=_generate_folio(db),
            patient_id=patient_id,
            doctor_id=1,
            reason=ai_output.resumen_paciente,
            transcription=input_data.conversation_text,
            status="completed",
            ai_accuracy_score=ai_accuracy_score,
        )
        db.add(consultation)
        # Flush para obtener el consultation.id sin cerrar la transacción
        db.flush()

        # 2. Nota clínica SOAPE (mapeo desde el diccionario 'soape')
        soape = ai_output.soape or {}
        clinical_note = ClinicalNote(
            consultation_id=consultation.id,
            subjective=soape.get("subjetivo"),
            objective=soape.get("objetivo"),
            analysis=soape.get("analisis"),
            plan=soape.get("plan"),
            evaluation=soape.get("evaluacion"),
        )
        db.add(clinical_note)

        # 3. Receta: cada entrada de 'receta' viene estructurada por campo
        for item in ai_output.receta or []:
            if not item.medicamento or not item.medicamento.strip():
                continue
            db.add(
                Prescription(
                    consultation_id=consultation.id,
                    medication=item.medicamento.strip(),
                    dose=item.dosis or None,
                    frequency=item.frecuencia or None,
                    duration=item.duracion or None,
                    indications=item.indicaciones or None,
                )
            )

        # 4. Alertas clínicas (estructuradas por campo)
        for alerta in ai_output.alertas or []:
            if not alerta.descripcion or not alerta.descripcion.strip():
                continue
            db.add(
                ClinicalAlert(
                    consultation_id=consultation.id,
                    alert_type=alerta.tipo or None,
                    description=alerta.descripcion.strip(),
                    severity=alerta.severidad or None,
                )
            )

        # 5. Diagnósticos sugeridos (normalizados: código, descripción y probabilidad
        #    se guardan en columnas independientes).
        for dx in ai_output.diagnosticos_sugeridos or []:
            if isinstance(dx, dict):
                codigo = (dx.get("codigo") or "").strip()
                desc = (dx.get("descripcion") or "").strip()
                prob = (dx.get("probabilidad") or "").strip()
            else:
                codigo = ""
                desc = str(dx).strip()
                prob = ""
            # 'description' es obligatorio; sin descripción no se registra el dx.
            if not desc:
                continue
            db.add(
                Diagnostic(
                    consultation_id=consultation.id,
                    codigo=codigo or None,
                    description=desc,
                    probabilidad=prob or None,
                )
            )

        # 6. Confirmar la transacción completa
        db.commit()
        logger.success(
            "Consulta {folio} persistida correctamente (paciente ID: {id}).",
            folio=consultation.folio,
            id=patient_id,
        )
        db.refresh(consultation)
        return consultation

    except SQLAlchemyError:
        # Ante cualquier error de integridad/base de datos, revertir todo
        logger.exception("Error de base de datos, ejecutando rollback")
        db.rollback()
        raise
