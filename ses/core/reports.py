"""
SES Enterprise Gateway — Corporate PDF Audit Report System
===========================================================

Production-grade PDF report generation for audit trails, compliance evidence,
usage analytics, and system health monitoring.

Requires: fpdf2 (pip install fpdf2)

Report types:
    - Evidence PDF   : Per-query audit trail with semantic search provenance
    - Usage PDF      : Business/billing analytics for a tenant
    - Compliance PDF : Multi-query compliance bundle with cross-reference index
    - Health PDF     : System status snapshot for IT/ops teams

Author : SES Enterprise Team
Version: 2.0.0
"""

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from fpdf import FPDF, XPos, YPos
except ImportError:
    FPDF = None
    XPos = None
    YPos = None

logger = logging.getLogger(__name__)

# ─── Design Tokens ────────────────────────────────────────────────────────────

COLOR_PRIMARY     = (26, 35, 126)    # #1a237e  – dark navy (headers)
COLOR_SECONDARY   = (40, 53, 147)    # #283593  – medium blue (section titles)
COLOR_ACCENT      = (66, 165, 245)   # #42a5f5  – accent blue (score bars)
COLOR_ROW_ALT     = (245, 245, 245)  # #f5f5f5  – alternating row background
COLOR_WHITE       = (255, 255, 255)
COLOR_BLACK       = (33, 33, 33)
COLOR_GRAY_TEXT   = (117, 117, 117)
COLOR_LIGHT_RULE  = (189, 189, 189)
COLOR_ERROR_RED   = (211, 47, 47)
COLOR_SUCCESS_GRN = (56, 142, 60)
COLOR_WARN_AMBER  = (255, 160, 0)
COLOR_WATERMARK   = (200, 200, 200)
COLOR_SCORE_BG    = (224, 224, 224)

MARGIN_LEFT   = 15
MARGIN_RIGHT  = 15
MARGIN_TOP    = 15
PAGE_WIDTH    = 210  # A4 mm

# Standard Windows TrueType font search paths (checked in order)
_TTF_CANDIDATES = [
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\calibri.ttf",
    r"C:\Windows\Fonts\tahoma.ttf",
    # Linux / macOS fallbacks
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]

_TTF_BOLD_MAP = {
    "segoeui.ttf":  "segoeuib.ttf",
    "arial.ttf":    "arialbd.ttf",
    "calibri.ttf":  "calibrib.ttf",
    "tahoma.ttf":   "tahomabd.ttf",
    "DejaVuSans.ttf": "DejaVuSans-Bold.ttf",
    "LiberationSans-Regular.ttf": "LiberationSans-Bold.ttf",
}

_TTF_ITALIC_MAP = {
    "segoeui.ttf":  "segoeuii.ttf",
    "arial.ttf":    "ariali.ttf",
    "calibri.ttf":  "calibrii.ttf",
    "tahoma.ttf":   "tahoma.ttf",           # Tahoma has no true italic
    "DejaVuSans.ttf": "DejaVuSans-Oblique.ttf",
    "LiberationSans-Regular.ttf": "LiberationSans-Italic.ttf",
}


def _detect_ttf_font() -> Optional[str]:
    """Return the first available TrueType font path, or ``None``."""
    for candidate in _TTF_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
    return None


def _sanitize_text(text: str) -> str:
    """
    Normalise text for safe PDF rendering.

    * Replaces smart quotes and dashes with ASCII equivalents.
    * Strips control characters that could corrupt the PDF stream.
    * Preserves standard newlines for ``multi_cell`` rendering.
    """
    if not text:
        return ""
    # Smart quotes / dashes → ASCII
    replacements = {
        "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "--",
        "\u2026": "...",
        "\u00a0": " ",  # non-breaking space
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    # Strip control chars except \n, \r, \t
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text


def _iso_now() -> str:
    """Return current UTC timestamp in ISO 8601 with timezone designator."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


# ─── Custom FPDF Subclass ────────────────────────────────────────────────────

class EnterpriseReportPDF(FPDF if FPDF is not None else object):
    """
    Custom FPDF subclass providing branded header, numbered footer,
    optional watermark, and Unicode-aware font management.
    """

    def __init__(
        self,
        title: str = "SES Enterprise Report",
        subtitle: Optional[str] = None,
        watermark: Optional[str] = None,
        classification: str = "INTERNAL",
        font_path: Optional[str] = None,
        orientation: str = "P",
    ):
        if FPDF is None:
            raise ImportError(
                "fpdf2 is required for PDF report generation. "
                "Install with: pip install fpdf2"
            )
        super().__init__(orientation=orientation, unit="mm", format="A4")

        self._report_title = title
        self._report_subtitle = subtitle
        self._watermark = watermark
        self._classification = classification
        self._font_path = font_path
        self._font_family = "Helvetica"  # fallback
        self._has_italic = True

        # Register Unicode font if a TTF file is provided
        if font_path and os.path.isfile(font_path):
            try:
                font_dir = os.path.dirname(font_path)
                font_base = os.path.basename(font_path)

                self.add_font("SESFont", "", fname=font_path)
                self._font_family = "SESFont"
                self._has_italic = False

                # Try to register bold variant
                bold_name = _TTF_BOLD_MAP.get(font_base)
                if bold_name:
                    bold_path = os.path.join(font_dir, bold_name)
                    if os.path.isfile(bold_path):
                        self.add_font("SESFont", "B", fname=bold_path)

                # Try to register italic variant
                italic_name = _TTF_ITALIC_MAP.get(font_base)
                if italic_name:
                    italic_path = os.path.join(font_dir, italic_name)
                    if os.path.isfile(italic_path):
                        self.add_font("SESFont", "I", fname=italic_path)
                        self._has_italic = True

                logger.debug("Registered Unicode font: %s", font_base)
            except Exception as exc:
                logger.warning("Failed to register TTF font %s: %s — falling back to Helvetica", font_path, exc)
                self._font_family = "Helvetica"
                self._has_italic = True

        self.set_auto_page_break(auto=True, margin=25)
        self.set_margins(MARGIN_LEFT, MARGIN_TOP, MARGIN_RIGHT)

    # ── Override: Page Header ──────────────────────────────────────────────

    def header(self):
        """Branded enterprise header drawn on every page."""
        # Navy banner
        self.set_fill_color(*COLOR_PRIMARY)
        self.rect(0, 0, PAGE_WIDTH, 22, "F")

        # Logo placeholder (small square)
        self.set_fill_color(*COLOR_WHITE)
        self.rect(MARGIN_LEFT, 4, 14, 14, "F")
        self.set_font(self._font_family, "B", 8)
        self.set_text_color(*COLOR_PRIMARY)
        self.set_xy(MARGIN_LEFT + 1.5, 8)
        self.cell(11, 5, "SES", align="C")

        # Title text
        self.set_text_color(*COLOR_WHITE)
        self.set_font(self._font_family, "B", 13)
        self.set_xy(MARGIN_LEFT + 18, 4)
        self.cell(0, 8, _sanitize_text(self._report_title), align="L")

        # Subtitle
        if self._report_subtitle:
            self.set_font(self._font_family, "", 8)
            self.set_xy(MARGIN_LEFT + 18, 12)
            self.cell(0, 6, _sanitize_text(self._report_subtitle), align="L")

        # Classification badge (right side)
        self.set_font(self._font_family, "B", 7)
        badge_text = self._classification.upper()
        badge_w = self.get_string_width(badge_text) + 6
        self.set_xy(PAGE_WIDTH - MARGIN_RIGHT - badge_w, 6)
        self.set_fill_color(*COLOR_WARN_AMBER)
        self.set_text_color(*COLOR_BLACK)
        self.cell(badge_w, 5, badge_text, border=0, fill=True, align="C")

        # Timestamp (right side, below badge)
        self.set_font(self._font_family, "", 6)
        self.set_text_color(200, 200, 220)
        self.set_xy(PAGE_WIDTH - MARGIN_RIGHT - 50, 13)
        self.cell(50, 4, _iso_now(), align="R")

        self.set_y(26)
        self.set_text_color(*COLOR_BLACK)

        # Watermark (drawn after header so it's behind body text visually)
        if self._watermark:
            self._render_watermark(self._watermark)

    # ── Override: Page Footer ──────────────────────────────────────────────

    def footer(self):
        """Footer with page numbers and classification."""
        self.set_y(-18)
        self.set_draw_color(*COLOR_LIGHT_RULE)
        self.line(MARGIN_LEFT, self.get_y(), PAGE_WIDTH - MARGIN_RIGHT, self.get_y())

        self.set_y(-15)
        self.set_font(self._font_family, "", 7)
        self.set_text_color(*COLOR_GRAY_TEXT)
        self.cell(0, 5, f"SES Enterprise Gateway  |  {self._classification}", align="L")

        # Page X of {nb}
        self.set_font(self._font_family, "", 7)
        self.cell(0, 5, f"Page {self.page_no()} of {{nb}}", align="R")

    # ── Watermark ──────────────────────────────────────────────────────────

    def _render_watermark(self, text: str):
        """Draw a diagonal, semi-transparent watermark across the page."""
        self.set_font(self._font_family, "B", 50)
        self.set_text_color(*COLOR_WATERMARK)
        with self.rotation(45, PAGE_WIDTH / 2, 148):
            tw = self.get_string_width(text)
            self.set_xy((PAGE_WIDTH - tw) / 2, 140)
            self.cell(tw, 20, text, align="C")
        # Reset text color
        self.set_text_color(*COLOR_BLACK)

    # ── Reusable Drawing Helpers ───────────────────────────────────────────

    def draw_section_title(self, title: str):
        """Render a medium-blue section heading with underline."""
        self.ln(4)
        self.set_font(self._font_family, "B", 12)
        self.set_text_color(*COLOR_SECONDARY)
        self.cell(0, 8, _sanitize_text(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*COLOR_SECONDARY)
        self.line(MARGIN_LEFT, self.get_y(), PAGE_WIDTH - MARGIN_RIGHT, self.get_y())
        self.ln(3)
        self.set_text_color(*COLOR_BLACK)

    def draw_horizontal_rule(self):
        """Light-gray horizontal rule."""
        self.set_draw_color(*COLOR_LIGHT_RULE)
        y = self.get_y()
        self.line(MARGIN_LEFT, y, PAGE_WIDTH - MARGIN_RIGHT, y)
        self.ln(3)

    def draw_kv_line(self, key: str, value: str):
        """Draw a bold-key / normal-value pair on one line."""
        self.set_font(self._font_family, "B", 9)
        self.cell(45, 6, _sanitize_text(key), align="L")
        self.set_font(self._font_family, "", 9)
        self.cell(0, 6, _sanitize_text(str(value)), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")

    def draw_score_bar(self, x: float, y: float, width: float, height: float, score: float):
        """
        Render a visual relevance bar.

        ``score`` should be in [0, 1].  The bar background is light gray;
        the filled portion uses the accent blue with an intensity that
        increases with the score value.
        """
        score = max(0.0, min(1.0, score))
        # Background track
        self.set_fill_color(*COLOR_SCORE_BG)
        self.rect(x, y, width, height, "F")
        # Filled portion
        fill_w = width * score
        if fill_w > 0:
            r = int(COLOR_ACCENT[0] * (0.5 + 0.5 * score))
            g = int(COLOR_ACCENT[1] * (0.5 + 0.5 * score))
            b = int(COLOR_ACCENT[2] * (0.5 + 0.5 * score))
            self.set_fill_color(min(r, 255), min(g, 255), min(b, 255))
            self.rect(x, y, fill_w, height, "F")
        # Percentage label
        self.set_font(self._font_family, "B", 6)
        self.set_text_color(*COLOR_WHITE)
        self.set_xy(x, y)
        self.cell(width, height, f"{score * 100:.0f}%", align="C")
        self.set_text_color(*COLOR_BLACK)

    def draw_body_text(self, text: str, size: int = 9):
        """Render a multi-cell paragraph of body text."""
        self.set_font(self._font_family, "", size)
        self.set_text_color(*COLOR_BLACK)
        self.multi_cell(0, 5, _sanitize_text(text))

    def draw_italic_block(self, text: str, indent: float = 10):
        """Render an indented, italic text block (for evidence snippets)."""
        self.set_x(MARGIN_LEFT + indent)
        style = "I" if self._has_italic else ""
        self.set_font(self._font_family, style, 8)
        self.set_text_color(*COLOR_GRAY_TEXT)
        available_w = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT - indent
        self.multi_cell(available_w, 4.5, _sanitize_text(text))
        self.set_text_color(*COLOR_BLACK)
        self.ln(2)

    def draw_metric_card(self, label: str, value: str, unit: str = ""):
        """Inline metric badge (used in summary rows)."""
        self.set_font(self._font_family, "B", 18)
        self.set_text_color(*COLOR_PRIMARY)
        val_text = _sanitize_text(f"{value}{unit}")
        self.cell(45, 12, val_text, align="C")
        self.set_font(self._font_family, "", 7)
        self.set_text_color(*COLOR_GRAY_TEXT)
        self.set_x(self.get_x() - 45)
        self.cell(45, 22, _sanitize_text(label), align="C")
        self.set_text_color(*COLOR_BLACK)


# ─── Report Service ──────────────────────────────────────────────────────────

class ReportService:
    """
    Enterprise report generator.

    Provides four PDF report methods covering audit evidence, usage analytics,
    multi-query compliance bundles, and system health snapshots.
    """

    def __init__(self, output_dir: str = "data/reports"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        # Detect best available TTF font once at init
        self._font_path: Optional[str] = _detect_ttf_font()
        if self._font_path:
            logger.info("PDF Unicode font detected: %s", self._font_path)
        else:
            logger.info("No TrueType font found — PDFs will use built-in Helvetica (ASCII only)")

    # ── helpers ────────────────────────────────────────────────────────────

    def _make_pdf(
        self,
        title: str,
        subtitle: Optional[str] = None,
        watermark: Optional[str] = None,
        classification: str = "INTERNAL",
    ) -> EnterpriseReportPDF:
        """Factory: create a pre-configured ``EnterpriseReportPDF`` instance."""
        if FPDF is None:
            raise ImportError(
                "fpdf2 is required for PDF report generation. "
                "Install with: pip install fpdf2"
            )
        pdf = EnterpriseReportPDF(
            title=title,
            subtitle=subtitle,
            watermark=watermark,
            classification=classification,
            font_path=self._font_path,
        )
        pdf.alias_nb_pages()
        return pdf

    def _output_path(self, prefix: str, identifier: str) -> str:
        """Build a unique output file path."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_id = re.sub(r"[^\w\-]", "_", identifier)[:40]
        filename = f"{prefix}_{safe_id}_{ts}.pdf"
        return os.path.join(self.output_dir, filename)

    # ══════════════════════════════════════════════════════════════════════
    # 1. EVIDENCE PDF
    # ══════════════════════════════════════════════════════════════════════

    def generate_evidence_pdf(
        self,
        query: str,
        answer: str,
        sources: List[Dict[str, Any]],
        client_id: str,
        report_id: Optional[str] = None,
        watermark: Optional[str] = None,
    ) -> str:
        """
        Generate an audit-trail PDF documenting a single RAG search query,
        its synthesised answer, and the semantic evidence sources.

        Parameters
        ----------
        query : str
            The user's search question.
        answer : str
            The LLM-generated response.
        sources : list[dict]
            Search result objects from the RAG engine.
        client_id : str
            Tenant or API-key identifier.
        report_id : str, optional
            Deterministic report UUID.  Auto-generated if omitted.
        watermark : str, optional
            Diagonal watermark text (e.g. ``"CONFIDENTIAL"``).

        Returns
        -------
        str
            Absolute path to the generated PDF file.
        """
        report_id = report_id or str(uuid.uuid4())
        pdf = self._make_pdf(
            title="Semantic Evidence Audit Report",
            subtitle="SES Enterprise Gateway",
            watermark=watermark,
            classification="CONFIDENTIAL" if watermark else "INTERNAL",
        )
        pdf.add_page()

        # ── Report Metadata ───────────────────────────────────────────────
        pdf.draw_section_title("Report Identification")
        pdf.draw_kv_line("Report ID:", report_id)
        pdf.draw_kv_line("Generated:", _iso_now())
        pdf.draw_kv_line("Client ID:", client_id)
        pdf.draw_kv_line("Total Sources:", str(len(sources)))
        pdf.ln(2)

        # ── Query ─────────────────────────────────────────────────────────
        pdf.draw_section_title("Query")
        pdf.draw_body_text(query, size=10)
        pdf.ln(3)

        # ── Synthesised Answer ────────────────────────────────────────────
        pdf.draw_section_title("Synthesized Answer")
        pdf.draw_body_text(answer, size=10)
        pdf.ln(3)

        # ── Evidence Trail Table ──────────────────────────────────────────
        pdf.draw_section_title("Semantic Evidence Trail")

        content_w = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
        col_num   = 8
        col_file  = content_w * 0.30
        col_score = content_w * 0.20
        col_chunk = content_w * 0.15
        col_hash  = content_w - col_num - col_file - col_score - col_chunk

        # Table header
        pdf.set_font(pdf._font_family, "B", 8)
        pdf.set_fill_color(*COLOR_PRIMARY)
        pdf.set_text_color(*COLOR_WHITE)
        y0 = pdf.get_y()
        pdf.cell(col_num,   6, "#",               border=1, fill=True, align="C")
        pdf.cell(col_file,  6, "Source File",      border=1, fill=True, align="C")
        pdf.cell(col_score, 6, "Relevance Score",  border=1, fill=True, align="C")
        pdf.cell(col_chunk, 6, "Chunk ID",         border=1, fill=True, align="C")
        pdf.cell(col_hash,  6, "Content Hash",     border=1, fill=True, align="C")
        pdf.ln()
        pdf.set_text_color(*COLOR_BLACK)

        for idx, source in enumerate(sources, 1):
            meta     = source.get("metadata", {})
            filename = meta.get("filename") or meta.get("file_name") or "unknown"
            score    = float(source.get("score", 0))
            chunk_id = str(meta.get("chunk_index", "-"))
            c_hash   = str(meta.get("content_hash", "-"))[:16]
            snippet  = source.get("text_snippet") or source.get("text", "") or ""

            # Alternating row colour
            if idx % 2 == 0:
                pdf.set_fill_color(*COLOR_ROW_ALT)
            else:
                pdf.set_fill_color(*COLOR_WHITE)

            pdf.set_font(pdf._font_family, "", 8)
            row_y = pdf.get_y()

            pdf.cell(col_num,   5.5, str(idx),                             border=1, fill=True, align="C")
            pdf.cell(col_file,  5.5, _sanitize_text(filename)[:35],        border=1, fill=True, align="L")

            # Score bar inside the score column
            score_x = pdf.get_x()
            score_y = pdf.get_y()
            pdf.cell(col_score, 5.5, "",                                   border=1, fill=True, align="C")
            pdf.draw_score_bar(score_x + 2, score_y + 1, col_score - 4, 3.5, score)

            pdf.set_xy(score_x + col_score, row_y)
            pdf.cell(col_chunk, 5.5, chunk_id,                             border=1, fill=True, align="C")
            pdf.cell(col_hash,  5.5, c_hash,                               border=1, fill=True, align="C")
            pdf.ln()

            # Snippet block below the row
            if snippet:
                truncated = snippet[:600] + ("..." if len(snippet) > 600 else "")
                pdf.draw_italic_block(truncated, indent=8)

            # Page-break guard
            if pdf.get_y() > 260:
                pdf.add_page()

        # ── Traceability Metadata ─────────────────────────────────────────
        pdf.draw_section_title("Traceability Metadata")
        seen_files: Dict[str, str] = {}
        for source in sources:
            meta = source.get("metadata", {})
            fname = meta.get("filename") or meta.get("file_name") or "unknown"
            fpath = meta.get("source_path") or "-"
            if fname not in seen_files:
                seen_files[fname] = fpath

        pdf.set_font(pdf._font_family, "", 8)
        for i, (fname, fpath) in enumerate(seen_files.items(), 1):
            if i % 2 == 0:
                pdf.set_fill_color(*COLOR_ROW_ALT)
            else:
                pdf.set_fill_color(*COLOR_WHITE)
            pdf.cell(8,  5, str(i),                        fill=True, align="C")
            pdf.cell(55, 5, _sanitize_text(fname)[:40],    fill=True, align="L")
            pdf.cell(0,  5, _sanitize_text(str(fpath)),    fill=True, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # ── Save ──────────────────────────────────────────────────────────
        out_path = self._output_path("evidence", client_id)
        pdf.output(out_path)
        logger.info("Evidence PDF generated: %s", out_path)
        return out_path

    # ══════════════════════════════════════════════════════════════════════
    # 2. USAGE REPORT PDF
    # ══════════════════════════════════════════════════════════════════════

    def generate_usage_report_pdf(
        self,
        analytics_data: Dict[str, Any],
        tenant_name: str,
        period: str = "Monthly",
        watermark: Optional[str] = None,
    ) -> str:
        """
        Generate a business/billing usage report PDF.

        Parameters
        ----------
        analytics_data : dict
            Output of ``DatabaseAdapter.get_analytics()``.
        tenant_name : str
            Display name for the tenant.
        period : str
            Report period label (e.g. ``"Monthly"``, ``"Q2 2026"``).
        watermark : str, optional
            Diagonal watermark text.

        Returns
        -------
        str
            Path to the generated PDF file.
        """
        pdf = self._make_pdf(
            title="Usage & Analytics Report",
            subtitle=f"{tenant_name} — {period}",
            watermark=watermark,
            classification="INTERNAL",
        )
        pdf.add_page()

        # ── Summary Metrics ───────────────────────────────────────────────
        pdf.draw_section_title("Summary Metrics")

        total_req  = analytics_data.get("total_requests", 0)
        total_srch = analytics_data.get("total_searches", 0)
        total_ing  = analytics_data.get("total_ingestions", 0)
        total_err  = analytics_data.get("total_errors", 0)
        avg_lat    = analytics_data.get("average_latency_ms", 0.0)

        content_w = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
        col_w     = content_w / 5

        # Header
        headers = ["Total Requests", "Searches", "Ingestions", "Errors", "Avg Latency"]
        values  = [str(total_req), str(total_srch), str(total_ing), str(total_err), f"{avg_lat:.1f} ms"]

        pdf.set_font(pdf._font_family, "B", 8)
        pdf.set_fill_color(*COLOR_PRIMARY)
        pdf.set_text_color(*COLOR_WHITE)
        for h in headers:
            pdf.cell(col_w, 6, h, border=1, fill=True, align="C")
        pdf.ln()

        pdf.set_font(pdf._font_family, "B", 11)
        pdf.set_text_color(*COLOR_PRIMARY)
        pdf.set_fill_color(*COLOR_WHITE)
        for v in values:
            pdf.cell(col_w, 10, v, border=1, fill=True, align="C")
        pdf.ln(6)
        pdf.set_text_color(*COLOR_BLACK)

        # ── Per-Key Performance ───────────────────────────────────────────
        pdf.draw_section_title("Per-Key Performance Breakdown")

        keys_perf = analytics_data.get("keys_performance", [])
        if not keys_perf:
            pdf.draw_body_text("No per-key performance data available for this period.")
        else:
            k_col_name = content_w * 0.30
            k_col_role = content_w * 0.15
            k_col_calls = content_w * 0.20
            k_col_lat  = content_w * 0.35

            pdf.set_font(pdf._font_family, "B", 8)
            pdf.set_fill_color(*COLOR_PRIMARY)
            pdf.set_text_color(*COLOR_WHITE)
            pdf.cell(k_col_name,  6, "Key Name",      border=1, fill=True, align="C")
            pdf.cell(k_col_role,  6, "Role",           border=1, fill=True, align="C")
            pdf.cell(k_col_calls, 6, "Total Calls",    border=1, fill=True, align="C")
            pdf.cell(k_col_lat,   6, "Avg Latency",    border=1, fill=True, align="C")
            pdf.ln()
            pdf.set_text_color(*COLOR_BLACK)

            for i, kp in enumerate(keys_perf):
                if i % 2 == 0:
                    pdf.set_fill_color(*COLOR_ROW_ALT)
                else:
                    pdf.set_fill_color(*COLOR_WHITE)
                pdf.set_font(pdf._font_family, "", 8)
                kname = kp.get("name", "-")
                krole = kp.get("role", "client")
                kcalls = str(kp.get("total_calls", 0))
                klat   = f"{kp.get('avg_latency_ms', 0):.1f} ms"
                pdf.cell(k_col_name,  5.5, _sanitize_text(kname)[:30],  border=1, fill=True, align="L")
                pdf.cell(k_col_role,  5.5, krole,                        border=1, fill=True, align="C")
                pdf.cell(k_col_calls, 5.5, kcalls,                       border=1, fill=True, align="C")
                pdf.cell(k_col_lat,   5.5, klat,                         border=1, fill=True, align="C")
                pdf.ln()

        # ── Report Footer Metadata ────────────────────────────────────────
        pdf.ln(8)
        pdf.draw_horizontal_rule()
        pdf.draw_kv_line("Report Period:", period)
        pdf.draw_kv_line("Tenant:", tenant_name)
        pdf.draw_kv_line("Generated:", _iso_now())

        out_path = self._output_path("usage", tenant_name)
        pdf.output(out_path)
        logger.info("Usage PDF generated: %s", out_path)
        return out_path

    # ══════════════════════════════════════════════════════════════════════
    # 3. COMPLIANCE SUMMARY PDF
    # ══════════════════════════════════════════════════════════════════════

    def generate_compliance_summary_pdf(
        self,
        queries_with_sources: List[Dict[str, Any]],
        tenant_name: str,
        watermark: str = "CONFIDENTIAL",
    ) -> str:
        """
        Generate a multi-page compliance bundle.

        Each element of *queries_with_sources* should be a dict with keys:
        ``query``, ``answer``, ``sources`` (list), ``timestamp`` (ISO string).

        The report contains:
        1. Executive summary with aggregate statistics.
        2. One page per query/answer/evidence set.
        3. Cross-reference index listing every source document.

        Parameters
        ----------
        queries_with_sources : list[dict]
            Collection of query audit records.
        tenant_name : str
            Display name for the tenant.
        watermark : str
            Watermark text (defaults to ``"CONFIDENTIAL"``).

        Returns
        -------
        str
            Path to the generated PDF file.
        """
        pdf = self._make_pdf(
            title="Compliance Evidence Bundle",
            subtitle=f"{tenant_name}",
            watermark=watermark,
            classification="CONFIDENTIAL",
        )

        content_w = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT

        # ── Executive Summary (page 1) ────────────────────────────────────
        pdf.add_page()
        pdf.draw_section_title("Executive Summary")

        total_queries = len(queries_with_sources)
        all_sources_flat: List[Dict[str, Any]] = []
        all_filenames: set = set()
        timestamps: List[str] = []

        for entry in queries_with_sources:
            sources = entry.get("sources", [])
            all_sources_flat.extend(sources)
            ts = entry.get("timestamp", "")
            if ts:
                timestamps.append(ts)
            for s in sources:
                meta = s.get("metadata", {})
                fname = meta.get("filename") or meta.get("file_name")
                if fname:
                    all_filenames.add(fname)

        unique_sources = len(all_filenames)

        # Date range
        if timestamps:
            sorted_ts = sorted(timestamps)
            date_range = f"{sorted_ts[0]} to {sorted_ts[-1]}"
        else:
            date_range = _iso_now()

        pdf.draw_kv_line("Total Queries Audited:", str(total_queries))
        pdf.draw_kv_line("Total Unique Source Documents:", str(unique_sources))
        pdf.draw_kv_line("Total Evidence Citations:", str(len(all_sources_flat)))
        pdf.draw_kv_line("Date Range:", date_range)
        pdf.draw_kv_line("Tenant:", tenant_name)
        pdf.draw_kv_line("Generated:", _iso_now())
        pdf.ln(4)

        pdf.draw_horizontal_rule()
        pdf.draw_body_text(
            "This document constitutes a formal compliance evidence bundle. "
            "Each query, its synthesised answer, and the contributing semantic "
            "sources are documented in full for regulatory and internal audit purposes."
        )

        # ── Per-Query Pages ───────────────────────────────────────────────
        for q_idx, entry in enumerate(queries_with_sources, 1):
            pdf.add_page()
            pdf.draw_section_title(f"Audit Record {q_idx} of {total_queries}")

            entry_ts = entry.get("timestamp", _iso_now())
            pdf.draw_kv_line("Timestamp:", entry_ts)
            pdf.ln(2)

            # Query
            pdf.set_font(pdf._font_family, "B", 10)
            pdf.set_text_color(*COLOR_SECONDARY)
            pdf.cell(0, 6, "Query:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(*COLOR_BLACK)
            pdf.draw_body_text(entry.get("query", ""), size=10)
            pdf.ln(2)

            # Answer
            pdf.set_font(pdf._font_family, "B", 10)
            pdf.set_text_color(*COLOR_SECONDARY)
            pdf.cell(0, 6, "Synthesized Answer:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(*COLOR_BLACK)
            pdf.draw_body_text(entry.get("answer", ""), size=9)
            pdf.ln(3)

            # Evidence mini-table
            sources = entry.get("sources", [])
            if sources:
                pdf.set_font(pdf._font_family, "B", 10)
                pdf.set_text_color(*COLOR_SECONDARY)
                pdf.cell(0, 6, "Evidence Sources:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_text_color(*COLOR_BLACK)

                col_num_c  = 8
                col_file_c = content_w * 0.40
                col_score_c = content_w * 0.20
                col_chunk_c = content_w - col_num_c - col_file_c - col_score_c

                pdf.set_font(pdf._font_family, "B", 7)
                pdf.set_fill_color(*COLOR_PRIMARY)
                pdf.set_text_color(*COLOR_WHITE)
                pdf.cell(col_num_c,   5, "#",          border=1, fill=True, align="C")
                pdf.cell(col_file_c,  5, "Source File", border=1, fill=True, align="C")
                pdf.cell(col_score_c, 5, "Score",       border=1, fill=True, align="C")
                pdf.cell(col_chunk_c, 5, "Chunk",       border=1, fill=True, align="C")
                pdf.ln()
                pdf.set_text_color(*COLOR_BLACK)

                for si, src in enumerate(sources, 1):
                    meta = src.get("metadata", {})
                    fname = meta.get("filename") or meta.get("file_name") or "unknown"
                    score = float(src.get("score", 0))
                    chunk = str(meta.get("chunk_index", "-"))

                    if si % 2 == 0:
                        pdf.set_fill_color(*COLOR_ROW_ALT)
                    else:
                        pdf.set_fill_color(*COLOR_WHITE)

                    pdf.set_font(pdf._font_family, "", 7)
                    pdf.cell(col_num_c,   5, str(si),                         border=1, fill=True, align="C")
                    pdf.cell(col_file_c,  5, _sanitize_text(fname)[:45],      border=1, fill=True, align="L")
                    pdf.cell(col_score_c, 5, f"{score * 100:.1f}%",           border=1, fill=True, align="C")
                    pdf.cell(col_chunk_c, 5, chunk,                           border=1, fill=True, align="C")
                    pdf.ln()

                    # Snippet
                    snippet = src.get("text_snippet") or src.get("text", "") or ""
                    if snippet:
                        pdf.draw_italic_block(snippet[:400], indent=6)

                    if pdf.get_y() > 260:
                        pdf.add_page()

        # ── Cross-Reference Index (final page) ────────────────────────────
        pdf.add_page()
        pdf.draw_section_title("Cross-Reference Index — All Source Documents")

        # Build: filename → list of query indices where it appeared
        xref: Dict[str, List[int]] = {}
        for q_idx, entry in enumerate(queries_with_sources, 1):
            for src in entry.get("sources", []):
                meta = src.get("metadata", {})
                fname = meta.get("filename") or meta.get("file_name") or "unknown"
                xref.setdefault(fname, []).append(q_idx)

        col_xf_name = content_w * 0.50
        col_xf_refs = content_w * 0.25
        col_xf_cnt  = content_w * 0.25

        pdf.set_font(pdf._font_family, "B", 8)
        pdf.set_fill_color(*COLOR_PRIMARY)
        pdf.set_text_color(*COLOR_WHITE)
        pdf.cell(col_xf_name, 6, "Document",          border=1, fill=True, align="C")
        pdf.cell(col_xf_refs, 6, "Referenced In",      border=1, fill=True, align="C")
        pdf.cell(col_xf_cnt,  6, "Total References",   border=1, fill=True, align="C")
        pdf.ln()
        pdf.set_text_color(*COLOR_BLACK)

        for i, (fname, q_indices) in enumerate(sorted(xref.items()), 1):
            if i % 2 == 0:
                pdf.set_fill_color(*COLOR_ROW_ALT)
            else:
                pdf.set_fill_color(*COLOR_WHITE)
            pdf.set_font(pdf._font_family, "", 7)
            unique_qs = sorted(set(q_indices))
            refs_str = ", ".join(f"Q{q}" for q in unique_qs)
            pdf.cell(col_xf_name, 5, _sanitize_text(fname)[:50],  border=1, fill=True, align="L")
            pdf.cell(col_xf_refs, 5, refs_str[:30],                border=1, fill=True, align="C")
            pdf.cell(col_xf_cnt,  5, str(len(q_indices)),          border=1, fill=True, align="C")
            pdf.ln()

            if pdf.get_y() > 270:
                pdf.add_page()

        out_path = self._output_path("compliance", tenant_name)
        pdf.output(out_path)
        logger.info("Compliance PDF generated: %s", out_path)
        return out_path

    # ══════════════════════════════════════════════════════════════════════
    # 4. SYSTEM HEALTH PDF
    # ══════════════════════════════════════════════════════════════════════

    def generate_system_health_pdf(
        self,
        health_data: Dict[str, Any],
        analytics_data: Dict[str, Any],
        tenant_name: str,
    ) -> str:
        """
        Generate a system health snapshot PDF for IT / ops teams.

        Parameters
        ----------
        health_data : dict
            Output of the ``/api/v1/health`` endpoint.
        analytics_data : dict
            Output of ``DatabaseAdapter.get_analytics()``.
        tenant_name : str
            Display name of the requesting tenant / admin.

        Returns
        -------
        str
            Path to the generated PDF file.
        """
        overall_status = health_data.get("status", "unknown")
        pdf = self._make_pdf(
            title="System Health Report",
            subtitle=f"SES Enterprise Gateway — {tenant_name}",
            watermark=None,
            classification="INTERNAL",
        )
        pdf.add_page()

        content_w = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT

        # ── Overall Status Banner ─────────────────────────────────────────
        if overall_status == "healthy":
            banner_color = COLOR_SUCCESS_GRN
            status_label = "ALL SYSTEMS OPERATIONAL"
        elif overall_status == "degraded":
            banner_color = COLOR_WARN_AMBER
            status_label = "DEGRADED PERFORMANCE"
        else:
            banner_color = COLOR_ERROR_RED
            status_label = "SYSTEM ISSUES DETECTED"

        pdf.set_fill_color(*banner_color)
        pdf.set_text_color(*COLOR_WHITE)
        pdf.set_font(pdf._font_family, "B", 14)
        pdf.cell(content_w, 12, status_label, fill=True, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(*COLOR_BLACK)
        pdf.ln(4)

        # ── Service Status Table ──────────────────────────────────────────
        pdf.draw_section_title("Service Status")

        services = health_data.get("services", {})
        col_svc  = content_w * 0.40
        col_stat = content_w * 0.30
        col_ind  = content_w * 0.30

        pdf.set_font(pdf._font_family, "B", 8)
        pdf.set_fill_color(*COLOR_PRIMARY)
        pdf.set_text_color(*COLOR_WHITE)
        pdf.cell(col_svc,  6, "Service",     border=1, fill=True, align="C")
        pdf.cell(col_stat, 6, "Status",      border=1, fill=True, align="C")
        pdf.cell(col_ind,  6, "Indicator",   border=1, fill=True, align="C")
        pdf.ln()
        pdf.set_text_color(*COLOR_BLACK)

        service_labels = {
            "qdrant":             "Qdrant Vector Store",
            "redis":              "Redis Cache & Rate Limiter",
            "ollama_api":         "Ollama LLM API",
            "rust_acceleration":  "Rust Vector Acceleration",
        }

        for i, (svc_key, svc_status) in enumerate(services.items()):
            label = service_labels.get(svc_key, svc_key)
            if i % 2 == 0:
                pdf.set_fill_color(*COLOR_ROW_ALT)
            else:
                pdf.set_fill_color(*COLOR_WHITE)

            pdf.set_font(pdf._font_family, "", 8)
            pdf.cell(col_svc, 6, label, border=1, fill=True, align="L")

            # Status text colour
            if svc_status in ("connected", "active"):
                pdf.set_text_color(*COLOR_SUCCESS_GRN)
                indicator = "OK"
            elif svc_status == "disabled":
                pdf.set_text_color(*COLOR_GRAY_TEXT)
                indicator = "--"
            else:
                pdf.set_text_color(*COLOR_ERROR_RED)
                indicator = "!!"

            pdf.set_font(pdf._font_family, "B", 8)
            pdf.cell(col_stat, 6, str(svc_status).upper(), border=1, fill=True, align="C")
            pdf.cell(col_ind,  6, indicator,               border=1, fill=True, align="C")
            pdf.ln()
            pdf.set_text_color(*COLOR_BLACK)

        pdf.ln(4)

        # ── Performance Metrics ───────────────────────────────────────────
        pdf.draw_section_title("Performance Metrics")

        total_req  = analytics_data.get("total_requests", 0)
        total_err  = analytics_data.get("total_errors", 0)
        avg_lat    = analytics_data.get("average_latency_ms", 0.0)
        total_srch = analytics_data.get("total_searches", 0)
        total_ing  = analytics_data.get("total_ingestions", 0)

        pdf.draw_kv_line("Total Requests Processed:", str(total_req))
        pdf.draw_kv_line("Total Errors:", str(total_err))
        pdf.draw_kv_line("Total Searches:", str(total_srch))
        pdf.draw_kv_line("Total Ingestions:", str(total_ing))
        pdf.draw_kv_line("Average Latency:", f"{avg_lat:.1f} ms")

        error_rate = (total_err / total_req * 100) if total_req > 0 else 0.0
        pdf.draw_kv_line("Error Rate:", f"{error_rate:.2f}%")
        pdf.ln(4)

        # ── Recent Error Logs ─────────────────────────────────────────────
        recent_logs = analytics_data.get("recent_logs", [])
        error_logs = [
            log for log in recent_logs
            if log.get("status_code", 200) >= 400
        ]

        pdf.draw_section_title("Recent Error Logs")
        if not error_logs:
            pdf.draw_body_text("No errors recorded in the recent log window.")
        else:
            col_ts   = content_w * 0.30
            col_ep   = content_w * 0.30
            col_code = content_w * 0.15
            col_lat2 = content_w * 0.25

            pdf.set_font(pdf._font_family, "B", 7)
            pdf.set_fill_color(*COLOR_PRIMARY)
            pdf.set_text_color(*COLOR_WHITE)
            pdf.cell(col_ts,   5, "Timestamp",  border=1, fill=True, align="C")
            pdf.cell(col_ep,   5, "Endpoint",   border=1, fill=True, align="C")
            pdf.cell(col_code, 5, "Status",     border=1, fill=True, align="C")
            pdf.cell(col_lat2, 5, "Latency",    border=1, fill=True, align="C")
            pdf.ln()
            pdf.set_text_color(*COLOR_BLACK)

            for i, elog in enumerate(error_logs[:20]):
                if i % 2 == 0:
                    pdf.set_fill_color(*COLOR_ROW_ALT)
                else:
                    pdf.set_fill_color(*COLOR_WHITE)
                pdf.set_font(pdf._font_family, "", 7)
                pdf.cell(col_ts,   5, str(elog.get("timestamp", "-"))[:25],   border=1, fill=True, align="L")
                pdf.cell(col_ep,   5, str(elog.get("endpoint", "-"))[:30],    border=1, fill=True, align="L")
                pdf.cell(col_code, 5, str(elog.get("status_code", "-")),      border=1, fill=True, align="C")
                lat_val = elog.get("latency_ms", 0)
                pdf.cell(col_lat2, 5, f"{lat_val:.0f} ms" if lat_val else "-", border=1, fill=True, align="C")
                pdf.ln()

        # ── Report metadata ───────────────────────────────────────────────
        pdf.ln(6)
        pdf.draw_horizontal_rule()
        pdf.draw_kv_line("Health Check Time:", health_data.get("timestamp", _iso_now()))
        pdf.draw_kv_line("Report Generated:", _iso_now())

        out_path = self._output_path("health", tenant_name)
        pdf.output(out_path)
        logger.info("Health PDF generated: %s", out_path)
        return out_path


# ─── Singleton Accessor ──────────────────────────────────────────────────────

_report_service: Optional[ReportService] = None


def get_report_service() -> ReportService:
    """Return (and lazily initialise) the global ``ReportService`` singleton."""
    global _report_service
    if _report_service is None:
        _report_service = ReportService()
    return _report_service
