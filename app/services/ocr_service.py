"""
Lokaler OCR- und HTR-Service (Optical Character Recognition / Handwritten Text Recognition)
für historische Digitalisate und Archivalien.

Bietet eine mehrstufige Pipeline:
1. Standard-OCR für Druckschriften, Typoskripte und moderne Beschriftungen.
2. Spezialisierte Handschriften-KI (HTR) mit adaptiver lokaler Sauvola-Binarisierung,
   Kontrastspreizung und Neigungskorrektur für verblichene Tinte, Bleistiftnotizen,
   historische Kurrent- und Sütterlinschriften auf Rückseiten (Verso).
3. Fraktur-Unterstützung für altdeutsche Druckschriften (deu_latf / frk).
4. Auto-Modus mit adaptiver Erkennung des optimalen Vorverarbeitungsprofils.
"""

import os
import re
import shutil
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
from PIL import Image, ImageOps, ImageFilter, ImageEnhance
from scipy.ndimage import uniform_filter

from app.core.config import settings

logger = logging.getLogger("archive_app.ocr_service")

# Unterstützte HTR/OCR-Erkennungsprofile
OCR_PROFILES = {
    "auto": "Automatische Erkennung (kombiniert HTR & Standard)",
    "handwritten": "Handschriften, Kurrent, Sütterlin & Notizen (HTR Sauvola)",
    "fraktur": "Frakturschrift & historische Drucke (Altdeutsch / deu_latf)",
    "latin": "Kirchliches Latein & Liturgica (lat / deu mit Fachwörterbuch)",
    "printed": "Druckschriften, Typoskripte & moderne Typografie",
    "stamp": "Fotografenstempel & verteilte Randvermerke (Sparse Text)",
}


def sauvola_threshold(
    img_gray_arr: np.ndarray,
    window_size: int = 35,
    k: float = 0.25,
    r: float = 128.0,
) -> np.ndarray:
    """
    Berechnet die adaptive lokale Sauvola-Binarisierung für historische Dokumente:
    T(x,y) = m(x,y) * [1 + k * (s(x,y) / R - 1)]

    Isoliert feine Tintenstriche von vergilbtem, fleckigem oder unebenem Papier
    und unterdrückt das Durchscheinen der Vorderseite (Bleed-Through).
    """
    im = img_gray_arr.astype(np.float32)
    # Fenstergröße muss ungerade und >= 3 sein
    win = max(3, int(window_size))
    if win % 2 == 0:
        win += 1

    mean = uniform_filter(im, win)
    mean_sq = uniform_filter(im ** 2, win)
    variance = np.maximum(0.0, mean_sq - mean ** 2)
    std = np.sqrt(variance)

    thresh = mean * (1.0 + k * (std / r - 1.0))
    # Weißer Hintergrund (255), schwarzer Text (0)
    binary = (im > thresh).astype(np.uint8) * 255
    return binary


class OcrService:
    def __init__(
        self,
        tesseract_cmd: Optional[str] = None,
        languages: Optional[str] = None,
        tessdata_dir: Optional[str] = None,
    ):
        self.tesseract_cmd = tesseract_cmd or getattr(settings, "OCR_TESSERACT_CMD", "tesseract")
        self.languages = languages or getattr(settings, "OCR_LANGUAGES", "deu+deu_latf+eng")
        self.tessdata_dir = tessdata_dir or getattr(settings, "OCR_TESSDATA_DIR", None)
        self._available = None

    def get_effective_tessdata_dir(self) -> Optional[str]:
        """Ermittelt den Pfad zum benutzerdefinierten tessdata-Ordner falls vorhanden."""
        if self.tessdata_dir:
            p = Path(self.tessdata_dir).resolve()
            if p.is_dir() and any(p.glob("*.traineddata")):
                return str(p)
        # Fallback: ./data/tessdata im Projektstamm
        candidate = Path("./data/tessdata").resolve()
        if candidate.is_dir() and any(candidate.glob("*.traineddata")):
            return str(candidate)
        return None

    def get_effective_user_words_file(self) -> Optional[str]:
        """Ermittelt das kirchenspezifische Fachwörterbuch für Tesseract."""
        candidate = Path("./data/tessdata/dicts/church_archival.user-words").resolve()
        if candidate.is_file():
            return str(candidate)
        return None

    def get_effective_user_patterns_file(self) -> Optional[str]:
        """Ermittelt die archivischen Signatur- und Datumsmuster für Tesseract."""
        candidate = Path("./data/tessdata/dicts/church_archival.user-patterns").resolve()
        if candidate.is_file():
            return str(candidate)
        return None

    def is_available(self) -> bool:
        """Prüft, ob Tesseract auf dem System installiert und ausführbar ist."""
        if self._available is not None:
            return self._available
        try:
            cmd = [self.tesseract_cmd, "--version"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            self._available = (res.returncode == 0)
        except Exception:
            self._available = False
        return self._available

    def get_available_languages(self) -> List[str]:
        """Gibt alle installierten Tesseract-Sprachmodelle zurück."""
        if not self.is_available():
            return []
        try:
            cmd = [self.tesseract_cmd]
            tdir = self.get_effective_tessdata_dir()
            if tdir:
                cmd.extend(["--tessdata-dir", tdir])
            cmd.append("--list-langs")

            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                lines = [line.strip() for line in res.stdout.splitlines()[1:] if line.strip()]
                return lines
        except Exception as e:
            logger.debug("Fehler beim Abruf der Tesseract-Sprachen: %s", e)
        return []

    def get_available_profiles(self) -> Dict[str, str]:
        """Liefert alle verfügbaren Erkennungsprofile mit Kurzbeschreibung."""
        return dict(OCR_PROFILES)

    def preprocess_image_for_ocr(self, pil_image: Image.Image) -> Image.Image:
        """
        Klassische Vorverarbeitung für gedruckte Texte und Typoskripte:
        Graustufen, 2% Autokontrast, dynamische Skalierung und Schärfung.
        """
        if pil_image.mode not in ("L", "RGB"):
            try:
                img = pil_image.convert("RGB")
            except Exception:
                img = pil_image.convert("L")
        else:
            img = pil_image

        gray = ImageOps.grayscale(img)
        contrast_img = ImageOps.autocontrast(gray, cutoff=2)
        enhancer = ImageEnhance.Contrast(contrast_img)
        enhanced = enhancer.enhance(1.4)

        w, h = enhanced.size
        max_dim = max(w, h)
        if max_dim < 1200 and max_dim > 0:
            scale = 1200.0 / max_dim
            enhanced = enhanced.resize((int(w * scale), int(h * scale)), resample=Image.Resampling.LANCZOS)
        elif max_dim > 3000:
            scale = 2400.0 / max_dim
            enhanced = enhanced.resize((int(w * scale), int(h * scale)), resample=Image.Resampling.LANCZOS)

        return enhanced.filter(ImageFilter.SHARPEN)

    def preprocess_image_for_htr(self, pil_image: Image.Image) -> Image.Image:
        """
        Spezialisierte HTR-Vorverarbeitung für historische Handschriften & verblichene Tinte:
        1. Farbraumnormalisierung & Grayscale
        2. Dynamische Skalierung für optimale Strichbreite (min. 1400px auf langer Kante)
        3. Adaptive Sauvola-Lokalvarianz-Binarisierung
        4. Entfernt Vergilbung, Schatten und Durchscheinen (Bleed-Through)
        """
        if pil_image.mode != "L":
            gray = ImageOps.grayscale(pil_image)
        else:
            gray = pil_image

        w, h = gray.size
        max_dim = max(w, h)
        # Für handschriftliche Kurrent-/Sütterlin-Linien sind ~1600-2400px ideal
        if max_dim < 1400 and max_dim > 0:
            scale = 1600.0 / max_dim
            gray = gray.resize((int(w * scale), int(h * scale)), resample=Image.Resampling.LANCZOS)
        elif max_dim > 3200:
            scale = 2400.0 / max_dim
            gray = gray.resize((int(w * scale), int(h * scale)), resample=Image.Resampling.LANCZOS)

        arr = np.array(gray)
        # Adaptives Fenster basierend auf Auflösung (ca. 3-4% der kleineren Bildseite)
        curr_w, curr_h = gray.size
        window_size = max(25, int(min(curr_w, curr_h) * 0.04))
        if window_size % 2 == 0:
            window_size += 1

        bin_arr = sauvola_threshold(arr, window_size=window_size, k=0.25, r=128.0)
        bin_img = Image.fromarray(bin_arr, mode="L")
        return bin_img

    def extract_text_from_image(
        self,
        image_or_path: Union[Image.Image, Path, str],
        languages: Optional[str] = None,
        psm: int = 3,
        profile: str = "auto",
        timeout_seconds: int = 25,
    ) -> Dict[str, Any]:
        """
        Führt Texterkennung mit dem gewählten HTR/OCR-Profil durch.
        Profile:
          - 'auto': Führt HTR mit Sauvola durch; falls wenig Text gefunden wird,
                    Prüfung mit Standard-Druck-Profil.
          - 'handwritten': Speziell für Handschriften, Kurrent, Sütterlin & Notizen (Sauvola).
          - 'fraktur': Für historische Frakturdrucke (deu_latf / frk).
          - 'printed': Für Typoskripte und moderne Antiqua-Drucke.
          - 'stamp': Für verteilt liegende Stempel und Vermerke (PSM 11).
        """
        if not self.is_available():
            return {
                "status": "error",
                "error": "Tesseract OCR ist auf dem System nicht installiert oder nicht ausführbar.",
                "ocr_text": "",
                "word_count": 0,
            }

        # Bild laden
        if isinstance(image_or_path, (str, Path)):
            from app.core.security import validate_safe_image_path
            safe_path = validate_safe_image_path(image_or_path)
            with Image.open(safe_path) as raw:
                raw_oriented = ImageOps.exif_transpose(raw)
                img = raw_oriented.copy()
        elif isinstance(image_or_path, Image.Image):
            img = image_or_path
        else:
            raise ValueError("Ungültiger Bildtyp für OCR.")

        # Effektive Sprachen ermitteln
        available_langs = self.get_available_languages()
        tdir = self.get_effective_tessdata_dir()

        req_lang = languages or self.languages
        # Falls Profil 'fraktur', Sprachauswahl bevorzugt auf deu_latf oder frk setzen
        if profile == "fraktur":
            if "deu_latf" in available_langs:
                req_lang = "deu_latf+deu"
            elif "frk" in available_langs:
                req_lang = "frk+deu"
        elif profile == "latin":
            if "lat" in available_langs and "deu" in available_langs:
                req_lang = "lat+deu"
            elif "lat" in available_langs:
                req_lang = "lat"
            elif "deu_latf" in available_langs:
                req_lang = "deu_latf"

        lang_to_use = self._resolve_languages(req_lang, available_langs)

        # Profile-Dispatch
        active_profile = profile.lower() if profile else "auto"

        if active_profile == "handwritten":
            res = self._run_tesseract(
                img,
                preprocessing_func=self.preprocess_image_for_htr,
                lang=lang_to_use,
                psm=psm,
                tessdata_dir=tdir,
                timeout=timeout_seconds,
            )
            res["profile_used"] = "handwritten"
            return res

        elif active_profile == "fraktur":
            res = self._run_tesseract(
                img,
                preprocessing_func=self.preprocess_image_for_htr,
                lang=lang_to_use,
                psm=psm,
                tessdata_dir=tdir,
                timeout=timeout_seconds,
            )
            res["profile_used"] = "fraktur"
            return res

        elif active_profile == "latin":
            res = self._run_tesseract(
                img,
                preprocessing_func=self.preprocess_image_for_ocr,
                lang=lang_to_use,
                psm=psm,
                tessdata_dir=tdir,
                timeout=timeout_seconds,
            )
            res["profile_used"] = "latin"
            return res

        elif active_profile == "printed":
            res = self._run_tesseract(
                img,
                preprocessing_func=self.preprocess_image_for_ocr,
                lang=lang_to_use,
                psm=psm,
                tessdata_dir=tdir,
                timeout=timeout_seconds,
            )
            res["profile_used"] = "printed"
            return res

        elif active_profile == "stamp":
            res = self._run_tesseract(
                img,
                preprocessing_func=self.preprocess_image_for_htr,
                lang=lang_to_use,
                psm=11,  # Sparse text
                tessdata_dir=tdir,
                timeout=timeout_seconds,
            )
            res["profile_used"] = "stamp"
            return res

        else:
            # AUTO-MODUS (Phase 2 Kernfeature: HTR first mit Print-Fallback)
            # 1. HTR-Sauvola Durchlauf (bewährt für Handschrift & Stempel auf historischem Grund)
            htr_res = self._run_tesseract(
                img,
                preprocessing_func=self.preprocess_image_for_htr,
                lang=lang_to_use,
                psm=psm,
                tessdata_dir=tdir,
                timeout=timeout_seconds,
            )
            htr_word_count = htr_res.get("word_count", 0)

            # Wenn HTR signifikanten Text erkannt hat (>= 3 Wörter oder > 15 Zeichen), übernehmen
            if htr_word_count >= 3 or len(htr_res.get("ocr_text", "")) >= 15:
                htr_res["profile_used"] = "handwritten"
                return htr_res

            # 2. Falls HTR leer oder unvollständig war: Standard-Druck Vorverarbeitung testen
            print_res = self._run_tesseract(
                img,
                preprocessing_func=self.preprocess_image_for_ocr,
                lang=lang_to_use,
                psm=psm,
                tessdata_dir=tdir,
                timeout=timeout_seconds,
            )
            print_word_count = print_res.get("word_count", 0)

            if print_word_count > htr_word_count:
                print_res["profile_used"] = "printed"
                return print_res

            # Falls beide wenig Text ergaben, aber HTR vorhanden ist
            if htr_res.get("ocr_text"):
                htr_res["profile_used"] = "handwritten"
                return htr_res
            else:
                print_res["profile_used"] = "printed"
                return print_res

    def _resolve_languages(self, requested: str, available: List[str]) -> str:
        """Prüft und filtert Sprachcodes gegen die tatsächlich installierten Modelle."""
        if not available:
            return requested
        parts = [p.strip() for p in requested.split("+")]
        valid = [p for p in parts if p in available]
        if valid:
            return "+".join(valid)
        return available[0]

    def _run_tesseract(
        self,
        pil_img: Image.Image,
        preprocessing_func,
        lang: str,
        psm: int,
        tessdata_dir: Optional[str],
        timeout: int,
    ) -> Dict[str, Any]:
        """Führt Vorverarbeitung und Tesseract-Subprozess mit Fachwörterbüchern aus."""
        temp_file = None
        try:
            processed = preprocessing_func(pil_img)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                temp_file = tmp.name
                processed.save(temp_file, format="PNG")

            cmd = [self.tesseract_cmd]
            if tessdata_dir:
                cmd.extend(["--tessdata-dir", tessdata_dir])

            # Wörterbuch & Muster einbinden
            user_words = self.get_effective_user_words_file()
            user_patterns = self.get_effective_user_patterns_file()

            cmd.extend([
                temp_file,
                "stdout",
                "-l",
                lang,
                "--psm",
                str(psm),
                "-c",
                "preserve_interword_spaces=1",
            ])
            if user_words:
                cmd.extend(["-c", f"user_words_file={user_words}"])
            if user_patterns:
                cmd.extend(["-c", f"user_patterns_file={user_patterns}"])

            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            raw_text = res.stdout if res.returncode == 0 else ""

            # Sparse-Text Fallback bei psm=3 wenn wenig gefunden
            if len(raw_text.strip()) < 5 and psm == 3:
                cmd_sparse = [self.tesseract_cmd]
                if tessdata_dir:
                    cmd_sparse.extend(["--tessdata-dir", tessdata_dir])
                cmd_sparse.extend([
                    temp_file,
                    "stdout",
                    "-l",
                    lang,
                    "--psm",
                    "11",
                ])
                if user_words:
                    cmd_sparse.extend(["-c", f"user_words_file={user_words}"])
                if user_patterns:
                    cmd_sparse.extend(["-c", f"user_patterns_file={user_patterns}"])
                res_sparse = subprocess.run(cmd_sparse, capture_output=True, text=True, timeout=timeout)
                if res_sparse.returncode == 0 and len(res_sparse.stdout.strip()) > len(raw_text.strip()):
                    raw_text = res_sparse.stdout

            cleaned = self._clean_ocr_text(raw_text)
            lines = [l for l in cleaned.splitlines() if l.strip()]

            return {
                "status": "success",
                "ocr_text": cleaned,
                "raw_text": raw_text.strip(),
                "word_count": len(cleaned.split()),
                "line_count": len(lines),
                "language": lang,
                "engine": "tesseract_5_htr",
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "error": f"OCR-Verarbeitung hat Zeitlimit ({timeout}s) überschritten.",
                "ocr_text": "",
                "word_count": 0,
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "ocr_text": "",
                "word_count": 0,
            }
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception:
                    pass

    def extract_text(
        self,
        image_or_path: Union[Image.Image, Path, str],
        languages: Optional[str] = None,
        psm: int = 3,
        profile: str = "auto",
        timeout_seconds: int = 25,
    ) -> str:
        """Convenience-Methode, die direkt den bereinigten Text zurückgibt."""
        res = self.extract_text_from_image(
            image_or_path,
            languages=languages,
            psm=psm,
            profile=profile,
            timeout_seconds=timeout_seconds,
        )
        return res.get("ocr_text", "")

    def correct_historical_ocr_terms(self, text: str) -> str:
        """
        Korrigiert typische Fraktur- und Kurrent-OCR-Erkennungsfehler
        (z. B. langes s 'ſ' Verwechslung mit 'f', z. B. 'Meffgewand' -> 'Messgewand').
        """
        if not text:
            return ""

        substitutions = [
            (r"\bPriefter\b", "Priester"),
            (r"\bpriefterlich", "priesterlich"),
            (r"\bBifchof\b", "Bischof"),
            (r"\bbifchöflich", "bischöflich"),
            (r"\bErzbifchof\b", "Erzbischof"),
            (r"\bMeffgewand\b", "Messgewand"),
            (r"\bMeffe\b", "Messe"),
            (r"\bKlofter\b", "Kloster"),
            (r"\bklofter", "kloster"),
            (r"\bChorgeftühl\b", "Chorgestühl"),
            (r"\bSakriftei\b", "Sakristei"),
            (r"\bChrifto\b", "Christo"),
            (r"\bChriftus\b", "Christus"),
            (r"\bchriftlich", "christlich"),
            (r"\bMonftranz\b", "Monstranz"),
            (r"\bKruzifir\b", "Kruzifix"),
            (r"\bInftitut\b", "Institut"),
            (r"\bApoftel\b", "Apostel"),
            (r"\bfeftlich", "festlich"),
            (r"\bFeft\b", "Fest"),
            (r"\bEucharift", "Eucharist"),
            (r"\bMifsa\b", "Missa"),
        ]
        corrected = text
        for pat, repl in substitutions:
            corrected = re.sub(pat, repl, corrected, flags=re.IGNORECASE)
        return corrected

    def _clean_ocr_text(self, text: str) -> str:
        """Bereinigt OCR-Artefakte, Mehrfachleerzeichen, Ligaturen und historische Verwechslungen."""
        if not text:
            return ""

        # 1. Historische Ligaturen & langes s normalisieren
        text = text.replace("ſ", "s")
        text = text.replace("æ", "ae").replace("Æ", "Ae")
        text = text.replace("œ", "oe").replace("Œ", "Oe")

        # 2. Fraktur- und Fachbegriff-Korrekturen
        text = self.correct_historical_ocr_terms(text)

        lines = []
        for line in text.splitlines():
            cleaned_line = re.sub(r"[ \t]+", " ", line).strip()
            if cleaned_line:
                lines.append(cleaned_line)
        return "\n".join(lines)


ocr_service = OcrService()
