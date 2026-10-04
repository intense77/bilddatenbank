"""
API-Routen für den Kirchlichen Thesaurus, Iconclass und GND-Normvokabular.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.thesaurus_service import thesaurus_service

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
    is_synonym: bool = False


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
