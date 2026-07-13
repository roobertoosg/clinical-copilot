from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Patient, Consultation, Medication, now_mx
from .schemas import ActivityEvent

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/activity-log", response_model=list[ActivityEvent])
def get_activity_log(db: Session = Depends(get_db)):
    """Bitácora combinada de la actividad del día, ordenada cronológicamente."""
    now = now_mx()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

    events: list[ActivityEvent] = []

    # 1. Pacientes registrados hoy
    patients = (
        db.query(Patient).filter(Patient.created_at >= start_of_day).all()
    )
    for p in patients:
        events.append(
            ActivityEvent(
                timestamp=p.created_at,
                type="patient",
                message=f"Nuevo paciente registrado: {p.first_name} {p.last_name}".strip(),
                reference=f"ID {p.id}",
            )
        )

    # 2. Consultas procesadas hoy
    consultations = (
        db.query(Consultation).filter(Consultation.date >= start_of_day).all()
    )
    for c in consultations:
        events.append(
            ActivityEvent(
                timestamp=c.date,
                type="consultation",
                message=f"Consulta {c.folio or f'#{c.id}'} completada",
                reference=c.folio,
            )
        )

    # 3. Medicamentos suspendidos hoy
    suspended = (
        db.query(Medication)
        .filter(
            Medication.is_active.is_(False),
            Medication.updated_at >= start_of_day,
        )
        .all()
    )
    for m in suspended:
        events.append(
            ActivityEvent(
                timestamp=m.updated_at,
                type="medication",
                message=f"Medicamento suspendido: {m.name}",
                reference=None,
            )
        )

    # Orden cronológico ascendente (de la mañana a la tarde)
    events.sort(key=lambda e: e.timestamp)
    return events
