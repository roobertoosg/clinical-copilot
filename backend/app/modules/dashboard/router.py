from datetime import datetime

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


def _start_of_month(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _previous_month_start(month_start: datetime) -> datetime:
    if month_start.month == 1:
        return month_start.replace(year=month_start.year - 1, month=12)
    return month_start.replace(month=month_start.month - 1)


def _avg_ai_accuracy_pct(
    db: Session,
    *,
    start: datetime,
    end: datetime,
) -> float | None:
    """Promedio de ``ai_accuracy_score`` (0–1) en [start, end) → porcentaje o None."""
    avg_score = (
        db.query(func.avg(Consultation.ai_accuracy_score))
        .filter(
            Consultation.ai_accuracy_score.isnot(None),
            Consultation.date >= start,
            Consultation.date < end,
        )
        .scalar()
    )
    if avg_score is None:
        return None
    return round(float(avg_score) * 100.0, 1)


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Contadores: pacientes, consultas de hoy y precisión IA (mes actual vs. anterior)."""
    now = now_mx()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_current_month = _start_of_month(now)
    start_previous_month = _previous_month_start(start_current_month)

    total_patients = db.query(func.count(Patient.id)).scalar() or 0
    consultations_today = (
        db.query(func.count(Consultation.id))
        .filter(Consultation.date >= start_of_day)
        .scalar()
        or 0
    )

    # Mes actual: [start_current_month, now+ε) → usamos ahora como cota superior práctica
    # con end exclusivo al inicio del próximo mes para consistencia de rangos.
    if start_current_month.month == 12:
        start_next_month = start_current_month.replace(
            year=start_current_month.year + 1, month=1
        )
    else:
        start_next_month = start_current_month.replace(
            month=start_current_month.month + 1
        )

    current_pct = _avg_ai_accuracy_pct(
        db, start=start_current_month, end=start_next_month
    )
    previous_pct = _avg_ai_accuracy_pct(
        db, start=start_previous_month, end=start_current_month
    )

    # Sin consultas con score este mes → 100% por defecto
    current_ai_accuracy = 100.0 if current_pct is None else current_pct
    # Sin histórico del mes anterior → tendencia 0
    if previous_pct is None:
        ai_accuracy_trend = 0.0
    else:
        ai_accuracy_trend = round(current_ai_accuracy - previous_pct, 1)

    return DashboardStats(
        total_patients=total_patients,
        consultations_today=consultations_today,
        current_ai_accuracy=current_ai_accuracy,
        ai_accuracy_trend=ai_accuracy_trend,
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
