"""
REST-API-Endpunkte für Langzeit-Bestandserhaltung & Fixity-Monitoring (ISO 14721 OAIS).
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from app.core.auth import User, require_curator
from app.core.security import validate_safe_image_path
from app.services.fixity_service import fixity_service
from app.services.metadata_db import metadata_db

router = APIRouter(prefix="/fixity", tags=["Langzeitarchivierung & Fixity"])


class VerifyRequest(BaseModel):
    folder_path: Optional[str] = Field(default=None, description="Optionaler Unterordner für fokussiertes Fixity-Audit")
    calculate_missing: bool = Field(default=True, description="Erzeugt fehlende SHA-256 Hashes für Altbestände automatisch")


class BatchPremisExportRequest(BaseModel):
    paths: List[str] = Field(..., description="Liste der Dateipfade für den gebündelten PREMIS-Export")
    archive_name: Optional[str] = Field(default="Historisches Archiv", description="Name der Gedächtnisinstitution")


@router.get("/status")
def get_fixity_status():
    """
    Liefert den aktuellen Integritätsstatus der Master-Dateien,
    den Fortschritt laufender Hintergrundprüfungen und Bitrot-Warnungen.
    """
    return fixity_service.get_status()


@router.get("/corrupted")
def get_corrupted_files(curator: User = Depends(require_curator)):
    """
    Liefert alle aktuell als beschädigt (Bit-Rot), unlesbar oder fehlend markierten Originale.
    Geschützt für Archivare und Administratoren.
    """
    return {
        "corrupted_items": fixity_service.get_corrupted_items(),
    }


@router.post("/verify")
def start_fixity_verification(
    req: VerifyRequest = VerifyRequest(),
    curator: User = Depends(require_curator),
):
    """
    Startet eine autonome Bitstream-Integritätsprüfung aller Master-Scans im Hintergrund.
    Erfordert Kurator- oder Administrator-Rechte.
    """
    res = fixity_service.start_verification(
        folder_path=req.folder_path,
        calculate_missing=req.calculate_missing,
        background=True,
    )
    metadata_db.add_audit_log(
        action="TRIGGER_FIXITY_AUDIT",
        target_type="STORAGE",
        target_id=req.folder_path or "ALL_MASTER_FILES",
        details={"calculate_missing": req.calculate_missing},
        operator=curator.username,
    )
    return res


@router.get("/premis")
def export_single_premis_xml(
    path: str = Query(..., description="Dateipfad des Archivbildes"),
):
    """
    Erzeugt ein standardkonformes PREMIS 3.0 XML (ISO 14721 OAIS)
    für die angegebene Master-Datei zum Nachweis der Fixity-Erhaltung.
    """
    safe_path = validate_safe_image_path(path)
    abs_str = str(safe_path.resolve())

    try:
        xml_bytes = fixity_service.export_premis_for_path(abs_str)
        filename = f"PREMIS_{safe_path.stem}.xml"
        return Response(
            content=xml_bytes,
            media_type="application/xml; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-cache",
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fehler bei PREMIS-Generierung: {e}",
        )


@router.post("/premis/export")
def export_batch_premis_xml(
    req: BatchPremisExportRequest,
):
    """
    Exportiert ein gebündeltes PREMIS 3.0 XML-Archivpaket für eine Liste von Digitalisaten
    (z. B. aus dem digitalen Leuchttisch).
    """
    if not req.paths:
        raise HTTPException(status_code=400, detail="Keine Dateipfade angegeben.")

    valid_paths = []
    for p in req.paths:
        try:
            sp = validate_safe_image_path(p)
            valid_paths.append(str(sp.resolve()))
        except Exception:
            continue

    if not valid_paths:
        raise HTTPException(status_code=400, detail="Keine gültigen Bilddateien gefunden.")

    try:
        xml_bytes = fixity_service.export_premis_batch(valid_paths)
        date_str = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"PREMIS_Batch_{date_str}.xml"
        return Response(
            content=xml_bytes,
            media_type="application/xml; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-cache",
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fehler bei gebündelter PREMIS-Generierung: {e}",
        )
