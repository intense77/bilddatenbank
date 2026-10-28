"""
Thesaurus-Service für kirchliche Fachbegriffe, Ikonographie (Iconclass) und GND-Normdaten.

Umfasst:
1. Lokale GND-Normdatenbank & Iconclass-Katalog in SQLite (Offline-First)
2. Thesaurus-basierte Synonym-Erweiterung (Query Expansion) für Volltext- und Vektorsuche
3. Zero-Shot Fachverschlagwortung mit OpenCLIP (ohne zusätzlichen VRAM-Bedarf)
4. Heuristische Träger- und Zustandserkennung historischer Bildoriginale (Albumin, Silbergelatine, Cyanotypie, CdV)
5. Auto-Vervollständigung und Fachbegriffs-Katalog für Archivare
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import numpy as np
from PIL import Image, ImageOps, ImageStat

from app.core.thesaurus_data import CHURCH_THESAURUS

logger = logging.getLogger("archive_app.thesaurus_service")


class ThesaurusService:
    def __init__(self):
        self._thesaurus = CHURCH_THESAURUS
        self._term_lookup: Dict[str, Dict[str, Any]] = {}
        self._cached_prompt_embeddings: Optional[np.ndarray] = None
        self._cached_prompt_items: List[Dict[str, Any]] = []
        self._build_index()

    def _build_index(self):
        """Erstellt schnellen Lookup-Index (lowercase) für kanonische Begriffe und Synonyme."""
        for item in self._thesaurus:
            canon = item["canonical"].strip().lower()
            self._term_lookup[canon] = item
            for syn in item.get("synonyms", []):
                syn_clean = syn.strip().lower()
                # Nur belegen, wenn noch nicht kanonisch belegt
                if syn_clean not in self._term_lookup or self._term_lookup[syn_clean]["canonical"].lower() != syn_clean:
                    self._term_lookup[syn_clean] = item

    def get_all_categories(self) -> List[str]:
        """Gibt alle verfügbaren Thesaurus-Kategorien zurück."""
        cats = sorted(list({item["category"] for item in self._thesaurus}))
        return cats

    def get_terms(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Liefert Begriffe aus dem kontrollierten Vokabular, optional nach Kategorie gefiltert."""
        if not category:
            return self._thesaurus
        cat_lower = category.strip().lower()
        return [item for item in self._thesaurus if item["category"].lower() == cat_lower]

    def expand_query(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Prüft, ob der Suchtext kirchliche Fachbegriffe enthält.
        Liefert kanonische Daten, Synonyme, Iconclass-Notation und CLIP-Prompts zurück.
        """
        q_clean = query.strip().lower()
        if not q_clean:
            return None

        # 1. Direkter Vollmatch
        if q_clean in self._term_lookup:
            matched_item = self._term_lookup[q_clean]
            return self._format_expansion_result(q_clean, matched_item)

        # 2. Wortweises Matching
        words = [w for w in re.split(r"[^\w]+", q_clean) if len(w) >= 3]
        for w in words:
            if w in self._term_lookup:
                matched_item = self._term_lookup[w]
                return self._format_expansion_result(w, matched_item)

        # 3. Substring-Matching (z.B. "messgewänder" -> "messgewand")
        for key, item in self._term_lookup.items():
            if len(key) >= 4 and (key in q_clean or q_clean in key):
                return self._format_expansion_result(key, item)

        return None

    def _format_expansion_result(self, matched_term: str, item: Dict[str, Any]) -> Dict[str, Any]:
        canonical = item["canonical"]
        synonyms = item.get("synonyms", [])
        
        all_terms: Set[str] = {canonical}
        all_terms.update(synonyms)
        
        return {
            "matched_term": matched_term,
            "canonical": canonical,
            "category": item["category"],
            "iconclass": item.get("iconclass"),
            "gnd": item.get("gnd"),
            "description": item.get("description", ""),
            "synonyms": synonyms,
            "expansion_terms": sorted(list(all_terms)),
            "clip_prompts": item.get("clip_prompts", []),
        }

    def autocomplete(self, prefix: str, limit: int = 8) -> List[Dict[str, Any]]:
        """Liefert Begriffsvorschläge für die Suchleiste und Metadaten-Felder."""
        clean_pref = prefix.strip().lower()
        if not clean_pref or len(clean_pref) < 2:
            return []

        suggestions: List[Dict[str, Any]] = []
        seen_canonicals: Set[str] = set()

        for item in self._thesaurus:
            canon = item["canonical"]
            if canon.lower().startswith(clean_pref):
                suggestions.append({
                    "term": canon,
                    "canonical": canon,
                    "category": item["category"],
                    "iconclass": item.get("iconclass"),
                    "gnd": item.get("gnd"),
                    "is_synonym": False,
                })
                seen_canonicals.add(canon)
                if len(suggestions) >= limit:
                    return suggestions

        for item in self._thesaurus:
            canon = item["canonical"]
            if canon in seen_canonicals:
                continue
            for syn in item.get("synonyms", []):
                if syn.lower().startswith(clean_pref):
                    suggestions.append({
                        "term": syn,
                        "canonical": canon,
                        "category": item["category"],
                        "iconclass": item.get("iconclass"),
                        "gnd": item.get("gnd"),
                        "is_synonym": True,
                    })
                    seen_canonicals.add(canon)
                    break
            if len(suggestions) >= limit:
                break

        return suggestions

    # =========================================================================
    # Zero-Shot Fachverschlagwortung mit OpenCLIP (Säule 3.3)
    # =========================================================================

    def _ensure_thesaurus_embeddings(self, clip_service: Any) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """
        Berechnet und puffert normierte CLIP-Textvektoren für alle kontrollierten Fachbegriffe.
        Benötigt 0 zusätzlichen VRAM, da OpenCLIP bereits für die Bildsuche im Speicher liegt.
        """
        if self._cached_prompt_embeddings is not None and len(self._cached_prompt_items) > 0:
            return self._cached_prompt_embeddings, self._cached_prompt_items

        vectors = []
        items = []

        for item in self._thesaurus:
            # Verwende den besten kuratierten CLIP-Prompt oder den kanonischen Begriff
            prompts = item.get("clip_prompts")
            prompt_text = prompts[0] if prompts else f"{item['canonical']}, {item['category']}, catholic church historical archive"
            try:
                vec = clip_service.embed_text(prompt_text)
                v = np.array(vec, dtype=np.float32)
                norm = np.linalg.norm(v)
                if norm > 0:
                    v = v / norm
                vectors.append(v)
                items.append(item)
            except Exception as e:
                logger.debug("Konnte Vektor für %s nicht erzeugen: %s", item.get("canonical"), e)

        if vectors:
            self._cached_prompt_embeddings = np.stack(vectors, axis=0)
            self._cached_prompt_items = items
            logger.info("Thesaurus Zero-Shot Matrix mit %d Fachbegriffen initialisiert.", len(items))
        else:
            self._cached_prompt_embeddings = np.empty((0, 512), dtype=np.float32)
            self._cached_prompt_items = []

        return self._cached_prompt_embeddings, self._cached_prompt_items

    def suggest_thesaurus_tags(
        self,
        image_embedding: List[float],
        clip_service: Any,
        top_k: int = 5,
        min_confidence: float = 0.20,
    ) -> List[Dict[str, Any]]:
        """
        Gleicht ein Bild-Embedding gegen die kontrollierte Liste kirchenspezifischer
        GND- und Iconclass-Begriffe ab. Berechnet Cosine-Similarity via Vektor-Skalarprodukt.
        """
        if not image_embedding:
            return []

        matrix, items = self._ensure_thesaurus_embeddings(clip_service)
        if len(items) == 0:
            return []

        img_vec = np.array(image_embedding, dtype=np.float32)
        norm = np.linalg.norm(img_vec)
        if norm > 0:
            img_vec = img_vec / norm

        # Skalarprodukt entspricht Cosinus-Ähnlichkeit bei L2-Normalisierung
        similarities = np.dot(matrix, img_vec)

        # Sortiere nach absteigender Ähnlichkeit
        sorted_indices = np.argsort(-similarities)

        results = []
        for idx in sorted_indices[:top_k * 2]:
            score = float(similarities[idx])
            if score < min_confidence and len(results) >= 2:
                break
            item = items[idx]
            results.append({
                "id": item["id"],
                "canonical": item["canonical"],
                "category": item["category"],
                "iconclass": item.get("iconclass"),
                "gnd": item.get("gnd"),
                "description": item.get("description", ""),
                "score": round(score, 4),
                "confidence": round(score, 4),
                "confidence_percent": int(min(1.0, max(0.0, (score - 0.15) / 0.20)) * 100),
            })
            if len(results) >= top_k:
                break

        return results

    # =========================================================================
    # Heuristische Träger- und Zustandserkennung (Säule 3 / Sektion 5)
    # =========================================================================

    def detect_carrier_and_condition(self, image_input: Union[Image.Image, Path, str]) -> Dict[str, Any]:
        """
        Analysiert Farbkanäle, Tonwertdynamik und Seitenverhältnis zur automatischen
        Erkennung des historischen Bildträgers (Albumin, Silbergelatine, Cyanotypie, CdV).
        """
        from PIL import ImageOps
        if isinstance(image_input, (str, Path)):
            from app.core.security import validate_safe_image_path
            p = validate_safe_image_path(image_input)
            with Image.open(p) as raw:
                img = ImageOps.exif_transpose(raw)
                img.load()
                return self._analyze_carrier_image(img)
        elif isinstance(image_input, Image.Image):
            return self._analyze_carrier_image(image_input)
        else:
            raise TypeError("Ungültiges Bild für Trägererkennung")

    def _analyze_carrier_image(self, img: Image.Image) -> Dict[str, Any]:
        w, h = img.size
        ratio = max(w, h) / max(min(w, h), 1)

        # Farbkanal-Statistik ermitteln (Thumbnail genügt für Farbtonanalyse)
        thumb = img.copy()
        if max(w, h) > 300:
            thumb.thumbnail((300, 300), Image.Resampling.BOX)

        rgb_img = thumb.convert("RGB")
        stat = ImageStat.Stat(rgb_img)
        mean_r, mean_g, mean_b = stat.mean[:3]
        std_r, std_g, std_b = stat.stddev[:3]

        # Farbsättigung und Farbkanaldifferenzen ermitteln
        hsv_img = rgb_img.convert("HSV")
        sat_stat = ImageStat.Stat(hsv_img)
        mean_sat = sat_stat.mean[1]  # 0 - 255

        # Heuristiken
        carrier_type = "Silbergelatine-Abzug (Schwarz-Weiß)"
        color_tone = "Monochrom / Schwarz-Weiß"
        estimated_era = "ca. 1890–1960 (Moderne Schwarzweiß-Fotografie)"
        gnd_carrier = "4128844-0"  # Silbergelatine-Verfahren

        # 1. Cyanotypie (Preußischblau: Blaukanal deutlich stärker als Rot)
        if mean_b > mean_r * 1.35 and mean_b > 70 and mean_sat > 40:
            carrier_type = "Cyanotypie (Eisenblaudruck / Blaupause)"
            color_tone = "Preußischblau / Cyan"
            estimated_era = "ca. 1880–1920 (Blaupause)"
            gnd_carrier = "4148604-3"

        # 2. Albumin- / Kollodiumpapier (Sepia: Rot > Grün > Blau, warmer Gelb-Braunton)
        elif mean_r > mean_b * 1.22 and mean_r > mean_g and mean_sat > 25:
            carrier_type = "Albuminabzug (Warmton / Sepia)"
            color_tone = "Sepia / Braungelton"
            estimated_era = "ca. 1860–1905 (Frühe Fotografie / 19. Jahrhundert)"
            gnd_carrier = "4141804-0"

        # 3. Farbfotografie (signifikante Sättigung und Farbvarianz)
        elif mean_sat > 55 and abs(mean_r - mean_b) > 20:
            carrier_type = "Farbfotografie (Chromogen / Farbabzug)"
            color_tone = "Vollfarbe"
            estimated_era = "ab ca. 1950 (Moderne Farbfotografie)"
            gnd_carrier = "4016443-3"

        # Format-Schätzung anhand des Seitenverhältnisses
        format_estimate = "Normalformat"
        if 1.52 <= ratio <= 1.68:
            format_estimate = "Carte de Visite (CdV) / Kleinbild (ca. 1:1.6)"
        elif 1.40 <= ratio < 1.52:
            format_estimate = "Kabinettformat / Kleinbild (ca. 2:3)"
        elif 1.0 <= ratio <= 1.12:
            format_estimate = "Mittelformat (Quadratisch 6x6 / 1:1)"
        elif 1.20 <= ratio <= 1.38:
            format_estimate = "Großformat / Glasplatte (ca. 3:4 bzw. 4:5)"

        # Kontrast- und Zustandsanalyse
        contrast_std = (std_r + std_g + std_b) / 3.0
        if contrast_std < 28:
            condition = "Ausgebleicht / Kontrastarm (Fading)"
        elif contrast_std > 65:
            condition = "Hoher Dynamikumfang / Guter Zustand"
        else:
            condition = "Normaler Erhaltungszustand"

        return {
            "carrier_type": carrier_type,
            "color_tone": color_tone,
            "format_estimate": format_estimate,
            "aspect_ratio": round(ratio, 2),
            "estimated_era": estimated_era,
            "gnd_carrier": gnd_carrier,
            "condition": condition,
            "dimensions": f"{w} x {h} px",
        }

    def suggest_metadata_for_image(
        self,
        image_path: Union[str, Path],
        clip_service: Any,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Kombiniert Zero-Shot Fachbegriff-Klassifikation und physikalische
        Träger-/Zustandsanalyse zu vollständigen Erschließungsvorschlägen für Archivare.
        """
        # 1. Bild-Embedding erzeugen
        img_vec = clip_service.embed_image(image_path)

        # 2. Zero-Shot Tags abgleichen
        tags = self.suggest_thesaurus_tags(img_vec, clip_service=clip_service, top_k=top_k)

        # 3. Träger- und Erhaltungsanalyse durchführen
        carrier = self.detect_carrier_and_condition(image_path)

        return {
            "thesaurus_tags": tags,
            "suggestions": tags,
            "carrier_analysis": carrier,
            "suggested_keywords": [t["canonical"] for t in tags],
            "primary_subject": tags[0] if tags else None,
        }

    def blend_thesaurus_vector(
        self,
        query: str,
        primary_vector: List[float],
        clip_service: Any,
        weight: float = 0.25,
    ) -> List[float]:
        """
        Falls der Suchbegriff im Thesaurus existiert, wird der primäre CLIP-Vektor
        mit den kuratierten Thesaurus-Prompts angereichert und renormalisiert.
        """
        expansion = self.expand_query(query)
        if not expansion or not expansion.get("clip_prompts"):
            return primary_vector

        try:
            thesaurus_prompt = expansion["clip_prompts"][0]
            aux_vector = clip_service.embed_text(thesaurus_prompt)
            
            p_vec = np.array(primary_vector, dtype=np.float32)
            a_vec = np.array(aux_vector, dtype=np.float32)

            p_norm = np.linalg.norm(p_vec)
            a_norm = np.linalg.norm(a_vec)
            if p_norm > 0:
                p_vec = p_vec / p_norm
            if a_norm > 0:
                a_vec = a_vec / a_norm

            blended = (1.0 - weight) * p_vec + weight * a_vec
            b_norm = np.linalg.norm(blended)
            if b_norm > 0:
                blended = blended / b_norm

            return blended.tolist()
        except Exception as e:
            logger.warning("Thesaurus-Vektorblending fehlgeschlagen: %s", e)
            return primary_vector


thesaurus_service = ThesaurusService()
