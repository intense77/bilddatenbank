# Lokales, datensparsames Bildarchiv-Suchsystem

Ein datensparsames, ressourcenschonendes und vollständig lokales Suchsystem für historische Bild- und Fotoarchive (GLAM-Bereich: Museen, Archive, Bibliotheken) basierend auf Vektor-Embeddings (OpenCLIP & ArcFace/InsightFace), archivischer Metadaten-Extraktion (EXIF/IPTC/XMP/JSON-Sidecars) und der Vektordatenbank Qdrant.

---

## 🏛️ Archivfachliche & Technische Kernmerkmale

* **100 % Lokaler Betrieb & Datenschutz by Design (Art. 5 / 9 DSGVO):**
  * Keine Cloud-Verbindungen, keine externen APIs, keine externen CDNs oder Tracking-Skripte.
  * Standardmäßig **deaktivierte biometrische Gesichtserkennung** (`ENABLE_FACE_RECOGNITION=false`) zur Schonung von Arbeitsspeicher (~1,5–2 GB RAM/VRAM-Einsparung) und zur strikten Einhaltung von Art. 9 DSGVO. Bei Bedarf granular aktivierbar.
* **Archivische Metadaten & JSON-Sidecars:**
  * Konsolidierte Extraktion aus EXIF/TIFF-Headern, IPTC Core, XMP (Dublin Core) und JSON-Begleitdateien (`datei.json` / `datei.ext.json`).
  * Indexierung standardisierter Kernfelder: Titel/Objektbezeichnung, Datierung, Urheber/Fotograf, Archivsignatur/Inventarnummer, Beschreibung, Rechte/Lizenz und Schlagwörter.
  * Anklickbare Schlagwort-Filterchips in der Web-Oberfläche für explorative Recherche.
* **Personen-Kuratierung & Hybride Freitextsuche:**
  * Automatisches DBSCAN-Personen-Clustering mit Klarnamenzuweisung (*„Bischof Ulrich“*).
  * Integrierte Kuratierungs-Werkzeuge: **Cluster-Merge** zum Zusammenführen getrennter Bestände und **Cluster-Split / Ausschluss** (*„Nicht diese Person“*) zum Entfernen falsch zugeordneter Porträts.
  * Hybride Relevanz-Verschmelzung: Benannte Personen werden in der normalen Freitextsuche automatisch erkannt und mit 100 % Relevanz und Personen-Badge ganz oben platziert.
* **Zweiblatt-Logik (Recto / Verso) & 3D-Karten-Flip:**
  * Automatische Paar-Erkennung zusammengehöriger Vorder- und Rückseiten (`_r`/`_v`, `_recto`/`_verso`, `_vorderseite`/`_rueckseite`, `_front`/`_back`, `_a`/`_b`, `_01`/`_02`).
  * Das Vorderseiten-Foto ist das visuelle Hauptobjekt; handschriftliche Notizen, Fotografenstempel und Datierungen der Rückseite werden als Primär-Metadaten verknüpft und in der Volltextsuche indexiert.
  * Interaktiver 3D-Karten-Flip im Bild-Modal (Button `🔁 Rückseite` bzw. Taste `V` / `U`) zum nahtlosen Wenden zwischen Bildmotiv und Belegträger.
* **IIIF Image API 3.0 & Deep Zoom:**
  * Standardkonformer lokaler IIIF 3.0 Kacheldienst (`/iiif/{id}/...` und `/api/iiif/{id}/...`) mit SSD-Tile-Cache in `.cache/iiif_tiles/`.
  * Flüssiges Hineinzoomen bis auf feinste Details (historische Glasplatten, Handschriften, Paramente) via lokalem OpenSeadragon-Viewer (100 % offline, datenschutzkonform).
* **Non-destruktive Bildoptimierung & Verlustfreies Drehen:**
  * Werkbank für non-destruktive Parameter (Helligkeit, Kontrast, Gamma, Schärfe, Negativ-Invertierung) mit interaktivem Vorher/Nachher Split-Slider.
  * Verlustfreie 90°-Drehung historischer JPEGs (JPEG DCT ohne Neukompression).
* **Hardware-Profiling & System-Tuning:**
  * Automatische Erkennung der System-Hardware (CPU-Kerne, RAM, GPU/VRAM) und dynamische Anpassung von Worker-Threads und Batch-Größen.
* **Personen-Kuratierung & Hybride Freitextsuche:**
  * Automatisches DBSCAN-Personen-Clustering mit Klarnamenzuweisung (*„Bischof Ulrich“*).
  * Integrierte Kuratierungs-Werkzeuge: **Cluster-Merge** zum Zusammenführen getrennter Bestände und **Cluster-Split / Ausschluss** (*„Nicht diese Person“*) zum Entfernen falsch zugeordneter Porträts.
  * Hybride Relevanz-Verschmelzung: Benannte Personen werden in der normalen Freitextsuche automatisch erkannt und mit 100 % Relevanz und Personen-Badge ganz oben platziert.
  * Vollautomatische EXIF-Orientierungs-Entzerrung (`PIL.ImageOps.exif_transpose`) und normalisierte Prozent-Bounding-Boxes für fehlerfreies Rendering in allen Browsern.
* **Ressourcen- & Speicheroptimierung:**
  * Automatischer Thumbnail- und Bildausschnitt-Cache (`.cache/thumbnails/`) mit MD5-Invalidierung zur schnellen Anzeige historischer Großformate und TIFF-Dateien.
  * Optimierte Vektorsuche und speicherschonendes Clustering.
* **Recht auf Vergessenwerden & Synchronisation (Art. 17 DSGVO):**
  * Integrierte Pruning-Funktion (`indexer.py --prune` bzw. `POST /api/system/prune`) zur Bereinigung gelöschter Bestände.
  * Endpunkt zur punktgenauen Löschung einzelner Bild- und Gesichtsvektoren (`DELETE /images/record`).
* **Sicherheit:**
  * Strikte Pfad-Validierung gegen Path-Traversal-Angriffe (`app/core/security.py`) bei allen Bild- und Metadaten-Endpunkten.
  * Beschränkte CORS-Origins über Konfiguration (`CORS_ORIGINS`).

---

## 🏗️ Architektur & Komponenten

* **Backend:** FastAPI (Python 3.11, asynchron)
* **Vektordatenbank:** Qdrant (lokale Docker-Instanz, Port 6333) mit persistentem Volume (`./qdrant_storage`)
* **Metadaten- & Zweiblatt-Datenbank:** SQLite (`data/archive_metadata.db` im WAL-Modus)
* **IIIF Image Service:** IIIF Image API 3.0 konformer Dienst mit OpenSeadragon Deep Zoom
* **Modelle & Merkmalsextraktion:**
  * **OpenCLIP ViT-B-32** (512 Dimensionen, Cosine Distance) für multimodale Bild- und Freitextsuche in `archive_images`.
  * **InsightFace / ArcFace** (512 Dimensionen, Cosine Distance) für Porträterkennung und DBSCAN-Gruppierung in `archive_faces`.
  * **Pillow & Defused XML:** Extraktion von EXIF, IPTC Core, XMP (Dublin Core) und JSON-Sidecars.
* **Frontend:** 100 % lokales, responsives Single-Page-Interface (HTML5, Vanilla JS, Offline-CSS ohne externe CDN-Abhängigkeiten).
* **Hardware-Beschleunigung:** Automatischer CUDA-Support für Nvidia-GPUs mit transparentem Fallback auf CPU.

---

## 📁 Projektstruktur

```text
.
├── docker-compose.yml       # Lokale Qdrant-Vektordatenbank mit persistentem Speicher
├── start_qdrant.sh          # Hilfsskript zum Starten des Qdrant-Containers
├── requirements.txt         # Python-Abhängigkeiten
├── .env.example             # Konfigurationsvorlage (DSGVO-Schalter, Pfade, Ports)
├── indexer.py               # Leistungsfähige CLI zur Archiv-Indexierung & Bereinigung
├── benchmark.py             # System-Hardware-Benchmarking & Performance-Profiling
├── todo.md                  # Roadmap & wissenschaftliches Backlog
├── app/
│   ├── main.py              # FastAPI-Applikation & Lifespan-Handler
│   ├── core/
│   │   ├── config.py        # Pydantic-Settings & Umgebungsvariablen
│   │   ├── security.py      # Pfadvalidierung (Sandbox gegen Path Traversal)
│   │   └── system_profiler.py # Automatische Hardware-Erkennung & Performance-Tuning
│   ├── services/
│   │   ├── qdrant_service.py   # Qdrant Client, Collections & Art. 17 Pruning
│   │   ├── metadata_db.py      # SQLite Archiv-Metadatenbank (WAL-Modus)
│   │   ├── recto_verso_service.py # Zweiblatt-Logik (Recto/Verso) & Paar-Erkennung
│   │   ├── iiif_service.py     # IIIF Image API 3.0 & Pyramidales Kacheln
│   │   ├── thesaurus_service.py # Kirchlicher Fachthesaurus & Iconclass
│   │   ├── clip_service.py     # OpenCLIP Text- & Bild-Embeddings
│   │   ├── face_service.py     # InsightFace Gesichtserkennung & ArcFace
│   │   ├── clustering_service.py # DBSCAN-Personengruppierung & Namensvergabe
│   │   ├── metadata_service.py # EXIF-, IPTC-, XMP- & Sidecar-Extraktion
│   │   ├── indexing_service.py # Idempotente Indexierung via UUIDv5
│   │   └── thumbnail_service.py# Performanter Thumbnail-Cache für TIFF/JPEG
│   └── api/
│       ├── deps.py          # Dependency Injection & Lazy Service Loading
│       ├── search.py        # Such-, Cluster-, Detail- & Bildauslieferungs-Routen
│       ├── thesaurus.py     # Thesaurus- und Schlagwort-Routen
│       ├── network.py       # Beziehungs- und Netzwerkgraphen
│       └── routes/
│           ├── archive.py   # Ordner-Scan, Inkrementelle Indexierung, Zweiblatt-API
│           ├── iiif.py      # IIIF Image API 3.0 Endpunkte & Kachelauslieferung
│           └── system.py    # Health-Check, DB-Info, System-Profil & Pruning
└── static/
    ├── index.html           # Web-Frontend mit 3D-Karten-Flip & OpenSeadragon
    ├── app.js               # Anwendungslogik & Bounding-Box-Visualisierung
    ├── style.css            # Minifiziertes, 100 % lokales Stylesheet mit 3D-CSS
    ├── anleitung.html       # Interaktive Bedienungsanleitung
    ├── datenschutz.html     # DSGVO-Dokumentation & Art. 9/17 Leitfaden
    └── lizenzen.html        # Lizenzübersicht für Software & Modelle
```

---

## 🚀 Schnellstart

### 1. Vektordatenbank starten
```bash
./start_qdrant.sh
# oder alternativ: docker compose up -d
```
Die Datenbank-Weboberfläche ist unter [http://localhost:6333/dashboard](http://localhost:6333/dashboard) erreichbar.

### 2. Python-Umgebung aktivieren
```bash
source .venv/bin/activate
# Sollten Abhängigkeiten fehlen: pip install -r requirements.txt
```

### 3. Konfiguration anpassen
```bash
cp .env.example .env
# In der .env können Archivpfade und der DSGVO-Gesichtserkennungs-Schalter gesetzt werden:
# ENABLE_FACE_RECOGNITION=false   (Standard: aus)
# ARCHIVE_DATA_DIR=./data
```

### 4. Archivbestände indizieren (CLI)
```bash
# Standard: Reine semantische Bild- & Metadaten-Suche (datensparsam):
python indexer.py --source-dir /pfad/zu/den/bildern

# Mit biometrischer Gesichtserkennung & automatischem Personen-Clustering:
python indexer.py --source-dir /pfad/zu/den/bildern --enable-faces --cluster-faces

# Synchronisation (gelöschte Bilder aus Index entfernen, neue hinzufügen):
python indexer.py --source-dir /pfad/zu/den/bildern --sync

# Vorschau ohne Datenbank-Schreibzugriffe (Dry-Run):
python indexer.py --source-dir /pfad/zu/den/bildern --dry-run
```

### 5. Web-Server starten
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
* **Web-Frontend:** [http://localhost:8000/](http://localhost:8000/)
* **Interaktive API-Dokumentation (Swagger UI):** [http://localhost:8000/docs](http://localhost:8000/docs)
* **System-Health-Check:** [http://localhost:8000/api/system/health](http://localhost:8000/api/system/health)

---

## 🔍 Wichtigste API-Endpunkte

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| `GET` | `/search/semantic` | Freitextsuche in natürlicher Sprache via OpenCLIP inkl. Metadaten-Treffern. |
| `GET` | `/search/similar` | Optische Ähnlichkeitssuche zu einem vorhandenen Archivbild. |
| `GET` / `POST` | `/search/faces/by-image` | Porträt- und Gesichtssuche anhand eines Bild-Uploads oder Bildpfads. |
| `GET` | `/faces/clusters` | Abruf aller erkannten Personen-Cluster inkl. Vorschaubildern. |
| `POST` | `/faces/clusters/{id}/label` | Zuweisung eines Klarnamens zu einem Personen-Cluster. |
| `POST` | `/faces/clusters/merge` | Führt zwei Personen-Cluster zusammen (mit Namens-Konsolidierung). |
| `POST` | `/faces/{face_id}/remove-from-cluster` | Entfernt ein Gesicht aus einem Cluster („Nicht diese Person“). |
| `POST` | `/faces/clusters/run` | Ausführung des DBSCAN-Clusterings über alle erkannten Gesichter. |
| `GET` | `/images/details` | Abruf von Metadaten, Abmessungen und Gesichts-Bounding-Boxes zu einem Bild. |
| `GET` | `/images/serve` | Sichere Auslieferung von Archivbildern mit Konvertierung und Thumbnail-Cache. |
| `DELETE` | `/images/record` | DSGVO-Löschung einzelner Bilder und deren Gesichtsvektoren aus Qdrant. |
| `POST` | `/api/system/prune` | Automatische Bereinigung verwaister Qdrant-Vektoren für nicht mehr existierende Dateien. |
| `POST` | `/api/archive/upload` | Drag-and-Drop Web-Upload neuer Bilddateien und .json-Sidecars mit Sofort-Indexierung. |
| `POST` | `/api/archive/scan-folder` | Schnelle Ordner-Vorschau (Dateizählung & Beispieldateien vor dem Einlesen). |
| `POST` | `/api/archive/index-folder` | Inkrementelle Einbindung eines bestehenden Ordners ohne Verschieben (inkl. Sandbox-Registrierung). |
| `GET` | `/api/archive/registered-folders` | Liste aller autorisierten Archiv-Verzeichnisse auf dem System. |
| `GET` | `/api/archive/two-sided` | Zweiblatt-Prüfung: Liefert Verknüpfungsstatus, Partner-URL & Verso-Notizen. |
| `POST` | `/api/archive/two-sided/notes` | Speichert/aktualisiert Notizen und Transkriptionen der Rückseite. |
| `GET` | `/api/iiif/{id}/info.json` | IIIF Image API 3.0 Manifest & Bildabmessungen für OpenSeadragon. |
| `GET` | `/api/iiif/{id}/{region}/{size}/{rot}/{qual}.{fmt}` | IIIF 3.0 Dynamische Kachelauslieferung (JPEG/WebP) mit SSD-Cache. |
| `GET` | `/api/system/profile` | Hardware-Profil des Host-Systems (RAM, CPU-Kerne, GPU/VRAM, Tuning). |
| `GET` | `/api/thesaurus/suggest` | Autocomplete & Vorschläge aus dem kirchlichen Fachthesaurus. |


---

## 📄 Dokumentation & Weitergabe

Zusätzlich zu dieser Datei stehen für die Weitergabe an Archivpersonal, Museumsleitung und Datenschutzbeauftragte eigenständige Dokumente bereit:
* **[anleitung.html](anleitung.html)** / **[anleitung.md](anleitung.md)**: Ausführliche Anleitung für Archivare und Kuratoren.
* **[datenschutz.html](datenschutz.html)** / **[datenschutz.md](datenschutz.md)**: Datenschutzkonzept, TOMs und Rechtsgrundlagen (Art. 6, 9, 17, 89 DSGVO).
* **[lizenzen.html](lizenzen.html)** / **[lizenzen.md](lizenzen.md)**: Lizenzen der verwendeten Open-Source-Bibliotheken und KI-Modelle.
* **[todo.html](todo.html)** / **[todo.md](todo.md)**: Roadmap & Status aller Entwicklungsziele.
