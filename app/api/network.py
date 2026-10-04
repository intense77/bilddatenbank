"""
FastAPI-Routen für Personen-Netzwerke & Co-Occurrence-Analyse.
Ermöglicht das Erkennen gemeinsamer Bildauftritte, Schnittmengen-Recherchen
und interaktive Beziehungs-Graphen.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException

from app.api.deps import get_network_service
from app.services.network_service import NetworkService

router = APIRouter(tags=["Personen-Netzwerk"])


@router.get("/network/person/{cluster_id}/co-occurrences", response_model=List[Dict[str, Any]])
def get_person_co_occurrences(
    cluster_id: str,
    limit: int = Query(default=15, ge=1, le=100, description="Maximale Anzahl an Begleitpersonen"),
    network_service: NetworkService = Depends(get_network_service),
):
    """
    Ermittelt alle Personen, die auf denselben Bildern wie cluster_id vorkommen.
    Liefert Liste: [{"cluster_id": str, "name": str, "shared_count": int, "thumbnail_url": str}]
    """
    return network_service.get_co_occurrences(cluster_id=cluster_id, limit=limit)


@router.get("/network/person/{cluster_id}/graph")
def get_person_network_graph(
    cluster_id: str,
    depth: int = Query(default=1, ge=1, le=2, description="Netzwerktiefe (1 = direkte Nachbarn, 2 = 2. Grad)"),
    min_shared: int = Query(default=2, ge=1, le=50, description="Mindestanzahl gemeinsamer Fotos für eine Kante"),
    network_service: NetworkService = Depends(get_network_service),
):
    """
    Baut ein Knoten-Kanten-JSON (nodes, edges) für vis-network / Cytoscape:
    - nodes: id, label, image, size, shape
    - edges: from, to, value (gemeinsame Fotos)
    """
    return network_service.get_network_graph(cluster_id=cluster_id, depth=depth, min_shared=min_shared)


@router.get("/network/shared-images", response_model=List[Dict[str, Any]])
def get_shared_images(
    person_a: str = Query(..., description="Cluster ID von Person A (z. B. 83 oder cluster_83)"),
    person_b: str = Query(..., description="Cluster ID von Person B (z. B. 0 oder cluster_0)"),
    limit: int = Query(default=100, ge=1, le=500, description="Maximale Anzahl gemeinsamer Bilder"),
    network_service: NetworkService = Depends(get_network_service),
):
    """
    Liefert die Schnittmenge aller Bilder, auf denen Person A und Person B gleichzeitig markiert sind.
    """
    return network_service.get_shared_images(cluster_a=person_a, cluster_b=person_b, limit=limit)
