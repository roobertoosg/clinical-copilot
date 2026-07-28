from datetime import datetime

from pydantic import BaseModel


class DashboardStats(BaseModel):
    """Contadores generales para las tarjetas de resumen."""

    total_patients: int
    consultations_today: int
    # Promedio de ai_accuracy_score del mes actual (0–100)
    current_ai_accuracy: float = 100.0
    # Diferencia vs. promedio del mes anterior (pp). 0 si no hay histórico.
    ai_accuracy_trend: float = 0.0


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
