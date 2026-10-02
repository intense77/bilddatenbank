"""
PDF Export Service für das Historische Bildarchiv.
Erstellt professionelle, druckfähige DIN A4 PDF-Kontaktabzüge und Archiv-Dossiers
aus ausgewählten Bildern des digitalen Leuchttischs.
100% lokal und ohne externe Abhängigkeiten über Pillow.
"""

import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.core.security import validate_safe_image_path
from app.services.thumbnail_service import thumbnail_service

logger = logging.getLogger("archive_app.pdf_export")

# DIN A4 bei 150 DPI (druckfähig, gestochen scharf, kompakte Dateigröße)
PAGE_WIDTH = 1240
PAGE_HEIGHT = 1754

# Schriften suchen (Standard-Linux-Pfade)
FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]
FONT_REGULAR_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
]


def _get_font(candidates: List[str], size: int) -> ImageFont.ImageFont:
    for path in candidates:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


class PdfExportService:
    def __init__(self):
        self.font_title = _get_font(FONT_BOLD_CANDIDATES, 32)
        self.font_header = _get_font(FONT_BOLD_CANDIDATES, 20)
        self.font_body_bold = _get_font(FONT_BOLD_CANDIDATES, 16)
        self.font_body = _get_font(FONT_REGULAR_CANDIDATES, 15)
        self.font_small = _get_font(FONT_REGULAR_CANDIDATES, 13)
        self.font_footer = _get_font(FONT_REGULAR_CANDIDATES, 12)

    def _draw_page_header(
        self,
        draw: ImageDraw.ImageDraw,
        title: str,
        subtitle: Optional[str] = None,
        page_num: int = 1,
        total_pages: int = 1,
    ):
        """Zeichnet die Kopf- und Fußzeile im Museums-Layout."""
        # Oberer Akzentbalken (Bernsteinfarben / Amber)
        draw.rectangle([(50, 40), (PAGE_WIDTH - 50, 44)], fill="#d97706")

        # Header-Titel
        draw.text((50, 56), title, font=self.font_header, fill="#0f172a")

        # Archiv-Metazeile rechts
        date_str = datetime.now().strftime("%d.%m.%Y")
        meta_text = f"Historisches Bildarchiv • {date_str}"
        draw.text((PAGE_WIDTH - 380, 58), meta_text, font=self.font_small, fill="#475569")

        if subtitle:
            draw.text((50, 85), subtitle, font=self.font_body, fill="#334155")
            draw.line([(50, 115), (PAGE_WIDTH - 50, 115)], fill="#cbd5e1", width=1)
            content_start_y = 135
        else:
            draw.line([(50, 95), (PAGE_WIDTH - 50, 95)], fill="#cbd5e1", width=1)
            content_start_y = 115

        # Fußzeile
        draw.line([(50, PAGE_HEIGHT - 65), (PAGE_WIDTH - 50, PAGE_HEIGHT - 65)], fill="#cbd5e1", width=1)
        footer_info = "Erstellt mit Historisches Bildarchiv (OpenCLIP & ArcFace)"
        draw.text((50, PAGE_HEIGHT - 52), footer_info, font=self.font_footer, fill="#64748b")
        page_str = f"Seite {page_num} von {total_pages}"
        draw.text((PAGE_WIDTH - 150, PAGE_HEIGHT - 52), page_str, font=self.font_footer, fill="#64748b")

        return content_start_y

    def _load_and_fit_image(self, file_path: str, max_w: int, max_h: int) -> Optional[Image.Image]:
        """Lädt ein Bild sicher und passt es proportional in die Box ein."""
        try:
            validated = validate_safe_image_path(file_path)
            # Nutzt optimiertes Laden über thumbnail_service oder Pillow direkt
            img = Image.open(validated)
            img = ImageOps.exif_transpose(img)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            return img
        except Exception as e:
            logger.warning("Konnte Bild für PDF nicht laden %s: %s", file_path, e)
            return None

    def generate_contact_sheet(
        self,
        items: List[Dict[str, Any]],
        title: str = "Archiv-Kontaktabzug",
        subtitle: Optional[str] = None,
        include_notes: bool = True,
    ) -> bytes:
        """
        Erzeugt einen mehrseitigen Kontaktabzug (2 Spalten x 3 Zeilen = 6 Bilder pro Seite).
        """
        pages: List[Image.Image] = []
        items_per_page = 6
        total_pages = max(1, (len(items) + items_per_page - 1) // items_per_page)

        cols = 2
        rows = 3
        slot_w = 540
        slot_h = 470
        img_max_w = slot_w - 20
        img_max_h = 310

        margin_x = 55
        gap_x = 50
        gap_y = 20

        for p_idx in range(total_pages):
            page = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), "#ffffff")
            draw = ImageDraw.Draw(page)
            start_y = self._draw_page_header(draw, title, subtitle, page_num=p_idx + 1, total_pages=total_pages)

            page_items = items[p_idx * items_per_page : (p_idx + 1) * items_per_page]

            for i_idx, item in enumerate(page_items):
                r = i_idx // cols
                c = i_idx % cols
                x = margin_x + c * (slot_w + gap_x)
                y = start_y + r * (slot_h + gap_y)

                # Rahmen / Kartenhintergrund für Bild-Eintrag
                draw.rounded_rectangle([(x, y), (x + slot_w, y + slot_h)], radius=8, fill="#f8fafc", outline="#e2e8f0", width=1)

                fp = item.get("file_path", "")
                fname = item.get("file_name") or Path(fp).name
                img = self._load_and_fit_image(fp, img_max_w, img_max_h)

                img_box_h = img_max_h
                if img:
                    # Bild mittig im Bild-Bereich zentrieren
                    ox = x + 10 + (img_max_w - img.width) // 2
                    oy = y + 10 + (img_max_h - img.height) // 2
                    page.paste(img, (ox, oy))
                else:
                    # Platzhalter
                    draw.rectangle([(x + 10, y + 10), (x + 10 + img_max_w, y + 10 + img_max_h)], fill="#e2e8f0")
                    draw.text((x + 150, y + 140), "Bild nicht lesbar", font=self.font_small, fill="#64748b")

                # Textbereich unter dem Bild
                text_y = y + img_box_h + 18
                draw.text((x + 14, text_y), fname, font=self.font_body_bold, fill="#0f172a")

                meta_parts = []
                if item.get("date"):
                    meta_parts.append(f"Datum: {item['date']}")
                if item.get("signature"):
                    meta_parts.append(f"Signatur: {item['signature']}")
                if item.get("creator"):
                    meta_parts.append(f"Urheber: {item['creator']}")
                
                if meta_parts:
                    draw.text((x + 14, text_y + 22), " • ".join(meta_parts), font=self.font_small, fill="#475569")

                # Erkannte Personen
                persons = item.get("persons") or []
                if persons:
                    p_str = "Personen: " + ", ".join(persons[:4])
                    if len(persons) > 4:
                        p_str += f" (+{len(persons) - 4})"
                    draw.text((x + 14, text_y + 44), p_str, font=self.font_small, fill="#d97706")

                # Kuratoren-Notiz
                note = item.get("notes") or item.get("note")
                if include_notes and note:
                    note_str = f"Notiz: {note[:60]}" + ("..." if len(note) > 60 else "")
                    draw.text((x + 14, text_y + 66), note_str, font=self.font_small, fill="#059669")

            pages.append(page)

        out_buf = io.BytesIO()
        pages[0].save(out_buf, format="PDF", resolution=150.0, save_all=True, append_images=pages[1:])
        return out_buf.getvalue()

    def generate_dossier(
        self,
        items: List[Dict[str, Any]],
        title: str = "Archiv-Dossier",
        subtitle: Optional[str] = None,
        include_notes: bool = True,
    ) -> bytes:
        """
        Erzeugt ein Einzelseiten-Dossier (1 großes Foto pro DIN-A4-Seite mit ausführlichen Metadaten).
        """
        pages: List[Image.Image] = []
        total_pages = max(1, len(items))

        img_max_w = PAGE_WIDTH - 120
        img_max_h = 950

        for p_idx, item in enumerate(items):
            page = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), "#ffffff")
            draw = ImageDraw.Draw(page)
            start_y = self._draw_page_header(draw, title, subtitle, page_num=p_idx + 1, total_pages=total_pages)

            fp = item.get("file_path", "")
            fname = item.get("file_name") or Path(fp).name
            img = self._load_and_fit_image(fp, img_max_w, img_max_h)

            if img:
                ox = 60 + (img_max_w - img.width) // 2
                oy = start_y + (img_max_h - img.height) // 2
                page.paste(img, (ox, oy))
                # Feiner Rahmen um das Foto
                draw.rectangle([(ox - 1, oy - 1), (ox + img.width, oy + img.height)], outline="#cbd5e1", width=1)
            else:
                draw.rectangle([(60, start_y), (PAGE_WIDTH - 60, start_y + img_max_h)], fill="#f1f5f9")
                draw.text((PAGE_WIDTH // 2 - 80, start_y + img_max_h // 2), "Bilddatei nicht lesbar", font=self.font_body, fill="#64748b")

            # Metadaten-Kasten im unteren Drittel
            meta_box_y = start_y + img_max_h + 30
            meta_box_h = PAGE_HEIGHT - meta_box_y - 85
            draw.rounded_rectangle([(60, meta_box_y), (PAGE_WIDTH - 60, meta_box_y + meta_box_h)], radius=12, fill="#f8fafc", outline="#e2e8f0", width=1)

            # Dateiname & Titel
            item_title = item.get("title") or fname
            draw.text((85, meta_box_y + 20), item_title, font=self.font_title, fill="#0f172a")

            cur_y = meta_box_y + 70
            metadata_rows = [
                ("Dateiname:", fname),
                ("Archivsignatur:", item.get("signature") or "—"),
                ("Datierung:", item.get("date") or "—"),
                ("Fotograf / Urheber:", item.get("creator") or "—"),
                ("Originalpfad:", fp),
            ]

            for label, val in metadata_rows:
                draw.text((85, cur_y), label, font=self.font_body_bold, fill="#475569")
                draw.text((270, cur_y), str(val), font=self.font_body, fill="#0f172a")
                cur_y += 28

            persons = item.get("persons") or []
            if persons:
                draw.text((85, cur_y), "Personen:", font=self.font_body_bold, fill="#d97706")
                draw.text((270, cur_y), ", ".join(persons), font=self.font_body, fill="#b45309")
                cur_y += 28

            note = item.get("notes") or item.get("note")
            if include_notes and note:
                draw.text((85, cur_y), "Kuratoren-Notiz:", font=self.font_body_bold, fill="#059669")
                draw.text((270, cur_y), str(note), font=self.font_body, fill="#047857")

            pages.append(page)

        out_buf = io.BytesIO()
        pages[0].save(out_buf, format="PDF", resolution=150.0, save_all=True, append_images=pages[1:])
        return out_buf.getvalue()


pdf_export_service = PdfExportService()
