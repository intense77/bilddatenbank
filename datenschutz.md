# Datenschutzkonzept & DSGVO-Hinweise

**Projekt:** Lokales Bildarchiv-Suchsystem für historische Bestände  
**Betreiber / Verantwortliche Stelle:** Archiv / Museum  
**Stand:** September 2026

---

## 1. Grundprinzipien: Privacy by Design & Datensparsamkeit

Dieses Bildarchiv-Suchsystem wurde nach den Grundsätzen des Art. 5 DSGVO (*Rechtmäßigkeit, Zweckbindung, Datenminimierung, Speicherbegrenzung, Integrität und Vertraulichkeit*) sowie Art. 25 DSGVO (*Datenschutz durch Technikgestaltung und datenschutzfreundliche Voreinstellungen*) konzipiert.

### Technische Kernmerkmale
1. **100 % Lokale Datenverarbeitung:**
   * Weder Bilddateien noch Berechnungen (Embeddings, Vektoren) verlassen das lokale System.
   * Keine Anbindung an externe Cloud-Dienste, kommerzielle KI-APIs (wie OpenAI, Google Vision oder Microsoft Azure) oder Tracking-Dienste.
2. **Keine Speicherung von Rohbildern in der Datenbank:**
   * Die Vektordatenbank Qdrant speichert ausschließlich mathematische Vektoren (512 Gleitkommazahlen) und technische Referenzpfade.
   * Die Originalbilder verbleiben unverändert in ihren geschützten Archivverzeichnissen.
3. **Keine Personenprofile:**
   * Es werden keine demografischen Merkmale wie Ethnie, Geschlecht oder Alter geschätzt oder persistiert.
   * Es werden ausschließlich geometrische Koordinaten (Bounding Boxes) und abstrakte ArcFace-Vektoren gespeichert.

---

## 2. Verarbeitung biometrischer Daten (Art. 9 DSGVO)

Gesichts-Embeddings (ArcFace 512-dim) stellen nach Art. 4 Nr. 14 DSGVO **biometrische Daten** dar, da sie durch ein spezielles technisches Verfahren gewonnen werden und die Identifizierung oder Wiedererkennung einer natürlichen Person ermöglichen.

### Rechtsgrundlagen der Verarbeitung
* **Historische Archive & Wissenschaft (Art. 89 DSGVO i. V. m. Landesarchivgesetzen / BDSG § 27 / § 28):**
  Die Verarbeitung von Archivgut im öffentlichen Interesse oder zu wissenschaftlichen und historischen Forschungszwecken ist privilegiert.
* **Wahrung berechtigter Interessen (Art. 6 Abs. 1 lit. f DSGVO):**
  Erschließung, Dokumentation und Auffindbarkeit von historischem Kulturgut und Bildzeugnissen der Zeitgeschichte.
* **Schutzfristen & Gemeinfreiheit:**
  Für Personen der Zeitgeschichte bzw. bei verstorbenen Personen gilt: Das allgemeine Persönlichkeitsrecht schützt Verstorbene postmortal; die DSGVO selbst findet auf Verstorbene grundsätzlich keine direkte Anwendung (Erwägungsgrund 27 DSGVO), landesrechtliche Archivschutzfristen bleiben unberührt.

### Schutzmaßnahmen
* **Zugangsbeschränkungen:** Der Zugriff auf das Backend und die Datenbank ist auf das lokale Netzwerk bzw. autorisierte Archivare beschränkt.
* **Cluster-Zuordnung:** Klarnamen werden nicht automatisiert aus dem Internet bezogen, sondern bedürfen der manuellen Kuratierung und Freigabe durch das Archivpersonal.

---

## 3. Betroffenenrechte (Art. 15–21 DSGVO)

Sollten auf historischen oder zeitgeschichtlichen Fotografien lebende Personen abgebildet sein, stehen diesen die gesetzlichen Betroffenenrechte zu:

1. **Recht auf Auskunft (Art. 15 DSGVO):** Auskunft darüber, ob und welche Bilder/Merkmale verarbeitet werden.
2. **Recht auf Löschung („Recht auf Vergessenwerden“, Art. 17 DSGVO):**
   * Das System ermöglicht über die Qdrant-API das punktgenaue Löschen einzelner Gesichts-Points (`archive_faces`) anhand der Bild-ID oder Personen-ID.
   * Wird ein Bild aus dem Quellverzeichnis entfernt, kann der Vektoreintrag über den Indexer oder Qdrant bereinigt werden.
3. **Recht auf Einschränkung der Verarbeitung (Art. 18 DSGVO):**
   * Markierung von sensiblen Bildern oder Ausschluss bestimmter Ordner über die Indexierungs-Filter (`--skip-faces`).
4. **Widerspruchsrecht (Art. 21 DSGVO):**
   * Betroffene können der Verwendung ihrer Abbildung widersprechen. Das Archiv prüft hierbei den Ausgleich zwischen Schutzinteressen der betroffenen Person und dem öffentlichen Dokumentationsinteresse.

---

## 4. Technische und organisatorische Maßnahmen (TOM, Art. 32 DSGVO)

| Bereich | Maßnahme |
| :--- | :--- |
| **Netzwerksicherheit** | Der Server lauscht auf `0.0.0.0:8000` bzw. `127.0.0.1:8000`. Für den Produktivbetrieb im Museumsnetzwerk sollte eine Firewall oder ein Reverse Proxy (z. B. Nginx mit TLS/HTTPS und Authentifizierung) vorgeschaltet werden. |
| **Datenbankzugriff** | Der Qdrant-Port `6333` kann optional mit einem API-Schlüssel (`QDRANT_API_KEY`) gesperrt werden. |
| **Dateisystem-Rechte** | Das Storage-Volume `./qdrant_storage` und die Quellbilder sind mit restriktiven Dateisystemrechten des Betriebssystems (`chmod 700` bzw. `chown museum:museum`) geschützt. |
| **Keine Telemetrie** | Sämtliche Tracking- und Analytik-Komponenten der Bibliotheken sind deaktiviert. |

---

## 5. Löschkonzept & Datenbereinigung

1. **Löschen von Gesichts-Clustern:**
   Wird ein Personen-Cluster im Archiv gelöscht, werden alle assoziierten Einträge in der Collection `archive_faces` unwiderruflich entfernt.
2. **Bereinigung bei Deindexierung:**
   Wird ein Archivbestand physisch gelöscht, werden bei einem Neuaufbau oder über gezielte Bereinigungsskripte alle zugehörigen Vektoren aus `archive_images` und `archive_faces` gelöscht.
