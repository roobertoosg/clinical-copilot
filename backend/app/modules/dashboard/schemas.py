from datetime import datetime

from pydantic import BaseModel


class DashboardStats(BaseModel):
    """Contadores generales para las tarjetas de resumen."""

    total_patients: int
    consultations_today: int


class RecentConsultationItem(BaseModel):
    """Fila del panel de consultas recientes."""

    id: int
    folio: str | None
    date: datetime | None
    patient_name: str


class CriticalAlertItem(BaseModel):
    """Alerta crítica (severidad Alta) para el panel lateral."""

    id: int
    date: datetime | None
    patient_name: str
    description: str
    severity: str | None
    alert_type: str | None
    folio: str | None
