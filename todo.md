# Offene Aufgaben (Roadmap & Backlog)

Dieses Dokument erfasst die noch offenen Handlungsfelder und geplanten Weiterentwicklungen für das historische Bildarchiv-Suchsystem aus Sicht von Langzeitarchivierung, Datensparsamkeit und Performance.

---

## 1. Ressourcen- & Skalierungsoptimierung beim Personen-Clustering
* **Ziel:** Robuste, speicherschonende Clusterbildung auch bei Beständen von über 20.000 Gesichtern.
* **Technischer Hintergrund:**
  * Derzeit nutzt [clustering_service.py](file:///home/norbert/Bilderdatenbank/app/services/clustering_service.py) `DBSCAN(metric='cosine')`, was in Scikit-Learn eine quadratische $N \times N$-Distanzmatrix im RAM anlegt ($O(N^2)$).
  * Da ArcFace-Embeddings L2-normalisiert sind ($\|u\|=1$), entspricht die Cosine-Distanz mathematisch der halben quadrierten euklidischen Distanz:
    $$\text{dist}_{\text{cosine}}(u, v) = 1 - \langle u, v \rangle = \frac{1}{2} \|u - v\|^2 \iff \|u - v\| = \sqrt{2 \cdot \text{dist}_{\text{cosine}}(u, v)}$$
* **Aufgaben:**
  - [ ] Umstellung von `metric='cosine'` auf `metric='euclidean'` mit $\varepsilon_{\text{euclid}} = \sqrt{2 \cdot \varepsilon_{\text{cosine}}}$.
  - [ ] Nutzung von raumteilenden Bäumen (`algorithm='ball_tree'` oder `'kd_tree'`) für $O(N \log N)$ Laufzeit und minimalen Speicherbedarf.
  - [ ] Optional: Chunking / Batching bei sehr großen Porträtsammlungen (> 50.000 Gesichter).

---

## 2. Provenienz & Revisionssicherheit bei Personen-Labels
* **Ziel:** Wissenschaftliche Nachvollziehbarkeit und Schutz vor unabsichtlichem Überschreiben bei der Zuweisung von Klarnamen.
* **Aufgaben:**
  - [ ] Speichern von Revisionsdaten im Qdrant-Payload bei Labelvergabe:
    * `labeled_at`: ISO-Zeitstempel der Benennung.
    * `labeled_by`: Benutzer-/Archivarskennung (z. B. aus Request-Header oder Konfiguration).
    * `previous_labels`: Historie bisheriger Zuweisungen.
  - [ ] Anzeige der Benennungs-Historie und des Bearbeiters in der Personen-Detailansicht des Web-Frontends.

---

## 3. End-to-End-Praxistest & Benchmark mit Echtdaten
* **Ziel:** Validierung der Performanz und Benutzerfreundlichkeit unter realen Museums-/Archivbedingungen.
* **Aufgaben:**
  - [ ] Testbestand historischer Scans (z. B. Glasplattennegative, Repros, Porträtkarten) in `./data` einspielen.
  - [ ] Inferenz-Geschwindigkeit (Sekunden pro 100 Scans) auf CPU und GPU messen.
  - [ ] Visuelle Begutachtung der Bounding-Box-Positionierung und Ähnlichkeitstreffer im Web-Frontend.
  - [ ] Dokumentation optimaler Batch-Größen für Standard-Bürorechner ohne dedizierte GPU.

---

## 4. Langzeitarchivierung & Standard-Schnittstellen (GLAM)
* **Ziel:** Interoperabilität mit übergeordneten Museumsdatenbanken und Portalen (Deutsche Digitale Bibliothek, Europeana).
* **Aufgaben:**
  - [ ] Exportfunktion für Suchergebnisse und Cluster nach Dublin Core oder LIDO (Lightweight Information Describing Objects) im XML/JSON-LD-Format.
  - [ ] REST-Endpunkt für OAI-PMH (Open Archives Initiative Protocol for Metadata Harvesting).
