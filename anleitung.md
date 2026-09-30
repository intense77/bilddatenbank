# Bedienungsanleitung: Lokales Bildarchiv-Suchsystem

Ein datensparsames, vollständig lokales Suchsystem für historische Bild- und Fotoarchive mit **semantischer Freitextsuche (OpenCLIP)** und **automatischer Personen- und Gesichtserkennung (ArcFace & DBSCAN-Clustering)**.

---

## Inhaltsverzeichnis
1. [Überblick & Funktionsweise](#1-überblick--funktionsweise)
2. [System starten & beenden](#2-system-starten--beenden)
3. [Eigene Bildbestände einlesen (Indexierung)](#3-eigene-bildbestände-einlesen-indexierung)
4. [Nutzung des Web-Frontends](#4-nutzung-des-web-frontends)
5. [Häufige Fragen & Besonderheiten](#5-häufige-fragen--besonderheiten)
6. [Wartung, Datensicherung & Fehlerbehebung](#6-wartung-datensicherung--fehlerbehebung)

---

## 1. Überblick & Funktionsweise

### Was macht dieses System?
Klassische Archivdatenbanken verlangen, dass jedes Foto händisch mit Schlagworten (Tags) verschlagwortet wird. Fehlt ein Schlagwort, wird das Bild nicht gefunden. 

Dieses System nutzt moderne **lokale KI-Modelle**:
* **OpenCLIP (ViT-B-32):** Versteht visuelle Konzepte, Szenen, Architekturen und Gegenstände in Bildern. Sie können in natürlicher Sprache suchen (*„gotischer Altar“*, *„Soldaten im Schützengraben“*, *„Marktplatz mit Kutsche“*), ohne dass diese Begriffe vorher irgendwo eingetippt wurden.
* **InsightFace (ArcFace):** Erkennt Gesichter auf historischen Fotos, selbst bei gealterten oder kontrastarmen Scans.
* **DBSCAN-Clustering:** Gruppiert mehrfach auftretende Gesichter vollautomatisch zu Personen-Clustern. Sie können einer Person einmalig einen Namen zuweisen (*„Bischof Müller“*), und alle Fundstellen werden synchronisiert.
* **100 % lokal & datensparsam:** Keine Cloud, keine externen APIs. Alle Daten und Vektoren verbleiben auf Ihrem Rechner.

---

## 2. System starten & beenden

Das System besteht aus zwei Komponenten:
1. **Qdrant (Vektordatenbank):** Speichert die mathematischen Merkmalsvektoren persistent im Ordner `./qdrant_storage`.
2. **FastAPI-Server:** Stellt die Suchlogik und die Weboberfläche bereit.

### Starten

Öffnen Sie ein Terminal im Projektverzeichnis (`/home/museum/Bildersuche`):

```bash
cd /home/museum/Bildersuche

# 1. Vektordatenbank Qdrant im Hintergrund starten
docker-compose up -d

# 2. Webserver starten
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Öffnen Sie nun Ihren Browser (z. B. Firefox):
* **Web-Frontend:** [http://localhost:8000/](http://localhost:8000/)
* **API-Dokumentation (Swagger UI):** [http://localhost:8000/docs](http://localhost:8000/docs)
* **Qdrant-Datenbank-Dashboard:** [http://localhost:6333/dashboard](http://localhost:6333/dashboard)

### Beenden

* Den Webserver im Terminal mit `Strg + C` stoppen.
* Die Datenbank stoppen:
  ```bash
  docker-compose stop
  ```

---

## 3. Eigene Bildbestände einlesen (Indexierung)

Das Einlesen neuer oder bestehender Bildordner erfolgt über das CLI-Skript `indexer.py`.

### Grundbefehl

```bash
cd /home/museum/Bildersuche
.venv/bin/python indexer.py --source-dir /pfad/zu/ihren/bildern --cluster-faces
```

*Beispiel für Ihren Bilderordner:*
```bash
.venv/bin/python indexer.py --source-dir /home/museum/Bilder/Kacheln --cluster-faces
```

### Parameter-Übersicht

| Parameter | Beschreibung |
| :--- | :--- |
| `--source-dir /pfad` | **(Pflicht)** Pfad zum Ordner mit Bilddateien. Durchsucht automatisch alle Unterordner. |
| `--cluster-faces` | Führt nach dem Einlesen automatisch das DBSCAN-Clustering durch, um erkannte Personen zusammenzufassen. |
| `--skip-faces` | Überspringt die Gesichtserkennung komplett (empfohlen für reine Sach- und Architekturfotos oder zur Beschleunigung). |
| `--batch-size 32` | Anzahl der Bilder pro Rechenschritt (Standard: 32). |
| `--dry-run` | Vorschau: Scannt den Ordner und zeigt, welche Dateien gefunden werden, ohne sie in die Datenbank einzutragen. |
| `--force` | Erzwingt die Neuindexierung, auch wenn ein Bild bereits eingelesen wurde. |

### Unterstützte Dateiformate
* `.jpg`, `.jpeg`
* `.png`
* `.tif`, `.tiff` (auch historische Drucke und CMYK-Scans)

> [!NOTE]
> **Inkrementelle Speicherung:** Das Skript erzeugt für jeden relativen Dateipfad eine eindeutige Kennung. Wenn Sie später neue Bilder in denselben Ordner ablegen und den Befehl erneut starten, werden **nur die neuen Bilder** berechnet. Bereits vorhandene Bilder werden übersprungen.

---

## 4. Nutzung des Web-Frontends

Nach dem Start erreichen Sie die Oberfläche unter **[http://localhost:8000/](http://localhost:8000/)**.

### Tab 1: Freitext-Suche
1. **Suchleiste:** Geben Sie ein Motiv oder eine Szene ein (z. B. *„gotischer Altar“*, *„Marktplatz“*, *„Soldaten 1914“*).
2. **Relevanz-Filter (Schwellenwert):**
   * *Standard (ab 23 %)*: Filtert unpassende Zufallstreffer aus (empfohlen).
   * *Streng (ab 25 %)*: Zeigt nur sehr eindeutige Treffer.
   * *Locker (ab 20 %)*: Zeigt auch Bilder mit entfernter thematischer Ähnlichkeit.
   * *Alle Treffer*: Zeigt immer die nächsten Nachbarn im Archiv.
3. **Beispiel-Chips:** Schnellauswahl häufiger Suchthemen per Mausklick.
4. **Ergebnis-Karten:** Jedes gefundene Bild zeigt den berechneten Ähnlichkeitswert (z. B. `78% Score`).

### Tab 2: Personen & Cluster
1. **Cluster-Übersicht:** Zeigt runde Porträtausschnitte aller Gesichter, die die KI als dieselbe Person identifiziert hat.
2. **Cluster ansehen:** Klick auf eine Person öffnet die Detailansicht mit allen Archivbildern, auf denen die Person vorkommt.
   * Das Gesicht der Person wird auf dem Originalbild mit einer **aktiven Markierungsbox** hervorgehoben.
3. **Klarname zuweisen:** Tragen Sie oben den Namen ein (z. B. *„Bischof Müller“*) und klicken Sie auf **Speichern**. Der Name ist ab sofort im gesamten Archiv mit dieser Person verknüpft.
4. **Cluster neu berechnen:** Ein Klick auf *„Cluster neu berechnen“* führt den DBSCAN-Algorithmus erneut aus (z. B. nachdem neue Porträts eingelesen wurden).

### Bild-Detailansicht (Modal)
* Klick auf ein beliebiges Bild in der Suche oder im Personen-Tab öffnet eine vergrößerte Ansicht.
* **Erkannte Gesichter:** Alle auf dem Bild erkannten Personen werden mit interaktiven Boxen markiert.
* **Ähnliche Bilder suchen:** Klick auf diesen Button nutzt das CLIP-Embedding dieses Fotos als Referenz und sucht optisch verwandte Motive im Archiv.
* **Originaldatei öffnen:** Öffnet den Originalscan im Vollbildmodus.

---

## 5. Häufige Fragen & Besonderheiten

### Warum erhalte ich Treffer für Wörter, die im Archiv gar nicht vorkommen?
Im Gegensatz zu einer Schlagwortsuche (wie in einer Excel-Tabelle) arbeitet eine Vektordatenbank nach dem Prinzip der **„Nächsten Nachbarn“ (k-NN)**:
* Jedes Bild und jede Suchanfrage ist ein Punkt im 512-dimensionalen Raum.
* Wenn Sie nach *„Kind“* suchen, aber kein Bild ein Kind enthält, fragt die Datenbank standardmäßig: *„Welche vorhandenen Bilder sind der Anfrage noch am wenigsten unähnlich?“*
* **Lösung:** Nutzen Sie den Relevanz-Filter in der Suchleiste (*„Standard (ab 23%)“*). Dann erhalten Sie bei fehlenden Motiven korrekterweise **0 Treffer**.

### Funktionieren auch TIFF-Dateien im Browser?
Ja. Webbrowser wie Firefox oder Chrome können das Format `.tif` normalerweise nicht direkt anzeigen. Das Backend wandelt TIFF- und CMYK-Bilder für das Web-Frontend **automatisch und verlustfrei im Speicher nach JPEG um**. Ihre Originaldateien auf der Festplatte bleiben dabei unberührt.

### Werden GPU / CUDA unterstützt?
Ja. Das System prüft beim Start via PyTorch, ob eine kompatible NVIDIA-Grafikkarte verfügbar ist. Ist keine GPU vorhanden oder reicht der Videospeicher (VRAM) nicht aus, schaltet das System automatisch auf optimierte CPU-Inferenz um.

---

## 6. Wartung, Datensicherung & Fehlerbehebung

### Wo liegen die Daten?
* **Die Vektoren und Metadaten:** Liegen im Ordner `./qdrant_storage` im Projektverzeichnis.
* **Ihre Originalbilder:** Verbleiben immer an ihrem ursprünglichen Speicherort (z. B. `/home/museum/Bilder`). Das System speichert in Qdrant lediglich den Dateipfad und die Merkmalsvektoren.

### Backup erstellen
Um alle indizierten Merkmale, erkannten Gesichter und vergebenen Personennamen zu sichern:
1. Qdrant stoppen: `docker-compose stop`
2. Den Ordner kopieren:
   ```bash
   cp -r /home/museum/Bildersuche/qdrant_storage /pfad/zum/backup/
   ```
3. Qdrant wieder starten: `docker-compose start`

### Fehlerbehebung

#### „Firefox can’t connect to the server at localhost:8000“
* Der FastAPI-Server läuft noch nicht. Starten Sie ihn im Terminal:
  ```bash
  cd /home/museum/Bildersuche
  .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
  ```

#### „Verbindung zu Qdrant fehlgeschlagen“
* Der Docker-Container von Qdrant ist gestoppt. Starten Sie ihn mit:
  ```bash
  cd /home/museum/Bildersuche
  docker-compose up -d
  ```
  Prüfen Sie den Status im Browser unter [http://localhost:6333/dashboard](http://localhost:6333/dashboard).
