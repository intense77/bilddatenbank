# Bedienungsanleitung: Lokales Bildarchiv-Suchsystem

Ein datensparsames, ressourcenschonendes und vollständig lokales Suchsystem für historische Bild- und Fotoarchive mit **semantischer Freitextsuche (OpenCLIP)**, **archivischer Metadaten-Extraktion (EXIF/IPTC/XMP/JSON-Sidecars)** und **automatischer Personen- und Gesichtserkennung (ArcFace & DBSCAN-Clustering)**.

---

## Inhaltsverzeichnis
1. [Überblick & Funktionsweise](#1-überblick--funktionsweise)
2. [System starten & beenden](#2-system-starten--beenden)
3. [Eigene Bildbestände einlesen (Indexierung)](#3-eigene-bildbestände-einlesen-indexierung)
4. [Archivische Metadaten & JSON-Sidecars](#4-archivische-metadaten--json-sidecars)
5. [Nutzung des Web-Frontends](#5-nutzung-des-web-frontends)
6. [Häufige Fragen & Besonderheiten](#6-häufige-fragen--besonderheiten)
7. [Wartung, Datensicherung & Fehlerbehebung](#7-wartung-datensicherung--fehlerbehebung)

---

## 1. Überblick & Funktionsweise

### Was macht dieses System?
Klassische Archivdatenbanken verlangen, dass jedes Foto händisch mit starren Schlagworten (Tags) verschlagwortet wird. Fehlt ein Schlagwort oder Schreibvarianten, bleibt das Bild unauffindbar. 

Dieses System kombiniert klassische Erschließungsdaten mit modernen **lokalen KI-Modellen**:
* **OpenCLIP (ViT-B-32):** Versteht visuelle Konzepte, Szenen, Architekturen und Gegenstände in Bildern. Sie können in natürlicher Sprache suchen (*„gotischer Altar“*, *„Soldaten im Schützengraben“*, *„Marktplatz mit Kutsche“*), ohne dass diese Begriffe vorher eingetippt wurden.
* **Archivische Metadaten-Fusion:** Liest automatisch vorhandene Bildheader (EXIF, TIFF-Tags, IPTC Core, XMP/Dublin Core) sowie kuratierte Begleitdateien (JSON-Sidecars) ein und stellt diese strukturiert dar.
* **InsightFace (ArcFace & RetinaFace):** Erkennt Gesichter auf historischen Fotos, selbst bei gealterten, kontrastarmen oder beschädigten Scans (optional aktivierbar).
* **DBSCAN-Clustering:** Gruppiert mehrfach auftretende Gesichter vollautomatisch zu Personen-Clustern. Sie können einer Person einmalig einen Namen zuweisen (*„Bischof Müller“*), und alle Fundstellen im Archiv werden synchronisiert.
* **100 % lokal & datensparsam:** Keine Cloud, keine externen APIs, keine CDNs. Alle Daten und Vektoren verbleiben ausschließlich auf Ihrem Rechner. Standardmäßig ist die biometrische Gesichtserkennung deaktiviert (DSGVO Art. 9).

---

## 2. System starten & beenden

Das System besteht aus zwei Komponenten:
1. **Qdrant (Vektordatenbank):** Speichert die mathematischen Merkmalsvektoren persistent im Ordner `./qdrant_storage`.
2. **FastAPI-Server:** Stellt die Suchlogik, die Metadaten-Dienste und die Weboberfläche bereit.

### Starten

Öffnen Sie ein Terminal im Projektverzeichnis (`/home/norbert/Bilderdatenbank`):

```bash
cd /home/norbert/Bilderdatenbank

# 1. Vektordatenbank Qdrant starten
./start_qdrant.sh
# alternativ: docker compose up -d

# 2. Webserver starten
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Öffnen Sie nun Ihren Webbrowser (z. B. Firefox oder Chromium):
* **Web-Frontend:** [http://localhost:8000/](http://localhost:8000/)
* **API-Dokumentation (Swagger UI):** [http://localhost:8000/docs](http://localhost:8000/docs)
* **Qdrant-Datenbank-Dashboard:** [http://localhost:6333/dashboard](http://localhost:6333/dashboard)

### Beenden

* Den Webserver im Terminal mit `Strg + C` beenden.
* Die Datenbank stoppen:
  ```bash
  docker compose stop
  ```

---

## 3. Eigene Bildbestände einlesen (Indexierung)

Das Einlesen neuer oder bestehender Bildordner erfolgt über das CLI-Skript `indexer.py`.

### Grundbefehle

```bash
# 1. Standard: Nur semantische Bild- & Metadatensuche (ressourcenschonend, DSGVO-konform)
.venv/bin/python indexer.py --source-dir /pfad/zu/den/archivbildern

# 2. Mit biometrischer Gesichtserkennung & automatischem Personen-Clustering
.venv/bin/python indexer.py --source-dir /pfad/zu/den/archivbildern --enable-faces --cluster-faces

# 3. Synchronisation: Gelöschte Dateien aus dem Index entfernen und neue aufnehmen
.venv/bin/python indexer.py --source-dir /pfad/zu/den/archivbildern --sync
```

### Parameter-Übersicht

| Parameter | Beschreibung |
| :--- | :--- |
| `--source-dir /pfad` | **(Pflicht)** Pfad zum Ordner mit Bilddateien. Durchsucht automatisch alle Unterordner rekursiv. |
| `--enable-faces` | Erzwingt die biometrische Gesichtserkennung (InsightFace/ArcFace) für diesen Lauf. |
| `--skip-faces` | Deaktiviert die Gesichtserkennung explizit (spart ~1,5–2 GB Arbeitsspeicher). |
| `--cluster-faces` | Führt nach dem Einlesen automatisch das DBSCAN-Clustering durch, um erkannte Personen zusammenzufassen. |
| `--prune` | **Bereinigung (Art. 17 DSGVO)**: Löscht Vektoren aus Qdrant, deren Bilddateien im Quellordner nicht mehr existieren. |
| `--sync` | **Vollständige Synchronisation**: Führt erst `--prune` aus und liest anschließend neue Bilder ein. |
| `--batch-size 32` | Anzahl der Bilder pro Rechenschritt (Standard: 32). |
| `--dry-run` | Vorschau: Scannt den Ordner und zeigt neue/gelöschte Dateien an, ohne Änderungen in der DB vorzunehmen. |
| `--force` | Erzwingt die Neuindexierung bereits eingelesener Dateien. |

### Unterstützte Dateiformate
* `.jpg`, `.jpeg`
* `.png`
* `.webp`
* `.tif`, `.tiff` (auch historische Drucke, Großformate und CMYK-Scans)

> [!NOTE]
> **Inkrementelle Speicherung & Idempotenz:** Das Skript erzeugt für jeden relativen Dateipfad eine feste UUIDv5. Wenn Sie später neue Bilder in denselben Ordner ablegen und den Befehl erneut starten, werden **nur neu hinzugekommene Bilder** berechnet. Bereits vorhandene Bilder werden übersprungen.

---

## 4. Archivische Metadaten & JSON-Sidecars

Für wissenschaftliche Archive ist die Erhaltung und Verknüpfung von Fachmetadaten unerlässlich. Das System liest Metadaten aus mehreren Quellen ein und führt sie zusammen:

### Automatisch extrahierte Quellen
1. **EXIF & TIFF-Header:** Erstellungsdatum (`DateTimeOriginal`), Urheber (`Artist`), Beschreibung (`ImageDescription`), Inventarnummer/Signatur (`DocumentName`, `ImageID`) und Copyright.
2. **IPTC Core:** Titel (`object_name`, `headline`), Urheber (`byline`), Nachweis (`credit`), Schlagwörter (`keywords`) und Erstellungsdatum (`date_created`).
3. **XMP / Dublin Core:** Aus eingebetteten XML-Blöcken (`dc:title`, `dc:creator`, `dc:date`, `dc:description`, `dc:rights`, `dc:subject`).

### Kuratierte JSON-Sidecars (Begleitdateien)
In der musealen Praxis enthalten TIFF-Scans oft veraltete oder scannergenerierte EXIF-Angaben. Über JSON-Begleitdateien können Archivare korrigierte und erweiterte Angaben hinterlegen, **ohne die Master-Bilddatei antasten zu müssen**.

Legen Sie im gleichen Verzeichnis wie das Bild eine Begleitdatei ab:
* Für `glasplatte_042.tif`: entweder `glasplatte_042.json` oder `glasplatte_042.tif.json`.

**Beispiel einer JSON-Sidecar-Datei:**
```json
{
  "title": "Historischer Marktplatz mit Wochenmarkt",
  "creator": "Atelier Heinrich Kramer",
  "date": "1912-09-18",
  "signature": "Hist-Archiv-1912-A42",
  "description": "Blick von der alten Rathausgalerie auf den belebten Wochenmarkt mit Ochsenkarren und Marktständen.",
  "keywords": ["Marktplatz", "Wochenmarkt", "Kutsche", "Rathaus", "Bürgertum"],
  "copyright": "Gemeinfrei (Public Domain Mark 1.0)"
}
```

> [!TIP]
> Angaben in der JSON-Sidecar-Datei haben Vorrang vor Kamera-Headerdaten und überschreiben fehlerhafte Scanner-Angaben.

---

## 5. Nutzung des Web-Frontends

Nach dem Start erreichen Sie die Oberfläche unter **[http://localhost:8000/](http://localhost:8000/)**.

### Tab 1: Freitext-Suche
1. **Suchleiste:** Geben Sie ein Motiv, ein Thema oder eine Epoche ein (z. B. *„gotischer Altar“*, *„Marktplatz 1910“*, *„Soldaten im Feld“*).
2. **Relevanz-Filter (Schwellenwert):**
   * *Standard (ab 23 %)*: Filtert unpassende Zufallstreffer aus (empfohlen).
   * *Streng (ab 25 %)*: Zeigt nur sehr eindeutige Treffer.
   * *Locker (ab 20 %)*: Zeigt auch Bilder mit entfernter thematischer Ähnlichkeit.
   * *Alle Treffer*: Zeigt stets die nächsten mathematischen Nachbarn.
3. **Ergebnis-Karten:** Jedes Bild zeigt den berechneten Score (z. B. `78% Score`), den archivalischen Titel, den Dateinamen sowie Tags für Datierung und Signatur.

### Tab 2: Personen & Cluster
*(Nur aktiv, wenn `ENABLE_FACE_RECOGNITION=true` gesetzt ist)*
1. **Cluster-Übersicht:** Zeigt runde Porträtausschnitte aller Gesichter, die die KI als dieselbe Person identifiziert hat.
2. **Cluster ansehen:** Klick auf eine Person öffnet die Detailansicht mit allen Archivbildern, auf denen die Person vorkommt. Das Gesicht wird auf dem Bild mit einer Markierungsbox hervorgehoben.
3. **Klarname zuweisen:** Tragen Sie den Personennamen ein (z. B. *„Bischof Müller“*) und klicken Sie auf **Speichern**. Der Name wird allen Gesichtern dieser Person in der Datenbank zugewiesen.
4. **Cluster neu berechnen:** Ein Klick auf *„Cluster neu berechnen“* führt das DBSCAN-Clustering erneut aus.

### Bild-Detailansicht (Modal)
Klick auf ein beliebiges Bild öffnet die vergrößerte Detailansicht:
* **Bild & Bounding Boxes:** Anzeige des Bildes mit interaktiven Markierungen aller erkannten Gesichter.
* **Archiv-Metadaten Seitenleiste:** Strukturierte Übersicht mit Titel, Datierung, Urheber, Signatur, Abmessungen, Beschreibung und Lizenz.
* **Interaktive Schlagwort-Chips:** Ein Klick auf ein Schlagwort (z. B. `#Wochenmarkt`) schließt das Modal und führt sofort die entsprechende Suche aus.
* **Ähnliche Bilder suchen:** Nutzt das CLIP-Embedding des Fotos als Referenz und sucht optisch verwandte Motive im Archiv.
* **Originaldatei öffnen:** Öffnet den hochauflösenden Scan in einem neuen Browsertab.

---

## 6. Häufige Fragen & Besonderheiten

### Warum erhalte ich Treffer für Wörter, die im Bild gar nicht vorkommen?
Im Gegensatz zu einer reinen Textsuche in einer Datenbank arbeitet eine Vektorsuche nach dem Prinzip der **„Nächsten Nachbarn“ (k-NN)**:
* Jedes Bild und jede Suchanfrage ist ein Punkt im 512-dimensionalen Vektorraum.
* Wenn Sie nach *„Dampflokomotive“* suchen, aber kein Bild eine Lokomotive zeigt, ermittelt die Datenbank diejenigen Bilder, die dieser Anfrage noch am wenigsten unähnlich sind.
* **Lösung:** Nutzen Sie den Relevanz-Filter in der Suchleiste (*„Standard (ab 23%)“*). Dann erhalten Sie bei fehlenden Motiven korrekterweise **0 Treffer**.

### Funktionieren auch TIFF-Dateien im Browser?
Ja. Webbrowser wie Firefox oder Chrome können TIFF-Dateien gewöhnlich nicht direkt anzeigen. Das Backend wandelt TIFF- und CMYK-Bilder für das Web-Frontend **automatisch und verlustfrei über einen Thumbnail-Cache nach JPEG um**. Ihre Originaldateien auf der Festplatte bleiben unverändert.

### Werden GPU / CUDA unterstützt?
Ja. Das System prüft beim Start via PyTorch, ob eine kompatible NVIDIA-Grafikkarte verfügbar ist. Ist keine GPU vorhanden oder reicht der Videospeicher nicht aus, schaltet das System automatisch auf optimierte CPU-Inferenz um.

---

## 7. Wartung, Datensicherung & Fehlerbehebung

### Wo liegen die Daten?
* **Die Vektoren und Metadaten:** Liegen im Ordner `./qdrant_storage` im Projektverzeichnis.
* **Der Thumbnail-Cache:** Liegt im Ordner `.cache/thumbnails/` und kann bei Bedarf jederzeit gefahrlos gelöscht werden.
* **Ihre Originalbilder:** Verbleiben immer an ihrem ursprünglichen Speicherort (z. B. im Archiv-Verzeichnis). Das System speichert in Qdrant lediglich relative/absolute Pfade und Merkmalsvektoren.

### Backup erstellen
Um alle indizierten Merkmale, erkannten Gesichter und vergebenen Personennamen zu sichern:
1. Qdrant stoppen: `docker compose stop`
2. Den Ordner kopieren:
   ```bash
   cp -r /home/norbert/Bilderdatenbank/qdrant_storage /pfad/zum/backup/
   ```
3. Qdrant wieder starten: `docker compose start`

### Fehlerbehebung

#### „Verbindung zum Server unter localhost:8000 fehlgeschlagen“
* Der FastAPI-Server läuft noch nicht. Starten Sie ihn im Terminal:
  ```bash
  cd /home/norbert/Bilderdatenbank
  .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
  ```

#### „Verbindung zu Qdrant fehlgeschlagen“
* Der Docker-Container von Qdrant ist gestoppt. Starten Sie ihn mit:
  ```bash
  cd /home/norbert/Bilderdatenbank
  ./start_qdrant.sh
  ```
  Prüfen Sie den Status im Browser unter [http://localhost:6333/dashboard](http://localhost:6333/dashboard).
