"""
Thesaurus-Service für kirchliche Fachbegriffe, Ikonographie (Iconclass) und GND-Normdaten.
Ermöglicht:
1. Thesaurus-basierte Synonym-Erweiterung (Query Expansion) für Volltext- und Vektorsuche
2. Ikonographische Klassifizierung nach Iconclass
3. Auto-Vervollständigung und Fachbegriffs-Katalog für Archivare
4. Zero-Shot Vektor-Anreicherung (OpenCLIP) mit kuratierten kirchlichen Prompts
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set
import numpy as np

from app.core.thesaurus_data import CHURCH_THESAURUS

logger = logging.getLogger("archive_app.thesaurus_service")


class ThesaurusService:
    def __init__(self):
        self._thesaurus = CHURCH_THESAURUS
        self._term_lookup: Dict[str, Dict[str, Any]] = {}
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
        """Liefert Begriffe, optional gefiltert nach Kategorie."""
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
        
        # Alle Suchbegriffe für Datenbankabgleich zusammentragen
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
        """Liefert Begriffsvorschläge für die Suchleiste."""
        clean_pref = prefix.strip().lower()
        if not clean_pref or len(clean_pref) < 2:
            return []

        suggestions: List[Dict[str, Any]] = []
        seen_canonicals: Set[str] = set()

        # Zuerst Matches auf kanonische Begriffe
        for item in self._thesaurus:
            canon = item["canonical"]
            if canon.lower().startswith(clean_pref):
                suggestions.append({
                    "term": canon,
                    "canonical": canon,
                    "category": item["category"],
                    "iconclass": item.get("iconclass"),
                    "is_synonym": False,
                })
                seen_canonicals.add(canon)
                if len(suggestions) >= limit:
                    return suggestions

        # Danach Matches auf Synonyme
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
                        "is_synonym": True,
                    })
                    seen_canonicals.add(canon)
                    break
            if len(suggestions) >= limit:
                break

        return suggestions

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

            # Normalisierung sicherstellen
            p_norm = np.linalg.norm(p_vec)
            a_norm = np.linalg.norm(a_vec)
            if p_norm > 0:
                p_vec = p_vec / p_norm
            if a_norm > 0:
                a_vec = a_vec / a_norm

            # Gewichtete Vektormischung
            blended = (1.0 - weight) * p_vec + weight * a_vec
            b_norm = np.linalg.norm(blended)
            if b_norm > 0:
                blended = blended / b_norm

            return blended.tolist()
        except Exception as e:
            logger.warning("Thesaurus-Vektorblending fehlgeschlagen: %s", e)
            return primary_vector


thesaurus_service = ThesaurusService()
