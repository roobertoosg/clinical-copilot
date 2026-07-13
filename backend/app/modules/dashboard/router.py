from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Patient, Consultation, ClinicalAlert, now_mx
from .schemas import DashboardStats, RecentConsultationItem, CriticalAlertItem

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _patient_name(patient: Patient | None) -> str:
    if patient is None:
        return "Paciente desconocido"
    return f"{patient.first_name or ''} {patient.last_name or ''}".strip()


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Contadores: total de pacientes y consultas procesadas hoy (hora de México)."""
    now = now_mx()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_patients = db.query(func.count(Patient.id)).scalar() or 0
    consultations_today = (
        db.query(func.count(Consultation.id))
        .filter(Consultation.date >= start_of_day)
        .scalar()
        or 0
    )

    return DashboardStats(
        total_patients=total_patients,
        consultations_today=consultations_today,
    )


@router.get("/recent-consultations", response_model=list[RecentConsultationItem])
def get_recent_consultations(db: Session = Depends(get_db)):
    """Últimas 10 consultas procesadas, de más reciente a más antigua."""
    consultations = (
        db.query(Consultation)
        .order_by(Consultation.date.desc())
        .limit(10)
        .all()
    )
    return [
        RecentConsultationItem(
            id=c.id,
            folio=c.folio,
            date=c.date,
            patient_name=_patient_name(c.patient),
        )
        for c in consultations
    ]


@router.get("/critical-alerts", response_model=list[CriticalAlertItem])
def get_critical_alerts(db: Session = Depends(get_db)):
    """Últimas alertas de severidad 'Alta' (JOIN alerta + consulta + paciente)."""
    rows = (
        db.query(ClinicalAlert, Consultation, Patient)
        .join(Consultation, ClinicalAlert.consultation_id == Consultation.id)
        .join(Patient, Consultation.patient_id == Patient.id)
        .filter(func.lower(ClinicalAlert.severity) == "alta")
        .order_by(Consultation.date.desc())
        .limit(10)
        .all()
    )

    logger.info("Dashboard: {n} alertas críticas encontradas.", n=len(rows))

    return [
        CriticalAlertItem(
            id=alert.id,
            date=consultation.date,
            patient_name=_patient_name(patient),
            description=alert.description or "",
            severity=alert.severity,
            alert_type=alert.alert_type,
            folio=consultation.folio,
        )
        for alert, consultation, patient in rows
    ]
