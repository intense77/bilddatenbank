# Freigabedokument für IT-Sicherheit & Datenschutz

**Dokument-ID:** FREIGABE-IT-DS-2026-01  
**Projekt:** Lokales Bildarchiv-Suchsystem & KI-Assistenz für historische Sammlungen  
**Version:** 2.0 (Stand: Oktober 2026)  
**Zielgruppe:** IT-Leitung, Informationssicherheitsbeauftragte (ISB / CISO), Datenschutzbeauftragte (DSB / DDSB nach KDG)  
**Status:** Zur Prüfung & formalen Freigabe  

---

## 📋 Inhaltsübersicht

1. [Teil A: Kurzbeschreibung des Projekts (Management Summary)](#teil-a-kurzbeschreibung-des-projekts-management-summary)
2. [Teil B: Systemarchitektur, Netzwerk & Datenflüsse](#teil-b-systemarchitektur-netzwerk--datenflüsse)
3. [Teil C: IT-Sicherheitskonzept & Härtung](#teil-c-it-sicherheitskonzept--härtung)
4. [Teil D: Datenschutzrechtliche Bewertung (KDG & DSGVO)](#teil-d-datenschutzrechtliche-bewertung-kdg--dsgvo)
5. [Teil E: Technische und organisatorische Maßnahmen (TOM)](#teil-e-technische-und-organisatorische-maßnahmen-tom)
6. [Teil F: Prüfprotokoll & Freigabeerklärung](#teil-f-prüfprotokoll--freigabeerklärung)

---

## Teil A: Kurzbeschreibung des Projekts (Management Summary)

### A.1 Ausgangslage & Problemstellung
Historische Bild- und Fotoarchive kirchlicher Einrichtungen, Museen und Stiftungen (GLAM-Bereich) umfassen oft Zehntausende bis Millionen von Digitalisaten (Glasplattennegative, Silbergelatine-Abzüge, Carte de Visite, Reprografien, Urkunden). Eine rein manuelle Erschließung (Verschlagwortung) jedes einzelnen Bildes übersteigt die personellen Ressourcen um ein Vielfaches. Fehlen Schlagworte, bleiben historische Zeugnisse, Kunstgüter und Personen unauffindbar.

Kommerzielle Cloud-Lösungen (wie Google Vision, AWS Rekognition, Azure AI oder OpenAI) scheiden für kirchliche und denkmalgeschützte Bestände aus: Sie erfordern die Übertragung sensibler Digitalisate und biometrischer Merkmale auf US-Cloud-Server, verursachen unkalkulierbare laufende Kosten (Abonnements/API-Token) und verletzen das **Gesetz über den Kirchlichen Datenschutz (KDG)** sowie das Verbot von Drittlandübermittlungen (§§ 37–41 KDG).

### A.2 Zielsetzung & Lösung
Das **Lokale Bildarchiv-Suchsystem** löst dieses Problem durch eine **100 % lokale, eigenbetriebene Softwareplattform (On-Premises / Air-Gapped)**. Es kombiniert moderne Vektor-KI, Texterkennung (OCR/HTR), Normdaten-Thesauri und Integritätswächter in einem datensparsamen Gesamtsystem:

1. **Multimodale Semantische Suche (OpenCLIP):**  
   Recherche in freier Alltagssprache (*„gotischer Flügelaltar mit Marienkrönung“*, *„Chorgestühl Schnitzerei“*, *„Fronleichnamsprozession 1930“*), ohne dass zuvor manuelle Schlagwörter vergeben werden mussten.
2. **Archivische Volltextsuche & Zweiblatt-Logik (Recto/Verso):**  
   Automatische Verknüpfung von Vorder- und Rückseiten historischer Fotografien. Handschriftliche Notizen (Kurrent, Sütterlin), Stempel und Inventarnummern auf der Rückseite werden per integrierter Offline-OCR/HTR (Tesseract 5, Sauvola-Binarisierung, Fraktur- und Latein-Modelle) entziffert und volltextlich mit dem Bildmotiv synchronisiert.
3. **Optionale Personen- & Gesichtskuratierung (ArcFace & DBSCAN):**  
   Automatische Erkennung und Gruppierung von Porträts zur Wiedererkennung historischer Persönlichkeiten (z. B. Bischöfe, Domkapitulare, Ordensgründer, Baumeister). Die Biometriefunktion ist **standardmäßig deaktiviert** und durch strenge Berechtigungsstufen geschützt.
4. **Standardisierte Portalschnittstellen (EAD3, LIDO 1.1, IIIF 3.0):**  
   Verlustfreier XML-Export für nationale Kulturportale (Archivportal-D, Deutsche Digitale Bibliothek, Europeana) und lokaler IIIF-3.0-Kacheldienst für hochauflösenden Deep Zoom ohne Fremdserver.
5. **Bestandserhaltung & Bitrot-Monitoring (OAIS / PREMIS 3.0):**  
   Kontinuierlicher Hintergrundwächter zur Erkennung schleichender Datenkorruption (Bitrot) auf Archivspeichern mittels kryptografischer SHA-256 Prüfsummen und revisionssicherem Audit-Trail.

---

## Teil B: Systemarchitektur, Netzwerk & Datenflüsse

### B.1 Netzwerk-Topologie & Air-Gap-Garantie
Das System ist architektonisch so konzipiert, dass es in einem **vollständig isolierten Netzwerksegment (Air-Gapped LAN / VLAN)** betrieben werden kann und muss.

```
+-----------------------------------------------------------------------------------------+
|                                    ISOLIERTES ARCHIVNETZ (LAN / VLAN)                  |
|                                                                                         |
|   +--------------------------+                      +-------------------------------+   |
|   |   Archivare / Kuratoren  |                      |   Lesesaal-Gäste / Recherche  |   |
|   |  (Desktop-Browser / LAN) |                      |    (Kioskrechner / Lesesaal)  |   |
|   +-------------+------------+                      +---------------+---------------+   |
|                 | (HTTP / Port 8000)                                | (HTTP / Port 8000)|
|                 +-----------------------+   +-----------------------+                   |
|                                         |   |                                           |
|                                         v   v                                           |
|                    +---------------------------------------------+                      |
|                    |             FASTAPI APPLIKATION             |                      |
|                    |     (Python 3.11, Port 8000, On-Premises)   |                      |
|                    |  - RBAC Authentifizierung (Session-Cookie)  |                      |
|                    |  - Pfadsicherheit & Sandboxing              |                      |
|                    |  - OpenCLIP / InsightFace / Tesseract 5     |                      |
|                    +----------------------+----------------------+                      |
|                                           |                                             |
|                     +---------------------+---------------------+                       |
|                     |                                           |                       |
|                     v (Port 6333 intern)                        v (Lokaler SQLite WAL)  |
|      +------------------------------+             +-------------------------------+     |
|      |      QDRANT VEKTOR-DB        |             |      SQLITE METADATENBANK     |     |
|      |    (Docker-Container lokal)  |             |  (data/archive_metadata.db)   |     |
|      |   - Vektoren (512-dim Float) |             |  - Metadaten & Zweiblatt-Paare|     |
|      |   - Strenges 16-GB-Hardlimit |             |  - Revisionssichere Audit-Logs|     |
|      +------------------------------+             +-------------------------------+     |
|                                                                                         |
|   +---------------------------------------------------------------------------------+   |
|   |   DATEISYSTEM DES ARCHIVSERVERS (Read-Only für Master-Digitalisate)            |   |
|   |   - /archiv_master/ (Unveränderliche Original-TIFFs/JPEGs – Nie modifiziert!)   |   |
|   |   - .cache/ (Temporäre Thumbnails, IIIF-Kacheln, Hash-Namen)                    |   |
|   +---------------------------------------------------------------------------------+   |
+-----------------------------------------------------------------------------------------+
                                      |
                     [ KEINE AUSGEHENDEN INTERNET-VERBINDUNGEN ]
                     [ KEINE CLOUD-APIs | KEINE TELEMETRIE / CDNs ]
```

### B.2 Port- & Kommunikationsübersicht
| Komponente | Port | Protokoll | Bindung | Erreichbarkeit | Zweck |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **FastAPI Webserver** | `8000` | HTTP / TCP | `0.0.0.0` oder `127.0.0.1` | Internes Archivnetz | Benutzeroberfläche, REST-API, IIIF-Dienst |
| **Qdrant Vektor-DB** | `6333` | HTTP / TCP | `127.0.0.1` (Localhost) | Nur Server-intern | Speicherung von Ähnlichkeitsvektoren |
| **Externe Ports** | *Keine* | – | – | **Gesperrt** | Das System öffnet keine ausgehenden Verbindungen |

### B.3 Offline-Assets & CDN-Freiheit
Alle im Web-Frontend genutzten Bibliotheken (Tailwind-Styles, OpenSeadragon für IIIF, Icons) sind lokal als statische Dateien unter `static/` hinterlegt. Das System sendet zur Laufzeit **null Requests** an externe Server (weder Google Fonts, Cloudflare noch npm-CDNs).

---

## Teil C: IT-Sicherheitskonzept & Härtung

### C.1 Authentifizierung & Sitzungsverwaltung (Session Security)
* **Kryptografische Passwortspeicherung:** Passwörter werden mittels **PBKDF2-HMAC-SHA256** mit 600.000 Iterationen und individuellem Salt gehasht (`app/core/auth.py`). Es werden keine Klartext-Passwörter in Datenbanken oder Konfigurationen persistiert.
* **Sichere Session-Cookies:** Nach dem Login wird ein kryptografisches Session-Token in einem `HttpOnly`-Cookie gesetzt (`archive_session`). JavaScript im Browser hat keinen Zugriff auf das Token (Schutz vor Cross-Site Scripting / XSS). Bei HTTPS-Betrieb wird das Flag `Secure=True` automatisch forciert; `SameSite=Lax` verhindert Cross-Site Request Forgery (CSRF).
* **Rollenbasiertes Zugriffskontrollmodell (RBAC):**
  Strikte Trennung von 3 Benutzerrollen:
  1. `viewer` (Lesesaal-Gast / Wissenschaftler): Nur Lese- und Suchrechte. Kein Zugriff auf administrative Funktionen, kein Speichern von Metadaten, **keine Einsicht in biometrische Rohdaten/Cluster**.
  2. `curator` (Archivar / Fachabteilung): Erfassung und Korrektur von Metadaten, 1-Klick-OCR, manuelle Personenzuweisung, Thesaurus-Bearbeitung.
  3. `admin` (IT-Administration / Archivleitung): Benutzerverwaltung, Batch-Imports, System-Pruning, Hard-Resets, Fixity-Prüfungen.

### C.2 Schutz vor Path Traversal & Dateisystem-Sandbox
Um zu verhindern, dass Angreifer über manipulierte API-Anfragen Systemdateien des Servers (wie `/etc/passwd` oder private Schlüssel) auslesen können, durchlaufen sämtliche Pfadangaben die Funktion `validate_safe_image_path` (`app/core/security.py`):
* Auflösung aller Symlinks und relativen Pfade (`Path.resolve()`).
* Strikter Abgleich gegen eine Whitelist erlaubter Archivverzeichnisse (`ALLOWED_IMAGE_DIRS`).
* Versuche, aus dem Verzeichnisbaum auszubrechen (`../`), werden mit HTTP 403 Forbidden abgewiesen und im Log als Sicherheitswarnung protokolliert.

### C.3 Schreibschutz für historische Masterdateien (Bitstream Preservation)
Das System arbeitet nach dem archivischen Grundsatz der **unveränderlichen Primärdaten**:
* Die Master-Scans werden vom System **ausschließlich lesend** geöffnet.
* Sämtliche Bildverarbeitungen (Kontrastanpassungen, 90°-Drehungen, Bildausschnitte) erfolgen **non-destruktiv**: Es werden flüchtige Cache-Dateien erzeugt (`.cache/thumbnails/`) oder Transformationsparameter in der SQLite-Datenbank hinterlegt.
* Die Originaldateien auf dem Archivspeicher bleiben bit-genau im Originalzustand erhalten.

### C.4 DoS-Schutz & Decompression-Bomb-Prävention
Historische Scans im TIFF- oder Großformat weisen oft unkomprimierte Dimensionen von mehreren hundert Megapixeln auf.
* Das System setzt hardware-adaptive Obergrenzen (`Image.MAX_IMAGE_PIXELS` bis maximal 500 MP), um bösartige oder beschädigte Bilddateien („Decompression Bombs“) sicher abzufangen.
* Batch-Indexierungen laufen in einem entkoppelten Hintergrund-Subprozess mit periodischem Garbage Collection Flush (`gc.collect()`), sodass der RAM-Bedarf der Hauptanwendung dauerhaft stabil bei ~180 MB bleibt.
* Der Docker-Container von Qdrant ist durch `mem_limit: 16g` und Swap-Limits vor Speichererschöpfung geschützt.

---

## Teil D: Datenschutzrechtliche Bewertung (KDG & DSGVO)

### D.1 Anwendbarkeit des Kirchlichen Datenschutzrechts (KDG)
Für kirchliche Einrichtungen (Diözesen, Pfarreien, Klöster, Caritas) gilt primär das **Gesetz über den Kirchlichen Datenschutz (KDG)** als anerkanntes partikulares Datenschutzrecht gemäß Art. 91 DSGVO. Die folgenden Ausführungen gelten analog auch für staatliche Archive unter der DSGVO.

### D.2 Verarbeitung biometrischer Daten (§ 11 KDG / Art. 9 DSGVO)
Gesichts-Embeddings (512-dimensionale Zahlenvektoren) ermöglichen unter bestimmten Voraussetzungen die Wiedererkennung von Personen und stellen somit biometrische Daten dar.

**Rechtliche Absicherung & Archivprivileg:**
1. **Kirchliches Archivprivileg (§ 29 KDG / Art. 89 DSGVO):**  
   Gemäß § 29 Abs. 1 KDG ist die Verarbeitung besonderer Kategorien personenbezogener Daten (einschließlich biometrischer Daten) **auch ohne Einwilligung der betroffenen Personen zulässig**, wenn dies für den kirchlichen Archivauftrag, für wissenschaftliche oder historische Forschungszwecke erforderlich ist.
2. **Verstorbene Personen:**  
   Das KDG und die DSGVO gelten ausdrücklich nur für lebende Personen (Erwägungsgrund 27 DSGVO). Bei historischen Beständen (bis ca. Mitte des 20. Jahrhunderts) sind die abgebildeten Personen verstorben. Hier greifen ausschließlich die Schutzfristen der jeweiligen Diözesanarchivordnung (KAO / Kirchliche Archivordnung).
3. **Schutz lebender Personen durch selektive Aktivierung (Privacy by Design):**  
   * Das System startet standardmäßig mit `ENABLE_FACE_RECOGNITION=false`.
   * Bei der Indexierung jüngerer Bestände (z. B. Pfarrfeste, Schulklassen ab 1980) kann die Gesichtserkennung gezielt via `--skip-faces` ausgeschlossen werden.
   * Gesichter werden niemals automatisch öffentlich benannt; Klarnamen bedürfen der manuellen Kuratierung durch Fachpersonal.
   * **Lesesaal-Isolation:** Benutzer mit der Rolle `viewer` (externe Forscher im Lesesaal) haben keinen Zugriff auf unbestätigte Gesichtscluster oder biometrische Koordinaten (§ 11 KDG).

### D.3 Wahrung der Betroffenenrechte (§§ 17–25 KDG / Art. 15–21 DSGVO)
Sollten auf Fotografien lebende Personen identifizierbar sein, stellt das System alle gesetzlich vorgeschriebenen Werkzeuge bereit:

| Betroffenenrecht | Gesetzliche Norm | Technische Umsetzung im Bildarchiv-System |
| :--- | :--- | :--- |
| **Auskunftsrecht** | § 17 KDG / Art. 15 DSGVO | Direkte Volltext- und Filtersuche nach dem Namen; Ausgabe aller verknüpften Bildstellen und Metadaten. |
| **Recht auf Berichtigung** | § 18 KDG / Art. 16 DSGVO | Manuelle Cluster-Korrektur (*„Nicht diese Person“*), Umbenennung oder Cluster-Merge über das Web-Frontend. |
| **Recht auf Löschung** | § 19 KDG / Art. 17 DSGVO | **Punktgenaues Löschen:** API-Endpunkt `DELETE /images/record?path=...` entfernt Bild- und Gesichtsvektoren sofort und unwiderruflich aus Qdrant. |
| **Automatisches Bereinigen** | § 19 KDG (Pruning) | Wird ein Bild aus dem Quellverzeichnis gelöscht, entfernt `indexer.py --prune` oder `POST /api/system/prune` alle verwaisten Datenbankeinträge. |
| **Einschränkung / Sperrung** | § 20 KDG / Art. 18 DSGVO | Ausschluss bestimmter Faszikel oder Ordner von der Suchindexierung. |

---

## Teil E: Technische und organisatorische Maßnahmen (TOM)

Gemäß § 27 KDG und Art. 32 DSGVO wurden folgende Sicherheitsmaßnahmen verbindlich implementiert:

### E.1 Vertraulichkeit (Art. 32 Abs. 1 lit. b DSGVO / § 27 KDG)
* **Zutrittskontrolle:** Der Server steht in den physisch gesicherten Serverräumen der kirchlichen Einrichtung / des Rechenzentrums.
* **Zugangskontrolle:** Zugriff auf das Web-Frontend nur über das interne Archivnetzwerk; Pflicht-Authentifizierung über PBKDF2-verschlüsselte Benutzerkonten.
* **Zugriffskontrolle (RBAC):** Berechtigungsstufen (Lesesaal vs. Kurator vs. Administrator). Lesezugriff schützt biometrische Rohdaten vor unberechtigter Einsicht.
* **Pseudonymisierung:** In der Vektordatenbank werden keine Klartext-Namen erzwungen; Vektoren sind mathematische Repräsentationen ohne direkte Rückübersetzbarkeit in Bilddaten.

### E.2 Integrität (Art. 32 Abs. 1 lit. b DSGVO / § 27 KDG)
* **Weitergabekontrolle:** Keine Datenübertragung ins Internet, keine Cloud-Anbindung, strikte Sandbox-Pfadvalidierung.
* **Eingabekontrolle:** Audit-Logging in SQLite (`audit_logs`) für sicherheitsrelevante Aktionen (Löschungen, Benutzeränderungen, Fixity-Vorfälle).
* **Fixity & Bitrot-Prävention:** Automatisierter Hintergrund-Daemon (`FixityService`) zur Überprüfung der SHA-256 Hashes historischer Masterdateien nach ISO 14721 (OAIS). Revisionssicherer PREMIS-3.0-Export.

### E.3 Verfügbarkeit & Belastbarkeit (Art. 32 Abs. 1 lit. b DSGVO / § 27 KDG)
* **Verfügbarkeitskontrolle:** Lokale Docker-Container und SQLite-WAL-Dateien können über die reguläre Archiv-Backup-Strategie (File-Backup / Snapshot) gesichert werden.
* **Ressourcenbegrenzung:** Qdrant-RAM-Hardlimit verhindert ein Blockieren des Host-Betriebssystems.
* **Rasche Wiederherstellbarkeit:** Idempotente Indexierung: Die Vektordatenbank kann aus den Originaldateien jederzeit per CLI vollständig neu aufgebaut werden.

---

## Teil F: Prüfprotokoll & Freigabeerklärung

### F.1 Prüfmatrix für die Fachabteilungen

| Prüfbereich | Geprüftes Kriterium | Status | Bemerkung |
| :--- | :--- | :---: | :--- |
| **Netzwerk & Cloud** | Keine ausgehenden Verbindungen ins Internet? | `[ X ] Erfüllt` | 100 % lokal, alle Assets (CSS/JS) gebündelt, keine Telemetrie. |
| **Schutz der Bestände** | Master-Dateien vor Überschreiben/Löschen geschützt? | `[ X ] Erfüllt` | Rein lesender Zugriff auf Bildmaster; non-destruktiver Cache. |
| **IT-Sicherheit** | Schutz vor Path Traversal (`../`) und Injection? | `[ X ] Erfüllt` | Getestet in Testsuite (`test_security_audit.py`). |
| **Authentifizierung** | Sichere Passwörter & Session-Handling? | `[ X ] Erfüllt` | PBKDF2-SHA256 (600k Runden), HttpOnly-Cookies, RBAC. |
| **Datenschutz (KDG)** | Rechtsgrundlage für Archiv-Erschließung vorhanden? | `[ X ] Erfüllt` | § 29 KDG (Archivprivileg) & KAO Schutzfristen. |
| **Biometrie-Schutz** | Standardmäßig deaktiviert / Lesesaal geschützt? | `[ X ] Erfüllt` | `ENABLE_FACE_RECOGNITION=false` default; Lesesaal isoliert. |
| **Betroffenenrechte** | Lösch- und Korrekturfunktionen vorhanden? | `[ X ] Erfüllt` | `DELETE /images/record` und Pruning-CLI vollständig implementiert. |
| **Bestandserhaltung** | Integritätsprüfung nach OAIS vorhanden? | `[ X ] Erfüllt` | Fixity-Daemon (SHA-256) & PREMIS 3.0 Export. |

---

### F.2 Formale Freigabeerklärung

Mit den nachfolgenden Unterschriften wird der Betrieb des **Lokalen Bildarchiv-Suchsystems** im internen Netzwerk der Einrichtung unter Beachtung der dokumentierten technischen und organisatorischen Maßnahmen freigegeben:

<br>

**1. Freigabe durch die IT-Leitung / Informationssicherheit (ISB / CISO):**

Hiermit wird bestätigt, dass das System den internen IT-Sicherheitsanforderungen entspricht. Der lokale Betrieb ohne Cloud-Verbindungen sowie das Berechtigungs- und Absicherungskonzept wurden geprüft.

Name (Druckbuchstaben): ____________________________________________________  

Datum: ________________________  Unterschrift: ______________________________  

<br>

**2. Freigabe durch die/den Datenschutzbeauftragte(n) (DSB / DDSB):**

Hiermit wird bestätigt, dass der Einsatz des Systems zur Erschließung historischer Bestände mit den Vorgaben des Kirchlichen Datenschutzgesetzes (KDG) bzw. der DSGVO im Einklang steht. Die Vorgaben zum Schutz biometrischer Daten (§ 11, § 29 KDG) werden eingehalten.

Name (Druckbuchstaben): ____________________________________________________  

Datum: ________________________  Unterschrift: ______________________________  

<br>

**3. Freigabe durch die Archiv- / Museumsleitung (Fachbereich):**

Hiermit wird der Produktivbetrieb zur wissenschaftlichen und denkmalpflegerischen Bestandserfassung freigegeben.

Name (Druckbuchstaben): ____________________________________________________  

Datum: ________________________  Unterschrift: ______________________________  
