"""PDF report generation for Fashion Trend Monitor.

This module deliberately owns presentation only.  Its public API is unchanged:
``PDFReporter.generate_category_report`` and ``generate_all_reports`` still
accept the same product data produced by the existing pipeline.
"""

from __future__ import annotations

import html
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import IndexingFlowable

try:
    from svglib.svglib import svg2rlg
except ImportError:  # The report still works when optional SVG support is absent.
    svg2rlg = None

from src.config import Config
from src.models import Product

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ASSETS_DIR = _PROJECT_ROOT / "assets" / "pdf"
_FONTS_DIR = _ASSETS_DIR / "fonts"
_ICONS_DIR = _ASSETS_DIR / "icons"


class Theme:
    """The small, shared Material-inspired design system for the report."""

    primary = colors.HexColor("#121212")
    surface = colors.white
    surface_variant = colors.HexColor("#F7F8F7")
    surface_green = colors.HexColor("#F1F8F3")
    surface_blue = colors.HexColor("#F2F6FC")
    surface_purple = colors.HexColor("#F7F3FB")
    text_primary = colors.HexColor("#1F1F1F")
    text_secondary = colors.HexColor("#5F6368")
    text_muted = colors.HexColor("#80868B")
    border = colors.HexColor("#DADCE0")
    green = colors.HexColor("#137333")
    link = colors.HexColor("#4338CA")

    font_regular = "Poppins"
    font_medium = "Poppins-Medium"
    font_semibold = "Poppins-SemiBold"
    font_bold = "Poppins-Bold"

    page_margin = 40
    header_height = 48
    footer_height = 42
    space_1 = 6
    space_2 = 10
    space_3 = 16
    space_4 = 24
    card_padding = 14
    radius = 8


def _register_fonts() -> None:
    try:
        pdfmetrics.registerFont(
            TTFont(Theme.font_regular, str(_FONTS_DIR / "Poppins-Regular.ttf"))
        )
        pdfmetrics.registerFont(
            TTFont(Theme.font_medium, str(_FONTS_DIR / "Poppins-Medium.ttf"))
        )
        pdfmetrics.registerFont(
            TTFont(Theme.font_semibold, str(_FONTS_DIR / "Poppins-SemiBold.ttf"))
        )
        pdfmetrics.registerFont(
            TTFont(Theme.font_bold, str(_FONTS_DIR / "Poppins-Bold.ttf"))
        )
        pdfmetrics.registerFontFamily(
            Theme.font_regular,
            normal=Theme.font_regular,
            bold=Theme.font_bold,
            italic=Theme.font_medium,
        )
    except Exception as exc:
        logger.warning("Could not register local Poppins fonts (%s).", exc)


def _has(value: Any) -> bool:
    return bool(
        value
        and str(value).strip()
        and str(value).strip().upper() not in {"N/A", "NONE", "NULL"}
    )


def _plain(value: Any) -> str:
    """Decode input once for canvas text and data comparisons."""
    return html.unescape(str(value or "")).strip()


def _text(value: Any) -> str:
    """Produce safe ReportLab Paragraph markup without double-escaping entities."""
    return html.escape(_plain(value), quote=True)


def _rich_ai_text(value: Any) -> str:
    escaped = _text(value)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    return re.sub(r"_(.+?)_", r"<i>\1</i>", escaped)


def _fit_image(path: Path, max_width: float, max_height: float) -> Optional[Image]:
    """Return an image constrained by a box while retaining its original aspect ratio."""
    try:
        with PILImage.open(path) as source:
            width, height = source.size
        if not width or not height:
            return None
        scale = min(max_width / width, max_height / height)
        image = Image(
            str(path), width=max(width * scale, 1), height=max(height * scale, 1)
        )
        return image
    except Exception as exc:
        logger.warning("Could not load product image %s: %s", path, exc)
        return None


def _svg_icon(name: str, size: float = 13) -> Flowable:
    if not svg2rlg:
        return Spacer(size, size)
    path = _ICONS_DIR / f"{name}.svg"
    if not path.exists():
        return Spacer(size, size)
    try:
        drawing = svg2rlg(str(path))
        if drawing and drawing.width and drawing.height:
            drawing.scale(size / drawing.width, size / drawing.height)
            drawing.width = size
            drawing.height = size
            return drawing
    except Exception as exc:
        logger.debug("Could not load SVG icon %s: %s", name, exc)
    return Spacer(size, size)


class RetailerMarker(Flowable):
    """A zero-height marker consumed by the document's normal afterFlowable hook."""

    def __init__(self, key: str, name: str) -> None:
        super().__init__()
        self.key = key
        self.name = _plain(name)

    def wrap(
        self, available_width: float, available_height: float
    ) -> Tuple[float, float]:
        return 0, 0

    def draw(self) -> None:
        pass


class PageCountMarker(Flowable):
    def wrap(
        self, available_width: float, available_height: float
    ) -> Tuple[float, float]:
        return 0, 0

    def draw(self) -> None:
        pass


class PaginationIndex(IndexingFlowable):
    """A standard multiBuild index which stabilises TOC entries and page totals."""

    def __init__(self) -> None:
        super().__init__()
        self._entries: List[Tuple[str, str, int]] = []
        self._last_entries: List[Tuple[str, str, int]] = []
        self._total_pages = 0
        self._last_total_pages = 0

    @property
    def entries(self) -> List[Tuple[str, str, int]]:
        return list(self._last_entries)

    @property
    def total_pages(self) -> int:
        return self._last_total_pages or self._total_pages

    def beforeBuild(self) -> None:
        self._last_entries = list(self._entries)
        self._last_total_pages = self._total_pages
        self._entries = []
        self._total_pages = 0

    def notify(self, kind: str, payload: Any) -> None:
        if kind == "RetailerSection":
            entry = tuple(payload)
            if entry not in self._entries:
                self._entries.append(entry)  # type: ignore[arg-type]
        elif kind == "ReportPageCount":
            self._total_pages = int(payload)

    def isSatisfied(self) -> bool:
        return (
            self._entries == self._last_entries
            and self._total_pages == self._last_total_pages
        )

    def wrap(
        self, available_width: float, available_height: float
    ) -> Tuple[float, float]:
        return 0, 0

    def draw(self) -> None:
        pass


class ReportDocument(BaseDocTemplate):
    def __init__(
        self, *args: Any, category_name: str, report_date: datetime, **kwargs: Any
    ) -> None:
        self.category_name = _plain(category_name)
        self.report_date = report_date
        self.current_retailer = "Report index"
        self.pagination: Optional[PaginationIndex] = None
        super().__init__(*args, **kwargs)

    def afterFlowable(self, flowable: Flowable) -> None:
        if isinstance(flowable, RetailerMarker):
            self.current_retailer = flowable.name
            self.notify("RetailerSection", (flowable.key, flowable.name, self.page))
        elif isinstance(flowable, PageCountMarker):
            self.notify("ReportPageCount", self.page)


def _cover_background(canvas: Any, doc: ReportDocument) -> None:
    canvas.saveState()
    background = _ASSETS_DIR / "backgrounds" / "cover_bg.png"
    if background.exists():
        canvas.drawImage(
            str(background), 0, 0, width=letter[0], height=letter[1], mask="auto"
        )
    canvas.restoreState()


def _content_chrome(canvas: Any, doc: ReportDocument) -> None:
    """Draw after flowables, so the retailer marker applies to its first page too."""
    canvas.saveState()
    page_width, page_height = letter
    left = doc.leftMargin
    # A small optical inset keeps right-aligned dates/page numbers inside the
    # visible trim area in PDF viewers that crop very close to the page edge.
    right = page_width - doc.rightMargin - 8
    retailer = _plain(doc.current_retailer or "Fashion Trend Monitor")
    date = doc.report_date.strftime("%d %B %Y").upper()
    total = doc.pagination.total_pages if doc.pagination else doc.page
    total = max(total, doc.page)

    canvas.setStrokeColor(Theme.border)
    canvas.setLineWidth(0.5)
    canvas.line(
        left,
        page_height - Theme.header_height,
        right,
        page_height - Theme.header_height,
    )
    canvas.line(left, Theme.footer_height, right, Theme.footer_height)

    canvas.setFillColor(Theme.green)
    canvas.setFont(Theme.font_bold, 8)
    canvas.drawString(left, page_height - 30, retailer.upper())
    canvas.setFillColor(Theme.text_secondary)
    canvas.setFont(Theme.font_medium, 8)
    canvas.drawString(
        left + pdfmetrics.stringWidth(retailer.upper(), Theme.font_bold, 8) + 9,
        page_height - 30,
        f"•  {doc.category_name} Collection",
    )
    canvas.setFont(Theme.font_semibold, 8)
    canvas.drawRightString(right, page_height - 30, date)

    canvas.setFont(Theme.font_medium, 8)
    canvas.drawString(left, 25, f"{retailer} • {doc.category_name} Collection")
    canvas.setFont(Theme.font_semibold, 8)
    canvas.setFillColor(Theme.text_primary)
    canvas.drawRightString(right, 25, f"Page {doc.page} of {total}")
    canvas.restoreState()


class RetailerChip(Flowable):
    """A width-aware, data-driven retailer card for the cover."""

    def __init__(self, name: str, logo_path: Optional[Path], width: float) -> None:
        super().__init__()
        self.name = _plain(name)
        self.logo_path = logo_path
        self.width = width
        self.height = 44

    def draw(self) -> None:
        canv = self.canv
        canv.saveState()
        canv.setFillColor(Theme.surface)
        canv.setStrokeColor(Theme.border)
        canv.roundRect(0, 0, self.width, self.height, Theme.radius, fill=1, stroke=1)
        x = Theme.card_padding
        if self.logo_path and self.logo_path.exists():
            try:
                with PILImage.open(self.logo_path) as source:
                    raw_w, raw_h = source.size
                scale = min(25 / raw_w, 25 / raw_h)
                logo_w, logo_h = raw_w * scale, raw_h * scale
                canv.drawImage(
                    str(self.logo_path),
                    x,
                    (self.height - logo_h) / 2,
                    logo_w,
                    logo_h,
                    mask="auto",
                )
                x += logo_w + Theme.space_2
            except Exception as exc:
                logger.debug("Could not draw logo %s: %s", self.logo_path, exc)
        label = self.name.upper()
        canv.setFillColor(Theme.text_primary)
        canv.setFont(Theme.font_semibold, 8.5)
        max_text = max(self.width - x - Theme.card_padding, 10)
        while (
            label and pdfmetrics.stringWidth(label, Theme.font_semibold, 8.5) > max_text
        ):
            label = label[:-2].rstrip() + "…"
        canv.drawString(x, 17, label)
        canv.restoreState()


class DynamicRetailerTOC(Flowable):
    """Build TOC cards from the page map resolved by ReportLab ``multiBuild``."""

    def __init__(
        self,
        reporter: "PDFReporter",
        retailer_dict: Dict[str, List[Product]],
        category: str,
        pagination: PaginationIndex,
        width: float,
    ) -> None:
        super().__init__()
        self.reporter = reporter
        self.retailer_dict = retailer_dict
        self.category = category
        self.pagination = pagination
        self.width = width
        self.table: Optional[Table] = None

    def _build_table(self) -> Table:
        known_pages = {key: page for key, _name, page in self.pagination.entries}
        rows: List[List[Any]] = []
        total_products = 0
        active = [
            (key, products) for key, products in self.retailer_dict.items() if products
        ]
        for number, (key, products) in enumerate(active, 1):
            total_products += len(products)
            rows.append(
                [
                    self.reporter._toc_card(
                        number,
                        key,
                        self.category,
                        len(products),
                        known_pages.get(key, 0),
                        self.width,
                    )
                ]
            )
            rows.append([Spacer(1, Theme.space_2)])
        summary = Table(
            [
                [
                    Paragraph(
                        f"<b>{len(active)}</b><br/><font size='8'>RETAILERS</font>",
                        ParagraphStyle(
                            "SummaryA",
                            fontName=Theme.font_semibold,
                            fontSize=16,
                            leading=18,
                            textColor=Theme.text_primary,
                        ),
                    ),
                    Paragraph(
                        f"<b>{total_products}</b><br/><font size='8'>NEW PRODUCTS</font>",
                        ParagraphStyle(
                            "SummaryB",
                            fontName=Theme.font_semibold,
                            fontSize=16,
                            leading=18,
                            alignment=TA_RIGHT,
                            textColor=Theme.green,
                        ),
                    ),
                ]
            ],
            colWidths=[self.width / 2, self.width / 2],
            hAlign="LEFT",
        )
        summary.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), Theme.surface_variant),
                    ("BOX", (0, 0), (-1, -1), 0.8, Theme.border),
                    ("LEFTPADDING", (0, 0), (-1, -1), Theme.card_padding),
                    ("RIGHTPADDING", (0, 0), (-1, -1), Theme.card_padding),
                    ("TOPPADDING", (0, 0), (-1, -1), Theme.space_2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), Theme.space_2),
                ]
            )
        )
        rows.append([summary])
        table = Table(rows, colWidths=[self.width], hAlign="LEFT", splitByRow=1)
        table.setStyle(
            TableStyle(
                [
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return table

    def wrap(
        self, available_width: float, available_height: float
    ) -> Tuple[float, float]:
        self.table = self._build_table()
        return self.table.wrap(available_width, available_height)

    def split(self, available_width: float, available_height: float) -> List[Flowable]:
        return self.table.split(available_width, available_height) if self.table else []

    def draw(self) -> None:
        if self.table:
            self.table.drawOn(self.canv, 0, 0)


class PDFReporter:
    def __init__(self, config: Config) -> None:
        self.config = config
        _register_fonts()
        self.styles = self._build_styles()

    def _build_styles(self) -> Dict[str, ParagraphStyle]:
        return {
            "eyebrow": ParagraphStyle(
                "Eyebrow",
                fontName=Theme.font_bold,
                fontSize=8,
                leading=10,
                textColor=Theme.green,
            ),
            "cover_title": ParagraphStyle(
                "CoverTitle",
                fontName=Theme.font_bold,
                fontSize=43,
                leading=47,
                textColor=Theme.text_primary,
            ),
            "cover_subtitle": ParagraphStyle(
                "CoverSubtitle",
                fontName=Theme.font_medium,
                fontSize=14,
                leading=20,
                textColor=Theme.text_secondary,
            ),
            "toc_title": ParagraphStyle(
                "TocTitle",
                fontName=Theme.font_bold,
                fontSize=30,
                leading=36,
                textColor=Theme.text_primary,
            ),
            "section_title": ParagraphStyle(
                "SectionTitle",
                fontName=Theme.font_bold,
                fontSize=24,
                leading=29,
                textColor=Theme.text_primary,
            ),
            "section_subtitle": ParagraphStyle(
                "SectionSubtitle",
                fontName=Theme.font_regular,
                fontSize=10,
                leading=14,
                textColor=Theme.text_secondary,
            ),
            "product_line": ParagraphStyle(
                "ProductLine",
                fontName=Theme.font_semibold,
                fontSize=15,
                leading=20,
                textColor=Theme.text_primary,
            ),
            "meta": ParagraphStyle(
                "Meta",
                fontName=Theme.font_medium,
                fontSize=9,
                leading=13,
                textColor=Theme.text_secondary,
            ),
            "card_label": ParagraphStyle(
                "CardLabel",
                fontName=Theme.font_bold,
                fontSize=8,
                leading=11,
                textColor=Theme.text_primary,
            ),
            "body": ParagraphStyle(
                "Body",
                fontName=Theme.font_regular,
                fontSize=9,
                leading=14,
                textColor=Theme.text_secondary,
            ),
            "attribute": ParagraphStyle(
                "Attribute",
                fontName=Theme.font_regular,
                fontSize=9,
                leading=13,
                textColor=Theme.text_secondary,
            ),
            "toc_name": ParagraphStyle(
                "TocName",
                fontName=Theme.font_semibold,
                fontSize=14,
                leading=18,
                textColor=Theme.text_primary,
            ),
        }

    def _logo_path(self, retailer_name: str) -> Optional[Path]:
        wanted = _plain(retailer_name)
        for key, settings in (self.config.retailers or {}).items():
            if _plain(settings.get("name", key)) != wanted:
                continue
            raw_path = settings.get("logo")
            if not raw_path:
                return None
            path = Path(raw_path)
            return path if path.is_absolute() else _PROJECT_ROOT / path
        return None

    def _card(
        self,
        rows: Sequence[Sequence[Any]],
        width: float,
        *,
        background: colors.Color = Theme.surface,
        border: colors.Color = Theme.border,
        padding: float = Theme.card_padding,
    ) -> Table:
        card = Table(list(rows), colWidths=[width], hAlign="LEFT", splitByRow=1)
        card.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), background),
                    ("BOX", (0, 0), (-1, -1), 0.8, border),
                    ("LEFTPADDING", (0, 0), (-1, -1), padding),
                    ("RIGHTPADDING", (0, 0), (-1, -1), padding),
                    # Padding belongs around a card, not around every row inside it.
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, 0), padding),
                    ("BOTTOMPADDING", (0, -1), (-1, -1), padding),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        return card

    def _cover_story(
        self,
        retailer_dict: Dict[str, List[Product]],
        category: str,
        content_width: float,
        date: datetime,
    ) -> List[Flowable]:
        retail_names = [name for name, products in retailer_dict.items() if products]
        date_display = date.strftime("%d %B %Y").upper()
        detail_width = content_width * 0.62
        details = Table(
            [
                [
                    _svg_icon("calendar", 22),
                    Paragraph(
                        f"<b>REPORT DATE</b><br/><font name='{Theme.font_semibold}'>{_text(date_display)}</font>",
                        self.styles["meta"],
                    ),
                ],
                [
                    _svg_icon("category", 22),
                    Paragraph(
                        f"<b>CATEGORY</b><br/><font name='{Theme.font_semibold}'>{_text(category)} Collection</font>",
                        self.styles["meta"],
                    ),
                ],
            ],
            colWidths=[30, detail_width - 30],
            hAlign="LEFT",
        )
        details.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), Theme.space_2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), Theme.space_2),
                ]
            )
        )
        story: List[Flowable] = [
            Spacer(1, 74),
            Paragraph("DAILY REPORT", self.styles["eyebrow"]),
            Spacer(1, Theme.space_3),
            Paragraph("Fashion<br/>Trend<br/>Monitor", self.styles["cover_title"]),
            Spacer(1, Theme.space_2),
            Paragraph(
                "AI-Powered Retail Trend Analysis", self.styles["cover_subtitle"]
            ),
            Spacer(1, Theme.space_4),
            details,
            Spacer(1, Theme.space_4),
            Paragraph("RETAILERS INCLUDED", self.styles["eyebrow"]),
            Spacer(1, Theme.space_2),
        ]
        if retail_names:
            gap = Theme.space_2
            # A minimum chip width preserves readable labels; columns remain derived from available space.
            columns = max(1, min(3, int((content_width + gap) // 150)))
            chip_width = (content_width - gap * (columns - 1)) / columns
            chips = [
                RetailerChip(name, self._logo_path(name), chip_width)
                for name in retail_names
            ]
            grid: List[List[Any]] = []
            for start in range(0, len(chips), columns):
                row: List[Any] = list(chips[start : start + columns])
                row.extend([Spacer(chip_width, 44)] * (columns - len(row)))
                grid.append(row)
            chip_table = Table(grid, colWidths=[chip_width] * columns, hAlign="LEFT")
            chip_table.setStyle(
                TableStyle(
                    [
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), gap / 2),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), gap),
                    ]
                )
            )
            story.append(chip_table)
        return story

    def _toc_card(
        self,
        index: int,
        name: str,
        category: str,
        product_count: int,
        page: int,
        width: float,
    ) -> Table:
        accent_width = min(max(width * 0.12, 44), 66)
        body_width = width - accent_width
        page_width = min(max(body_width * 0.14, 56), 72)
        text_width = body_width - page_width
        number = Paragraph(
            f"{index:02d}",
            ParagraphStyle(
                "TocNo",
                fontName=Theme.font_bold,
                fontSize=22,
                alignment=TA_CENTER,
                textColor=Theme.green,
            ),
        )
        details = Paragraph(
            f"<b>{_text(name)}</b><br/><font size='10' color='#5F6368'>{_text(category)} Collection<br/><b>{product_count}</b> new products</font>",
            ParagraphStyle(
                "TocDetails",
                fontName=Theme.font_semibold,
                fontSize=14,
                leading=18,
                textColor=Theme.text_primary,
            ),
        )
        page_cell = Paragraph(
            f"<font size='7' color='#80868B'><b>PAGE</b></font><br/><font size='18' color='#4338CA'><b>{page:02d}</b></font>",
            ParagraphStyle(
                "TocPage",
                fontName=Theme.font_bold,
                fontSize=18,
                leading=19,
                alignment=TA_RIGHT,
            ),
        )
        row = Table(
            [[number, details, page_cell]],
            colWidths=[accent_width, text_width, page_width],
            hAlign="LEFT",
        )
        row.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (0, 0),
                        (
                            Theme.surface_green
                            if index % 3 == 1
                            else (
                                Theme.surface_blue
                                if index % 3 == 2
                                else Theme.surface_purple
                            )
                        ),
                    ),
                    ("BACKGROUND", (1, 0), (-1, -1), Theme.surface),
                    ("BOX", (0, 0), (-1, -1), 0.8, Theme.border),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), Theme.card_padding),
                    ("RIGHTPADDING", (0, 0), (-1, -1), Theme.card_padding),
                    ("TOPPADDING", (0, 0), (-1, -1), Theme.space_3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), Theme.space_3),
                ]
            )
        )
        return row

    def _toc_story(
        self,
        retailer_dict: Dict[str, List[Product]],
        category: str,
        pagination: PaginationIndex,
        width: float,
    ) -> List[Flowable]:
        return [
            RetailerMarker("__toc__", "Report index"),
            Paragraph("Table of Contents", self.styles["toc_title"]),
            Spacer(1, Theme.space_2),
            DynamicRetailerTOC(self, retailer_dict, category, pagination, width),
        ]

    def _attribute_rows(self, product: Product) -> Iterable[Tuple[str, str, str]]:
        analysis = product.ai_analysis
        attrs = getattr(analysis, "category_specific_info", {}) or {}

        def choose(*keys: str) -> str:
            for key in keys:
                if _has(attrs.get(key)):
                    return _plain(attrs[key])
            return "—"

        yield "pattern", "Design pattern", (
            _plain(getattr(analysis, "design_pattern", ""))
            if _has(getattr(analysis, "design_pattern", ""))
            else "—"
        )
        yield "composition", "Composition", (
            choose("Composition", "composition")
            if choose("Composition", "composition") != "—"
            else (_plain(product.composition) if _has(product.composition) else "—")
        )
        yield "fit", "Garment fit", (
            choose("Fit", "fit")
            if choose("Fit", "fit") != "—"
            else (_plain(product.fit) if _has(product.fit) else "—")
        )
        yield "material", "Material", (
            choose("Material", "material")
            if choose("Material", "material") != "—"
            else (_plain(product.material_type) if _has(product.material_type) else "—")
        )
        excluded = {
            "composition",
            "material",
            "material type",
            "fit",
            "garment fit",
            "design pattern",
        }
        additional = [
            f"• {_plain(k).title()}: {_plain(v)}"
            for k, v in attrs.items()
            if _has(v) and _plain(k).lower() not in excluded
        ]
        if not additional:
            additional = [
                f"• {_plain(k).title()}: {_plain(v)}"
                for k, v in (product.fit_details or {}).items()
                if _has(v)
            ]
        yield "attributes", "Attributes", (
            "<br/>".join(_text(item) for item in additional) if additional else "—"
        )

    def _product_story(
        self, product: Product, serial: int, width: float
    ) -> List[Flowable]:
        """A compact product block: media and core details share one visual row.

        The row is deliberately sized from the page frame, not fixed document
        coordinates.  Long analysis remains a separate flowable below it and
        may continue naturally on the next page without splitting the product
        identity, image, or specification grid.
        """
        name = _text(product.name or "Untitled product")
        price = _text(product.price) if _has(product.price) else "Price N/A"
        link = _text(product.product_url)
        header = [
            Paragraph(
                f"<font color='#137333'><b>{serial:02d}.</b></font>&nbsp;&nbsp;{name}&nbsp;&nbsp;"
                f"<font color='#BDBDBD'>•</font>&nbsp;&nbsp;<font color='#1F1F1F'><b>{price}</b></font>",
                self.styles["product_line"],
            ),
            Paragraph(
                f"Art. No: {_text(product.art_no or 'N/A')}&nbsp;&nbsp;&nbsp;&nbsp;<link href='{link}' color='#4338CA'>View online</link>",
                self.styles["meta"],
            ),
            Spacer(1, Theme.space_2),
        ]
        column_gap = Theme.space_3
        media_width = width * 0.38
        media_column_width = media_width + column_gap
        details_width = width - media_column_width
        media_max_height = min(media_width * 1.28, 3.15 * inch)
        photo = (
            _fit_image(
                Path(product.screenshot_path),
                media_width - (2 * Theme.card_padding),
                media_max_height,
            )
            if product.screenshot_path
            else None
        )
        if photo:
            media = self._card(
                [[photo]],
                media_width,
                background=Theme.surface_variant,
                padding=Theme.card_padding,
            )
        else:
            media = self._card(
                [[Paragraph("Product image unavailable", self.styles["body"])]],
                media_width,
                background=Theme.surface_variant,
            )
        description = _text((product.description or "No description available.")[:360])
        description_card = self._card(
            [
                [
                    Paragraph(
                        "SCRAPED WEBSITE SPECIFICATIONS", self.styles["card_label"]
                    )
                ],
                [Spacer(1, 3)],
                [Paragraph(f"“{description}”", self.styles["body"])],
            ],
            details_width,
            padding=Theme.space_2,
        )
        attr_rows: List[List[Any]] = []
        label_width = details_width * 0.42
        value_width = details_width - label_width
        for icon, label, value in self._attribute_rows(product):
            label_content = Table(
                [
                    [
                        _svg_icon(icon, 14),
                        Paragraph(_text(label).upper(), self.styles["card_label"]),
                    ]
                ],
                colWidths=[20, label_width - 20],
            )
            label_content.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ]
                )
            )
            # Additional attributes are assembled from individually escaped items
            # separated by the one safe ReportLab tag below.
            formatted_value = value if "<br/>" in value else _text(value)
            attr_rows.append(
                [label_content, Paragraph(formatted_value, self.styles["attribute"])]
            )
        attributes = Table(
            attr_rows, colWidths=[label_width, value_width], hAlign="LEFT", splitByRow=1
        )
        attributes.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), Theme.surface_variant),
                    ("BOX", (0, 0), (-1, -1), 0.8, Theme.border),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, Theme.border),
                    ("LEFTPADDING", (0, 0), (-1, -1), Theme.space_2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), Theme.space_2),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        details = Table(
            [[description_card], [Spacer(1, Theme.space_2)], [attributes]],
            colWidths=[details_width],
            hAlign="LEFT",
        )
        details.setStyle(
            TableStyle(
                [
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        product_grid = Table(
            [[media, details]],
            colWidths=[media_column_width, details_width],
            hAlign="LEFT",
        )
        product_grid.setStyle(
            TableStyle(
                [
                    ("LEFTPADDING", (0, 0), (0, 0), 0),
                    ("RIGHTPADDING", (0, 0), (0, 0), column_gap),
                    ("LEFTPADDING", (1, 0), (1, 0), 0),
                    ("RIGHTPADDING", (1, 0), (1, 0), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        analysis = product.ai_analysis
        bullets = [
            item
            for item in (getattr(analysis, "bullet_summary", []) or [])
            if _has(item)
        ][:3]
        confidence = (
            _text(getattr(analysis, "confidence_score", ""))
            if _has(getattr(analysis, "confidence_score", ""))
            else ""
        )
        analysis_rows: List[List[Any]] = [
            [
                Paragraph(
                    "VISUAL TREND ANALYSIS",
                    ParagraphStyle(
                        "AnalysisLabel",
                        parent=self.styles["card_label"],
                        textColor=Theme.green,
                    ),
                )
            ]
        ]
        if confidence:
            analysis_rows.append(
                [Paragraph(f"Confidence: {confidence}", self.styles["meta"])]
            )
        analysis_rows.append([Spacer(1, Theme.space_1)])
        analysis_rows.extend(
            [
                [Paragraph(f"• {_rich_ai_text(item)}", self.styles["body"])]
                for item in bullets
            ]
            or [[Paragraph("No visual attributes extracted.", self.styles["body"])]]
        )
        analysis_card = self._card(
            analysis_rows,
            width,
            background=Theme.surface_green,
            border=colors.HexColor("#C8E6C9"),
            padding=Theme.space_2,
        )
        # The product identity must never be stranded at the foot of a page.
        # The compact grid is bounded by the page frame, so it is safe to keep
        # this small unit together while leaving the analysis card free to flow.
        primary_product = KeepTogether(header + [product_grid])
        return [
            primary_product,
            Spacer(1, Theme.space_2),
            analysis_card,
            Spacer(1, Theme.space_3),
        ]

    def generate_category_report(
        self, retailer_dict: Dict[str, List[Product]], category_name: str
    ) -> Path:
        date = datetime.now()
        destination = (
            self.config.output_path.parent
            / f"Fashion_Trend_Report_{category_name}_{date:%Y-%m-%d}.pdf"
        )
        doc = ReportDocument(
            str(destination),
            pagesize=letter,
            leftMargin=Theme.page_margin,
            rightMargin=Theme.page_margin,
            topMargin=Theme.header_height + Theme.space_3,
            bottomMargin=Theme.footer_height + Theme.space_3,
            category_name=category_name,
            report_date=date,
        )
        frame = Frame(
            doc.leftMargin,
            doc.bottomMargin,
            doc.width,
            doc.height,
            id="report",
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )
        doc.addPageTemplates(
            [
                PageTemplate(id="cover", frames=[frame], onPage=_cover_background),
                PageTemplate(id="content", frames=[frame], onPageEnd=_content_chrome),
            ]
        )
        pagination = PaginationIndex()
        doc.pagination = pagination
        story: List[Flowable] = [pagination]
        story.extend(self._cover_story(retailer_dict, category_name, doc.width, date))
        story.extend([NextPageTemplate("content"), PageBreak()])
        story.extend(
            self._toc_story(retailer_dict, category_name, pagination, doc.width)
        )
        story.append(PageBreak())
        is_first_retailer = True
        for retailer_key, products in retailer_dict.items():
            if not products:
                continue
            # Retailer sections are intentional navigation boundaries.  Product
            # cards within a retailer still flow naturally and may share pages.
            if not is_first_retailer:
                story.append(PageBreak())
            is_first_retailer = False
            retailer_name = _plain(retailer_key)
            story.extend(
                [
                    RetailerMarker(retailer_key, retailer_name),
                    Spacer(1, Theme.space_1),
                    Paragraph(_text(retailer_name), self.styles["section_title"]),
                    Paragraph(
                        f"{_text(category_name)} Collection • {len(products)} new products",
                        self.styles["section_subtitle"],
                    ),
                    Spacer(1, Theme.space_3),
                ]
            )
            for serial, product in enumerate(products, 1):
                story.extend(self._product_story(product, serial, doc.width))
        story.append(PageCountMarker())
        doc.multiBuild(story)
        logger.info("PDF for %s saved to %s", category_name, destination)
        return destination

    def generate_all_reports(
        self, master_product_dict: Dict[str, Dict[str, List[Product]]]
    ) -> Dict[str, Path]:
        return {
            category: self.generate_category_report(retailers, category)
            for category, retailers in master_product_dict.items()
            if any(retailers.values())
        }
