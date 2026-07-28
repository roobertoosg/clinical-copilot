"""ETL idempotente: carga el catálogo de medicamentos desde CSV a PostgreSQL.

Lee backend/data/catalogo_2000_productos.csv e inserta en medications_catalog.
Si la tabla ya contiene registros, omite la carga (salvo ``--force``).

Uso (desde backend/):
    ./venv/bin/python scripts/load_catalog.py
    ./venv/bin/python scripts/load_catalog.py --force   # trunca y recarga
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


def _normalize_row(row: dict) -> dict:
    """Limpia BOM / espacios en encabezados del CSV."""
    return {
        (k or "").lstrip("\ufeff").strip(): (v or "").strip()
        for k, v in row.items()
    }


def load_catalog(*, force: bool = False) -> None:
    if not CSV_PATH.exists():
        print(f"❌ No se encontró el archivo CSV: {CSV_PATH}")
        sys.exit(1)

    print("🛠️  Verificando esquema de medications_catalog...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing = db.query(MedicationCatalog).count()
        if existing > 0 and not force:
            print(
                f"⏭️  La tabla medications_catalog ya tiene {existing} registros. "
                "Se omite la carga (idempotente). Usa --force para recargar."
            )
            return

        if force and existing > 0:
            print(f"🧹 --force: eliminando {existing} registros previos...")
            db.query(MedicationCatalog).delete()
            db.commit()

        print(f"📂 Leyendo catálogo desde {CSV_PATH.name}...")
        batch: list[MedicationCatalog] = []
        total = 0

        # utf-8-sig elimina BOM que rompe el header ``producto``
        with CSV_PATH.open(encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            for raw in reader:
                row = _normalize_row(raw)
                producto = row.get("producto") or ""
                sustancia = row.get("sustancia_activa") or ""
                if not producto and not sustancia:
                    continue
                batch.append(
                    MedicationCatalog(
                        producto=producto,
                        marca=row.get("marca") or None,
                        sustancia_activa=sustancia,
                        categoria=row.get("categoria") or None,
                        ean=row.get("ean") or None,
                        laboratorio=row.get("laboratorio") or None,
                        estatus=row.get("estatus") or "ACTIVO",
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
    load_catalog(force="--force" in sys.argv)
