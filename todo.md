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
  - [ ] Inferenz-Geschwindigkeit (Sekunden pro 100 Scans) auf CPU und GPU messen.
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
  - [ ] **Farbprofile & Farbraum-Konvertierung (CMYK, 16-Bit Grayscale):**
    * Sicheres Abfangen von CMYK-TIFFs, 16-Bit-Graustufen und unkomprimierten Repro-TIFFs via Pillow statt nacktem `cv2.imread`.
    * Automatische, farbgetreue Normalisierung zu 8-Bit-sRGB vor der Weitergabe an Inferenz-Pipelines.
  - [ ] **Decompression-Bomb-Schutz konfigurieren:**
    * Anheben bzw. Absichern von `Image.MAX_IMAGE_PIXELS` in Pillow, damit Großscans (z. B. 12.000 × 9.000 Pixel / 108 Megapixel) nicht mit `DecompressionBombError` abgebrochen werden.
  - [ ] **Skalierung vor KI-Inferenz (VRAM- & RAM-Schonung):**
    * Vor der Übergabe an CLIP und InsightFace hochauflösende Scans im Speicher auf max. 2.000 Pixel lange Kante herunterskalieren.
    * Verhindert Out-of-Memory-Crashes (OOM), spart bis zu 90 % Inferenzzeit und bewahrt die volle Erkennungsgenauigkeit.

---

## 11. Effizientes Caching & Thumbnail-Management (Proaktive Pipeline)
* **Ziel:** Blitzschneller Seitenaufbau ohne Netzwerklast beim Durchsuchen zehntausender Bestände.
* **Aufgaben:**
  - [ ] **Proaktive Thumbnail-Generierung beim Erst-Indexieren:**
    * Direkt beim Indexieren Ablage eines standardisierten Web-Thumbnails (WebP, max. 800 px) sowie quadratischer 160 px-Gesichtscrops im Cache-Verzeichnis (`./data/thumbnails`).
    * Beseitigt Verzögerungen durch On-the-fly-Konvertierung bei großen Trefferlisten.
  - [ ] **Konsequenter Verzicht auf Originale im Galerie-Betrieb:**
    * Galerien, Suchlisten und Leuchttisch laden ausschließlich die leichten WebP-Derivate; das hochauflösende Master-Original wird erst beim Hineinzoomen (> 100 %) oder im Download/Export geladen.

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
  - [ ] **Automatische Paar-Erkennung (Zweiblatt-Logik):**
    * Zusammenführen von `_r`/`_v`-Dateipaaren zu einem gemeinsamen archivischen Datensatz.
  - [ ] **Rückseiten-Notiz als Primär-Metadatum des Vorderseiten-Fotos:**
    * Der per OCR/VLM auf der Rückseite entzifferte handschriftliche Text (z. B. *„Fronleichnam 1928, Pfarrer Huber mit Kirchenchor“*) wird als Primär-Metadatum direkt mit dem Vorderseiten-Foto verknüpft und semantisch indexiert.
    * Bei der Freitextsuche nach Begriffen auf der Rückseite wird direkt das Vorderseiten-Foto als Suchtreffer ausgegeben.
  - [ ] **Interaktiver 3D-Karten-Flip im Bild-Modal:**
    * Button „Rückseite ansehen / Umdrehen“ mit animiertem Karten-Wechsel zwischen Vorder- und Rückseite.

---

## 15. IIIF Image API 3.0 & Deep Zoom (Pyramidales Kacheln)
* **Ziel:** Flüssige Betrachtung gigapixel-großer Scans (Glasplatten, Repros > 100 MB) im Webbrowser ohne RAM-Überlastung des Clients.
* **Aufgaben:**
  - [ ] **Leichtgewichtiger IIIF-Kacheldienst:**
    * Implementierung eines lokalen IIIF-Image-API-konformen Endpunkts (`/iiif/{id}/...`) auf Basis dynamischer Kachelung (Pillow / libvips / pyramidales WebP).
  - [ ] **Deep-Zoom-Integration (OpenSeadragon / Mirador):**
    * Flüssiges Hineinzoomen bis auf den Seidenfaden historischer Paramente oder Inschriften auf Kirchturm-Glocken.

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


