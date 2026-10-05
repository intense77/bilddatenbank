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

Öffnen Sie ein Terminal im Projektverzeichnis:

```bash
cd /pfad/zum/Bildersuche

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
1. **Suchleiste:** Geben Sie ein Motiv, ein Thema, eine Epoche oder einen Personennamen ein (z. B. *„gotischer Altar“*, *„Marktplatz 1910“*, *„Soldaten im Feld“* oder *„Bischof Ulrich“*).
2. **Hybride Personensuche:** Sobald Sie nach dem Namen einer erfassten Person suchen, erkennt das System dies automatisch. Treffer, auf denen diese Person zu sehen ist, werden mit **100 % Relevanz** ganz oben platziert und mit einem Personen-Badge (z. B. `👤 Bischof Ulrich`) optisch hervorgehoben.
3. **Relevanz-Filter (Schwellenwert):**
   * *Standard (ab 23 %)*: Filtert unpassende Zufallstreffer aus (empfohlen).
   * *Streng (ab 25 %)*: Zeigt nur sehr eindeutige Treffer.
   * *Locker (ab 20 %)*: Zeigt auch Bilder mit entfernter thematischer Ähnlichkeit.
   * *Alle Treffer*: Zeigt stets die nächsten mathematischen Nachbarn.
4. **Ergebnis-Karten:** Jedes Bild zeigt den berechneten Score (z. B. `78% Score`), den archivalischen Titel, den Dateinamen, Tags für Datierung/Signatur sowie erkannte Personen.

### Tab 2: Personen & Cluster
*(Nur aktiv, wenn `ENABLE_FACE_RECOGNITION=true` bzw. der Gesichtserkennungs-Schalter aktiv ist)*
1. **Echtzeit-Suchfeld & Schnellfilter:**
   * **Suchleiste:** Filtern Sie die Personenliste in Echtzeit nach Namen oder Cluster-ID.
   * **Filterchips:** Wechseln Sie mit einem Klick zwischen *„Alle“*, *„Benannt“* (nur Personen mit vergebenem Klarnamen) und *„Unbenannt“* (offene Personen-Cluster zur Erschließung).
2. **Cluster-Übersicht:** Zeigt runde Porträtausschnitte aller Gesichter, die die KI als dieselbe Person identifiziert hat, inklusive Anzahl der Vorkommen im Archiv.
3. **Cluster ansehen:** Klick auf eine Person öffnet die Detailansicht mit allen Archivbildern, auf denen die Person vorkommt. Das Gesicht wird auf jedem Scan präzise mit einer goldenen Bounding Box umrahmt (inkl. automatischer EXIF-Entzerrung bei hochformatigen oder gedrehten Scans).
4. **Klarname zuweisen:** Tragen Sie den Personennamen ein (z. B. *„Bischof Ulrich“*) und klicken Sie auf **Speichern**. Der Name wird allen Gesichtern dieser Person in der Datenbank zugewiesen und automatisch für die Freitextsuche in den Bildmetadaten synchronisiert.
5. **Cluster zusammenführen (Merge):**
   * Mit dem Button **„Zusammenführen…“** können Sie zwei getrennte Cluster vereinen (z. B. wenn eine Persönlichkeit in jungen Jahren und im Seniorenalter aufgrund veränderter Gesichtszüge getrennt gruppiert wurde).
   * Wählen Sie das Ziel-Cluster aus und vergeben Sie den gemeinsamen Klarnamen. Alle Gesichter und Elternbilder werden sofort konsolidiert.
6. **Falsch zugeordnete Gesichter ausschließen (Split / „Nicht diese Person“):**
   * Auf jeder Bildkarte in der Cluster-Detailansicht befindet sich der Button **„Entfernen“** (*„Nicht diese Person“*).
   * Entfernt ein versehentlich zugeordnetes Porträt aus dem Cluster und aktualisiert das Elternbild, ohne die übrigen Gesichter zu verändern.
7. **Cluster neu berechnen:** Ein Klick auf *„Cluster neu berechnen“* führt das DBSCAN-Clustering über alle archivierten Gesichter erneut aus.

### Tab 3: Bestände & Upload
Ermöglicht das Hinzufügen von Bildern direkt über die Weboberfläche:
1. **Bestehende Ordner ohne Verschieben einbinden:**
   * **Grafische Verzeichnisauswahl (Button *„Auswählen…“*):** Öffnet einen interaktiven Dateisystem-Browser direkt im Webinterface mit Schnellzugriff auf Netzlaufwerke (GVFS/NAS), Persönlichen Ordner (`~`), Projekt-Daten oder Festplatten-Mounts (`/media`, `/mnt`). Sie können sich bequem durch Unterordner klicken und den gewünschten Bestand per Klick übernehmen – ganz ohne Pfad-Tippfehler.
   * **Manuelle Pfadeingabe:** Unterstützt absolute Pfade, Tilde-Auflösung (`~/Bilder`) sowie GVFS-Netzwerk-Mounts (`/run/user/1000/gvfs/...`).
   * **Vorschau-Button:** Prüft vorab die Erreichbarkeit, zählt die enthaltenen Bilddateien und Sidecars und zeigt Beispieldateien an.
   * **Ordner jetzt indexieren:** Bindet das Verzeichnis sicher in die Pfad-Sandbox ein (`ALLOWED_IMAGE_DIRS`) und indexiert alle Bilder inkrementell vor Ort.
2. **Neue Scans per Drag-and-Drop hochladen:**
   * Ziehen Sie Bilddateien (JPG, PNG, WEBP, TIF/TIFF) und optionale `.json`-Sidecars direkt in die gestrichelte Ablagezone.
   * Das System speichert die Dateien im Archiv und berechnet sofort alle Merkmals-Embeddings und Metadaten.

### Bild-Detailansicht (Modal)
Klick auf ein beliebiges Bild öffnet die vergrößerte Detailansicht:
* **Bild & Bounding Boxes:** Anzeige des Bildes mit interaktiven Markierungen aller erkannten Gesichter. Gesichtsrahmen lassen sich über den Button oben rechts jederzeit ein- oder ausblenden.
* **Archiv-Metadaten & Bearbeitung (Rechte Seitenleiste):** 
  * *Metadaten-Tab:* Strukturierte Übersicht mit Signatur, Titel, Datierung, Urheber, Abmessungen, Beschreibung, Iconclass und Lizenz. Metadaten können über den ✏️-Button direkt in SQLite editiert werden.
  * *Bearbeiten-Tab (Non-destruktiv):* Feinjustierung von Helligkeit, Kontrast, Gamma, Schärfung und Negativ-Invertierung. Mit dem Button **„Original“** (gedrückt halten) oder dem **Split-Slider** (Taste `S`) lässt sich das Vorher/Nachher-Ergebnis stufenlos vergleichen.
* **Zweiblatt-Logik & 3D-Karten-Flip (Recto / Verso):**
  * Handelt es sich um ein Vorder-/Rückseiten-Paar (z. B. `foto_01_r.jpg` und `foto_01_v.jpg` oder `_recto`/`_verso`, `_vorderseite`/`_rueckseite`, `_a`/`_b`), erkennt das System die Partnerdatei automatisch.
  * In der Menüleiste erscheint der Button **`🔁 Rückseite / Vorderseite`**. Durch Klick oder die Schnelltaste **`V`** bzw. **`U`** dreht sich das Bild in einer flüssigen 3D-Karten-Animation um 180° um.
  * In der Seitenleiste unter **📄 Rückseite & Notizen** können handschriftliche Vermerke, Stempelabdrücke und Transkriptionen eingegeben und gespeichert werden. Diese Notizen werden direkt mit dem Bild verknüpft und in der Volltextsuche indexiert.
* **IIIF Image API 3.0 & Deep Zoom:**
  * Der Button **`Deep Zoom`** schaltet auf den hochauflösenden, lokalen OpenSeadragon-Kachelbetrachter um.
  * Ermöglicht stufenloses Hineinzoomen bis auf die Pixelebene historischer Großformate und Glasplatten – völlig ohne RAM-Überlastung des Browsers.
  * Bietet Werkzeuge für 1:1 Pixelansicht, 90°-Drehung und Gesamteinpassung.
* **Verlustfreies Drehen (JPEG DCT):**
  * Über die Tasten `↺ 90° links` / `↻ 90° rechts` (bzw. Taste `R`) lässt sich das Originalbild verlustfrei ohne Rekomprimierung in 90°-Schritten rotieren.
* **Bildausschnitt-Suche (Crop-to-Search):**
  * Klicken Sie auf **„Ausschnitt suchen“** und ziehen Sie mit der Maus einen Rahmen um ein Motivdetail (z. B. ein Altaraufsatz, Wappen, liturgisches Gerät oder Inschrift).
  * Das Backend schneidet das Detail zu, berechnet das Embedding und findet alle Scans mit diesem oder ähnlichen Motiven.
* **Adobe XMP Sidecars:**
  * Über das Dropdown-Menü **„XMP“** lassen sich Dublin-Core-konforme `.xmp`-Metadaten-Dateien herunterladen oder direkt neben dem Original-Masterbild auf der Festplatte sichern.
* **Navigation & Schließen:**
  * **✕ Schließen:** Oben rechts befindet sich ein prominenter, fest verankerter Schließen-Button (auch per Taste `Esc`).
  * **Aus Personen-Clustern:** Wurde das Bild aus einem Personen-Cluster geöffnet, erscheint sowohl oben links (`← Zur Übersicht`) als auch im Personen-Kontrollbanner ein gut sichtbarer Button **`← Zurück zur Übersicht`**, der direkt zur Kachelansicht dieser Person zurückführt.

---

### Tastaturkürzel (Schnellübersicht)

Drücken Sie jederzeit die Taste **`?`** in der Web-Oberfläche, um die Tastaturhilfe einzublenden:

| Taste | Funktion |
| :--- | :--- |
| **`Esc`** | Modal, Detailansicht oder Vollbild schließen / Zurück zur Übersicht |
| **`V`** oder **`U`** | Zweiblatt 3D-Karten-Flip (Wenden zwischen Vorder- und Rückseite) |
| **`F`** | Vollbild-Leinwand ein- und ausschalten |
| **`S`** | Vorher/Nachher Split-Slider im Bild-Modal umschalten |
| **`L`** | Archiv-Lupe (250 % Detailvergrößerung) ein- und ausschalten |
| **`R`** | Bild um 90° im Uhrzeigersinn drehen |
| **`I`** | Negativ/Positiv-Invertierung umschalten |
| **`+`** / **`-`** | Zoom im Bild-Modal vergrößern / verkleinern |
| **`0`** | Zoom-Stufe auf 100 % zurücksetzen |
| **`→`** / **`←`** | Nächstes bzw. vorheriges Bild der Suchergebnisse öffnen |
| **`/`** | Suchfeld sofort fokussieren und Eingabe beginnen |
| **`?`** | Tastaturkürzel-Übersicht anzeigen |

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
   cp -r ./qdrant_storage /pfad/zum/backup/
   ```
3. Qdrant wieder starten: `docker compose start`

### Fehlerbehebung

#### „Verbindung zum Server unter localhost:8000 fehlgeschlagen“
* Der FastAPI-Server läuft noch nicht. Starten Sie ihn im Terminal:
  ```bash
  .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
  ```

#### „Verbindung zu Qdrant fehlgeschlagen“
* Der Docker-Container von Qdrant ist gestoppt. Starten Sie ihn mit:
  ```bash
  ./start_qdrant.sh
  ```
  Prüfen Sie den Status im Browser unter [http://localhost:6333/dashboard](http://localhost:6333/dashboard).
