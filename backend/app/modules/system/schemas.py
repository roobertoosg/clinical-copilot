from datetime import datetime

from pydantic import BaseModel


class ActivityEvent(BaseModel):
    """Un evento de la bitácora de actividad del sistema."""

    timestamp: datetime
    type: str          # 'patient' | 'consultation' | 'medication'
    message: str
    reference: str | None = None  # ej. folio o nombre asociado
