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
  - [x] Umstellung von `metric='cosine'` auf `metric='euclidean'` mit $\varepsilon_{\text{euclid}} = \sqrt{2 \cdot \varepsilon_{\text{cosine}}}$.
  - [x] Nutzung von raumteilenden Bäumen (`algorithm='ball_tree'` oder `'kd_tree'`) für $O(N \log N)$ Laufzeit und minimalen Speicherbedarf.
  - [x] Chunking / Batching bei sehr großen Porträtsammlungen (> 50.000 Gesichter):
    * Adaptiver BallTree mit hardwaregesteuerter `leaf_size` und dynamischer Multithread-Parallelisierung (`n_jobs`).

---

## 7. Nachvollziehbarkeit, Human-in-the-Loop & Provenienz bei Personen-Labels
* **Ziel:** Wissenschaftliche Nachvollziehbarkeit, ethische Kennzeichnung von KI-Zuweisungen und Schutz vor Fehlklassifikationen.
* **Aufgaben:**
  - [ ] **Status-Flags für Personen-Metadaten:**
    * Jede Personenzuweisung im Payload erhält einen definierten Herkunftsstatus:
      * `KI_AUTO`: Vom Algorithmus vorgeschlagen (z. B. 82 % Ähnlichkeit mit *Bischof Müller*).
      * `VERIFIED`: Von einer Archivkraft im Prüf-Modus begutachtet und verbindlich bestätigt.
      * `REJECTED`: Falsch-positiver Treffer (sorgt dauerhaft dafür, dass dieses Gesicht bei Neuberechnungen nicht wieder in dieses Cluster wandert).
  - [ ] **Konfigurierbarer Konfidenz-Schwellenwert im UI:**
    * Schieberegler in der Cluster- und Gesichts-Ansicht („Nur Gesichter mit Konfidenz > X % anzeigen“), um Rauschen und Fehl-Detektionen bei kontrastarmen oder beschädigten historischen Schwarz-Weiß-Aufnahmen auszublenden.
  - [ ] **Revisionsdaten & Historie:**
    * Speichern von `labeled_at` (Zeitstempel), `labeled_by` (Bearbeiter) und `previous_labels` im Qdrant-Payload.
    * Anzeige des Prüfstatus und der Benennungs-Historie in der Detailansicht.

---

## 8. End-to-End-Praxistest & Benchmark mit Echtdaten
* **Ziel:** Validierung der Performanz und Benutzerfreundlichkeit unter realen Archivbedingungen.
* **Aufgaben:**
  - [ ] Testbestand historischer Scans (z. B. Glasplattennegative, Repros, Porträtkarten) in `./data` einspielen.
  - [x] Inferenz-Geschwindigkeit (Sekunden pro 100 Scans) auf CPU und GPU messen (`benchmark.py`).
  - [ ] Visuelle Begutachtung der Bounding-Box-Positionierung und Ähnlichkeitstreffer im Web-Frontend.
  - [ ] Dokumentation optimaler Batch-Größen für Standard-Bürorechner ohne dedizierte GPU.

---

## 9. Optimierung der Freitext- & Personensuche (Treffer-Vollständigkeit, Relevanz & Paginierung)
* **Ziel:** 100 % verlässliche Auffindbarkeit aller Bilder namentlich bekannter Personen, Beseitigung unpassender CLIP-Zufallstreffer bei Namenssuche und flexible Durchsicht großer Bestände.

### Priorität 1: Kritisch / Hohe Notwendigkeit (Vollständigkeit & Korrektheit)
- [x] **Beseitigung des 5.000er-Scroll-Flaschenhalses bei der Namenssuche (`app/api/search.py`):**
  * *Ist-Zustand:* Bei der Suche nach Namen scrollt das Backend ungefiltert maximal 5.000 Gesichter aus `archive_faces` (bei aktuell > 80.000 Gesichtern werden ~94 % ignoriert). Bei Personen mit z. B. 28 gelabelten Gesichtern werden rein zufällig nur die 2 gefunden, die unter den ersten 5.000 IDs liegen.
  * *Soll-Zustand:* Gezielte Qdrant-Filterabfrage mit `must_not=[IsEmptyCondition("label")]` und Match auf den Namen oder direktes Nachschlagen über die lokale SQLite-Metadatenbank.
  * *Nutzen:* Es werden ausnahmslos **alle vorhandenen Bilder einer gesuchten Person** sofort gefunden.
- [x] **Saubere Trennung von Personen-Matches und CLIP-Zufallstreffern:**
  * *Ist-Zustand:* Bei Eingabe eines Namens (z. B. *„Sabine“*) findet die Suche die Person, füllt aber die restlichen Plätze der Trefferliste mit visuellen CLIP-Vektortreffern auf (z. B. zufällige historische Bilder mit Score 26–29 %).
  * *Soll-Zustand:* Wenn der Suchbegriff einem vergebenen Personennamen entspricht, werden primär exklusive Personen-Treffer angezeigt bzw. semantische Bild-Treffer optisch klar als „Ähnliche Motive (CLIP)“ abgegrenzt.

### Priorität 2: Mittlere Notwendigkeit (Ergonomie & Trefferanzahl)
- [x] **Paginierung & „Mehr Ergebnisse laden“ (Infinite Scroll / Pagination):**
  * *Ist-Zustand:* Die Trefferanzahl ist fest auf 20 (bzw. im Dropdown maximal 80) begrenzt. Ein Nachladen weiterer Treffer ist nicht möglich.
  * *Soll-Zustand:* Einführung von `offset`/`page` im Backend-Endpunkt `/search/semantic` und eines „Mehr Ergebnisse laden“-Buttons (bzw. optionalem Infinite Scroll) im Suchgitter.
- [x] **Dynamischer Relevanz-Schwellenwert (Threshold-Tuning):**
  * *Ist-Zustand:* Der Standard-Schwellenwert von `0.23` (23 %) schneidet bei CLIP oft viele valide Treffer mit Scores zwischen 0.20 und 0.22 hart ab, sodass scheinbar nur 1–2 Treffer existieren.
  * *Soll-Zustand:* Bei Personentreffern (Score 1.0) Schwellenwert-Logik komplett umgehen; bei Motivsuchen Standard-Schwellenwert auf 0.20 optimieren oder dynamisch anhand der Score-Verteilung staffeln.

### Priorität 3: Komfort- & Erweiterungsfunktionen (Zukunft)
- [x] **Volltextsuche in archivischen Metadatenfeldern (Hybrid Search):**
  * Suchbegriff nicht nur in Gesichts-Labels und per CLIP suchen, sondern parallel in `title`, `signature`, `description` und `keywords` (in SQLite / Qdrant-Payload).
- [x] **Konfigurierbares Standard-Trefferlimit:**
  * Voreinstellung im Suchformular auf Wunsch auf 40 oder 60 Treffer anpassen.

---

## 10. Robustheit im Datei-Handling (Historische Scans & Sonderformate)
* **Ziel:** Absturzsichere Ingest-Pipeline für unberechenbare historische Digitalisate (Glasplatten, Großformate, Altdaten).
* **Aufgaben:**
  - [x] **Farbprofile & Farbraum-Konvertierung (CMYK, 16-Bit Grayscale):**
    * Sicheres Abfangen von CMYK-TIFFs via `ImageCms` unter Erhalt des ICC-Farbprofils sowie lineare 16-Bit-Normalisierung zu 8-Bit sRGB vor Weitergabe an KI & Hashing (`safe_normalize_image_to_rgb`).
  - [x] **Decompression-Bomb-Schutz konfigurieren:**
    * Adaptives Anheben von `Image.MAX_IMAGE_PIXELS` anhand der erkannten Systemressourcen (bis zu 500 Megapixel), verhindert `DecompressionBombError` bei historischen Riesen-Scans.
  - [x] **Skalierung vor KI-Inferenz (VRAM- & RAM-Schonung):**
    * Vor der Übergabe an CLIP und InsightFace hochauflösende Scans im Speicher auf max. 1.600–2.000 Pixel lange Kante herunterskalieren.
    * Verhindert Out-of-Memory-Crashes (OOM), spart bis zu 90 % Inferenzzeit und bewahrt die volle Erkennungsgenauigkeit.

---

## 11. Effizientes Caching & Thumbnail-Management (Proaktive Pipeline)
* **Ziel:** Blitzschneller Seitenaufbau ohne Netzwerklast beim Durchsuchen zehntausender Bestände.
* **Aufgaben:**
  - [x] **Proaktive Thumbnail-Generierung beim Erst-Indexieren:**
    * Direkt beim Indexieren Ablage eines standardisierten Web-Thumbnails (WebP, max. 400–800 px) sowie quadratischer 160 px-Gesichtscrops im Cache-Verzeichnis (`./.cache/thumbnails`).
    * Beseitigt Verzögerungen durch On-the-fly-Konvertierung bei großen Trefferlisten.
  - [x] **Konsequenter Verzicht auf Originale im Galerie-Betrieb:**
    * Galerien, Suchlisten und Leuchttisch laden ausschließlich die leichten WebP-Derivate (`max_dim=400/600`); das hochauflösende Master-Original wird erst beim Hineinzoomen / Deep Zoom via IIIF oder im Download geladen.

---

## 12. Logging, Fehler-Reporting & Reject-Management (Batch-Robustheit)
* **Ziel:** Unterbrechungsfreie Massenverarbeitung und volle Transparenz für die Archivleitung.
* **Aufgaben:**
  - [ ] **Strukturiertes Fehlerprotokoll (`failed_files.jsonl`):**
    * Treten bei beschädigten Dateien, Dateisystemfehlern oder Rechten Problemen Ausnahmen auf, bricht der Indexer nicht ab, sondern führt die Datei mit Zeitstempel, Pfad und Fehlerursache in einer JSONL-Logdatei.
  - [ ] **Status-Dashboard & Reject-Übersicht:**
    * Übersichtsanzeige im Admin-/Import-Tab mit Kennzahlen:
      * Anzahl indexierter Master-Bilder
      * Anzahl detektierter Gesichter & Cluster
      * Fehlgeschlagene / korrupte Dateien mit Detailansicht zur manuellen Nachprüfung.

---

## 13. Archivische Schutzfristen & Zugriffstrennung (KDG / DSGVO)
* **Ziel:** Rechtssicherer Betrieb in Lesesaal und Verwaltung unter Einhaltung gesetzlicher und kirchlicher Sperrfristen.
* **Aufgaben:**
  - [ ] **Bestandsfilterung per Ordner-Mapping:**
    * Kennzeichnung ganzer Teilverzeichnisse mit Schutzfristen-Tags (z. B. `sperrfrist_aktiv`, `intern_leitung`).
  - [ ] **Mandanten- / Rollen-Filterung in der Suche:**
    * Gesperrte Bestände werden standardmäßig in Lesesaal-Recherchen ausgeblendet und erfordern eine explizite Berechtigungsfreigabe.

---

## 14. Kontextuelle Verknüpfung von Vorder- und Rückseite (Zweiblatt-Logik: Recto / Verso)
* **Ziel:** Das Vorderseiten-Foto ist das visuelle Hauptobjekt; die beschriftete Rückseite (Fotografenstempel, Datierungen, handschriftliche Widmungen) fungiert als verknüpfter Text- und Belegträger.
* **Archivischer Mehrwert gegenüber Standard-Software:**
  * Kommerzielle Tools behandeln Scans von Vorder- und Rückseite als zwei isolierte, zusammenhanglose Dateien.
  * Hier erkennt das System anhand von Dateinamenskonventionen (`_r`/`_v`, `_recto`/`_verso`, `_a`/`_b`, `_01`/`_02`) automatisch, dass zwei Scans physisch zusammengehören.
* **Aufgaben:**
  - [x] **Automatische Paar-Erkennung (Zweiblatt-Logik):**
    * Zusammenführen von `_r`/`_v`-Dateipaaren zu einem gemeinsamen archivischen Datensatz.
  - [x] **Rückseiten-Notiz als Primär-Metadatum des Vorderseiten-Fotos:**
    * Der per OCR/VLM auf der Rückseite entzifferte handschriftliche Text (z. B. *„Fronleichnam 1928, Pfarrer Huber mit Kirchenchor“*) wird als Primär-Metadatum direkt mit dem Vorderseiten-Foto verknüpft und semantisch indexiert.
    * Bei der Freitextsuche nach Begriffen auf der Rückseite wird direkt das Vorderseiten-Foto als Suchtreffer ausgegeben.
  - [x] **Interaktiver 3D-Karten-Flip im Bild-Modal:**
    * Button „Rückseite ansehen / Umdrehen“ mit animiertem Karten-Wechsel zwischen Vorder- und Rückseite.

---

## 15. IIIF Image API 3.0 & Deep Zoom (Pyramidales Kacheln)
* **Ziel:** Flüssige Betrachtung gigapixel-großer Scans (Glasplatten, Repros > 100 MB) im Webbrowser ohne RAM-Überlastung des Clients.
* **Aufgaben:**
  - [x] **Leichtgewichtiger IIIF-Kacheldienst:**
    * Implementierung eines lokalen IIIF-Image-API-konformen Endpunkts (`/iiif/{id}/...` und `/api/iiif/{id}/...`) auf Basis dynamischer Kachelung (Pillow / pyramidales WebP & JPEG mit SSD-Caching in `.cache/iiif_tiles/`).
  - [x] **Deep-Zoom-Integration (OpenSeadragon / Mirador):**
    * Flüssiges Hineinzoomen bis auf den Seidenfaden historischer Paramente oder Inschriften auf Kirchturm-Glocken via lokalem OpenSeadragon (100 % offline, datenschutzkonform ohne externe CDNs).

---

## 16. Serien- & Stapel-Metadatenbearbeitung (Batch Cataloguing)
* **Ziel:** Effiziente Massenerschließung ganzer Fotonachlässe, Alben oder Ereignisserien ohne redundante Einzeleingaben.
* **Aufgaben:**
  - [ ] **Mehrfachauswahl im Frontend:**
    * Checkboxen- und Gummiband-Auswahl im Suchgitter und Leuchttisch.
  - [ ] **Batch-Editor Dialog:**
    * Gleichzeitiges Zuweisen von Datierung, Urheber/Fotograf, Provenienz/Bestand, Ort und Schlagworten auf alle markierten Bilder.

---

## 17. Konservatorische Schadens-Kartierung & Erhaltungszustand
* **Ziel:** Fachgerechte Zustandsdokumentation für Restaurierung, Konservierung und Versicherung nach ICOM-Standard.
* **Aufgaben:**
  - [ ] **Schadens-Annotationslayer im Bild-Modal:**
    * Grafisches Markieren von Schäden (*Silberspiegelung, Stockflecken/Schimmel, Risse, Fehlstellen, Glasbruch, chemischer Essig-Zerfall*).
  - [ ] **Klassifikation des Erhaltungszustands:**
    * Dokumentation von Erhaltungsstufen (Stufe I: Sehr gut bis Stufe IV: Akut gefährdet / restaurierungsbedürftig) im Metadaten-Payload.

---

## 18. Visuelle Georeferenzierung & Pfarr-Topographie
* **Ziel:** Räumliche Erschließung und territoriale Verknüpfung historischer Aufnahmen ohne Abhängigkeit von modernen GPS-EXIF-Daten.
* **Archivischer Mehrwert gegenüber Standard-Software:**
  * Kommerzielle Tools verlassen sich stur auf GPS-Metadaten, die historische Glasplatten und analoge Fotoabzüge naturgemäß nicht besitzen.
  * Historische kirchliche Bestände sind stattdessen streng territorial gegliedert (*Bistum → Dekanat → Pfarrei → Filialkirche*).
* **Aufgaben:**
  - [ ] **Pfarreien-Kataster & territoriale Hierarchie:**
    * Verknüpfung der semantischen Suche mit einem Pfarreien- und Ortskataster.
    * Wer nach Kirchtürmen, Altären oder Prozessionsaufnahmen sucht, kann die Suche flexibel auf bestimmte Pfarreien, Dekanate oder Bistumsregionen eingrenzen.
  - [ ] **Gebäude- & Architektur-Ähnlichkeitssuche:**
    * Wiedererkennung desselben Kirchturms, Hochaltars, Portals oder derselben Kirchenfassade aus verschiedenen Blickwinkeln und über historische Epochen hinweg (z. B. Vorher/Nachher-Vergleich vor und nach Kriegszerstörung, Barockisierung oder Restaurierung).
  - [ ] **Interaktive Koordinatenzuweisung:**
    * OpenStreetMap / Leaflet-Kartenmodul zur schnellen manuellen Verortung per Mausklick.
  - [ ] **Geografische Umkreissuche:**
    * Qdrant-Geo-Distanzfilter für Recherchen im Umkreis (z. B. *„Alle historischen Fotos im Umkreis von 2 km um Kloster Beuron“*).

---

## 19. Kuratierte Mappen & Publikations-/Druckerei-Paketexport
* **Ziel:** Projektbezogene Bildzusammenstellungen für Ausstellungen, Heimatbücher und Leihanfragen mit druckfertigem Nachweis.
* **Aufgaben:**
  - [ ] **Persistente Kuratoren-Mappen:**
    * Dauerhaftes Speichern und Verwalten benannter Kollektionen (über den temporären Leuchttisch hinaus).
  - [ ] **Publikations-Paket (Druckerei-ZIP):**
    * Automatisierter Download der Master-Originale inklusive druckreifem **Bildnachweis-Verzeichnis (PDF & CSV)** mit korrekten Zitationen, Copyright-Vermerken und Bildunterschriften.

---

## 20. Kirchlicher Thesaurus & Ikonographischer Standard für die Freitextsuche (GND, Iconclass, AAT)
* **Ziel:** Maximale Treffsicherheit bei der Recherche nach christlicher Kunst, Liturgie, Paramenten und Ordensleben durch semantische Begriffserweiterung und kontrolliertes Fachvokabular.

### Etablierte Fachstandards & Klassifikationen
* **Iconclass:** Internationaler kunsthistorischer Standard für christliche Ikonographie (z. B. Bibelszenen, Heiligenattribute, liturgische Riten; genutzt im *Bildarchiv Foto Marburg* und *Deutschen Dokumentationszentrum für Kunstgeschichte*).
* **GND (Gemeinsame Normdatei der DNB):** Normierte Sachbegriffe für kirchliche Ämter, Orden, Festtage und Sakralgegenstände.
* **Getty AAT (Art & Architecture Thesaurus, dt. Fassung):** Normiertes Vokabular für Sakralarchitektur, Paramente und Vasa sacra.

### Fachspezifische Vokabular-Kategorien
* **Vasa sacra (Liturgische Geräte):** *Monstranz, Kelch, Ziborium, Patene, Weihrauchfass (Thuribulum), Weihrauchschiffchen, Vortragekreuz, Aspergill (Weihwassersprengel), Messkännchen, Reliquiar, Ciborium, Ostensorium*.
* **Paramente (Liturgische Gewänder):** *Kasel (Messgewand), Dalmatik, Albe, Stola, Chormantel (Pluviale), Birett, Mitra, Pallium, Schultervelum, Zingulum, Talar*.
* **Sakrale Architektur & Kirchenausstattung:** *Hochaltar, Zelebrationsaltar, Tabernakel, Kanzel, Taufbecken/Taufstein, Chorgestühl, Beichtstuhl, Sakristei, Marienaltar, Pietà, Kreuzwegstation, Epitaph, Orgelprospekt, Glockenstuhl, Baldachin, Lettner*.
* **Liturgische Feiern & Riten:** *Fronleichnamsprozession, Primiz, Erstkommunion, Firmung, Priesterweihe, Bischofsweihe, Ewige Anbetung, Bittprozession, Maiandacht, Karfreitagsliturgie, Patrozinium, Pontifikalamt, Vesper*.
* **Klerus & Ordenswesen:** *Bischof, Weihbischof, Abt/Äbtissin, Pfarrer, Kaplan, Diakon, Ministrant, Ordensschwester/Nonne (Habit), Franziskaner, Benediktiner, Jesuiten, Dominikaner, Zisterzienser*.

### Technische Umsetzungsaufgaben
- [x] **Thesaurus-basierte Synonym-Erweiterung (Query Expansion):**
  * Sucht ein Nutzer nach *„Messgewand“*, expandiert die Such-Engine im Hintergrund automatisch auf *„Kasel“*, *„Parament“*, *„Pluviale“* und *„Dalmatik“*.
  * Sucht jemand nach *„Monstranz“*, werden auch *„Allerheiligstes“*, *„Ostensorium“* oder *„Aussetzung“* semantisch assoziiert.
- [x] **Zero-Shot Prompt-Katalog für kirchliche Motive:**
  * Vorberechnete OpenCLIP-Embeddings für die wichtigsten kirchlichen Begriffe (GND/Iconclass), um bei neu indexierten Bildern automatisch passende Schlagwort-Vorschläge zu generieren (ohne zusätzlichen VRAM-Bedarf).
- [x] **Iconclass-Notationen im XMP-Sidecar:**
  * Optionale Einbettung von Iconclass-Codes (z. B. `11Q714` für Messfeier/Liturgie) in die standardisierten `.xmp`-Metadaten.

---

## 21. Archivische Findbuch-Synchronisation (Echtes Read-Only-Sync über bestehenden Fileservern)
* **Ziel:** Das System fungiert als intelligenter Indexierungs- und Recherche-Layer über unveränderten Fileservern und bindet bestehende analoge oder digitale Findbücher nahtlos ein.
* **Archivischer Mehrwert gegenüber Standard-Software:**
  * Kommerzielle Tools erzwingen häufig den Import in proprietäre Datenbankstrukturen oder das Umbenennen/Verschieben von Ordnern; Metadaten müssen mühsam doppelt gepflegt werden.
  * Dieses System belässt den Fileserver 100 % unberührt (read-only) und synchronisiert externe Findbücher deklarativ.
* **Aufgaben:**
  - [ ] **Ingest externer Findbücher (CSV, Excel, XML/EAD):**
    * Einlesen bestehender Tabellen und Findbücher über eine intuitive Schnittstelle im Import-Tab.
  - [ ] **Automatischer Signatur- & Bestandsabgleich:**
    * Automatischer Match zwischen Findbuch-Datensätzen und Bilddateien anhand von Archivsignatur, Dateinamen oder Ordnerstrukturen.
  - [ ] **Gemeinsame Verschmelzung in der Recherche:**
    * Findbuch-Metadaten (Provenienz, Aktentitel, Altsignatur, Sperrfrist, Enthält-Vermerke) und KI-Erkennungen (CLIP-Motive, Gesichter, OCR) verschmelzen in einer einheitlichen Detailansicht, ohne dass das originale Archivverzeichnis verändert werden muss.

---

## 22. Alters- & Zeitstrahl-Mapping für Personen (Age-Invariant Face Tracking über Jahrzehnte)
* **Ziel:** Zuverlässige Identifikation und Zusammenführung derselben historischen Persönlichkeit über eine Lebensspanne von 30 bis 60 Jahren hinweg.
* **Archivischer Mehrwert gegenüber Standard-Software:**
  * Kommerzielle Consumer-Tools (Apple Photos, Google Photos, Standard-ArcFace) erkennen dieselbe Person oft nicht mehr wieder, wenn zwischen den Aufnahmen 30 oder 50 Jahre liegen (z. B. der Neupriester mit 25 Jahren vs. derselbe Mann als Weihbischof mit 70 Jahren).
  * Durch Altersmerkmale (Falten, graue Haare/Kahlheit, Brillen, veränderte Gesichtsform) sinkt die biometrische Vektordistanz unter den üblichen Schwellenwert.
* **Aufgaben:**
  - [ ] **Biografische Lebensdaten-Verknüpfung:**
    * Hinterlegung von Lebensdaten (Geburtsjahr, Weihe-/Amtsantrittsjahr, Sterbejahr) direkt am Personen-Cluster.
    * Automatische chronologische Sortierung der Cluster-Fotos entlang eines visuellen Lebens-Zeitstrahls.
  - [ ] **Adaptive Ähnlichkeits-Schwellenwerte für Altersübergänge:**
    * Dynamische Anpassung des mathematischen Schwellenwerts: Liegen zwei Aufnahmen zeitlich weit auseinander (z. B. 1935 vs. 1970), nutzt das System adaptive Toleranzen und fokussiert unveränderliche skelettäre Gesichtsmerkmale (Augenabstand, Nasenwurzel, Ohr- und Kinnproportionen).
  - [ ] **Vorschlagssystem für „Mögliche Identitäten über Jahrzehnte“:**
    * Intelligenter Prüf-Vorschlag im Cluster-Detail: *„Könnte dieser Alumnus von 1935 derselbe Domkapitular auf dem Foto von 1968 sein?“*
    * Ermöglicht Archivaren das Zusammenführen von „Jung-“ und „Alt-Clustern“ mit einem Klick (Merge) unter Erhalt der biometrischen Altersspanne.

---

## 23. Personen-Netzwerke & Co-Occurrence-Navigation (Graph-Erkundung & Beziehungsanalyse)
* **Ziel:** Aufdecken verborgener historischer Beziehungen, Cliquen und Netzwerke durch gemeinsame Bildauftritte (Co-Occurrences) und nahtlose Navigation von Person zu Person („Wikipedia-Prinzip“).
* **Archivischer Mehrwert:**
  * **Historische Deduktion:** Unbenannte Personen im Umfeld prominenter Persönlichkeiten (z. B. *„Wer ist der unbekannte Geistliche, der auf 6 verschiedenen Fotos neben Bischof Müller steht?“*) können über Co-Occurrence-Muster und Aktenabgleich in Minuten identifiziert werden.
  * **Serendipity & freies Erkunden:** Archivare und Historiker können sich von Foto zu Foto durch das soziale Geflecht einer Stadt oder Pfarrei hangeln, ohne die Recherche abbrechen zu müssen.
* **Aufgaben:**
  - [x] **Direktsprung zum Cluster jeder abgebildeten Person (Cross-Cluster-Navigation):**
    * Im Bild-Detailmodal und in den Gesichts-Tags: Klick auf eine Person B auf dem Foto von Person A führt mit einem Klick direkt zu allen Bildern von Person B (`jumpToCluster`).
  - [x] **Schnittmengen-Filter (Gemeinsame Aufnahmen zweier Personen):**
    * Schnellfilter-Aktion: *„Zeige alle Fotos, auf denen Person A und Person B gemeinsam abgebildet sind“* (Qdrant-Schnittmenge der Elternbilder zweier Cluster über `/network/shared-images`).
  - [x] **Häufigkeits-Rangliste der Begleitpersonen (Co-Occurrence Ranking):**
    * Statistische Auswertung im Personen-Profil: *„Wird oft gesehen mit: ...“* mit Profil-Chips, gemeinsamen Fotoanzahlen und 1-Klick-Filter (`/network/person/{cluster_id}/co-occurrences`).
  - [x] **Interaktiver Beziehungs-Graph (Netzwerk-Visualisierung):**
    * Neuer Tab „Netzwerk“ mit interaktiver Force-Directed Graph-Darstellung via lokal gebündeltem vis-network (Knoten = Personen-Crops, Kanten = gemeinsame Fotos; Kantendicke = Häufigkeit, Tiefenstufen 1 & 2, Schwellenwert-Filter, Klick-Zentrierung & Profil-Sprung).

---

## 24. Performanz- & Skalierungsarchitektur für Massen-Imports (Universelle Ingest-Pipeline)
* **Ziel:** Universeller, hardware-agnostischer und robuster Massen-Import, der auch bei großen Beständen (> 50.000 Bilder), über Netzwerkfreigaben (NAS/SMB) und auf variierender Hardware (starke GPU-Workstations bis Standard-Büro-Server ohne dedizierte GPU) dauerhaft performant bleibt und nicht mit wachsender Bildzahl einbricht.
* **Problemstellung & Flaschenhals-Analyse:**
  * Mit wachsender Collection-Größe (> 50.000 Bilder, > 160.000 Gesichter) wachsen die Kosten synchroner Einzel-Schreibvorgänge (`wait=true`) in Qdrant drastisch, da HNSW-Segmente im Hintergrund ständig reorganisiert werden.
  * Synchrone Netzwerk-Latenzen über FUSE/GVFS-Shares blockieren die KI-Inferenz; I/O und Compute laufen strikt nacheinander statt überlappend.
* **Aufgaben:**
  - [x] **Batch-Upserts in Qdrant:**
    * Vektoren nicht bildweise einzeln schreiben, sondern in konfigurierbaren Batches (z. B. 50–100 Bilder auf einmal) sammeln und gebündelt übertragen.
    * Reduziert den Qdrant-Lock- und WAL-Overhead um ca. 70–80 % und verhindert ständiges Einbremsen durch Segment-Flushes.
  - [x] **Asynchrones Prefetching & Pipelining (I/O- und Compute-Entkopplung):**
    * Entkopplung über Produzent-Konsument-Architektur (Worker-Queue): Das nächste Bild wird im Hintergrund über das Netzwerk gestreamt, validiert und vorbereitet, während die GPU/CPU noch an der Inferenz (CLIP / InsightFace) des aktuellen Bildes rechnet.
    * Beseitigt Leerlaufzeiten von Netzwerk und Recheneinheiten vollständig.
  - [x] **Echtes Kernel-CIFS-Mount & Netzwerk-I/O-Optimierung:**
    * NAS-Ordner fest über nativer Kernel-Treiber (`mount -t cifs`) einbinden statt über die träge, single-threaded GVFS-Desktop-Emulation (`/run/user/1000/gvfs/...`).
    * Dokumentation und Prüf-Routine im System, die bei GVFS-Pfaden warnt und CIFS-Optionen vorschlägt.
  - [x] **Universeller, hardware-agnostischer Lösungsansatz:**
    * *Dynamische Ressourcen-Adaption:* Automatische Erkennung der Systemressourcen (CUDA-VRAM, CPU-Kerne, RAM) und adaptive Anpassung von Batch-Größen und Worker-Threads (`app/core/system_profile.py`).
    * *Temporäres Deferral der HNSW-Indexierung bei Massen-Imports:* Automatisches Aussetzen des HNSW-Indexbaus (`indexing_threshold=0`) bei großen Bulk-Imports (>= 500 Bilder) und optimierter Wiederaufbau nach Abschluss.
    * *Stabile I/O-Pufferung:* Sicheres Zwischenspeichern im lokalen Cache und begrenzte Queue.

---

## 25. UI-Responsivität & Entkopplung von Lese-/Schreiblast während aktiver Hintergrund-Imports
* **Ziel:** Das Web-Frontend (Personen-Cluster, Detailansichten, Suchanfragen, Bildbetrachtung) muss sich auch während eines laufenden massiven Hintergrund-Imports mit maximaler Geschwindigkeit (< 50 ms) bedienen lassen, ohne durch Datenbank-Sperren oder Netzwerk-I/O ausgebremst zu werden.
* **Problemstellung & Analyse:**
  * Bisher scrollt `get_clusters()` bei jedem Aufruf über 80 HTTP-Requests hinweg sämtliche 160.000 Gesichter aus Qdrant (Dauer: ~13,5 s), während der Import mit `wait=true` im Sekundentakt Schreib-Locks auf dieselbe Collection setzt.
  * Beim Klick auf ein Cluster versucht der Webserver ad-hoc über die überlastete SMB/GVFS-Netzwerkverbindung Vorschaubilder vom NAS zu generieren, während der Import dieselbe Leitung belegt.
  * Webserver und Import teilen sich im selben Python-Prozess den Global Interpreter Lock (GIL) und CPU-Ressourcen ohne Vorrangsteuerung.
* **Aufgaben:**
  - [x] **SQLite als primärer Index für Cluster-Metadaten (Aggregationen entkoppeln):**
    * Anlage einer relationalen Tabelle `clusters (id TEXT PRIMARY KEY, name TEXT, face_count INTEGER, preview_image TEXT, last_updated TIMESTAMP)` in der lokalen SQLite-Datenbank (`app/services/metadata_db.py`).
    * `get_clusters()` liest die Liste in < 1 ms direkt aus SQLite, anstatt 160.000 Vektorpunkte über HTTP aus Qdrant zu scrollen. Qdrant wird ausschließlich für Vektorähnlichkeit genutzt, nicht für relationale `GROUP BY`-Abfragen.
  - [x] **Proaktives Thumbnail-Caching direkt beim Import:**
    * Der Import-Job schneidet die 160-Pixel-Gesichtsausschnitte und WebP-Thumbnails direkt während des Lesens auf die lokale SSD (`.cache/thumbnails/`), da das Bild und die Bounding-Box ohnehin im RAM liegen.
    * Beim Klick auf ein Cluster im UI muss kein einziges Byte mehr über das NAS übertragen werden – 100 % der Porträts laden sofort von der lokalen SSD.
  - [x] **Nicht-blockierende Schreibvorgänge (`wait=False`) in Qdrant:**
    * Umstellung der Upsert-Aufrufe beim Import von synchron (`wait=True`) auf asynchron (`wait=False`) in Kombination mit Batches.
    * Qdrant nimmt Schreib-Batches sofort entgegen und glättet das Schreiben im Hintergrund, sodass Lese-Abfragen für die Benutzeroberfläche nicht blockiert werden.
  - [x] **Priorisierung für Web-Anfragen (Quality of Service / QoS & Prozess-Entkopplung):**
    * Ausführung rechenintensiver Import-Aufgaben mit niedrigerer CPU-Priorität (`os.nice(10)`).
    * Interaktive Benutzer-Requests (Cluster laden, Bilder betrachten, Freitextsuche) erhalten im Betriebssystem sofort Vorrang vor dem Hintergrund-Import.

---

## 26. Umfassende Performance-Stellschrauben für Großbestände (> 100.000 Bilder)
* **Ziel:** Maximale System-Performance, Speichereffizienz und Reaktionsgeschwindigkeit über alle Ebenen hinweg (KI-Inferenz, Vektordatenbank, Relationale Datenbank, Browser-DOM).
* **Priorisierte Handlungsfelder & Aufgaben:**
  - [x] **Vektordatenbank & Qdrant-Engine:**
    * *Skalare Quantisierung (INT8):* Aktivierung von Qdrants `ScalarQuantization(int8)` für `archive_images` und `archive_faces`. Reduziert den RAM-Verbrauch um 75 % und beschleunigt Distanzberechnungen über AVX2/AVX-512 bzw. Tensor Cores um das 3- bis 4-fache bei > 99 % identischer Treffergüte.
    * *gRPC-Protokoll statt HTTP-REST:* Aktivierung von `prefer_grpc = True` (`QDRANT_GRPC_PORT = 6334`). Beseitigt den massiven JSON-Serialisierungs-Overhead für 512-dimensionale Float-Arrays zugunsten von binären Protobuf-Streams.
  - [x] **KI-Inferenz & GPU-Beschleunigung (OpenCLIP & InsightFace):**
    * *Mixed Precision Inferenz (FP16 / Tensor Cores):* Ausführung von OpenCLIP via `torch.cuda.amp.autocast(dtype=torch.float16)` zur vollen Ausnutzung der NVIDIA Tensor Cores. Verdoppelt bis verdreifacht die Inferenzrate bei halbiertem VRAM-Bedarf.
    * *Intelligentes Vorab-Downsampling vor KI & Hashing:* Herunterskalieren sehr großer Masterscans (15–50 Megapixel) auf max. 1.600–2.000 Pixel vor der Übergabe an CLIP ($224 \times 224$), InsightFace ($640 \times 640$) und pHash/dHash. Spart bis zu 60 % CPU-Dekompressionszeit und verhindert RAM-Spitzen.
    * *Batching bei der Feature-Extraktion:* Vorbereitung von `embed_images_batch()` zur effizienten GPU-Auslastung.
  - [x] **Frontend & Browser-DOM:**
    * *Paginierung oder Virtual Scrolling für Personen-Cluster:* Einführung von Seitenblöcken (60 Karten/Seite) und „Weitere Personen laden“-Funktion in `#clusters-grid`. Verhindert Browser-Speicherüberlastung, Layout-Thrashing und träges Scrollen.
    * *WebP-Thumbnails statt JPEG:* Umstellung der dynamischen Thumbnail-Erzeugung (`/images/serve` und Vorschaubilder) auf WebP. Reduziert die Bild-Payloads um 30–50 % bei identischer visueller Schärfe.
  - [x] **Relationale Datenbank & Metadaten (SQLite):**
    * *Aktivierung des WAL-Modus (Write-Ahead Logging):* Konfiguration von `PRAGMA journal_mode = WAL;`, `PRAGMA synchronous = NORMAL;` und 64 MB RAM-Cache (`PRAGMA cache_size = -64000;`). Stellt sicher, dass Lese- und Schreibzugriffe vollständig entkoppelt sind und sich niemals gegenseitig blockieren.

---

## 27. OOM-Schutz, Speichersicherheit & Prozess-Robustheit für Langzeit-Imports & Massen-Clustering
* **Ziel:** 100 % Stabilität bei tagelangen Dauer-Imports (> 70.000 Bilder, > 200.000 Gesichter) ohne Speicherlecks, Heap-Aufblähung oder OOM-Killer-Abstürze durch den Linux-Kernel.
* **Problemstellung & Analyse:**
  * Nach 19 Stunden Dauer-Import erreichte der Uvicorn/FastAPI-Prozess über 53 GB RAM (RSS) und 97 GB virtuellen Speicher, bis der Linux-Kernel den Prozess mit SIGKILL beendete.
  * Ursachen:
    1. Akkumulation von Speicherarenen in ONNX Runtime (InsightFace) und PyTorch CUDA Caching über zehntausende unterschiedliche Bildauflösungen ohne periodisches `gc.collect()` / `empty_cache()`.
    2. Nicht-geschlossene PIL-Bildobjekte und In-Memory-Byte-Puffer führen zu massiver glibc-Heapfragmentierung.
    3. Automatisches DBSCAN-Clustering von über 200.000 Gesichtern im selben Atemzug: Scikit-learns `BallTree` mit 8 Worker-Threads in 512 Dimensionen erzeugt eine Speicher-Explosion bei der Nachbarschaftsberechnung.
    4. Fehlende Prozess-Isolation: Der Import läuft im selben Python-Prozess wie der Webserver.
    5. Workstation-Konfiguration: Nur 8 GB Swap auf einer 61-GB-RAM-Maschine lässt keinen Puffer für kurze Spitzen.
* **Aufgaben:**
  - [x] **1. Speicherbereinigung & Leak-Prävention im Import-Loop (`indexing_service.py`):**
    * Periodischer Flush alle 50–100 Bilder: Explizites `gc.collect()` und `torch.cuda.empty_cache()` (falls CUDA aktiv).
    * Sofortiges Schließen und Freigeben von PIL-Image-Objekten (`pil_img.close()`, `raw_transposed.close()`, `del prepared_data`) nach der Merkmalsextraktion.
    * Begrenzung von Puffer- und Queue-Objekten, um Speicher-Aufstauungen zu unterbinden.
  - [x] **2. Entkopplung des automatischen Massen-Clusterings (`archive.py`):**
    * Kein unkontrolliertes automatisches Voll-Clustering von hunderttausenden Gesichtern direkt am Ende eines 19-stündigen Massen-Imports im Webserver-Thread.
    * Konfigurierbares Schwellenwert-Verhalten: Bei Großbeständen (> 5.000 Gesichter) wird der Import sauber beendet und das Clustering als separater, kontrollierter Schritt angeboten.
  - [x] **3. Skalierbares & speicherschonendes Clustering für Großbestände (> 200.000 Gesichter in `clustering_service.py`):**
    * Streaming- und Chunk-basiertes Laden aus Qdrant ohne 217.000 Python-Objekte gleichzeitig im Heap zu halten.
    * Beseitigung der Ball-Tree-Speicherfalle in 512 Dimensionen (Dimensionsreduktion/PCA oder Chunked/Cosine-Nachbarschaftssuche mit strengem Speicherlimit).
    * Payload-Updates in Qdrant in großen Chunks (z. B. 500 Punkte) zur Minimierung von Lock- und Netzwerk-Overhead.
  - [x] **4. Prozess-Isolation für Batch-Imports:**
    * Auslagerung rechenintensiver Massen-Imports in einen separaten Hintergrund-Subprozess (`multiprocessing.Process` / isolierter Worker-Task).
    * Nach Abschluss des Jobs gibt das Betriebssystem 100 % des C-Heaps (PyTorch, ONNX, PIL) an den Kernel zurück; der Webserver bleibt dauerhaft schlank bei ~200 MB RAM.
  - [x] **5. System- & Container-Absicherung (Workstation & Docker):**
    * Definition von Speicherobergrenzen (`mem_limit: 16g`, `mem_reservation: 4g`) in `docker-compose.yml` und Live-Aktivierung auf `archive_qdrant` via `docker update`. Verhindert unkontrollierte Speicherkonflikte zwischen Qdrant und Host.
    * Bereitstellung der Befehle zur NVMe-Swap-Erweiterung auf 40 GB (32 GB Zusatz-Swap auf `/dev/nvme0n1p2`), um dem Linux-Kernel bei massiven Spitzenlasten elastischen Puffer vor dem OOM-Killer zu geben.






