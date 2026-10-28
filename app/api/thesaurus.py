"""
API-Routen für den Kirchlichen Thesaurus, Iconclass, GND-Normdatenbank
und OpenCLIP Zero-Shot Fachverschlagwortung.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.auth import User, require_curator
from app.core.config import settings
from app.core.security import validate_safe_image_path
from app.api.deps import get_clip_service, get_qdrant_service
from app.services.clip_service import ClipService
from app.services.qdrant_service import QdrantService
from app.services.thesaurus_service import thesaurus_service
from app.services.metadata_db import metadata_db

router = APIRouter(prefix="/thesaurus", tags=["Thesaurus & Ikonographie"])


class ThesaurusTerm(BaseModel):
    id: str
    canonical: str
    category: str
    synonyms: List[str] = []
    iconclass: Optional[str] = None
    gnd: Optional[str] = None
    description: Optional[str] = None
    clip_prompts: List[str] = []


class QueryExpansionResponse(BaseModel):
    has_expansion: bool
    matched_term: Optional[str] = None
    canonical: Optional[str] = None
    category: Optional[str] = None
    iconclass: Optional[str] = None
    gnd: Optional[str] = None
    description: Optional[str] = None
    synonyms: List[str] = []
    expansion_terms: List[str] = []


class ThesaurusSuggestion(BaseModel):
    term: str
    canonical: str
    category: str
    iconclass: Optional[str] = None
    gnd: Optional[str] = None
    is_synonym: bool = False


class ApplyTagsRequest(BaseModel):
    path: str = Field(..., description="Dateipfad des Archivbildes")
    tags: List[str] = Field(..., description="Zu übernehmende GND-/Thesaurus-Schlagwörter")
    carrier_type: Optional[str] = Field(default=None, description="Optionaler erkannter Bildträger")
    primary_category: Optional[str] = Field(default=None, description="Thesaurus-Hauptkategorie")


@router.get("/expand", response_model=QueryExpansionResponse)
def expand_query(
    q: str = Query(..., min_length=2, description="Suchbegriff zur kirchlichen Synonym-Erweiterung"),
):
    """
    Ermittelt kirchliche Fachbegriffe, Synonyme, Iconclass-Codes und GND-Nummern zu einem Suchbegriff.
    """
    res = thesaurus_service.expand_query(q)
    if not res:
        return QueryExpansionResponse(has_expansion=False)
    
    return QueryExpansionResponse(
        has_expansion=True,
        matched_term=res.get("matched_term"),
        canonical=res.get("canonical"),
        category=res.get("category"),
        iconclass=res.get("iconclass"),
        gnd=res.get("gnd"),
        description=res.get("description"),
        synonyms=res.get("synonyms") or [],
        expansion_terms=res.get("expansion_terms") or [],
    )


@router.get("/categories", response_model=List[str])
def list_categories():
    """Liefert alle im Thesaurus erfassten Vokabular-Kategorien."""
    return thesaurus_service.get_all_categories()


@router.get("/terms", response_model=List[ThesaurusTerm])
def list_terms(
    category: Optional[str] = Query(None, description="Optionaler Filter nach Kategorie"),
):
    """Liefert den kontrollierten Fachbegriffs-Katalog."""
    return thesaurus_service.get_terms(category=category)


@router.get("/suggest", response_model=List[ThesaurusSuggestion])
def suggest_terms(
    prefix: str = Query(..., min_length=1, description="Anfangsbuchstaben des Begriffs"),
    limit: int = Query(default=8, ge=1, le=20),
):
    """Auto-Vervollständigung kirchlicher Fachbegriffe und Synonyme."""
    return thesaurus_service.autocomplete(prefix=prefix, limit=limit)


# =========================================================================
# Säule 3: Zero-Shot Verschlagwortung, Trägererkennung & SQLite-GND
# =========================================================================

@router.get("/authorities")
def search_authorities(
    q: Optional[str] = Query(default="", description="Suchtext in GND-Normdatenbank"),
    category: Optional[str] = Query(default=None, description="Filter nach Kategorie"),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Durchsucht die lokale GND- und Iconclass-Normdatenbank (Offline-First)."""
    if not q:
        return metadata_db.get_all_gnd_authorities(category=category)[:limit]
    return metadata_db.search_gnd_authorities(query=q, limit=limit, category=category)


@router.get("/suggest-for-image")
def suggest_for_image(
    path: str = Query(..., description="Dateipfad des Archivbildes"),
    clip: ClipService = Depends(get_clip_service),
    top_k: int = Query(default=5, ge=1, le=10),
):
    """
    Zero-Shot Fachverschlagwortung & Trägererkennung:
    Gleicht das Bild mit OpenCLIP gegen den kirchlichen GND-Thesaurus ab
    und analysiert den historischen Bildträger (Albumin, SW, Cyanotypie, CdV).
    """
    safe_path = validate_safe_image_path(path)
    try:
        suggestions = thesaurus_service.suggest_metadata_for_image(
            image_path=safe_path,
            clip_service=clip,
            top_k=top_k,
        )
        return {
            "success": True,
            "file_path": str(safe_path.resolve()),
            **suggestions,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fehler bei Zero-Shot Fachverschlagwortung: {e}",
        )


@router.get("/carrier")
def analyze_carrier(
    path: str = Query(..., description="Dateipfad des Archivbildes"),
):
    """Heuristische Träger- und Zustandserkennung anhand von Farbkanälen, Dynamik und Format."""
    safe_path = validate_safe_image_path(path)
    try:
        carrier = thesaurus_service.detect_carrier_and_condition(safe_path)
        return {
            "success": True,
            "file_path": str(safe_path.resolve()),
            "carrier_analysis": carrier,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fehler bei Trägererkennung: {e}",
        )


@router.post("/apply-tags")
def apply_tags_to_image(
    req: ApplyTagsRequest,
    curator: Optional[User] = Depends(require_curator),
    qdrant: QdrantService = Depends(get_qdrant_service),
):
    """
    Übernimmt ausgewählte GND-Fachbegriffe und Trägerbezeichnungen
    in die Bildmetadaten (SQLite, Qdrant-Vektorpayload und XMP-Sidecar).
    """
    from qdrant_client.http import models as rest_models
    safe_path = validate_safe_image_path(req.path)
    abs_str = str(safe_path.resolve())

    # 1. Bestehende Metadaten aus SQLite abrufen
    db_meta = metadata_db.get_metadata(abs_str) or {}
    existing_keywords = list(db_meta.get("keywords") or [])

    # Neue Schlagwörter zusammenfügen (ohne Duplikate, Reihenfolge bewahrend)
    merged_keywords = list(dict.fromkeys(existing_keywords + req.tags))
    if req.carrier_type and req.carrier_type not in merged_keywords:
        merged_keywords.append(req.carrier_type)

    # In SQLite speichern
    saved = metadata_db.upsert_metadata(
        file_path=abs_str,
        file_name=safe_path.name,
        title=db_meta.get("title"),
        signature=db_meta.get("signature"),
        date=db_meta.get("date"),
        creator=db_meta.get("creator"),
        description=db_meta.get("description"),
        keywords=merged_keywords,
        persons=db_meta.get("persons"),
    )
    if not saved:
        raise HTTPException(status_code=500, detail="Konnte Metadaten in Datenbank nicht aktualisieren.")

    # Audit-Log
    metadata_db.add_audit_log(
        action="APPLY_GND_TAGS",
        target_type="IMAGE",
        target_id=abs_str,
        details={"tags_added": req.tags, "carrier": req.carrier_type},
        operator=curator.username if curator else "curator",
    )

    # 2. Qdrant-Vektorpayload synchronisieren
    try:
        records, _ = qdrant.client.scroll(
            collection_name=settings.COLLECTION_IMAGES,
            scroll_filter=rest_models.Filter(
                should=[
                    rest_models.FieldCondition(key="file_path", match=rest_models.MatchValue(value=abs_str)),
                    rest_models.FieldCondition(key="image_path", match=rest_models.MatchValue(value=abs_str)),
                ]
            ),
            limit=1,
            with_payload=False,
        )
        if records:
            qdrant.client.set_payload(
                collection_name=settings.COLLECTION_IMAGES,
                payload={"keywords": merged_keywords},
                points=[records[0].id],
            )
    except Exception as q_err:
        pass

    # 3. XMP-Sidecar aktualisieren
    try:
        from app.services.xmp_service import xmp_service
        xmp_service.write_sidecar(
            image_path=safe_path,
            title=db_meta.get("title"),
            creator=db_meta.get("creator"),
            date=db_meta.get("date"),
            description=db_meta.get("description"),
            keywords=merged_keywords,
            persons=db_meta.get("persons"),
        )
    except Exception:
        pass

    return {
        "success": True,
        "file_path": abs_str,
        "keywords": merged_keywords,
        "merged_keywords": merged_keywords,
        "tags_applied": req.tags,
        "tags_count": len(merged_keywords),
    }
