# Lokales, datensparsames Bildarchiv-Suchsystem

Ein lokales Suchsystem für historische Bildbestände basierend auf Vektor-Embeddings (OpenCLIP & ArcFace/InsightFace) und Qdrant.

## Architektur & Komponenten

- **Backend**: FastAPI (Python 3.11)
- **Vektordatenbank**: Qdrant via Docker Compose (`./qdrant_storage`)
- **Modelle**:
  - **OpenCLIP ViT-B-32** (512 Dimensionen, Cosine Distance) für multimodale Bild- und Freitextsuche in `archive_images`.
  - **InsightFace (ArcFace)** (512 Dimensionen, Cosine Distance) für Gesichtserkennung und Porträtsuche in `archive_faces` mit Metadaten (`image_path`, `bbox`, `face_id`, `cluster_id`).
- **Hardware-Beschleunigung**: Automatischer CUDA-Support mit Fallback auf CPU.

---

## Projektstruktur

```text
.
├── docker-compose.yml       # Lokale Qdrant-Instanz mit persistentem Storage-Volume
├── requirements.txt         # Python-Abhängigkeiten (FastAPI, Qdrant, OpenCLIP, InsightFace)
├── .env.example             # Konfigurationsvorlage
├── indexer.py               # CLI-Batch-Verarbeitung für Bildarchive
└── app/
    ├── main.py              # FastAPI-Applikation & Lifespan-Handler
    ├── core/
    │   └── config.py        # Settings via pydantic-settings
    ├── services/
    │   ├── qdrant_service.py   # Qdrant Client & Collection Management
    │   ├── clip_service.py     # OpenCLIP Embeddings (Text & Bild)
    │   ├── face_service.py     # InsightFace Gesichtserkennung & ArcFace
    │   └── indexing_service.py # Verarbeitungs- & Speicherlogik
    └── api/
        ├── deps.py          # Dependency Injection (Services)
        ├── router.py        # Zentraler API Router
        └── routes/
            ├── search.py    # /api/search (text, image, face)
            └── system.py    # /api/system (health, collections)
```

---

## Schnellstart

### 1. Qdrant starten
```bash
docker compose up -d
```
Die Qdrant-Weboberfläche ist anschließend unter [http://localhost:6333/dashboard](http://localhost:6333/dashboard) erreichbar.

### 2. Python-Umgebung einrichten
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
> **Hinweis für CUDA-Unterstützung**: Falls PyTorch mit CUDA benötigt wird:
> `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121`

### 3. Konfiguration anpassen
```bash
cp .env.example .env
```

### 4. Historische Bestände indizieren (CLI)
```bash
# Bildverzeichnis mit Standardeinstellungen (Batch-Größe 32, inkl. Gesichter) indizieren:
python indexer.py --source-dir /pfad/zu/den/archivbildern

# Nur CLIP-Bildsuche (ohne Gesichtserkennung) mit angepasster Batch-Größe:
python indexer.py --source-dir /pfad/zu/den/archivbildern --batch-size 64 --skip-faces

# Vorschau der gefundenen Dateien (Dry-Run):
python indexer.py --source-dir ./data --dry-run
```

### 5. API-Server starten
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- **Web-Frontend**: [http://localhost:8000/](http://localhost:8000/)
- Swagger UI / API-Dokumentation: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health-Check: [http://localhost:8000/api/system/health](http://localhost:8000/api/system/health)

---

## API-Endpunkte

### Semantische Bildsuche
- `GET /search/semantic?q={text}&limit=20`
  Vektorisiert den Suchtext via CLIP und liefert sortierte Dateipfade + Scores aus `archive_images`.

### Gesichts-Ähnlichkeitssuche
- `GET /search/faces/by-image?limit=10` oder `POST /search/faces/by-image`
  Nimmt ein Bild/Porträtausschnitt (als Datei-Upload oder `image_path`), extrahiert das Gesicht und sucht Treffer in `archive_faces`.

### Personen-Clustering & Metadaten
- `GET /faces/clusters`
  Gibt alle gefundenen Personen-Cluster zurück (inkl. Vorschaubildern als Base64-Crop).
- `POST /faces/clusters/{cluster_id}/label`
  Weist einem Personen-Cluster einen Klarnamen zu (z. B. `{"label": "Bischof Müller"}`).
- `POST /faces/clusters/run`
  Führt das DBSCAN-Clustering (`eps=0.55`, `min_samples=2`, `metric='cosine'`) aus und aktualisiert die `cluster_id` in Qdrant.
