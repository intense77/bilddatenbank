# Lizenzübersicht & Drittanbieter-Lizenzen

**Projekt:** Lokales Bildarchiv-Suchsystem für historische Bestände  
**Stand:** September 2026

Dieses Dokument bietet eine vollständige Übersicht über die im System eingesetzten Software-Bibliotheken, Frameworks und vortrainierten KI-Modelle sowie deren lizenzrechtliche Rahmenbedingungen.

---

## 1. Software-Bibliotheken & Frameworks

| Komponente | Lizenz | Verwendung im Projekt | Projekt-URL |
| :--- | :--- | :--- | :--- |
| **FastAPI** | MIT License | Web-Framework & REST-API | [fastapi.tiangolo.com](https://fastapi.tiangolo.com/) |
| **Uvicorn** | BSD 3-Clause | Asynchroner ASGI-Webserver | [www.uvicorn.org](https://www.uvicorn.org/) |
| **Qdrant** | Apache 2.0 | Vektordatenbank (Docker-Instanz) | [qdrant.tech](https://qdrant.tech/) |
| **Qdrant Client** | Apache 2.0 | Python SDK für Datenbankabfragen | [github.com/qdrant/qdrant-client](https://github.com/qdrant/qdrant-client) |
| **PyTorch** | BSD-Style | Deep-Learning-Framework (Inferenz) | [pytorch.org](https://pytorch.org/) |
| **Torchvision** | BSD 3-Clause | Bildverarbeitungs-Pipelines für PyTorch | [github.com/pytorch/vision](https://github.com/pytorch/vision) |
| **OpenCLIP** | MIT License | Multimodale Text- und Bild-Embeddings | [github.com/mlfoundations/open_clip](https://github.com/mlfoundations/open_clip) |
| **ONNX Runtime** | MIT License | Leistungsoptimierte Inferenz-Engine | [onnxruntime.ai](https://onnxruntime.ai/) |
| **Pillow (PIL)** | HPND License | Bilddekodierung, Skalierung & Konvertierung | [python-pillow.org](https://python-pillow.org/) |
| **NumPy** | BSD 3-Clause | Mathematische Vektoroperationen | [numpy.org](https://numpy.org/) |
| **Scikit-learn** | BSD 3-Clause | DBSCAN-Clustering für Personengruppen | [scikit-learn.org](https://scikit-learn.org/) |
| **Pydantic** | MIT License | Datenvalidierung & Schema-Definition | [docs.pydantic.dev](https://docs.pydantic.dev/) |
| **Tailwind CSS** | MIT License | Frontend-Styling & Layout (via CDN) | [tailwindcss.com](https://tailwindcss.com/) |
| **tqdm** | MIT & MPL 2.0 | CLI-Fortschrittsbalken | [github.com/tqdm/tqdm](https://github.com/tqdm/tqdm) |

---

## 2. Vortrainierte KI-Modelle & Modellgewichte

### A. OpenCLIP (ViT-B-32 / laion2b_s34b_b79k)
* **Lizenz:** MIT License (Open Source)
* **Trainingsdatensatz:** LAION-2B (öffentlich zugängliche Bild-Text-Paare)
* **Rechtliche Einordnung:** Freie Nutzung für wissenschaftliche, kulturelle, private und kommerzielle Zwecke gestattet.

### B. InsightFace (ArcFace / buffalo_l)
* **Lizenz:** InsightFace Non-Commercial / Research License
* **Wichtiger Hinweis zur Nutzung:**
  * Die vortrainierten Modellgewichte von InsightFace (Paket `buffalo_l` mit RetinaFace & ArcFace) werden von den Autoren unter einer **nicht-kommerziellen Lizenz für Forschung, Bildung und Gemeinnützigkeit** bereitgestellt.
  * **Museen, kirchliche Einrichtungen, öffentliche Archive und Kulturprojekte:** Die interne Erschließung und Nutzung im Rahmen des öffentlichen Kultur- und Bildungsauftrags fällt unter die freie, nicht-kommerzielle Nutzung.
  * **Gewerbliche Weitervermarktung:** Sollte das System in einem kommerziellen Produkt weiterverkauft oder gewerblich betrieben werden, ist entweder eine kommerzielle Lizenz bei den InsightFace-Autoren (DeepInsight) anzufragen oder das Modell durch ein vollständig unter Apache 2.0 / MIT lizenziertes Gesichtsmodell (z. B. FaceNet oder MagFace) zu ersetzen.

---

## 3. Lizenzierung dieses Projekt-Quellcodes

Der im Rahmen dieses Projekts erstellte Quellcode (`app/`, `indexer.py`, `static/`, Skripte und Dokumentation) steht unter der **MIT-Lizenz**:

```text
Copyright (c) 2026 Archiv & Museum

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
