"""ETL idempotente: carga el catálogo de medicamentos desde CSV a PostgreSQL.

Lee backend/data/catalogo_2000_productos.csv e inserta en medications_catalog.
Si la tabla ya contiene registros, omite la carga.

Uso (desde backend/):
    ./venv/bin/python scripts/load_catalog.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

# Raíz del backend en sys.path para importar app.*
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.db import models  # noqa: F401 — registra modelos en Base.metadata
from app.db.models import MedicationCatalog
from app.db.session import Base, SessionLocal, engine

CSV_PATH = BACKEND_DIR / "data" / "catalogo_2000_productos.csv"
BATCH_SIZE = 500


def load_catalog() -> None:
    if not CSV_PATH.exists():
        print(f"❌ No se encontró el archivo CSV: {CSV_PATH}")
        sys.exit(1)

    print("🛠️  Verificando esquema de medications_catalog...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing = db.query(MedicationCatalog).count()
        if existing > 0:
            print(
                f"⏭️  La tabla medications_catalog ya tiene {existing} registros. "
                "Se omite la carga (idempotente)."
            )
            return

        print(f"📂 Leyendo catálogo desde {CSV_PATH.name}...")
        batch: list[MedicationCatalog] = []
        total = 0

        with CSV_PATH.open(encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                batch.append(
                    MedicationCatalog(
                        producto=(row.get("producto") or "").strip(),
                        marca=(row.get("marca") or "").strip() or None,
                        sustancia_activa=(row.get("sustancia_activa") or "").strip(),
                        categoria=(row.get("categoria") or "").strip() or None,
                        ean=(row.get("ean") or "").strip() or None,
                        laboratorio=(row.get("laboratorio") or "").strip() or None,
                        estatus=(row.get("estatus") or "ACTIVO").strip() or "ACTIVO",
                    )
                )
                if len(batch) >= BATCH_SIZE:
                    db.bulk_save_objects(batch)
                    db.commit()
                    total += len(batch)
                    print(f"   … {total} registros insertados")
                    batch.clear()

        if batch:
            db.bulk_save_objects(batch)
            db.commit()
            total += len(batch)

        print(f"✅ Catálogo cargado: {total} medicamentos en medications_catalog.")

    except Exception as exc:
        db.rollback()
        print(f"❌ Error al cargar el catálogo: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    load_catalog()
