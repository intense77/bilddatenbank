# Offene Aufgaben (Roadmap & Backlog)

Dieses Dokument erfasst die geplanten Weiterentwicklungen für das historische Bildarchiv-Suchsystem aus Sicht von **Langzeitarchivierung**, **Datensparsamkeit**, **Ressourceneffizienz** und **fachlicher Praxis in Diözesan- und Kirchenarchiven**.

---

## 1. Kuratierungs-Werkzeuge in der Benutzeroberfläche (Archivare-Tools)
* **Ziel:** Maximale Arbeitsergonomie bei der wissenschaftlichen Erschließung und Verifikation.
* **Aufgaben:**
  - [ ] **Crop-to-Search (Bildauschnitt-Suche):**
    * Möglichkeit, im Web-Frontend per Maus einen Rahmen um ein Bilddetail zu ziehen (z. B. ein Altaraufsatz, Wappen, liturgisches Gerät oder ein Gemälde im Hintergrund).
    * Backend schneidet den Bildbereich serverseitig zu, berechnet das OpenCLIP-Embedding und sucht visuell ähnliche Details im Gesamtarchiv.
  - [ ] **Cluster-Merge & -Split (Personen-Kuratierung):**
    * *Cluster-Merge:* Zwei getrennte Personen-Cluster zusammenführen (z. B. wenn eine historische Persönlichkeit in jungen Jahren und im Seniorenalter aufgrund von Altersveränderungen getrennt gruppiert wurde).
    * *Cluster-Split / Ausschluss:* Falsch zugeordnete Gesichter mit einem Klick aus einem Cluster entfernen („Nicht diese Person“) und als unzugeordneten Noise-Point markieren.
  - [ ] **Historische Zeitleiste & Facettierung:**
    * Interaktiver Schieberegler nach Entstehungsjahr/Epoche (z. B. *1880–1914*, *1914–1939*, *1945–1970*) unter Nutzung von Qdrant-Bereichsfiltern (`gte`/`lte`).
    * Filter nach bekannten Archivsignaturen, Beständen oder Fotografen/Ateliers.

---

## 2. Duplikats- & Varianten-Erkennung (Deduping & Stacking)
* **Ziel:** Vermeidung verstopfter Trefferlisten durch Serienabzüge, Kontaktabzüge oder Mehrfachbelichtungen bei Nachlässen.
* **Aufgaben:**
  - [ ] **Zweistufige Ähnlichkeitserkennung:**
    * *Stufe 1 (Deterministisch):* Perceptual Hashing (dHash / pHash via `imagehash`) für 100 % identische Bilder, Größenvarianten und minimale Crops (extrem schnell, 0 MB VRAM).
    * *Stufe 2 (Optische Varianten):* CLIP-Vektordistanz mit hohem Schwellenwert (Cosine-Score > 0.94) für Serienaufnahmen und abweichende Belichtungen.
  - [ ] **Visuelles „Stacking“ im Web-Frontend:**
    * Varianten werden nicht destruktiv gelöscht (Erhalt des Bestandszusammenhangs), sondern in den Suchergebnissen zu einem aufklappbaren Bildstapel („+3 Varianten“) zusammengefasst.

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
