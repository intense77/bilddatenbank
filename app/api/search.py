import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import re
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from PIL import Image, ImageOps

from app.core.config import settings
from app.core.security import validate_safe_image_path
from app.api.deps import (
    get_clip_service,
    get_face_service,
    get_qdrant_service,
    get_clustering_service,
    get_variant_service,
    get_image_rotation_service,
)
from app.services.clip_service import ClipService, load_image_rgb
from app.services.face_service import FaceService
from app.services.qdrant_service import QdrantService
from app.services.clustering_service import ClusteringService
from app.services.variant_service import VariantService
from app.services.thumbnail_service import thumbnail_service
from app.services.metadata_service import metadata_service
from qdrant_client.http import models as rest_models

router = APIRouter(tags=["Suche & Cluster"])

UUID_NAMESPACE = uuid.UUID("3d4b6845-816b-4e45-8b3c-9ad51b5bbfcb")


# --- Pydantic Modelle ---

class SemanticSearchResult(BaseModel):
    file_path: str = Field(..., description="Absoluter Dateipfad des Bildes")
    file_name: Optional[str] = Field(None, description="Dateiname")
    score: float = Field(..., description="Cosine-Ähnlichkeitsscore (0.0 bis 1.0)")
    id: str = Field(..., description="Qdrant Point ID")
    title: Optional[str] = Field(None, description="Archivtitel / Objektbezeichnung")
    creator: Optional[str] = Field(None, description="Urheber / Fotograf / Künstler")
    date: Optional[str] = Field(None, description="Datierung / Entstehungsdatum")
    signature: Optional[str] = Field(None, description="Archivsignatur / Inventarnummer")
    description: Optional[str] = Field(None, description="Objektbeschreibung")
    keywords: Optional[List[str]] = Field(default=[], description="Schlagwörter")
    persons: Optional[List[str]] = Field(default=[], description="Erkannte & benannte Personen")
    is_stack: bool = Field(default=False, description="Zeigt an, ob dieses Bild einen Stapel aus Varianten/Duplikaten repräsentiert")
    variants_count: int = Field(default=0, description="Anzahl der im Stapel zusammengefassten Varianten")
    variants: Optional[List[Any]] = Field(default=[], description="Liste der zusammengefassten Varianten")
    variant_type: Optional[str] = Field(default=None, description="Klassifizierung: EXACT_DUPLICATE, FORMAT_VARIANT, SERIES_VARIANT")
    variant_label: Optional[str] = Field(default=None, description="Lesbare Bezeichnung der Beziehung")
    variant_similarity: Optional[float] = Field(default=None, description="Ähnlichkeits-Score zur primären Aufnahme")
    primary_id: Optional[str] = Field(default=None, description="ID der primären Aufnahme bei Varianten")


class FaceSearchResult(BaseModel):
    id: str
    score: float
    file_path: str
    bbox: List[int]
    bbox_percent: Optional[Dict[str, float]] = None
    orig_width: Optional[int] = None
    orig_height: Optional[int] = None
    det_score: float
    cluster_id: Optional[str] = None
    label: Optional[str] = None


class ClusterLabelRequest(BaseModel):
    label: str = Field(..., min_length=1, description="Klarname der Person, z. B. 'Bischof Müller'", example="Bischof Müller")


class ClusterMergeRequest(BaseModel):
    source_cluster_id: str = Field(..., description="ID des Quell-Clusters, das aufgelöst wird", example="cluster_1")
    target_cluster_id: str = Field(..., description="ID des Ziel-Clusters, in das integriert wird", example="cluster_0")
    target_label: Optional[str] = Field(None, description="Optionaler gemeinsamer Name für das zusammengeführte Cluster", example="Bischof Ulrich")


class RotateImageRequest(BaseModel):
    path: str = Field(..., description="Lokaler Dateipfad des Archivbildes")
    angle: int = Field(default=90, description="Drehwinkel in Grad: 90 (rechts/CW), 180, 270 bzw. -90 (links/CCW)")


class ClusterFaceItem(BaseModel):
    face_id: str
    file_path: Optional[str] = None
    bbox: Optional[List[int]] = None
    bbox_percent: Optional[Dict[str, float]] = None
    orig_width: Optional[int] = None
    orig_height: Optional[int] = None
    det_score: Optional[float] = None


class ClusterResponse(BaseModel):
    cluster_id: str
    label: Optional[str] = None
    face_count: int
    preview_image: Optional[str] = Field(None, description="Base64 Data-URL des Gesichts-Crops")
    faces: List[ClusterFaceItem] = []


class ClusteringRunResponse(BaseModel):
    total_faces: int
    clusters_found: int
    clustered_faces: int
    noise_faces: int
    clusters: Dict[str, int] = {}
    message: Optional[str] = None


class CropSearchRequest(BaseModel):
    image_path: str = Field(..., description="Lokaler Pfad zum Referenzbild")
    x: float = Field(..., ge=0.0, description="X-Koordinate der linken oberen Ecke (relativ 0.0-1.0 oder Pixel)")
    y: float = Field(..., ge=0.0, description="Y-Koordinate der linken oberen Ecke (relativ 0.0-1.0 oder Pixel)")
    width: float = Field(..., gt=0.0, description="Breite der ausgewählten Region")
    height: float = Field(..., gt=0.0, description="Höhe der ausgewählten Region")
    is_normalized: bool = Field(default=True, description="True wenn x, y, width, height relativ im Intervall [0.0, 1.0] angegeben sind")
    limit: int = Field(default=24, ge=1, le=100)
    score_threshold: Optional[float] = Field(default=None, ge=-1.0, le=1.0)
    stack_variants: bool = Field(default=True, description="Fasst Varianten und Duplikate zu Bildstapeln zusammen")


# --- Endpunkte ---

@router.get("/search/semantic", response_model=List[SemanticSearchResult])
def search_semantic(
    q: str = Query(..., description="Natürlicher Suchtext (z. B. 'historischer Marktplatz', 'Soldatenporträt')"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximale Anzahl Ergebnisse"),
    score_threshold: Optional[float] = Query(default=None, ge=-1.0, le=1.0, description="Mindest-Ähnlichkeitsscore"),
    stack_variants: bool = Query(default=True, description="Fasst Varianten und Duplikate zu Bildstapeln zusammen"),
    clip_service: ClipService = Depends(get_clip_service),
    qdrant: QdrantService = Depends(get_qdrant_service),
    variant_service: VariantService = Depends(get_variant_service),
):
    """
    Vektorisiert den Suchtext via CLIP und führt Vektorsuche in `archive_images` durch.
    Erkennt zudem automatisch benannte Personen aus `archive_faces` und führt eine
    hybride Relevanz-Verschmelzung durch, damit namentlich gesuchte Personen sofort
    mit 100% Relevanz an erster Stelle stehen.
    """
    q_clean = q.strip().lower()
    q_words = [w for w in re.split(r"[^\w]+", q_clean) if len(w) >= 2]

    # 1. Personen-Namenssuche in archive_faces
    matched_person_images: Dict[str, Dict[str, Any]] = {}
    try:
        face_records, _ = qdrant.client.scroll(
            collection_name=settings.COLLECTION_FACES,
            limit=5000,
            with_payload=True,
            with_vectors=False,
        )
        for r in face_records:
            p = r.payload or {}
            lbl = p.get("label")
            if not lbl or not isinstance(lbl, str):
                continue
            lbl_clean = lbl.strip()
            lbl_lower = lbl_clean.lower()
            lbl_words = [w for w in re.split(r"[^\w]+", lbl_lower) if len(w) >= 2]

            # Matching Kriterien:
            # - Exakter Treffer: "bischof müller" == "bischof müller" -> 1.0
            # - Teilstring: "müller" in "bischof müller" oder umgekehrt -> 0.98
            # - Wort-Übereinstimmung -> 0.95
            is_match = False
            match_score = 0.0

            if q_clean == lbl_lower:
                is_match = True
                match_score = 1.0
            elif q_clean in lbl_lower or lbl_lower in q_clean:
                is_match = True
                match_score = 0.98
            elif any(qw in lbl_words or any(qw in lw for lw in lbl_words) for qw in q_words):
                is_match = True
                match_score = 0.95

            if is_match:
                img_path = p.get("file_path") or p.get("image_path")
                if img_path:
                    if img_path not in matched_person_images:
                        matched_person_images[img_path] = {
                            "labels": {lbl_clean},
                            "score": match_score,
                            "parent_image_id": p.get("parent_image_id"),
                        }
                    else:
                        matched_person_images[img_path]["labels"].add(lbl_clean)
                        matched_person_images[img_path]["score"] = max(
                            matched_person_images[img_path]["score"], match_score
                        )
    except Exception as e:
        logger.warning("Personen-Suche in archive_faces fehlgeschlagen: %s", e)

    # 2. CLIP Semantische Vektorsuche
    fetch_limit = limit * 2 if stack_variants else limit
    hits = []
    try:
        query_vector = clip_service.embed_text(q)
        hits = qdrant.search_images(
            query_vector=query_vector,
            limit=fetch_limit,
            score_threshold=score_threshold,
        )
    except Exception as e:
        logger.warning("CLIP Textvektorisierung fehlgeschlagen: %s", e)

    results_map: Dict[str, SemanticSearchResult] = {}

    # Zuerst CLIP-Hits verarbeiten
    for hit in hits:
        payload = hit.payload or {}
        file_path = payload.get("file_path") or payload.get("image_path", "")
        if not file_path:
            continue
        file_name = payload.get("file_name") or payload.get("filename") or Path(file_path).name

        score = float(hit.score)
        matched_persons = set(payload.get("persons") or [])

        # Wurde das Bild zusätzlich durch Personen-Match gefunden?
        if file_path in matched_person_images:
            p_info = matched_person_images[file_path]
            matched_persons.update(p_info["labels"])
            score = max(score, p_info["score"])

        results_map[file_path] = SemanticSearchResult(
            id=str(hit.id),
            score=round(score, 4),
            file_path=file_path,
            file_name=file_name,
            title=payload.get("title"),
            creator=payload.get("creator"),
            date=payload.get("date"),
            signature=payload.get("signature"),
            description=payload.get("description"),
            keywords=payload.get("keywords") or [],
            persons=sorted(list(matched_persons)),
        )

    # Nun noch alle Personen-Treffer hinzufügen, falls CLIP sie nicht in den Top-Hits hatte
    for file_path, p_info in matched_person_images.items():
        if file_path in results_map:
            continue

        img_payload = {}
        parent_id = p_info.get("parent_image_id")
        try:
            if parent_id:
                ret = qdrant.client.retrieve(
                    collection_name=settings.COLLECTION_IMAGES,
                    ids=[parent_id],
                    with_payload=True,
                )
                if ret:
                    img_payload = ret[0].payload or {}
            if not img_payload:
                rec, _ = qdrant.client.scroll(
                    collection_name=settings.COLLECTION_IMAGES,
                    scroll_filter=rest_models.Filter(
                        should=[
                            rest_models.FieldCondition(key="file_path", match=rest_models.MatchValue(value=file_path)),
                            rest_models.FieldCondition(key="image_path", match=rest_models.MatchValue(value=file_path)),
                        ]
                    ),
                    limit=1,
                    with_payload=True,
                )
                if rec:
                    img_payload = rec[0].payload or {}
                    parent_id = str(rec[0].id)
        except Exception as e:
            logger.warning("Bilddaten für %s konnten nicht geladen werden: %s", file_path, e)

        file_name = img_payload.get("file_name") or img_payload.get("filename") or Path(file_path).name
        all_persons = set(img_payload.get("persons") or [])
        all_persons.update(p_info["labels"])

        fallback_id = str(parent_id or uuid.uuid5(UUID_NAMESPACE, Path(file_path).name))
        results_map[file_path] = SemanticSearchResult(
            id=fallback_id,
            score=round(p_info["score"], 4),
            file_path=file_path,
            file_name=file_name,
            title=img_payload.get("title"),
            creator=img_payload.get("creator"),
            date=img_payload.get("date"),
            signature=img_payload.get("signature"),
            description=img_payload.get("description"),
            keywords=img_payload.get("keywords") or [],
            persons=sorted(list(all_persons)),
        )

    # Sortiere nach Score absteigend und liefere maximal 'limit' Ergebnisse
    sorted_results = sorted(results_map.values(), key=lambda r: r.score, reverse=True)
    if stack_variants:
        sorted_results = variant_service.stack_search_results(sorted_results, similarity_threshold=0.92)
    return sorted_results[:limit]


@router.api_route("/search/faces/by-image", methods=["GET", "POST"], response_model=List[FaceSearchResult])
async def search_faces_by_image(
    file: Optional[UploadFile] = File(None, description="Hochgeladene Bilddatei oder Porträtausschnitt"),
    image_path: Optional[str] = Query(None, description="Alternativ: Pfad zu einer lokalen Bilddatei"),
    limit: int = Query(default=10, ge=1, le=50, description="Maximale Anzahl an Treffern"),
    score_threshold: Optional[float] = Query(default=None, ge=-1.0, le=1.0, description="Mindest-Score"),
    face_service: FaceService = Depends(get_face_service),
    qdrant: QdrantService = Depends(get_qdrant_service),
):
    """
    Nimmt ein hochgeladenes Bild oder einen Crop, extrahiert das Gesicht
    und sucht die ähnlichsten Gesichter in `archive_faces`.
    Unterstützt sowohl POST (Multipart File Upload) als auch GET.
    """
    if file is not None:
        try:
            content = await file.read()
            img = Image.open(io.BytesIO(content))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Ungültige Bilddatei: {str(e)}")
    elif image_path:
        path = validate_safe_image_path(image_path)
        try:
            img = Image.open(path)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Fehler beim Öffnen des Bildes: {str(e)}")
    else:
        raise HTTPException(
            status_code=400,
            detail="Bitte übergeben Sie eine Datei im Multipart-Body oder den Parameter 'image_path'.",
        )

    detected_faces = face_service.extract_faces(img)
    if not detected_faces:
        raise HTTPException(
            status_code=404,
            detail="Auf dem übergebenen Bild konnte kein Gesicht erkannt werden.",
        )

    # Gesicht mit der höchsten Konfidenz auswählen
    best_face = max(detected_faces, key=lambda f: f["det_score"])
    face_vector = best_face["embedding"]

    hits = qdrant.search_faces(
        query_vector=face_vector,
        limit=limit,
        score_threshold=score_threshold,
    )

    results = []
    for hit in hits:
        payload = hit.payload or {}
        orig_w = payload.get("orig_width")
        orig_h = payload.get("orig_height")
        bbox = payload.get("bbox", [0, 0, 0, 0])
        bbox_pct = payload.get("bbox_percent")
        if not bbox_pct and orig_w and orig_h and bbox and len(bbox) == 4:
            x1, y1, x2, y2 = bbox
            bbox_pct = {
                "left": round((x1 / orig_w) * 100, 4),
                "top": round((y1 / orig_h) * 100, 4),
                "width": round(((x2 - x1) / orig_w) * 100, 4),
                "height": round(((y2 - y1) / orig_h) * 100, 4),
            }

        results.append(
            FaceSearchResult(
                id=str(hit.id),
                score=hit.score,
                file_path=payload.get("file_path") or payload.get("image_path", ""),
                bbox=bbox,
                bbox_percent=bbox_pct,
                orig_width=orig_w,
                orig_height=orig_h,
                det_score=payload.get("det_score", 1.0),
                cluster_id=payload.get("cluster_id"),
                label=payload.get("label"),
            )
        )
    return results


@router.get("/faces/clusters", response_model=List[ClusterResponse])
def get_clusters(
    include_preview: bool = Query(default=True, description="Vorschaubild-Pfad erzeugen"),
    include_faces: bool = Query(default=False, description="Vollständige Gesichterliste pro Cluster beilegen (Standard: False für ultraschnelles Laden)"),
    clustering_service: ClusteringService = Depends(get_clustering_service),
):
    """
    Gibt alle gefundenen Personen-Cluster zurück (inkl. Vorschaubild-URLs).
    Standardmäßig wird include_faces=False genutzt, damit auch bei 10.000+ Gesichtern
    die Übersicht in Bruchteilen einer Sekunde lädt.
    """
    if not settings.ENABLE_FACE_RECOGNITION:
        return []
    clusters = clustering_service.get_clusters(include_preview=include_preview, include_faces=include_faces)
    return clusters


@router.get("/faces/clusters/{cluster_id}/preview")
def get_cluster_preview(
    cluster_id: str,
    clustering_service: ClusteringService = Depends(get_clustering_service),
):
    """
    Liefert das gecropte Vorschaubild (JPEG) des Personen-Clusters mit Caching-Headern.
    Ermöglicht dem Browser asynchrones, schnelles Nachladen der Gesichter.
    """
    if not settings.ENABLE_FACE_RECOGNITION:
        raise HTTPException(status_code=403, detail="Biometrische Gesichtserkennung ist deaktiviert.")
    
    image_bytes = clustering_service.get_cluster_preview_bytes(cluster_id)
    if not image_bytes:
        raise HTTPException(status_code=404, detail=f"Kein Vorschaubild für Cluster '{cluster_id}' gefunden.")
    
    return Response(
        content=image_bytes,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "public, max-age=86400, immutable",
        },
    )


@router.get("/faces/clusters/{cluster_id}", response_model=ClusterResponse)
def get_cluster_details(
    cluster_id: str,
    clustering_service: ClusteringService = Depends(get_clustering_service),
):
    """
    Liefert die Detailinformationen inklusive aller zugeordneten Gesichter und Bildpfade
    für ein einzelnes Personen-Cluster on-demand.
    """
    if not settings.ENABLE_FACE_RECOGNITION:
        raise HTTPException(status_code=403, detail="Biometrische Gesichtserkennung ist deaktiviert.")
    
    cluster = clustering_service.get_cluster_details(cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail=f"Cluster '{cluster_id}' nicht gefunden.")
    return cluster



@router.post("/faces/clusters/{cluster_id}/label")
def label_cluster(
    cluster_id: str,
    request: Optional[ClusterLabelRequest] = None,
    label: Optional[str] = Query(None, description="Alternativer Query-Parameter für das Label"),
    clustering_service: ClusteringService = Depends(get_clustering_service),
):
    """
    Weist einem Personen-Cluster einen Klarnamen zu (z. B. 'Bischof Müller').
    Aktualisiert alle Gesichts-Punkte dieses Clusters in Qdrant.
    """
    if not settings.ENABLE_FACE_RECOGNITION:
        raise HTTPException(
            status_code=403,
            detail="Biometrische Gesichtserkennung ist in der Systemkonfiguration deaktiviert (ENABLE_FACE_RECOGNITION=false)."
        )

    final_label = None
    if request and request.label:
        final_label = request.label
    elif label:
        final_label = label

    if not final_label or not final_label.strip():
        raise HTTPException(status_code=400, detail="Ein nicht-leerer Klarname (Label) muss angegeben werden.")

    updated_count = clustering_service.label_cluster(cluster_id=cluster_id, label=final_label.strip())
    if updated_count == 0:
        raise HTTPException(status_code=404, detail=f"Kein Gesicht mit cluster_id '{cluster_id}' gefunden.")

    return {
        "status": "success",
        "cluster_id": cluster_id,
        "label": final_label.strip(),
        "updated_faces": updated_count,
    }


@router.post("/faces/clusters/merge")
def merge_clusters(
    request: ClusterMergeRequest,
    clustering_service: ClusteringService = Depends(get_clustering_service),
):
    """
    Führt zwei Personen-Cluster zusammen (z. B. bei Altersunterschieden oder veränderten Lichtverhältnissen).
    Alle Gesichter des Quell-Clusters werden in das Ziel-Cluster integriert.
    """
    if not settings.ENABLE_FACE_RECOGNITION:
        raise HTTPException(
            status_code=403,
            detail="Biometrische Gesichtserkennung ist in der Systemkonfiguration deaktiviert (ENABLE_FACE_RECOGNITION=false)."
        )

    if request.source_cluster_id == request.target_cluster_id:
        raise HTTPException(status_code=400, detail="Quell- und Ziel-Cluster dürfen nicht identisch sein.")

    result = clustering_service.merge_clusters(
        source_cluster_id=request.source_cluster_id,
        target_cluster_id=request.target_cluster_id,
        target_label=request.target_label,
    )

    if result.get("status") == "not_found" or result.get("merged_count", 0) == 0:
        raise HTTPException(status_code=404, detail=f"Keine Gesichter im Quell-Cluster '{request.source_cluster_id}' gefunden.")

    return result


@router.post("/faces/{face_id}/remove-from-cluster")
def remove_face_from_cluster(
    face_id: str,
    clustering_service: ClusteringService = Depends(get_clustering_service),
):
    """
    Entfernt ein fälschlicherweise zugeordnetes Gesicht aus seinem Cluster ('Nicht diese Person').
    Setzt cluster_id und label auf None und bereinigt die Personen-Liste des Elternbildes.
    """
    if not settings.ENABLE_FACE_RECOGNITION:
        raise HTTPException(
            status_code=403,
            detail="Biometrische Gesichtserkennung ist in der Systemkonfiguration deaktiviert (ENABLE_FACE_RECOGNITION=false)."
        )

    success = clustering_service.remove_face_from_cluster(face_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Gesichtspunkt '{face_id}' nicht gefunden.")

    return {
        "status": "success",
        "face_id": face_id,
        "message": "Gesicht erfolgreich aus Cluster entfernt.",
    }


@router.post("/faces/clusters/run", response_model=ClusteringRunResponse)
def trigger_clustering(
    eps: float = Query(default=0.55, ge=0.01, le=1.0, description="DBSCAN Epsilon (Cosine-Distanz)"),
    min_samples: int = Query(default=2, ge=1, description="Mindestanzahl Gesichter pro Cluster"),
    clustering_service: ClusteringService = Depends(get_clustering_service),
):
    """
    Führt das DBSCAN-Clustering (eps=0.55, min_samples=2, metric='cosine')
    für alle Gesichter in `archive_faces` aus und aktualisiert die `cluster_id` in Qdrant.
    """
    if not settings.ENABLE_FACE_RECOGNITION:
        raise HTTPException(
            status_code=403,
            detail="Biometrische Gesichtserkennung ist in der Systemkonfiguration deaktiviert (ENABLE_FACE_RECOGNITION=false)."
        )

    result = clustering_service.run_clustering(eps=eps, min_samples=min_samples)
    return result


@router.get("/images/serve")
def serve_image(
    path: str = Query(..., description="Lokaler Dateipfad des Archivbildes"),
    max_dim: Optional[int] = Query(default=None, description="Optional: Maximale Kantenlänge für schnelle Vorschau"),
):
    """
    Liefert ein Bild aus dem lokalen Archiv-Dateisystem sicher aus.
    Konvertiert TIFF-Bilder und CMYK automatisch für den Browser in JPEG und nutzt den Thumbnail-Cache.
    """
    file_path = validate_safe_image_path(path)
    suffix = file_path.suffix.lower()

    # Wenn TIFF oder Skalierung gewünscht ist, über den Thumbnail-Cache in JPEG ausliefern
    if suffix in [".tif", ".tiff"] or max_dim is not None:
        dim = max_dim if max_dim is not None else 1600
        try:
            thumb_bytes = thumbnail_service.get_or_create_thumbnail(file_path, max_dim=dim)
            return Response(
                content=thumb_bytes,
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=86400"},
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Fehler beim Aufbereiten des Bildes: {e}")

    media_type = "image/jpeg"
    if suffix == ".png":
        media_type = "image/png"
    elif suffix == ".webp":
        media_type = "image/webp"

    return FileResponse(path=file_path, media_type=media_type, headers={"Cache-Control": "public, max-age=86400"})


@router.post("/images/rotate")
def rotate_image(
    req: RotateImageRequest,
    rotation_service = Depends(get_image_rotation_service),
):
    """
    Dreht eine Bilddatei verlustfrei (z.B. 90° im Uhrzeigersinn oder gegen den Uhrzeigersinn).
    - JPEG: Echtes physikalisch verlustfreies DCT-Transponieren via jpegtran mit Erhalt aller Metadaten
    - PNG/TIFF/WebP: Mathematisch verlustfreie Transformation
    - Normalisierung des EXIF-Orientation-Tags auf 1
    - Aktualisiert anschließend automatisch den Thumbnail-Cache und den Qdrant-Index (CLIP & Gesichter).
    """
    file_path = validate_safe_image_path(req.path)
    try:
        result = rotation_service.rotate_image(file_path=file_path, angle=req.angle)
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Fehler beim Drehen des Bildes (%s): %s", req.path, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fehler beim Drehen des Bildes: {e}")


@router.get("/images/details")
def get_image_details(
    path: str = Query(..., description="Lokaler Dateipfad des Archivbildes"),
    qdrant: QdrantService = Depends(get_qdrant_service),
):
    """
    Gibt Metadaten und alle in diesem Bild erkannten Gesichter (inkl. Bounding Boxes und Cluster-Infos) zurück.
    """
    file_path = validate_safe_image_path(path)

    try:
        with Image.open(file_path) as raw_img:
            img = ImageOps.exif_transpose(raw_img)
            width, height = img.size
    except Exception:
        width, height = 0, 0

    abs_path_str = str(file_path.resolve())
    face_records, _ = qdrant.client.scroll(
        collection_name=settings.COLLECTION_FACES,
        scroll_filter=rest_models.Filter(
            should=[
                rest_models.FieldCondition(key="file_path", match=rest_models.MatchValue(value=abs_path_str)),
                rest_models.FieldCondition(key="image_path", match=rest_models.MatchValue(value=abs_path_str)),
            ]
        ),
        limit=100,
        with_payload=True,
        with_vectors=False,
    )

    faces = []
    for r in face_records:
        p = r.payload or {}
        orig_w = p.get("orig_width") or width
        orig_h = p.get("orig_height") or height
        bbox = p.get("bbox", [])
        bbox_pct = p.get("bbox_percent")
        if not bbox_pct and orig_w and orig_h and bbox and len(bbox) == 4:
            x1, y1, x2, y2 = bbox
            bbox_pct = {
                "left": round((x1 / orig_w) * 100, 4),
                "top": round((y1 / orig_h) * 100, 4),
                "width": round(((x2 - x1) / orig_w) * 100, 4),
                "height": round(((y2 - y1) / orig_h) * 100, 4),
            }

        faces.append({
            "face_id": str(r.id),
            "bbox": bbox,
            "bbox_percent": bbox_pct,
            "orig_width": orig_w,
            "orig_height": orig_h,
            "det_score": p.get("det_score", 1.0),
            "cluster_id": p.get("cluster_id"),
            "label": p.get("label"),
        })

    # Metadaten aus Qdrant abrufen oder direkt aus Bild/Sidecar extrahieren
    metadata: Dict[str, Any] = {}
    try:
        img_records, _ = qdrant.client.scroll(
            collection_name=settings.COLLECTION_IMAGES,
            scroll_filter=rest_models.Filter(
                should=[
                    rest_models.FieldCondition(key="file_path", match=rest_models.MatchValue(value=abs_path_str)),
                    rest_models.FieldCondition(key="image_path", match=rest_models.MatchValue(value=abs_path_str)),
                ]
            ),
            limit=1,
            with_payload=True,
            with_vectors=False,
        )
        if img_records and img_records[0].payload:
            payload = img_records[0].payload
            metadata = payload.get("metadata") or {
                "title": payload.get("title"),
                "creator": payload.get("creator"),
                "date": payload.get("date"),
                "description": payload.get("description"),
                "signature": payload.get("signature"),
                "copyright": payload.get("copyright"),
                "keywords": payload.get("keywords", []),
            }
    except Exception:
        pass

    # Fallback: Direkt aus Datei und eventuellen Sidecars extrahieren
    if not metadata or not any(metadata.values()):
        metadata = metadata_service.extract_metadata(file_path)

    return {
        "file_path": abs_path_str,
        "file_name": file_path.name,
        "width": width,
        "height": height,
        "faces": faces,
        "metadata": metadata,
    }


@router.get("/search/similar", response_model=List[SemanticSearchResult])
def search_similar_images(
    image_path: str = Query(..., description="Pfad zum Referenzbild"),
    limit: int = Query(default=20, ge=1, le=100),
    stack_variants: bool = Query(default=True, description="Fasst Varianten und Duplikate zu Bildstapeln zusammen"),
    clip_service: ClipService = Depends(get_clip_service),
    qdrant: QdrantService = Depends(get_qdrant_service),
    variant_service: VariantService = Depends(get_variant_service),
):
    """
    Sucht optisch ähnliche Bilder zu einem vorhandenen Archivbild mittels CLIP-Embedding.
    """
    path = validate_safe_image_path(image_path)

    try:
        image_vector = clip_service.embed_image(path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler bei der Vektorisierung: {e}")

    fetch_limit = limit * 2 if stack_variants else limit
    hits = qdrant.search_images(query_vector=image_vector, limit=fetch_limit)
    results = []
    for hit in hits:
        p = hit.payload or {}
        fp = p.get("file_path") or p.get("image_path", "")
        results.append(
            SemanticSearchResult(
                id=str(hit.id),
                score=hit.score,
                file_path=fp,
                file_name=p.get("file_name") or p.get("filename") or Path(fp).name,
                title=p.get("title"),
                creator=p.get("creator"),
                date=p.get("date"),
                signature=p.get("signature"),
                description=p.get("description"),
                keywords=p.get("keywords") or [],
                persons=p.get("persons") or [],
            )
        )

    if stack_variants:
        results = variant_service.stack_search_results(results, similarity_threshold=0.92)

    return results[:limit]


@router.post("/search/crop", response_model=List[SemanticSearchResult])
def search_by_crop(
    request: CropSearchRequest,
    clip_service: ClipService = Depends(get_clip_service),
    qdrant: QdrantService = Depends(get_qdrant_service),
    variant_service: VariantService = Depends(get_variant_service),
):
    """
    Crop-to-Search (Bildausschnitt-Suche):
    Schneidet den vom Archivar gewählten Bildausschnitt serverseitig zu,
    erzeugt das 512-dim OpenCLIP-Embedding und sucht visuell ähnliche Details im Gesamtarchiv.
    """
    file_path = validate_safe_image_path(request.image_path)

    try:
        img = load_image_rgb(file_path)
        img_w, img_h = img.size

        if request.is_normalized:
            left = max(0, int(request.x * img_w))
            top = max(0, int(request.y * img_h))
            crop_w = int(request.width * img_w)
            crop_h = int(request.height * img_h)
        else:
            left = max(0, int(request.x))
            top = max(0, int(request.y))
            crop_w = int(request.width)
            crop_h = int(request.height)

        right = min(img_w, left + crop_w)
        bottom = min(img_h, top + crop_h)

        if (right - left) < 6 or (bottom - top) < 6:
            raise HTTPException(
                status_code=400,
                detail="Der gewählte Ausschnitt ist zu klein (mindestens 6x6 Pixel erforderlich)."
            )

        cropped = img.crop((left, top, right, bottom))
        crop_vector = clip_service.embed_image(cropped)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler bei der Bildausschnitt-Verarbeitung: {e}")

    fetch_limit = request.limit * 2 if request.stack_variants else request.limit
    hits = qdrant.search_images(
        query_vector=crop_vector,
        limit=fetch_limit,
        score_threshold=request.score_threshold,
    )

    results = []
    for hit in hits:
        p = hit.payload or {}
        fp = p.get("file_path") or p.get("image_path", "")
        results.append(
            SemanticSearchResult(
                id=str(hit.id),
                score=round(hit.score, 4),
                file_path=fp,
                file_name=p.get("file_name") or p.get("filename") or Path(fp).name,
                title=p.get("title"),
                creator=p.get("creator"),
                date=p.get("date"),
                signature=p.get("signature"),
                description=p.get("description"),
                keywords=p.get("keywords") or [],
                persons=p.get("persons") or [],
            )
        )

    if request.stack_variants:
        results = variant_service.stack_search_results(results, similarity_threshold=0.92)

    return results[:request.limit]


@router.get("/images/variants")
def get_image_variants(
    path: str = Query(..., description="Dateipfad des Referenzbildes"),
    limit: int = Query(default=25, ge=1, le=100),
    score_threshold: float = Query(default=0.88, ge=0.5, le=1.0),
    variant_service: VariantService = Depends(get_variant_service),
):
    """
    Sucht gezielt alle Duplikate, Größen-/Ausschnittsvarianten und Serienaufnahmen
    zu einem ausgewählten Bild im Gesamtbestand.
    """
    file_path = validate_safe_image_path(path)
    return variant_service.find_variants_for_image(
        image_path=file_path,
        limit=limit,
        score_threshold=score_threshold,
    )


@router.get("/archive/variant-clusters")
def get_variant_clusters(
    eps: float = Query(default=0.075, ge=0.01, le=0.5, description="DBSCAN Epsilon für Bildvektoren"),
    min_samples: int = Query(default=2, ge=2, le=20, description="Mindestanzahl Bilder pro Stapel"),
    limit_groups: int = Query(default=100, ge=1, le=500),
    variant_service: VariantService = Depends(get_variant_service),
):
    """
    Liefert archivweite Duplikat- und Variantengruppen (Serienaufnahmen, Repros),
    damit Archivare redundante oder zusammenhängende Scans überblicken können.
    """
    return variant_service.get_archive_variant_clusters(
        eps=eps,
        min_samples=min_samples,
        limit_groups=limit_groups,
    )


@router.delete("/images/record")
def delete_image_record(
    path: Optional[str] = Query(None, description="Dateipfad des aus dem Index zu entfernenden Bildes"),
    image_id: Optional[str] = Query(None, description="Qdrant Point-ID des Bildes"),
    qdrant: QdrantService = Depends(get_qdrant_service),
):
    """
    Löscht ein Bild und alle assoziierten Gesichtsvektoren aus Qdrant (Recht auf Vergessenwerden, Art. 17 DSGVO).
    """
    if not path and not image_id:
        raise HTTPException(status_code=400, detail="Entweder 'path' oder 'image_id' muss angegeben werden.")

    target_ids = []
    target_paths = []
    if image_id:
        target_ids.append(image_id)
    if path:
        target_paths.append(str(Path(path).resolve()))

    qdrant.delete_images(target_ids)
    qdrant.delete_faces_by_parent_images(target_ids, file_paths=target_paths)
    return {
        "status": "success",
        "deleted_image_ids": target_ids,
        "deleted_paths": target_paths,
    }
