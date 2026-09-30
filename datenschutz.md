# Datenschutzkonzept & DSGVO-Hinweise

**Projekt:** Lokales Bildarchiv-Suchsystem für historische Bestände (GLAM)  
**Betreiber / Verantwortliche Stelle:** Archiv / Museum  
**Stand:** Oktober 2026

---

## 1. Grundprinzipien: Privacy by Design & Datensparsamkeit

Dieses Bildarchiv-Suchsystem wurde nach den Grundsätzen des Art. 5 DSGVO (*Rechtmäßigkeit, Zweckbindung, Datenminimierung, Speicherbegrenzung, Integrität und Vertraulichkeit*) sowie Art. 25 DSGVO (*Datenschutz durch Technikgestaltung und datenschutzfreundliche Voreinstellungen*) konzipiert.

### Technische Kernmerkmale
1. **100 % Lokale Datenverarbeitung:**
   * Weder Bilddateien noch Berechnungen (Embeddings, Vektoren) verlassen das lokale System.
   * Keine Anbindung an externe Cloud-Dienste, kommerzielle KI-APIs oder Tracking-Dienste.
   * **Vollständiger Offline-Betrieb des Web-Frontends:** Sämtliche Stylesheets (CSS) und Schriften sind lokal gebündelt. Es werden keine Verbindungen zu externen Content Delivery Networks (wie Google Fonts oder Tailwind CDN) aufgebaut.
2. **Datenschutzfreundliche Voreinstellung (Privacy by Default, Art. 25 Abs. 2 DSGVO):**
   * Die biometrische Gesichtserkennung ist standardmäßig **deaktiviert** (`ENABLE_FACE_RECOGNITION=false`).
   * Das System startet rein als semantische Motiv- und Metadaten-Suchmaschine ohne Erfassung biometrischer Merkmale.
3. **Keine Speicherung von Bilddaten in der Datenbank:**
   * Die Vektordatenbank Qdrant speichert ausschließlich mathematische Vektoren (512 Gleitkommazahlen) und technische Referenzpfade.
   * Die Originalbilder verbleiben unverändert in ihren geschützten Dateisystem-Archivverzeichnissen.
4. **Keine demografischen Personenprofile:**
   * Es werden keine demografischen Merkmale wie Ethnie, Geschlecht oder Alter geschätzt oder persistiert.
   * Es werden ausschließlich geometrische Koordinaten (Bounding Boxes) und mathematische Ähnlichkeitsvektoren verarbeitet.

---

## 2. Verarbeitung biometrischer Daten (Art. 9 DSGVO)

Gesichts-Embeddings (ArcFace 512-dim) stellen nach Art. 4 Nr. 14 DSGVO **biometrische Daten** dar, da sie durch ein spezielles technisches Verfahren gewonnen werden und die Identifizierung oder Wiedererkennung einer natürlichen Person ermöglichen.

### Rechtsgrundlagen der Verarbeitung
* **Historische Archive & Wissenschaft (Art. 89 DSGVO i. V. m. Landesarchivgesetzen / BDSG § 27 / § 28):**
  Die Verarbeitung von Archivgut im öffentlichen Interesse oder zu wissenschaftlichen und historischen Forschungszwecken ist privilegiert.
* **Wahrung berechtigter Interessen (Art. 6 Abs. 1 lit. f DSGVO):**
  Erschließung, Dokumentation und Auffindbarkeit von historischem Kulturgut und Bildzeugnissen der Zeitgeschichte.
* **Schutzfristen & Gemeinfreiheit:**
  Für Personen der Zeitgeschichte bzw. bei verstorbenen Personen gilt: Das allgemeine Persönlichkeitsrecht schützt Verstorbene postmortal; die DSGVO selbst findet auf Verstorbene grundsätzlich keine direkte Anwendung (Erwägungsgrund 27 DSGVO). Landesrechtliche Archivschutzfristen bleiben unberührt.

### Schutzmaßnahmen
* **Zweistufige Aktivierung (Opt-in):** Die Gesichtsvektorisierung erfordert eine bewusste Konfiguration (`ENABLE_FACE_RECOGNITION=true` in der `.env` oder `--enable-faces` im CLI-Indexer).
* **Zugangsbeschränkungen:** Der Zugriff auf Backend und Datenbank ist auf autorisierte Rechner beschränkt; ein Pfad-Sandbox-Filter (`validate_safe_image_path`) verhindert unbefugten Zugriff außerhalb der freigegebenen Archivpfade.
* **Kuratierte Namensvergabe:** Klarnamen werden nicht automatisiert aus externen Quellen bezogen, sondern bedürfen der manuellen Zuweisung durch Archivpersonal.

---

## 3. Betroffenenrechte & Recht auf Vergessenwerden (Art. 15–21 DSGVO)

Sollten auf historischen oder zeitgeschichtlichen Fotografien lebende Personen abgebildet sein, stehen diesen die gesetzlichen Betroffenenrechte zu:

1. **Recht auf Auskunft (Art. 15 DSGVO):** Auskunft darüber, ob und welche Bilder/Merkmale verarbeitet werden.
2. **Recht auf Löschung („Recht auf Vergessenwerden“, Art. 17 DSGVO):**
   * **API-Löschung:** Über den Endpunkt `DELETE /images/record?path=...` können einzelne Bildvektoren und alle damit verknüpften Gesichtsvektoren sofort und unwiderruflich aus Qdrant entfernt werden.
   * **Automatisches Pruning:** Wird ein Bild aus dem Dateisystem entfernt, bereinigt der Befehl `indexer.py --prune` oder der Endpunkt `POST /api/system/prune` alle verwaisten Vektoreinträge aus der Datenbank.
3. **Recht auf Einschränkung der Verarbeitung (Art. 18 DSGVO):**
   * Gezielter Ausschluss bestimmter Sammlungen oder Ordner von der Gesichtserkennung über `--skip-faces`.
4. **Widerspruchsrecht (Art. 21 DSGVO):**
   * Betroffene können der Verwendung ihrer Abbildung widersprechen. Das Archiv prüft hierbei den Ausgleich zwischen Schutzinteressen der Person und dem öffentlichen Dokumentationsauftrag.

---

## 4. Technische und organisatorische Maßnahmen (TOM, Art. 32 DSGVO)

* **Sicherheit der Pfade:** Striktes Verbot von Pfad-Traversierungen (`../`); Anfragen nach Dateien außerhalb der konfigurierten Archivverzeichnisse werden mit HTTP 403 abgewiesen.
* **CORS-Einschränkung:** Das Backend ist nicht für beliebige Web-Ursprünge geöffnet, sondern beschränkt Anfragen auf die in `CORS_ORIGINS` definierten Domains.
* **Sichere Hash-Speicherung im Cache:** Temporäre Bild-Thumbnails werden unter MD5-Hash-Namen abgelegt, um Rückschlüsse im Cache zu minimieren.
