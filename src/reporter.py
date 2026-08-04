"""
PDF reporter module for Fashion Trend Monitor.

Generates professional fashion trend reports per category with Roboto typography.
Each product card shows two clearly separated sections:
  1. PRODUCT DETAILS  — authoritative scraped data (composition, material, fit, description)
  2. AI VISUAL ANALYSIS — 3-5 bullet-point visual observations from the vision model

Empty fields are omitted. AI-only fields fall back to "Not Clearly Known" when empty.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from PIL import Image as PILImage

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, HRFlowable, KeepTogether
)
from reportlab.graphics.shapes import Drawing, Rect, Circle, String, Path as RLPath
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from src.config import Config
from src.models import Product

logger = logging.getLogger(__name__)

# ── Font Registration ─────────────────────────────────────────────────────────
_FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_FONTS_REGISTERED = False


def _register_fonts():
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    try:
        pdfmetrics.registerFont(TTFont("Roboto", str(_FONTS_DIR / "Roboto-Regular.ttf")))
        pdfmetrics.registerFont(TTFont("Roboto-Bold", str(_FONTS_DIR / "Roboto-Bold.ttf")))
        pdfmetrics.registerFont(TTFont("Roboto-Italic", str(_FONTS_DIR / "Roboto-Italic.ttf")))
        from reportlab.pdfbase.pdfmetrics import registerFontFamily
        registerFontFamily("Roboto", normal="Roboto", bold="Roboto-Bold", italic="Roboto-Italic")
        _FONTS_REGISTERED = True
        logger.info("Roboto fonts registered.")
    except Exception as e:
        logger.warning(f"Could not register Roboto fonts ({e}). Falling back to Helvetica.")


# ── Text Helpers ──────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    """Escape XML special characters for ReportLab Paragraph."""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _render_ai(text: str) -> str:
    """Convert AI markdown **bold** / _italic_ markers to ReportLab XML tags."""
    if not text:
        return ""
    text = text.replace("&", "&amp;")
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'_(.+?)_', r'<i>\1</i>', text)
    return text


def _has(value: str) -> bool:
    """Return True if value is a non-empty, meaningful string."""
    return bool(value and value.strip() and value.strip().upper() not in ("N/A", "NONE", "NULL"))


# ── Fashion Doodle Fallback ───────────────────────────────────────────────────

def create_fashion_doodle(width: float = 2.4 * inch, height: float = 3.2 * inch) -> Drawing:
    """Vector fashion sketch used when product photo cannot be downloaded."""
    d = Drawing(width, height)
    d.add(Rect(0, 0, width, height,
               fillColor=colors.HexColor("#F8FAFC"),
               strokeColor=colors.HexColor("#E2E8F0"),
               strokeWidth=0.5, rx=6, ry=6))
    cx, cy = width / 2.0, height / 2.0 + 10

    hook = RLPath(strokeColor=colors.HexColor("#475569"), strokeWidth=2, fillColor=None)
    hook.moveTo(cx, cy + 45)
    hook.curveTo(cx + 12, cy + 60, cx - 12, cy + 70, cx, cy + 78)
    d.add(hook)

    hanger = RLPath(strokeColor=colors.HexColor("#475569"), strokeWidth=2.2, fillColor=None)
    hanger.moveTo(cx - 50, cy + 30)
    hanger.lineTo(cx, cy + 45)
    hanger.lineTo(cx + 50, cy + 30)
    hanger.lineTo(cx - 50, cy + 30)
    d.add(hanger)

    garment = RLPath(strokeColor=colors.HexColor("#94A3B8"), strokeWidth=1.5,
                     strokeDashArray=[4, 3], fillColor=colors.HexColor("#F1F5F9"))
    garment.moveTo(cx - 38, cy + 24)
    garment.curveTo(cx - 28, cy - 10, cx - 45, cy - 55, cx - 55, cy - 75)
    garment.lineTo(cx + 55, cy - 75)
    garment.curveTo(cx + 45, cy - 55, cx + 28, cy - 10, cx + 38, cy + 24)
    garment.closePath()
    d.add(garment)

    d.add(Circle(cx - 30, cy + 50, 2.5, fillColor=colors.HexColor("#CBD5E1"), strokeColor=None))
    d.add(Circle(cx + 35, cy + 55, 3.5, fillColor=colors.HexColor("#FEF3C7"), strokeColor=None))
    d.add(String(cx, 14, "PHOTO UNAVAILABLE", textAnchor="middle",
                 fontName="Helvetica", fontSize=6.5, fillColor=colors.HexColor("#94A3B8")))
    return d


# ── Custom Canvas with Decorations & Footer ───────────────────────────────────

class ArtisticFashionCanvas(canvas.Canvas):
    """Canvas subclass that draws subtle corner accents and a footer on every page."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self._generation_ts = datetime.now().strftime("%Y-%m-%d  %H:%M")

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_page_chrome(num_pages)
            super().showPage()
        super().save()

    def _draw_page_chrome(self, page_count: int):
        self.saveState()

        # Soft accent blobs — top-right corner, well away from content
        self.setFillColor(colors.HexColor("#FEF3C7"))
        self.circle(595, 800, 55, fill=1, stroke=0)
        self.setFillColor(colors.HexColor("#F3E8FF"))
        self.circle(565, 815, 35, fill=1, stroke=0)
        self.setFillColor(colors.HexColor("#ECFDF5"))
        self.circle(15, 15, 60, fill=1, stroke=0)

        # Thin editorial rule just below header margin
        self.setStrokeColor(colors.HexColor("#1E293B"))
        self.setLineWidth(1.2)
        self.line(36, 750, 576, 750)

        # Footer — left: brand, centre: timestamp, right: page
        self.setFont("Helvetica-Bold", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawString(36, 20, "FASHION TREND MONITOR")

        self.setFont("Helvetica", 7)
        self.setFillColor(colors.HexColor("#94A3B8"))
        self.drawCentredString(306, 20, f"Generated: {self._generation_ts}")

        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawRightString(576, 20, f"{self._pageNumber:02d} / {page_count:02d}")

        self.restoreState()


# ── PDF Reporter ──────────────────────────────────────────────────────────────

class PDFReporter:
    """Generates styled per-category PDF fashion trend reports."""

    def __init__(self, config: Config):
        self.config = config
        _register_fonts()

    # ── Font helper ───────────────────────────────────────────────────────────

    def _f(self, bold: bool = False, italic: bool = False) -> str:
        if bold:
            return "Roboto-Bold"
        if italic:
            return "Roboto-Italic"
        return "Roboto"

    # ── Style definitions ─────────────────────────────────────────────────────

    def _build_styles(self) -> dict:
        F = self._f
        return {
            # Page-level
            "title": ParagraphStyle("RTitle",
                fontName=F(bold=True), fontSize=20, leading=24,
                textColor=colors.HexColor("#0F172A"), alignment=TA_LEFT),
            "subtitle": ParagraphStyle("RSubtitle",
                fontName=F(), fontSize=9, leading=13,
                textColor=colors.HexColor("#475569"), alignment=TA_RIGHT),
            "sum_label": ParagraphStyle("RSumLabel",
                fontName=F(bold=True), fontSize=8, leading=12,
                textColor=colors.HexColor("#475569")),
            "sum_value": ParagraphStyle("RSumValue",
                fontName=F(), fontSize=8, leading=12,
                textColor=colors.HexColor("#0F172A")),

            # Product item
            "item_title": ParagraphStyle("RItemTitle",
                fontName=F(bold=True), fontSize=11, leading=15,
                textColor=colors.HexColor("#0F172A")),
            "item_meta": ParagraphStyle("RItemMeta",
                fontName=F(), fontSize=8.5, leading=12,
                textColor=colors.HexColor("#64748B")),

            # Section Badges
            "badge_web": ParagraphStyle("RBadgeWeb",
                fontName=F(bold=True), fontSize=8, leading=11,
                textColor=colors.HexColor("#1E40AF"), spaceBefore=0, spaceAfter=2),
            "badge_ai": ParagraphStyle("RBadgeAI",
                fontName=F(bold=True), fontSize=8, leading=11,
                textColor=colors.HexColor("#0F766E"), spaceBefore=0, spaceAfter=2),

            # Scraped Web Specs
            "web_desc": ParagraphStyle("RWebDesc",
                fontName=F(italic=True), fontSize=8, leading=11.5,
                textColor=colors.HexColor("#334155")),
            "spec_label": ParagraphStyle("RSpecLabel",
                fontName=F(bold=True), fontSize=7.5, leading=11,
                textColor=colors.HexColor("#475569")),
            "spec_val": ParagraphStyle("RSpecVal",
                fontName=F(), fontSize=7.5, leading=11,
                textColor=colors.HexColor("#0F172A")),

            # AI Analysis Bullets
            "bullet": ParagraphStyle("RBullet",
                fontName=F(), fontSize=8, leading=12,
                textColor=colors.HexColor("#1E293B"), leftIndent=4),
            "muted": ParagraphStyle("RMuted",
                fontName=F(italic=True), fontSize=8, leading=12,
                textColor=colors.HexColor("#94A3B8")),
        }

    # ── Internal card builder ─────────────────────────────────────────────────

    def _build_right_column(self, product: Product, styles: dict, category_name: str) -> list:
        """Build a rich, structured multi-section layout for the right column of a product card."""
        elems = []
        F = self._f

        # ── SECTION 1: SCRAPED WEBSITE SPECIFICATIONS ─────────────────────────
        elems.append(Paragraph("SCRAPED WEBSITE SPECIFICATIONS", styles["badge_web"]))
        elems.append(HRFlowable(width="100%", thickness=0.8,
                                color=colors.HexColor("#2563EB"), spaceAfter=4))

        # Description callout block (if scraped description exists)
        if _has(product.description):
            desc_text = _clean(product.description[:320])
            desc_p = Paragraph(f'"{desc_text}"', styles["web_desc"])
            desc_box = Table([[desc_p]], colWidths=[4.3 * inch])
            desc_box.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#BFDBFE")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            elems.append(desc_box)
            elems.append(Spacer(1, 4))

        # Structured Specs Grid — Composition / Material / Fit prefer AI-extracted values
        attrs = {}
        if product.ai_analysis and hasattr(product.ai_analysis, "category_specific_info"):
            attrs = product.ai_analysis.category_specific_info or {}

        def _attr(*keys: str) -> str:
            for key in keys:
                val = attrs.get(key, "")
                if _has(val):
                    return _clean(val)
            return ""

        price_str = _clean(product.price) if _has(product.price) else "Price not listed"
        comp_str = (
            _attr("Composition", "composition")
            or (_clean(product.composition) if _has(product.composition) else "")
            or "—"
        )
        mat_str = (
            _attr("Material", "material")
            or (_clean(product.material_type) if _has(product.material_type) else "")
            or "—"
        )
        fit_str = (
            _attr("Fit", "fit")
            or (_clean(product.fit) if _has(product.fit) else "")
            or "—"
        )
        
        # Design Pattern logic
        pattern_str = "—"
        if product.ai_analysis and hasattr(product.ai_analysis, "design_pattern"):
            if _has(product.ai_analysis.design_pattern) and product.ai_analysis.design_pattern != "N/A":
                pattern_str = _clean(product.ai_analysis.design_pattern)

        # Attributes: AI key-value bullets (Tops → Sleeve/Neckline; Bottoms → Waist Rise/Style; etc.)
        skip_keys = {"composition", "material", "material type", "fit", "garment fit", "design pattern"}
        detail_pairs = []
        if attrs:
            for k, v in attrs.items():
                if _has(v) and k.strip().lower() not in skip_keys:
                    detail_pairs.append(f"• <b>{_clean(k).title()}:</b> {_clean(v)}")
        else:
            for k, v in (product.fit_details or {}).items():
                if _has(v) and k.strip().lower() not in skip_keys:
                    detail_pairs.append(f"• <b>{_clean(k).title()}:</b> {_clean(v)}")

        details_str = "<br/>".join(detail_pairs) if detail_pairs else "—"

        # Collect non-empty fields
        fields = []
        if price_str and price_str != "—" and price_str != "Price not listed":
            fields.append(("Price", f"<b>{price_str}</b>"))
        if pattern_str and pattern_str != "—":
            fields.append(("Design Pattern", pattern_str))
        if comp_str and comp_str != "—":
            fields.append(("Composition", comp_str))
        if mat_str and mat_str != "—":
            fields.append(("Material", mat_str))
        if fit_str and fit_str != "—":
            fields.append(("Garment Fit", fit_str))
        if details_str and details_str != "—":
            fields.append(("Attributes", details_str))
            
        # Pad fields to be even length so they fit nicely in a 4-column grid (2 pairs per row)
        if len(fields) % 2 != 0:
            fields.append(("", ""))

        specs_table_data = []
        for i in range(0, len(fields), 2):
            row = []
            
            # First pair
            label1, val1 = fields[i]
            if label1:
                row.extend([Paragraph(label1, styles["spec_label"]), Paragraph(val1, styles["spec_val"])])
            else:
                row.extend(["", ""])
                
            # Second pair
            label2, val2 = fields[i+1]
            if label2:
                row.extend([Paragraph(label2, styles["spec_label"]), Paragraph(val2, styles["spec_val"])])
            else:
                row.extend(["", ""])
                
            specs_table_data.append(row)
            
        if not specs_table_data:
            # Fallback if somehow empty
            specs_table_data = [["", "", "", ""]]
        specs_tbl = Table(specs_table_data, colWidths=[0.85 * inch, 1.3 * inch, 0.75 * inch, 1.4 * inch])
        specs_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 3),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        elems.append(specs_tbl)

        # ── SECTION 2: AI VISUAL TREND ANALYSIS ─────────────────────────────
        elems.append(Spacer(1, 6))
        
        ai = product.ai_analysis
        confidence_str = f"  (Confidence: {ai.confidence_score})" if ai and hasattr(ai, "confidence_score") and _has(ai.confidence_score) else ""
        elems.append(Paragraph(f"VISUAL TREND ANALYSIS{confidence_str}", styles["badge_ai"]))
        elems.append(HRFlowable(width="100%", thickness=0.8,
                                color=colors.HexColor("#0D9488"), spaceAfter=4))
        bullets = [b for b in (ai.bullet_summary if ai else [])
                   if b and b.strip() and b.strip() not in ("", '""')]

        if bullets:
            ai_elems = []
            for bullet in bullets[:4]:
                clean_b = _render_ai(bullet.strip().lstrip("•–- "))
                if clean_b:
                    ai_elems.append(Paragraph(f"• {clean_b}", styles["bullet"]))
                    ai_elems.append(Spacer(1, 1.5))
            
            ai_box = Table([[ai_elems]], colWidths=[4.3 * inch])
            ai_box.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0FDF4")),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#A7F3D0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            elems.append(ai_box)
        else:
            elems.append(Paragraph("Visual trend analysis pending.", styles["muted"]))

        return elems

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_category_report(
        self,
        products: List[Product],
        category_name: str,
        output_dir: Optional[Path] = None
    ) -> Path:
        """Generate a single category PDF report and return its path."""
        target_dir = output_dir or self.config.output_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime("%Y-%m-%d")
        safe_cat = category_name.replace(" ", "_")
        target_path = target_dir / f"report_{date_str}_{safe_cat}.pdf"

        logger.info(f"Generating PDF for '{category_name}' ({len(products)} items) -> {target_path}")

        doc = SimpleDocTemplate(
            str(target_path),
            pagesize=letter,
            rightMargin=36, leftMargin=36,
            topMargin=50, bottomMargin=44,
        )

        styles = self._build_styles()
        story = []

        # ── Page Header ───────────────────────────────────────────────────────
        date_formatted = datetime.now().strftime("%B %d, %Y").upper()
        header = Table([[
            Paragraph("FASHION TREND REPORT", styles["title"]),
            Paragraph(
                f"<b>{category_name.upper()} COLLECTION</b><br/>{date_formatted}",
                styles["subtitle"]
            ),
        ]], colWidths=[4.2 * inch, 2.8 * inch])
        header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        story.append(header)
        story.append(Spacer(1, 4))
        story.append(HRFlowable(width="100%", thickness=1,
                                color=colors.HexColor("#CBD5E1"), spaceAfter=8))

        # ── Summary block ─────────────────────────────────────────────────────
        summary_data = [
            [
                Paragraph("Retailer", styles["sum_label"]),
                Paragraph("H&amp;M India", styles["sum_value"]),
                Paragraph("Category", styles["sum_label"]),
                Paragraph(category_name, styles["sum_value"]),
            ],
            [
                Paragraph("Report Date", styles["sum_label"]),
                Paragraph(datetime.now().strftime("%d %b %Y"), styles["sum_value"]),
                Paragraph("New Products", styles["sum_label"]),
                Paragraph(str(len(products)), styles["sum_value"]),
            ],
        ]
        summary_tbl = Table(summary_data, colWidths=[1.0*inch, 1.8*inch, 1.0*inch, 1.8*inch])
        summary_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(summary_tbl)
        story.append(Spacer(1, 16))

        if not products:
            story.append(Paragraph(
                f"No new arrivals detected for {category_name} during this cycle.",
                styles["muted"]
            ))
            doc.build(story, canvasmaker=ArtisticFashionCanvas)
            return target_path

        # ── Product cards ─────────────────────────────────────────────────────
        for idx, product in enumerate(products, 1):
            item_elems = []

            # Title
            item_elems.append(Paragraph(
                f"{idx:02d}. {_clean(product.name)}",
                styles["item_title"]
            ))

            # Meta line: price • art no • link
            price_raw = product.price if _has(product.price) else None
            price_meta = _clean(price_raw) if price_raw else "Price not available"
            link = f"<a href='{product.product_url}' color='#2563EB'><u>View Online</u></a>"
            item_elems.append(Paragraph(
                f"{price_meta}  •  Art. No: {product.art_no}  •  {link}",
                styles["item_meta"]
            ))
            item_elems.append(Spacer(1, 6))

            # Photo or doodle
            photo = None
            if product.screenshot_path and Path(product.screenshot_path).exists():
                try:
                    with PILImage.open(product.screenshot_path) as test_img:
                        test_img.verify()
                    photo = Image(product.screenshot_path, width=2.4 * inch, height=3.2 * inch)
                except Exception as e:
                    logger.warning(f"Corrupt image for {product.art_no}: {e}")
            if photo is None:
                photo = create_fashion_doodle(2.4 * inch, 3.2 * inch)

            # Right column
            right_elems = self._build_right_column(product, styles, category_name)
            right_col = Table(
                [[el] for el in right_elems],
                colWidths=[4.4 * inch]
            )
            right_col.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]))

            # Assemble card
            card = Table(
                [[photo, right_col]],
                colWidths=[2.6 * inch, 4.4 * inch]
            )
            card.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAFAFA")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LINEAFTER", (0, 0), (0, -1), 0.4, colors.HexColor("#E2E8F0")),
            ]))

            item_elems.append(card)
            item_elems.append(Spacer(1, 16))
            story.append(KeepTogether(item_elems))

        doc.build(story, canvasmaker=ArtisticFashionCanvas)
        logger.info(f"PDF for '{category_name}' saved to {target_path}")
        return target_path

    def generate_all_reports(self, products: List[Product]) -> Dict[str, Path]:
        """Group products by category and generate one PDF per category."""
        categorized: Dict[str, List[Product]] = {}
        for p in products:
            cat = p.category or "General"
            categorized.setdefault(cat, []).append(p)

        report_paths: Dict[str, Path] = {}
        for cat_name, cat_products in categorized.items():
            report_paths[cat_name] = self.generate_category_report(cat_products, cat_name)
        return report_paths
