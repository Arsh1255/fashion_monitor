"""
PDF reporter module for Fashion Trend Monitor.

Generates professional fashion trend reports per category with Roboto typography.
Each product card shows two clearly separated sections:
  1. PRODUCT DETAILS  — authoritative scraped data (composition, material, fit, description)
  2. AI VISUAL ANALYSIS — 3-5 bullet-point visual observations from the vision model

Supports multi-retailer grouping with a Table of Contents and Dynamic Footers.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any

from PIL import Image as PILImage

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle,
    Image, HRFlowable, KeepTogether, PageBreak
)
from reportlab.platypus.flowables import Flowable
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.graphics.shapes import Drawing, Rect, Path as RLPath
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
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _render_ai(text: str) -> str:
    if not text:
        return ""
    text = text.replace("&", "&amp;")
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'_(.+?)_', r'<i>\1</i>', text)
    return text


def _has(value: str) -> bool:
    return bool(value and value.strip() and value.strip().upper() not in ("N/A", "NONE", "NULL"))


# ── Fashion Doodle Fallback ───────────────────────────────────────────────────

def create_fashion_doodle(width: float = 2.4 * inch, height: float = 3.2 * inch) -> Drawing:
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
    hanger.moveTo(cx, cy + 45)
    hanger.lineTo(cx - 50, cy)
    hanger.lineTo(cx + 50, cy)
    hanger.closePath()
    d.add(hanger)
    return d

# ── Dynamic Footer Flowable ───────────────────────────────────────────────────

class SetRetailerAction(Flowable):
    """Flowable to update the document's current retailer state."""
    def __init__(self, retailer_name: str):
        super().__init__()
        self.retailer_name = retailer_name
        self.width = 0
        self.height = 0

    def wrap(self, availWidth, availHeight):
        return 0, 0

    def draw(self):
        pass

    def apply(self, doc):
        doc.current_retailer = self.retailer_name


class RetailerDocTemplate(BaseDocTemplate):
    """Custom template that tracks current retailer for dynamic footers."""
    def __init__(self, *args, **kwargs):
        self.category_name = kwargs.pop('category_name', 'General')
        super().__init__(*args, **kwargs)
        self.current_retailer = ""
        self._generation_ts = datetime.now().strftime("%Y-%m-%d  %H:%M")

    def afterFlowable(self, flowable):
        if isinstance(flowable, SetRetailerAction):
            flowable.apply(self)
        if hasattr(flowable, 'toc_level'):
            text = flowable.getPlainText()
            self.notify('TOCEntry', (flowable.toc_level, text, self.page))


def draw_dynamic_footer(canvas, doc):
    canvas.saveState()

    # Soft accent blobs — top-right corner, well away from content
    canvas.setFillColor(colors.HexColor("#FEF3C7"))
    canvas.circle(595, 800, 55, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#F3E8FF"))
    canvas.circle(565, 815, 35, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#ECFDF5"))
    canvas.circle(15, 15, 60, fill=1, stroke=0)

    # Thin editorial rule just below header margin
    canvas.setStrokeColor(colors.HexColor("#1E293B"))
    canvas.setLineWidth(1.2)
    canvas.line(36, 750, 576, 750)

    # Footer — left: Retailer, centre: Category + Time, right: page
    canvas.setFont("Helvetica-Bold", 7.5)
    canvas.setFillColor(colors.HexColor("#64748B"))
    retailer_label = doc.current_retailer.upper() if doc.current_retailer else "FASHION TREND MONITOR"
    canvas.drawString(36, 20, retailer_label)

    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#94A3B8"))
    canvas.drawCentredString(306, 20, f"Category: {doc.category_name} | Generated: {doc._generation_ts}")

    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawRightString(576, 20, f"Page {doc.page}")

    canvas.restoreState()


# ── PDF Reporter ──────────────────────────────────────────────────────────────

class PDFReporter:
    """Generates styled per-category PDF fashion trend reports."""

    def __init__(self, config: Config):
        self.config = config
        _register_fonts()

    def _f(self, bold: bool = False, italic: bool = False) -> str:
        if bold: return "Roboto-Bold"
        if italic: return "Roboto-Italic"
        return "Roboto"

    def _build_styles(self) -> dict:
        F = self._f
        return {
            "title": ParagraphStyle("RTitle", fontName=F(bold=True), fontSize=24, leading=28, textColor=colors.HexColor("#0F172A"), alignment=TA_CENTER),
            "subtitle": ParagraphStyle("RSubtitle", fontName=F(), fontSize=12, leading=16, textColor=colors.HexColor("#475569"), alignment=TA_CENTER),
            "toc_header": ParagraphStyle("RToCHeader", fontName=F(bold=True), fontSize=16, leading=20, textColor=colors.HexColor("#0F172A"), spaceAfter=10),
            "retailer_header": ParagraphStyle("RRetailerHeader", fontName=F(bold=True), fontSize=20, leading=24, textColor=colors.HexColor("#1E3A8A"), spaceAfter=20, spaceBefore=10),
            
            "item_title": ParagraphStyle("RItemTitle", fontName=F(bold=True), fontSize=11, leading=15, textColor=colors.HexColor("#0F172A")),
            "item_meta": ParagraphStyle("RItemMeta", fontName=F(), fontSize=8.5, leading=12, textColor=colors.HexColor("#64748B")),
            "badge_web": ParagraphStyle("RBadgeWeb", fontName=F(bold=True), fontSize=8, leading=11, textColor=colors.HexColor("#1E40AF"), spaceBefore=0, spaceAfter=2),
            "badge_ai": ParagraphStyle("RBadgeAI", fontName=F(bold=True), fontSize=8, leading=11, textColor=colors.HexColor("#0F766E"), spaceBefore=0, spaceAfter=2),
            "web_desc": ParagraphStyle("RWebDesc", fontName=F(italic=True), fontSize=8, leading=11.5, textColor=colors.HexColor("#334155")),
            "spec_label": ParagraphStyle("RSpecLabel", fontName=F(bold=True), fontSize=7.5, leading=11, textColor=colors.HexColor("#475569")),
            "spec_val": ParagraphStyle("RSpecVal", fontName=F(), fontSize=7.5, leading=11, textColor=colors.HexColor("#0F172A")),
            "bullet": ParagraphStyle("RBullet", fontName=F(), fontSize=8, leading=12, textColor=colors.HexColor("#1E293B"), leftIndent=4),
        }

    def _build_right_column(self, product: Product, styles: dict) -> list:
        elems = []
        
        elems.append(Paragraph("SCRAPED WEBSITE SPECIFICATIONS", styles["badge_web"]))
        elems.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#2563EB"), spaceAfter=4))

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

        attrs = {}
        if product.ai_analysis and hasattr(product.ai_analysis, "category_specific_info"):
            attrs = product.ai_analysis.category_specific_info or {}

        def _attr(*keys: str) -> str:
            for key in keys:
                val = attrs.get(key, "")
                if _has(val): return _clean(val)
            return ""

        price_str = _clean(product.price) if _has(product.price) else "Price not listed"
        comp_str = _attr("Composition", "composition") or (_clean(product.composition) if _has(product.composition) else "") or "—"
        mat_str = _attr("Material", "material") or (_clean(product.material_type) if _has(product.material_type) else "") or "—"
        fit_str = _attr("Fit", "fit") or (_clean(product.fit) if _has(product.fit) else "") or "—"
        
        pattern_str = "—"
        if product.ai_analysis and hasattr(product.ai_analysis, "design_pattern"):
            if _has(product.ai_analysis.design_pattern) and product.ai_analysis.design_pattern != "N/A":
                pattern_str = _clean(product.ai_analysis.design_pattern)

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

        fields = []
        if price_str and price_str not in ("—", "Price not listed"): fields.append(("Price", f"<b>{price_str}</b>"))
        if pattern_str != "—": fields.append(("Design Pattern", pattern_str))
        if comp_str != "—": fields.append(("Composition", comp_str))
        if mat_str != "—": fields.append(("Material", mat_str))
        if fit_str != "—": fields.append(("Garment Fit", fit_str))
        if details_str != "—": fields.append(("Attributes", details_str))
            
        if len(fields) % 2 != 0: fields.append(("", ""))

        specs_table_data = []
        for i in range(0, len(fields), 2):
            row = []
            l1, v1 = fields[i]
            row.extend([Paragraph(l1, styles["spec_label"]), Paragraph(v1, styles["spec_val"])] if l1 else ["", ""])
            l2, v2 = fields[i+1]
            row.extend([Paragraph(l2, styles["spec_label"]), Paragraph(v2, styles["spec_val"])] if l2 else ["", ""])
            specs_table_data.append(row)
            
        if not specs_table_data: specs_table_data = [["", "", "", ""]]
        specs_tbl = Table(specs_table_data, colWidths=[0.85 * inch, 1.3 * inch, 0.75 * inch, 1.4 * inch])
        specs_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 3),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        elems.append(specs_tbl)

        elems.append(Spacer(1, 6))
        
        ai = product.ai_analysis
        confidence_str = f"  (Confidence: {ai.confidence_score})" if ai and hasattr(ai, "confidence_score") and _has(ai.confidence_score) else ""
        elems.append(Paragraph(f"VISUAL TREND ANALYSIS{confidence_str}", styles["badge_ai"]))
        elems.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#0D9488"), spaceAfter=4))
        
        bullets = [b for b in (ai.bullet_summary if ai else []) if b and b.strip() and b.strip() not in ("", '""')]
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
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#86EFAC")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            elems.append(ai_box)
        else:
            elems.append(Paragraph("<i>No visual attributes extracted.</i>", styles["web_desc"]))
            
        return elems

    def generate_category_report(self, retailer_dict: Dict[str, List[Product]], category_name: str) -> Path:
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_name = f"Fashion_Trend_Report_{category_name}_{date_str}.pdf"
        target_path = self.config.output_path.parent / file_name

        doc = RetailerDocTemplate(
            str(target_path),
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=54,
            bottomMargin=40,
            category_name=category_name
        )
        
        frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
        template = PageTemplate(id='RetailerTemplate', frames=frame, onPage=draw_dynamic_footer)
        doc.addPageTemplates([template])

        styles = self._build_styles()
        story = []

        # ── COVER PAGE ─────────────────────────────────────────────────────────
        story.append(Spacer(1, 2.5 * inch))
        story.append(Paragraph("FASHION TREND MONITOR", styles["title"]))
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph(f"Analysis Report - {category_name.upper()}", styles["subtitle"]))
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph(f"Generated on {date_str}", styles["subtitle"]))
        story.append(PageBreak())

        # ── TABLE OF CONTENTS ──────────────────────────────────────────────────
        story.append(SetRetailerAction("Table of Contents"))
        story.append(Paragraph("Table of Contents", styles["toc_header"]))
        toc = TableOfContents()
        toc.levelStyles = [
            ParagraphStyle(fontName=self._f(bold=True), fontSize=12, name='TOCHeading1', leftIndent=20, firstLineIndent=-20, spaceBefore=5, leading=16),
        ]
        story.append(toc)
        story.append(PageBreak())

        # ── RETAILER SECTIONS ──────────────────────────────────────────────────
        for retailer_name, products in retailer_dict.items():
            if not products:
                continue

            story.append(SetRetailerAction(retailer_name))
            
            # Create TOC entry header
            header_para = Paragraph(retailer_name, styles["retailer_header"])
            header_para.toc_level = 0
            story.append(header_para)

            for product in products:
                item_elems = []
                
                name_clean = _clean(product.name) if product.name else "Untitled Product"
                item_elems.append(Paragraph(name_clean, styles["item_title"]))
                item_elems.append(Spacer(1, 2))

                price_raw = product.price if _has(product.price) else None
                price_meta = _clean(price_raw) if price_raw else "Price not available"
                link = f"<a href='{product.product_url}' color='#2563EB'><u>View Online</u></a>"
                item_elems.append(Paragraph(f"{price_meta}  •  Art. No: {product.art_no}  •  {link}", styles["item_meta"]))
                item_elems.append(Spacer(1, 6))

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

                right_elems = self._build_right_column(product, styles)
                right_col = Table([[el] for el in right_elems], colWidths=[4.4 * inch])
                right_col.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]))

                card = Table([[photo, right_col]], colWidths=[2.6 * inch, 4.4 * inch])
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

            story.append(PageBreak())

        # Build requires multiple passes for Table of Contents
        doc.multiBuild(story)
        logger.info(f"PDF for '{category_name}' saved to {target_path}")
        return target_path

    def generate_all_reports(self, master_product_dict: Dict[str, Dict[str, List[Product]]]) -> Dict[str, Path]:
        """Iterate over master dictionary and generate one PDF per top-level category (e.g. Men, Women)."""
        report_paths: Dict[str, Path] = {}
        for cat_name, retailer_dict in master_product_dict.items():
            # Only generate report if there are actually products in this category
            has_products = any(len(products) > 0 for products in retailer_dict.values())
            if has_products:
                report_paths[cat_name] = self.generate_category_report(retailer_dict, cat_name)
        return report_paths
