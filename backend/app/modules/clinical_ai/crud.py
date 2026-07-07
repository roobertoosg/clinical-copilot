from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import (
    ClinicalAlert,
    ClinicalNote,
    Consultation,
    Prescription,
)
from .schemas import AIClinicalOutput, ConsultationInput


def save_consultation_results(
    db: Session,
    patient_id: int,
    input_data: ConsultationInput,
    ai_output: AIClinicalOutput,
) -> Consultation:
    """Persiste el resultado de una consulta clínica en una única transacción.

    Crea la Consultation y sus registros asociados (ClinicalNote, Prescription,
    ClinicalAlert). Si algo falla se hace rollback completo para no dejar datos
    parciales en la base de datos.
    """
    try:
        # 1. Registro principal de la consulta
        consultation = Consultation(
            patient_id=patient_id,
            reason=ai_output.resumen_paciente,
            transcription=input_data.conversation_text,
            status="completed",
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

        # 5. Confirmar la transacción completa
        db.commit()
        db.refresh(consultation)
        return consultation

    except SQLAlchemyError:
        # Ante cualquier error de integridad/base de datos, revertir todo
        db.rollback()
        raise
