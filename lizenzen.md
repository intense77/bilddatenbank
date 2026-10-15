# Lizenzübersicht & Drittanbieter-Lizenzen

**Projekt:** Lokales Bildarchiv-Suchsystem für historische Bestände (GLAM)  
**Stand:** Oktober 2026

Dieses Dokument bietet eine vollständige Übersicht über die im System eingesetzten Software-Bibliotheken, Frameworks und vortrainierten KI-Modelle sowie deren lizenzrechtliche Rahmenbedingungen.

---

## 1. Software-Bibliotheken & Frameworks

| Komponente | Lizenz | Verwendung im Projekt | Projekt-URL |
| :--- | :--- | :--- | :--- |
| **FastAPI** | MIT License | Asynchrones Web-Framework & REST-API | [fastapi.tiangolo.com](https://fastapi.tiangolo.com/) |
| **Uvicorn** | BSD 3-Clause | Asynchroner ASGI-Webserver | [www.uvicorn.org](https://www.uvicorn.org/) |
| **Pydantic & Settings** | MIT License | Typvalidierung & Konfigurationsmanagement | [docs.pydantic.dev](https://docs.pydantic.dev/) |
| **python-multipart** | Apache 2.0 | Multipart/Form-Data Parser für Uploads | [github.com/Kludex/python-multipart](https://github.com/Kludex/python-multipart) |
| **python-dotenv** | BSD 3-Clause | Laden von Umgebungsvariablen aus `.env` | [github.com/theskumar/python-dotenv](https://github.com/theskumar/python-dotenv) |
| **Qdrant** | Apache 2.0 | Vektordatenbank (lokale Container-Instanz) | [qdrant.tech](https://qdrant.tech/) |
| **Qdrant Client** | Apache 2.0 | Python SDK für Vektoroperationen & Payload-Indexe | [github.com/qdrant/qdrant-client](https://github.com/qdrant/qdrant-client) |
| **PyTorch** | BSD-Style | Deep-Learning-Framework (Inferenz für CLIP & ArcFace) | [pytorch.org](https://pytorch.org/) |
| **Torchvision** | BSD 3-Clause | Bildverarbeitungs-Pipelines für PyTorch | [github.com/pytorch/vision](https://github.com/pytorch/vision) |
| **OpenCLIP** | MIT License | Multimodale Text- und Bild-Embeddings (ViT-B-32) | [github.com/mlfoundations/open_clip](https://github.com/mlfoundations/open_clip) |
| **ONNX Runtime (GPU)** | MIT License | Leistungsoptimierte Inferenz-Engine für Gesichtsmodelle | [onnxruntime.ai](https://onnxruntime.ai/) |
| **InsightFace** | Non-Commercial / MIT | Gesichtslokalisierung (RetinaFace) & Extraktion | [github.com/deepinsight/insightface](https://github.com/deepinsight/insightface) |
| **Pillow (PIL)** | HPND License | Bilddekodierung, EXIF/IPTC-Extraktion, Caching | [python-pillow.org](https://python-pillow.org/) |
| **NumPy** | BSD 3-Clause | Mathematische Vektor- & Matrixoperationen | [numpy.org](https://numpy.org/) |
| **Scikit-learn** | BSD 3-Clause | DBSCAN-Clustering für Personengruppierung | [scikit-learn.org](https://scikit-learn.org/) |
| **SQLite (sqlite3)** | Public Domain | Relationale Metadaten-, Fixity- & Cluster-DB | [sqlite.org](https://sqlite.org/) |
| **OpenSeadragon** | New BSD License | Lokaler IIIF 3.0 Deep-Zoom Viewer für Gigapixel-Scans | [openseadragon.github.io](https://openseadragon.github.io/) |
| **Cropper.js** | MIT License | Interaktive Bildausschnitt-Markierung (Crop-to-Search) | [fengyuanchen.github.io/cropperjs](https://fengyuanchen.github.io/cropperjs/) |
| **Tailwind CSS** | MIT License | Lokales Standalone-CSS (100 % offline, kein CDN) | [tailwindcss.com](https://tailwindcss.com/) |
| **tqdm** | MIT & MPL 2.0 | CLI-Fortschrittsanzeige beim Indexieren | [github.com/tqdm/tqdm](https://github.com/tqdm/tqdm) |
| **pytest & anyio** | MIT License | Testframework & asynchrone Testausführung | [pytest.org](https://pytest.org/) |
| **Python-Markdown** | BSD 3-Clause | Generierung eigenständiger Offline-Dokumentationen | [python-markdown.github.io](https://python-markdown.github.io/) |

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
  * **Gewerbliche Weitervermarktung:** Sollte das System in einem kommerziellen Produkt weiterverkauft oder gewerblich betrieben werden, ist entweder eine kommerzielle Lizenz bei den InsightFace-Autoren anzufragen oder das Modell durch ein vollständig unter Apache 2.0 / MIT lizenziertes Modell (z. B. FaceNet oder MagFace) zu ersetzen.

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

---

## 4. Vollständige Lizenztexte der Drittanbieter-Komponenten

Zur lückenlosen Einhaltung der Notice- und Attribution-Auflagen der eingesetzten Open-Source-Lizenzen sind nachfolgend die standardisierten Lizenztexte hinterlegt:

### A. MIT License
*Betrifft u. a.: FastAPI, Pydantic, OpenCLIP, ONNX Runtime, Cropper.js, Tailwind CSS, pytest, anyio*

```text
The MIT License (MIT)

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

### B. BSD 3-Clause License
*Betrifft u. a.: Uvicorn, NumPy, Scikit-learn, Torchvision, python-dotenv, Python-Markdown*

```text
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

### C. Apache License, Version 2.0
*Betrifft u. a.: Qdrant, Qdrant Python Client, python-multipart*

```text
                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

1. Definitions.
   "License" shall mean the terms and conditions for use, reproduction,
   and distribution as defined by Sections 1 through 9 of this document.
   "Licensor" shall mean the copyright owner or entity authorized by
   the copyright owner that is granting the License.
   "Legal Entity" shall mean the union of the acting entity and all
   other entities that control, are controlled by, or are under common
   control with that entity.
   "You" (or "Your") shall mean an individual or Legal Entity
   exercising permissions granted by this License.

2. Grant of Copyright License. Subject to the terms and conditions of
   this License, each Contributor hereby grants to You a perpetual,
   worldwide, non-exclusive, no-charge, royalty-free, irrevocable
   copyright license to reproduce, prepare Derivative Works of,
   publicly display, publicly perform, sublicense, and distribute the
   Work and such Derivative Works in Source or Object form.

3. Grant of Patent License. Subject to the terms and conditions of
   this License, each Contributor hereby grants to You a perpetual,
   worldwide, non-exclusive, no-charge, royalty-free, irrevocable
   patent license to make, have made, use, offer to sell, sell, import,
   and otherwise transfer the Work.

4. Redistribution. You may reproduce and distribute copies of the
   Work or Derivative Works thereof in any medium, with or without
   modifications, and in Source or Object form, provided that You
   meet the following conditions:
   (a) You must give any other recipients of the Work or Derivative Works
       a copy of this License; and
   (b) You must cause any modified files to carry prominent notices
       stating that You changed the files; and
   (c) You must retain, in the Source form of any Derivative Works that
       You distribute, all copyright, patent, trademark, and attribution
       notices from the Source form of the Work; and
   (d) If the Work includes a "NOTICE" text file as part of its distribution,
       then any Derivative Works that You distribute must include a readable
       copy of the attribution notices contained within such NOTICE file.

5. Disclaimer of Warranty. Unless required by applicable law or agreed to in
   writing, Licensor provides the Work (and each Contributor provides its
   Contributions) on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
   ANY KIND, either express or implied.
```

### D. Historical Permission Notice and Disclaimer (HPND)
*Betrifft: Pillow (PIL)*

```text
The Python Imaging Library (PIL) is:
    Copyright © 1997-2011 by Secret Labs AB
    Copyright © 1995-2011 by Fredrik Lundh
Pillow is the friendly PIL fork. It is:
    Copyright © 2010-2026 by Jeffrey A. Clark and contributors

Permission to use, copy, modify, and distribute this software and its
documentation for any purpose and without fee is hereby granted, provided
that the above copyright notice appear in all copies and that both that
copyright notice and this permission notice appear in supporting
documentation, and that the name of Secret Labs AB or the author not be
used in advertising or publicity pertaining to distribution of the
software without specific, written prior permission.

SECRET LABS AB AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS
SOFTWARE, INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS.
IN NO EVENT SHALL SECRET LABS AB OR THE AUTHOR BE LIABLE FOR ANY SPECIAL,
INDIRECT OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE
OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
PERFORMANCE OF THIS SOFTWARE.
```

### E. New BSD License
*Betrifft: OpenSeadragon (IIIF Deep-Zoom Viewer)*

```text
Copyright (c) OpenSeadragon contributors

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

* Neither the name of OpenSeadragon nor the names of its
  contributors may be used to endorse or promote products derived from
  this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES.
```

### F. InsightFace Non-Commercial Research License
*Betrifft: InsightFace ArcFace / RetinaFace Modellgewichte (buffalo_l)*

```text
The InsightFace models and weights are provided for academic research, education,
and non-commercial cultural/heritage preservation purposes only.
Commercial redistribution, commercial deployment, or commercial services utilizing
the pre-trained model weights are strictly prohibited without an explicit commercial
license from the InsightFace project authors.
```

