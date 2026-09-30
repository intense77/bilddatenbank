import io
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from PIL import Image

from app.core.config import settings
from app.api.deps import (
    get_clip_service,
    get_face_service,
    get_qdrant_service,
    get_clustering_service,
)
from app.services.clip_service import ClipService, load_image_rgb
from app.services.face_service import FaceService
from app.services.qdrant_service import QdrantService
from app.services.clustering_service import ClusteringService
from qdrant_client.http import models as rest_models

router = APIRouter(tags=["Suche & Cluster"])


# --- Pydantic Modelle ---

class SemanticSearchResult(BaseModel):
    file_path: str = Field(..., description="Absoluter Dateipfad des Bildes")
    file_name: Optional[str] = Field(None, description="Dateiname")
    score: float = Field(..., description="Cosine-Ähnlichkeitsscore (0.0 bis 1.0)")
    id: str = Field(..., description="Qdrant Point ID")


class FaceSearchResult(BaseModel):
    id: str
    score: float
    file_path: str
    bbox: List[int]
    det_score: float
    cluster_id: Optional[str] = None
    label: Optional[str] = None


class ClusterLabelRequest(BaseModel):
    label: str = Field(..., min_length=1, description="Klarname der Person, z. B. 'Bischof Müller'", example="Bischof Müller")


class ClusterFaceItem(BaseModel):
    face_id: str
    file_path: Optional[str] = None
    bbox: Optional[List[int]] = None
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


# --- Endpunkte ---

@router.get("/search/semantic", response_model=List[SemanticSearchResult])
def search_semantic(
    q: str = Query(..., description="Natürlicher Suchtext (z. B. 'historischer Marktplatz', 'Soldatenporträt')"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximale Anzahl Ergebnisse"),
    score_threshold: Optional[float] = Query(default=None, ge=-1.0, le=1.0, description="Mindest-Ähnlichkeitsscore"),
    clip_service: ClipService = Depends(get_clip_service),
    qdrant: QdrantService = Depends(get_qdrant_service),
):
    """
    Vektorisiert den Suchtext via CLIP, führt Vektorsuche in `archive_images` durch
    und liefert sortierte Dateipfade + Scores.
    """
    try:
        query_vector = clip_service.embed_text(q)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler bei der Textvektorisierung: {str(e)}")

    hits = qdrant.search_images(
        query_vector=query_vector,
        limit=limit,
        score_threshold=score_threshold,
    )

    results = []
    for hit in hits:
        payload = hit.payload or {}
        file_path = payload.get("file_path") or payload.get("image_path", "")
        file_name = payload.get("file_name") or payload.get("filename") or Path(file_path).name

        results.append(
            SemanticSearchResult(
                id=str(hit.id),
                score=hit.score,
                file_path=file_path,
                file_name=file_name,
            )
        )
    return results


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
        path = Path(image_path)
        if not path.is_file():
            raise HTTPException(status_code=404, detail=f"Bilddatei nicht gefunden: {image_path}")
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
        results.append(
            FaceSearchResult(
                id=str(hit.id),
                score=hit.score,
                file_path=payload.get("file_path") or payload.get("image_path", ""),
                bbox=payload.get("bbox", [0, 0, 0, 0]),
                det_score=payload.get("det_score", 1.0),
                cluster_id=payload.get("cluster_id"),
                label=payload.get("label"),
            )
        )
    return results


@router.get("/faces/clusters", response_model=List[ClusterResponse])
def get_clusters(
    include_preview: bool = Query(default=True, description="Vorschaubild als Base64 erzeugen"),
    clustering_service: ClusteringService = Depends(get_clustering_service),
):
    """
    Gibt alle gefundenen Personen-Cluster zurück (inkl. Vorschaubildern via Bounding-Box-Crop).
    """
    clusters = clustering_service.get_clusters(include_preview=include_preview)
    return clusters


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
    result = clustering_service.run_clustering(eps=eps, min_samples=min_samples)
    return result


@router.get("/images/serve")
def serve_image(
    path: str = Query(..., description="Lokaler Dateipfad des Archivbildes"),
    max_dim: Optional[int] = Query(default=None, description="Optional: Maximale Kantenlänge für schnelle Vorschau"),
):
    """
    Liefert ein Bild aus dem lokalen Dateisystem aus.
    Konvertiert TIFF-Bilder und CMYK automatisch für den Browser in JPEG.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Bilddatei nicht gefunden.")

    suffix = file_path.suffix.lower()
    # Wenn TIFF oder Skalierung gewünscht ist, über PIL in JPEG umwandeln
    if suffix in [".tif", ".tiff"] or max_dim is not None:
        try:
            with Image.open(file_path) as raw_img:
                img = load_image_rgb(raw_img)
                if max_dim is not None and (img.width > max_dim or img.height > max_dim):
                    img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=85)
                return Response(
                    content=buffer.getvalue(),
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


@router.get("/images/details")
def get_image_details(
    path: str = Query(..., description="Lokaler Dateipfad des Archivbildes"),
    qdrant: QdrantService = Depends(get_qdrant_service),
):
    """
    Gibt Metadaten und alle in diesem Bild erkannten Gesichter (inkl. Bounding Boxes und Cluster-Infos) zurück.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Bilddatei nicht gefunden.")

    try:
        with Image.open(file_path) as img:
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
        faces.append({
            "face_id": str(r.id),
            "bbox": p.get("bbox", []),
            "det_score": p.get("det_score", 1.0),
            "cluster_id": p.get("cluster_id"),
            "label": p.get("label"),
        })

    return {
        "file_path": abs_path_str,
        "file_name": file_path.name,
        "width": width,
        "height": height,
        "faces": faces,
    }


@router.get("/search/similar", response_model=List[SemanticSearchResult])
def search_similar_images(
    image_path: str = Query(..., description="Pfad zum Referenzbild"),
    limit: int = Query(default=20, ge=1, le=100),
    clip_service: ClipService = Depends(get_clip_service),
    qdrant: QdrantService = Depends(get_qdrant_service),
):
    """
    Sucht optisch ähnliche Bilder zu einem vorhandenen Archivbild mittels CLIP-Embedding.
    """
    path = Path(image_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Bilddatei nicht gefunden: {image_path}")

    try:
        image_vector = clip_service.embed_image(path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler bei der Vektorisierung: {e}")

    hits = qdrant.search_images(query_vector=image_vector, limit=limit)
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
            )
        )
    return results
