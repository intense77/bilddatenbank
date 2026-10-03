# Offene Aufgaben (Roadmap & Backlog)

Dieses Dokument erfasst die geplanten Weiterentwicklungen für das historische Bildarchiv-Suchsystem aus Sicht von **Langzeitarchivierung**, **Datensparsamkeit**, **Ressourceneffizienz** und **fachlicher Praxis in Diözesan- und Kirchenarchiven**.

---

## 1. Kuratierungs-Werkzeuge in der Benutzeroberfläche (Archivare-Tools)
* **Ziel:** Maximale Arbeitsergonomie bei der wissenschaftlichen Erschließung und Verifikation.
* **Aufgaben:**
  - [x] **Crop-to-Search (Bildausschnitt-Suche / Region-of-Interest):**
    * Interaktiver Auswahlrahmen im Web-Frontend per Maus über jedem Archivbild im Detail-Modal (z. B. für Altaraufsätze, Wappen, liturgische Geräte oder Gemäldedetails im Hintergrund).
    * Backend schneidet den gewählten Ausschnitt serverseitig und verlustfrei zu (`POST /search/crop`), berechnet das 512-dim OpenCLIP-Embedding und findet visuell ähnliche Details im Gesamtarchiv.
    * Trefferliste im Suchgitter mit Angabe der Detail-Dimensionen und Referenzbild.
  - [x] **Cluster-Merge & -Split (Personen-Kuratierung):**
    * *Cluster-Merge:* Zwei getrennte Personen-Cluster zusammenführen (`POST /faces/clusters/merge`) inklusive automatischer Konsolidierung des Namens und Resynchronisation der Elternbilder.
    * *Cluster-Split / Ausschluss:* Falsch zugeordnete Gesichter mit einem Klick („Nicht diese Person“ / `POST /faces/{face_id}/remove-from-cluster`) aus einem Cluster entfernen und als unzugeordneten Punkt markieren.
  - [x] **Verlustfreie Bilddrehung (Lossless Image Rotation):**
    * Physikalisches, 100 % verlustfreies 90°/180°/270°-Transponieren von JPEG-Scans via DCT-Koeffizienten-Transformation (`jpegtran`) ohne Pixel-Rekompression oder Generationsverluste.
    * Erhalt sämtlicher archivischer Metadaten-Marker (EXIF, IPTC, XMP, ICC-Profile) und automatische Normalisierung des EXIF-Orientation-Tags auf 1.
    * Mathematisch verlustfreie Transformation für PNG, TIFF und WebP.
    * Schnellzugriff per `↺ 90°` und `↻ 90°` im Bild-Detailmodal sowie Schnell-Drehbutton auf Suchkarten.
    * Automatische Invalidierung des Thumbnail-Caches und Live-Reindexierung in Qdrant (aufgerichtetes CLIP-Embedding & Gesichts-Detektion).
  - [ ] **Historische Zeitleiste & Facettierung:**
    * Interaktiver Schieberegler nach Entstehungsjahr/Epoche (z. B. *1880–1914*, *1914–1939*, *1945–1970*) unter Nutzung von Qdrant-Bereichsfiltern (`gte`/`lte`).
    * Filter nach bekannten Archivsignaturen, Beständen oder Fotografen/Ateliers.

---

## 2. Duplikats- & Varianten-Erkennung (Deduping & Stacking)
* **Ziel:** Vermeidung verstopfter Trefferlisten durch Serienabzüge, Kontaktabzüge oder Mehrfachbelichtungen bei Nachlässen.
* **Aufgaben:**
  - [x] **Zweistufige Ähnlichkeitserkennung:**
    * *Stufe 1 (Deterministisch):* Perceptual Hashing (dHash / pHash via `imagehash`) für 100 % identische Bilder, Größenvarianten und minimale Crops (extrem schnell, 0 MB VRAM).
    * *Stufe 2 (Optische Varianten):* CLIP-Vektordistanz mit hohem Schwellenwert (Cosine-Score > 0.92) für Serienaufnahmen und abweichende Belichtungen.
  - [x] **Visuelles „Stacking“ im Web-Frontend:**
    * Varianten werden nicht destruktiv gelöscht (Erhalt des Bestandszusammenhangs), sondern in den Suchergebnissen zu einem Bildstapel („+3 Varianten“) mit visueller Tiefenschattierung zusammengefasst.
    * Interaktiver Stack-Inspector & Varianten-Vergleich mit technischer Gegenüberstellung (Auflösung, Master-Empfehlung, Dateigröße, Ähnlichkeit).
    * Dedizierter Tab „Duplikate & Stapel“ zur archivweiten Analyse und Durchforstung von Beständen.

---

## 3. Archiv-Interoperabilität & Metadaten-Export (XMP, EAD, CSV)
* **Ziel:** Nahtloser Datenaustausch mit Archivinformationssystemen (AIS: *ACTApro, Faust, ScopeArchiv*) und Bildverwaltungstools (*DigiKam, Adobe Bridge*).
* **Aufgaben:**
  - [ ] **XMP-Sidecar-Generierung:**
    * Schreiben von Bounding Boxes und Personen-Namen nach dem Standard *Metadata Working Group (MWG) Regions* direkt in Begleitdateien (`.xmp`).
    * Gewährleistet das automatische Auslesen von Gesichtspositionen in professionellen Bildbetrachtern.
  - [ ] **Findbuch- & Tabellenexport:**
    * Export gefilterter Rechercheergebnisse oder Personen-Cluster als CSV/Excel-Tabelle (inkl. Signatur, Dateipfad, Personen, Datierung, Beschreibung).
  - [ ] **GLAM-Standardformate:**
    * Exportfunktion nach Dublin Core (XML/JSON-LD), EAD (Encoded Archival Description) und LIDO für übergeordnete Portale (Deutsche Digitale Bibliothek, Europeana).

---

## 4. Lokale Handschriften- & Inschriften-Erkennung (OCR / HTR)
* **Ziel:** Volltext-Erschließung historischer handschriftlicher Rückseitennotizen, Passepartout-Beschriftungen und bildimmanenter Inschriften.
* **Aufgaben:**
  - [ ] **Schlankes, lokales OCR/HTR-Modul:**
    * Integration einer leichtgewichtigen Texterkennung (z. B. PaddleOCR oder Tesseract 5 für Druckschriften/Typoskripte; feingetuntes TrOCR für deutsche Handschriften/Kurrent).
    * Speicherung des extrahierten Texts im Qdrant-Payload unter `ocr_text`.
  - [ ] **Hybride Suche (Vektor + Volltext):**
    * Einrichtung eines Qdrant-Volltextindexes mit deutscher Stemming-/Tokenisierung auf dem Feld `ocr_text`.
    * Ermöglicht die kombinierte Suche (z. B. optische Suche nach *„Primizfeier“* kombiniert mit Volltextsuche nach *„P. Johann 1934“*).

---

## 5. Automatische Metadaten-Vorschläge & GND-Konformität
* **Ziel:** Strukturierte Deskriptoren für kirchliche Kunst- und Kulturgüter ohne hohen manuellen Erfassungsaufwand.
* **Aufgaben:**
  - [ ] **Zero-Shot Fachverschlagwortung mit OpenCLIP:**
    * Ressourcenschonender Abgleich der Bild-Embeddings gegen eine kontrollierte Liste kirchenspezifischer GND-Begriffe (z. B. *Altartisch, Monstranz, Reliquiar, Chorgestühl, Kasel, Kruzifix, Taufstein, Beichtstuhl, Kanzel*).
    * 0 zusätzlicher VRAM-Bedarf, da OpenCLIP bereits im Arbeitsspeicher liegt.
  - [ ] **Träger- & Zustandserkennung:**
    * Heuristische Erkennung von Bildträgern (Glasplattennegativ, Schwarz-Weiß-Abzug, Diapositiv, koloriertes Foto) anhand von Farbkanälen, Tonwerten und Seitenverhältnissen.

---

## 6. Ressourcen- & Skalierungsoptimierung beim Personen-Clustering
* **Ziel:** Robuste, speicherschonende Clusterbildung auch bei Beständen von über 20.000 Gesichtern.
* **Technischer Hintergrund:**
  * Derzeit nutzt [clustering_service.py](file:///home/norbert/Bilderdatenbank/app/services/clustering_service.py) `DBSCAN(metric='cosine')`, was in Scikit-Learn eine quadratische $N \times N$-Distanzmatrix im RAM anlegt ($O(N^2)$).
  * Da ArcFace-Embeddings L2-normalisiert sind ($\|u\|=1$), entspricht die Cosine-Distanz mathematisch der halben quadrierten euklidischen Distanz:
    $$\text{dist}_{\text{cosine}}(u, v) = 1 - \langle u, v \rangle = \frac{1}{2} \|u - v\|^2 \iff \|u - v\| = \sqrt{2 \cdot \text{dist}_{\text{cosine}}(u, v)}$$
* **Aufgaben:**
  - [ ] Umstellung von `metric='cosine'` auf `metric='euclidean'` mit $\varepsilon_{\text{euclid}} = \sqrt{2 \cdot \varepsilon_{\text{cosine}}}$.
  - [ ] Nutzung von raumteilenden Bäumen (`algorithm='ball_tree'` oder `'kd_tree'`) für $O(N \log N)$ Laufzeit und minimalen Speicherbedarf.
  - [ ] Chunking / Batching bei sehr großen Porträtsammlungen (> 50.000 Gesichter).

---

## 7. Provenienz & Revisionssicherheit bei Personen-Labels
* **Ziel:** Wissenschaftliche Nachvollziehbarkeit und Schutz vor unabsichtlichem Überschreiben bei der Zuweisung von Klarnamen.
* **Aufgaben:**
  - [ ] Speichern von Revisionsdaten im Qdrant-Payload bei Labelvergabe:
    * `labeled_at`: ISO-Zeitstempel der Benennung.
    * `labeled_by`: Benutzer-/Archivarskennung (z. B. aus Request-Header oder Konfiguration).
    * `previous_labels`: Historie bisheriger Zuweisungen.
  - [ ] Anzeige der Benennungs-Historie und des Bearbeiters in der Personen-Detailansicht des Web-Frontends.

---

## 8. End-to-End-Praxistest & Benchmark mit Echtdaten
* **Ziel:** Validierung der Performanz und Benutzerfreundlichkeit unter realen Archivbedingungen.
* **Aufgaben:**
  - [ ] Testbestand historischer Scans (z. B. Glasplattennegative, Repros, Porträtkarten) in `./data` einspielen.
  - [ ] Inferenz-Geschwindigkeit (Sekunden pro 100 Scans) auf CPU und GPU messen.
  - [ ] Visuelle Begutachtung der Bounding-Box-Positionierung und Ähnlichkeitstreffer im Web-Frontend.
  - [ ] Dokumentation optimaler Batch-Größen für Standard-Bürorechner ohne dedizierte GPU.

---

## 9. Optimierung der Freitext- & Personensuche (Treffer-Vollständigkeit, Relevanz & Paginierung)
* **Ziel:** 100 % verlässliche Auffindbarkeit aller Bilder namentlich bekannter Personen, Beseitigung unpassender CLIP-Zufallstreffer bei Namenssuche und flexible Durchsicht großer Bestände.

### Priorität 1: Kritisch / Hohe Notwendigkeit (Vollständigkeit & Korrektheit)
- [ ] **Beseitigung des 5.000er-Scroll-Flaschenhalses bei der Namenssuche (`app/api/search.py`):**
  * *Ist-Zustand:* Bei der Suche nach Namen scrollt das Backend ungefiltert maximal 5.000 Gesichter aus `archive_faces` (bei aktuell > 80.000 Gesichtern werden ~94 % ignoriert). Bei Personen mit z. B. 28 gelabelten Gesichtern werden rein zufällig nur die 2 gefunden, die unter den ersten 5.000 IDs liegen.
  * *Soll-Zustand:* Gezielte Qdrant-Filterabfrage mit `must_not=[IsEmptyCondition("label")]` und Match auf den Namen oder direktes Nachschlagen über die lokale SQLite-Metadatenbank.
  * *Nutzen:* Es werden ausnahmslos **alle vorhandenen Bilder einer gesuchten Person** sofort gefunden.
- [ ] **Saubere Trennung von Personen-Matches und CLIP-Zufallstreffern:**
  * *Ist-Zustand:* Bei Eingabe eines Namens (z. B. *„Sabine“*) findet die Suche die Person, füllt aber die restlichen Plätze der Trefferliste mit visuellen CLIP-Vektortreffern auf (z. B. zufällige historische Bilder mit Score 26–29 %).
  * *Soll-Zustand:* Wenn der Suchbegriff einem vergebenen Personennamen entspricht, werden primär exklusive Personen-Treffer angezeigt bzw. semantische Bild-Treffer optisch klar als „Ähnliche Motive (CLIP)“ abgegrenzt.

### Priorität 2: Mittlere Notwendigkeit (Ergonomie & Trefferanzahl)
- [ ] **Paginierung & „Mehr Ergebnisse laden“ (Infinite Scroll / Pagination):**
  * *Ist-Zustand:* Die Trefferanzahl ist fest auf 20 (bzw. im Dropdown maximal 80) begrenzt. Ein Nachladen weiterer Treffer ist nicht möglich.
  * *Soll-Zustand:* Einführung von `offset`/`page` im Backend-Endpunkt `/search/semantic` und eines „Mehr Ergebnisse laden“-Buttons (bzw. optionalem Infinite Scroll) im Suchgitter.
- [ ] **Dynamischer Relevanz-Schwellenwert (Threshold-Tuning):**
  * *Ist-Zustand:* Der Standard-Schwellenwert von `0.23` (23 %) schneidet bei CLIP oft viele valide Treffer mit Scores zwischen 0.20 und 0.22 hart ab, sodass scheinbar nur 1–2 Treffer existieren.
  * *Soll-Zustand:* Bei Personentreffern (Score 1.0) Schwellenwert-Logik komplett umgehen; bei Motivsuchen Standard-Schwellenwert auf 0.20 optimieren oder dynamisch anhand der Score-Verteilung staffeln.

### Priorität 3: Komfort- & Erweiterungsfunktionen (Zukunft)
- [ ] **Volltextsuche in archivischen Metadatenfeldern (Hybrid Search):**
  * Suchbegriff nicht nur in Gesichts-Labels und per CLIP suchen, sondern parallel in `title`, `signature`, `description` und `keywords` (in SQLite / Qdrant-Payload).
- [ ] **Konfigurierbares Standard-Trefferlimit:**
  * Voreinstellung im Suchformular auf Wunsch auf 40 oder 60 Treffer anpassen.

