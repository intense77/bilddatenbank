# Datenschutzkonzept & KDG-/DSGVO-Hinweise

**Projekt:** Lokales Bildarchiv-Suchsystem für historische Bestände (GLAM / Diözesanarchive)  
**Betreiber / Verantwortliche Stelle:** Diözesanarchiv / Kirchliches Archiv / Museum  
**Stand:** Oktober 2026

---

## 1. Grundprinzipien: Privacy by Design, Datensparsamkeit & Datenhoheit

Dieses Bildarchiv-Suchsystem wurde nach den Grundsätzen des **Gesetzes über den Kirchlichen Datenschutz (KDG)** (bzw. Art. 5 DSGVO) konzipiert: *Rechtmäßigkeit, Zweckbindung, Datenminimierung, Speicherbegrenzung, Integrität und Vertraulichkeit* (§ 7 KDG) sowie *Datenschutz durch Technikgestaltung und datenschutzfreundliche Voreinstellungen* (§ 26 KDG / Art. 25 DSGVO).

### Technische Kernmerkmale
1. **100 % Lokale Datenverarbeitung (Vollständige Datenhoheit):**
   * Weder Bilddateien noch Berechnungen (Embeddings, Vektoren) verlassen das lokale Netzwerk der kirchlichen Einrichtung.
   * **Keine Drittlandübermittlung (§§ 37–41 KDG):** Keine Anbindung an US-amerikanische oder kommerzielle Cloud-Dienste (wie Microsoft Azure AI, OpenAI oder AWS) – damit entfallen komplexe AV-Verträge, Standardvertragsklauseln und CLOUD-Act-Konflikte.
   * **Vollständiger Offline-Betrieb des Web-Frontends:** Sämtliche Stylesheets (CSS) und Schriften sind lokal gebündelt. Es werden keine Verbindungen zu externen Content Delivery Networks (wie Google Fonts oder Tailwind CDN) aufgebaut.
2. **Keine Speicherung von Bilddaten in der Datenbank:**
   * Die Vektordatenbank Qdrant speichert ausschließlich mathematische Vektoren (512 Gleitkommazahlen) und technische Referenzpfade.
   * Die Originalbilder verbleiben unverändert in ihren geschützten Dateisystem-Archivverzeichnissen.
3. **Keine demografischen Personenprofile:**
   * Es werden keine demografischen Merkmale wie Ethnie, Geschlecht oder Alter geschätzt oder persistiert.
   * Es werden ausschließlich geometrische Koordinaten (Bounding Boxes) und mathematische Ähnlichkeitsvektoren verarbeitet.

---

## 2. Verarbeitung biometrischer Daten & das Kirchliche Archivprivileg (§ 29 KDG)

Gesichts-Embeddings (ArcFace 512-dim) stellen nach § 4 Nr. 14 KDG (bzw. Art. 4 Nr. 14 DSGVO) **biometrische Daten** dar, da sie durch ein spezielles technisches Verfahren gewonnen werden und die Identifizierung oder Wiedererkennung einer natürlichen Person ermöglichen.

### Rechtsgrundlagen der Verarbeitung im kirchlichen Archiv
1. **Kirchliches Archivprivileg (§ 29 KDG / Art. 89 DSGVO):**
   * § 29 Abs. 1 KDG regelt die *Verarbeitung zu Archivzwecken im kirchlichen Interesse*. Er erlaubt die Verarbeitung besonderer Kategorien personenbezogener Daten (§ 11 Abs. 1 KDG – inklusive biometrischer Merkmale) **ausdrücklich ohne gesonderte Einwilligung der betroffenen Personen**, sofern dies für den kirchlichen Archivauftrag erforderlich ist.
2. **Verstorbene Personen & Kirchliche Archivordnung (KAO):**
   * Das KDG findet auf Verstorbene grundsätzlich keine direkte Anwendung (allgemeine Rechtsauffassung entsprechend Erwägungsgrund 27 DSGVO). Für historische Fotografien verstorbener Persönlichkeiten der Zeitgeschichte (Bischöfe, Pfarrer, Ordensleute, Gemeindevertreter) greift das postmortale Persönlichkeitsrecht sowie die Schutzfristen der jeweiligen Diözesanarchivordnung (KAO).
3. **Wahrung berechtigter Interessen (§ 6 Abs. 1 lit. g KDG / Art. 6 Abs. 1 lit. f DSGVO):**
   * Wissenschaftliche Erschließung, Bewahrung und Auffindbarkeit von historischem Kulturgut und Zeugnissen der Bistumsgeschichte.

---

## 3. Funktion des System-Schalters: Ressourcensteuerung & Bestandspolitik

> **Wichtige Klarstellung zur Frage des „Opt-in“:**  
> Das System verlangt **kein individuelles Opt-in der abgebildeten Personen**, da die interne Erschließung durch § 29 KDG gesetzlich legitimiert ist.  
> Der Konfigurationsschalter `ENABLE_FACE_RECOGNITION=false/true` ist vielmehr ein **administratives Steuerungswerkzeug des Archivars**.

### Warum dieser Schalter im Archivalltag unverzichtbar ist:

1. **Ressourcen- & Performance-Gewinn:**
   * Das Laden der Gesichtsmodelle (RetinaFace + ArcFace) bindet dauerhaft ca. 1,5 bis 2 GB RAM/VRAM und verlangsamt die Inferenz.
   * Viele typische Bestände in Diözesanarchiven enthalten **überhaupt keine Personen** (z. B. Architekturaufnahmen von Kirchen und Klöstern, Inventaraufnahmen von Monstranzen, Altären und Kelchen, Paramente, Urkunden oder Siegel).
   * Wird ein solcher Bestand eingelesen, schaltet der Archivar die Gesichtserkennung ab (`--skip-faces` bzw. `ENABLE_FACE_RECOGNITION=false`). Das System verarbeitet die Scans **3- bis 5-mal schneller** und läuft auf Standard-Bürorechnern flüsterleise.

2. **Differenzierte Bestandspolitik (§ 29 Abs. 2 KDG):**
   * § 29 Abs. 2 KDG verlangt angemessene Schutzmaßnahmen zur Wahrung der Grundrechte. Archive unterscheiden hier in der Praxis:
     * **Historische Altbestände (bis ca. 1950/1960):** Priesterporträts, Weihen, Kirchenbau. Alle Personen sind verstorben → **Biometrie permanent AN** (`ENABLE_FACE_RECOGNITION=true`).
     * **Jüngere Bestände / Zeitgeschichte (ab ca. 1980 bis heute):** Pfarrfeste, Erstkommunionen, Jugendtage mit vielen lebenden Gemeindemitgliedern und Kindern → **Biometrie AUS**, reine semantische CLIP-Suche reicht völlig aus.
   * Mit den CLI-Flags (`--enable-faces` vs. `--skip-faces`) behält der Archivar die präzise Kontrolle über jeden einzelnen Bestand.

3. **Dauerhafter Regelbetrieb im internen Archivnetz:**
   * Wenn das System auf einem internen Archivserver steht und primär historische Fotobestände erschließt, kann `ENABLE_FACE_RECOGNITION=true` in der `.env` **dauerhaft aktiviert werden**.
   * Die biometrischen Funktionen stehen dann allen autorisierten Archivaren nahtlos zur Verfügung, während gegenüber dem Diözesandatenschutzbeauftragten (DDSB) die Einhaltung von § 26 KDG (*Privacy by Design*) nachgewiesen werden kann.

---

## 4. Betroffenenrechte & Recht auf Vergessenwerden (§§ 17–25 KDG / Art. 15–21 DSGVO)

Sollten auf Fotografien lebende Personen abgebildet sein, stehen diesen die gesetzlichen Betroffenenrechte zu:

1. **Recht auf Auskunft (§ 17 KDG):** Auskunft darüber, ob und welche Bildmerkmale verarbeitet werden.
2. **Recht auf Löschung („Recht auf Vergessenwerden“, § 19 KDG / Art. 17 DSGVO):**
   * **Punktgenaue API-Löschung:** Über den Endpunkt `DELETE /images/record?path=...` können einzelne Bildvektoren und alle damit verknüpften Gesichtsvektoren sofort und unwiderruflich aus Qdrant entfernt werden.
   * **Automatisches Pruning:** Wird ein Bild aus dem Dateisystem entfernt, bereinigt der Befehl `indexer.py --prune` oder der Endpunkt `POST /api/system/prune` alle verwaisten Vektoreinträge aus der Datenbank.
3. **Recht auf Einschränkung der Verarbeitung (§ 20 KDG):**
   * Gezielter Ausschluss bestimmter Sammlungen oder Ordner von der Gesichtserkennung über `--skip-faces`.
4. **Widerspruchsrecht (§ 23 KDG):**
   * Betroffene können der Verwendung ihrer Abbildung widersprechen. Das Archiv prüft den Ausgleich zwischen Schutzinteressen der Person und dem kirchlichen Dokumentationsauftrag.

---

## 5. Technische und organisatorische Maßnahmen (TOM, § 27 KDG / Art. 32 DSGVO)

* **Zugangsbeschränkung & Berechtigungskonzept:** Das System ist für den internen Einsatz konzipiert; kein offener, unauthentifizierter Zugang aus dem öffentlichen Internet.
* **Sicherheit der Pfade:** Striktes Verbot von Pfad-Traversierungen (`../`); Anfragen nach Dateien außerhalb der konfigurierten Archivverzeichnisse werden von `validate_safe_image_path` abgewiesen.
* **CORS-Einschränkung:** Das Backend beschränkt Web-Aufrufe strikt auf die in `CORS_ORIGINS` definierten Domains.
* **Sichere Hash-Speicherung im Cache:** Temporäre Bild-Thumbnails werden unter MD5-Hash-Namen abgelegt, um Rückschlüsse im Cache zu minimieren.
* **Kuratierte Namensvergabe:** Klarnamen werden nicht automatisiert zugewiesen, sondern bedürfen der manuellen Verifikation durch das Archivpersonal.
