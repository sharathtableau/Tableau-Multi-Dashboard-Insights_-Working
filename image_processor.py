import os
import logging
from PIL import Image
from pdf2image import convert_from_path
from PyPDF2 import PdfMerger
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from typing import List, Dict, Any
import tempfile
from datetime import datetime
import cv2
import numpy as np
import time

# PPTX imports
try:
    from pptx import Presentation
    from pptx.util import Inches as PPTInches, Pt as PPTPt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.oxml.ns import qn
    from pptx.oxml import parse_xml
    from lxml import etree
    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False

# PDF generation imports
try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False

import base64

# Gemini AI imports
try:
    from google import genai
    from PIL import Image as PILImage
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logging.warning("google-genai not available.")

# Anthropic AI imports
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logging.warning("anthropic library not available.")

# Load configuration
try:
    import config
    from config import GEMINI_API_KEY, GEMINI_MODEL, ENABLE_AI_INSIGHTS
    print(f"[IMAGE_PROCESSOR] Loaded config OK. GEMINI_MODEL={GEMINI_MODEL}")
    logging.info(f"AI CONFIG: Primary Model={GEMINI_MODEL}, Provider={getattr(config, 'AI_PROVIDER', 'gemini')}")
except Exception as _cfg_err:
    import os
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    GEMINI_MODEL = "gemini-2.5-flash"
    ENABLE_AI_INSIGHTS = False
    print(f"[IMAGE_PROCESSOR] Config import FAILED: {_cfg_err}. Using fallback model.")
    logging.warning(f"config.py not found or incomplete. Error: {_cfg_err}")

class ImageProcessor:
    def __init__(self):
        self.temp_files = []
        
        # Initialize Gemini AI client
        self.gemini_client = None
        self.anthropic_client = None
        
        if config.ENABLE_AI_INSIGHTS:
            if config.AI_PROVIDER == "anthropic" and ANTHROPIC_AVAILABLE:
                try:
                    self.anthropic_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
                    logging.info("Anthropic client initialized successfully")
                except Exception as e:
                    logging.error(f"Failed to initialize Anthropic client: {e}")
            
            # If anthropic was not chosen or failed/unavailable, try Gemini
            if not self.anthropic_client and config.GEMINI_API_KEY and GEMINI_AVAILABLE:
                try:
                    self.gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
                    logging.info("Gemini client initialized successfully")
                except Exception as e:
                    logging.error(f"Failed to initialize Gemini client: {e}")
        else:
            reasons = []
            if not ENABLE_AI_INSIGHTS: reasons.append("ENABLE_AI_INSIGHTS is False")
            if not GEMINI_API_KEY: reasons.append("GEMINI_API_KEY is missing")
            if not GEMINI_AVAILABLE: reasons.append("google-genai library missing")
            logging.warning(f"Gemini AI is disabled. Reasons: {', '.join(reasons)}")

    def _format_filters(self, filters_dict: Dict) -> str:
        """Helper to format applied filters into a readable string"""
        if not filters_dict:
            return ""
        filter_strings = []
        for name, value in filters_dict.items():
            filter_strings.append(f"{name}: {value}")
        return ", ".join(filter_strings)
    
    def _format_datasource_info(self, datasources: List) -> str:
        """Helper to format datasource info into a readable string"""
        if not datasources:
            return ""
        parts = []
        for ds in datasources:
            name = ds.get('name', 'Data Source')
            has_extract = ds.get('hasExtracts', False)
            updated_at = ds.get('updatedAt')
            
            if updated_at:
                try:
                    from datetime import datetime as dt
                    date = dt.fromisoformat(updated_at.replace('Z', '+00:00'))
                    # Convert UTC to local system time
                    local_date = date.astimezone()
                    formatted_date = local_date.strftime('%b %d, %Y %I:%M %p')
                except:
                    formatted_date = updated_at
                
                if has_extract:
                    parts.append(f"Extract \u2014 As of {formatted_date}")
                else:
                    parts.append(f"Updated: {formatted_date}")
            elif has_extract:
                parts.append("Extract (refresh date unavailable)")
            else:
                parts.append("Live connection")
        
        return "; ".join(parts)
    
    def pdf_to_png(self, pdf_path: str, dpi: int = 200) -> str:
        """Convert PDF to PNG image"""
        try:
            # Convert PDF to images
            images = convert_from_path(pdf_path, dpi=dpi)
            
            if not images:
                raise Exception("No images found in PDF")
            
            # Use the first page
            image = images[0]
            
            # Generate PNG filename
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]
            png_path = os.path.join(os.path.dirname(pdf_path), f"{base_name}.png")
            
            # Save as PNG
            image.save(png_path, "PNG")
            
            logging.info(f"Successfully converted PDF to PNG: {png_path}")
            return png_path
            
        except Exception as e:
            logging.error(f"Failed to convert PDF to PNG: {str(e)}")
            raise Exception(f"PDF conversion failed: {str(e)}")
    
    def trim_to_dashboard_size(self, png_path: str, design_w: int = 0, design_h: int = 0) -> str:
        """
        Trim the blank whitespace margins that Tableau adds above and below the
        dashboard content when exporting to PDF (US Letter page).

        Uses pixel-level detection to find the actual first and last rows that
        contain non-background content, so no content is ever clipped regardless
        of how Tableau positions the content on the page.

        A small safety buffer is kept around the detected content boundary so that
        faint borders or anti-aliased edges are never lost.

        Returns the path to the trimmed PNG (saved alongside the original), or the
        original path unchanged if no meaningful whitespace is found.
        """
        BACKGROUND_THRESHOLD = 245   # pixels brighter than this are considered background
        SAFETY_BUFFER = 5            # extra pixels to keep above/below detected content
        MIN_WHITESPACE = 20          # only trim when at least this many blank rows exist

        try:
            img = Image.open(png_path)
            page_w, page_h = img.size

            # Work in grayscale for fast per-row min detection
            gray = img.convert('L')

            # Scan top-to-bottom for first row with any non-background pixel
            first_content_row = None
            for y in range(page_h):
                row = gray.crop((0, y, page_w, y + 1))
                if min(row.getdata()) < BACKGROUND_THRESHOLD:
                    first_content_row = y
                    break

            if first_content_row is None:
                logging.info("trim_to_dashboard_size: no content found, skipping trim.")
                return png_path

            # Scan bottom-to-top for last row with any non-background pixel
            last_content_row = first_content_row
            for y in range(page_h - 1, first_content_row, -1):
                row = gray.crop((0, y, page_w, y + 1))
                if min(row.getdata()) < BACKGROUND_THRESHOLD:
                    last_content_row = y
                    break

            top_whitespace    = first_content_row
            bottom_whitespace = page_h - last_content_row - 1

            logging.info(
                f"trim_to_dashboard_size: detected content rows {first_content_row}–{last_content_row} "
                f"(top_ws={top_whitespace}px, bot_ws={bottom_whitespace}px)"
            )

            # Only trim if there is meaningful whitespace on at least one side
            if top_whitespace < MIN_WHITESPACE and bottom_whitespace < MIN_WHITESPACE:
                logging.info("trim_to_dashboard_size: whitespace too small, skipping trim.")
                return png_path

            y_start = max(0,       first_content_row - SAFETY_BUFFER)
            y_end   = min(page_h,  last_content_row  + SAFETY_BUFFER + 1)

            logging.info(f"Trimming PNG to y=[{y_start}, {y_end}] (content + {SAFETY_BUFFER}px buffer)")

            cropped = img.crop((0, y_start, page_w, y_end))

            base, ext = os.path.splitext(png_path)
            trimmed_path = f"{base}_trimmed{ext}"
            cropped.save(trimmed_path, "PNG")
            logging.info(f"Trimmed PNG saved: {trimmed_path} ({cropped.size[0]}×{cropped.size[1]})")
            return trimmed_path

        except Exception as e:
            logging.error(f"trim_to_dashboard_size failed: {e}")
            return png_path  # fall back to original on any error

    def crop_image(self, image_path: str, crop_data: Dict[str, float]) -> str:
        """Crop an image based on crop coordinates"""
        try:
            image = Image.open(image_path)
            
            # Extract crop coordinates
            x1 = int(crop_data['x'])
            y1 = int(crop_data['y'])
            x2 = int(crop_data['x'] + crop_data['width'])
            y2 = int(crop_data['y'] + crop_data['height'])
            
            # Ensure coordinates are within image bounds
            x1 = max(0, min(x1, image.width))
            y1 = max(0, min(y1, image.height))
            x2 = max(0, min(x2, image.width))
            y2 = max(0, min(y2, image.height))
            
            # Ensure we have a valid crop area
            if x2 <= x1 or y2 <= y1:
                raise Exception("Invalid crop coordinates")
            
            # Crop the image
            cropped_image = image.crop((x1, y1, x2, y2))
            
            # Generate unique cropped filename with timestamp so successive crops
            # produce different filenames and the browser doesn't serve a cached version.
            import time as _time
            base_name = os.path.splitext(os.path.basename(image_path))[0]
            # Strip any previous _cropped_<ts> suffix so base stays clean
            if '_cropped' in base_name:
                base_name = base_name[:base_name.index('_cropped')]
            ts = int(_time.time() * 1000)
            cropped_path = os.path.join(os.path.dirname(image_path), f"{base_name}_cropped_{ts}.png")
            
            # Save cropped image
            cropped_image.save(cropped_path, "PNG")
            
            logging.info(f"Successfully cropped image: {cropped_path}")
            return cropped_path
            
        except Exception as e:
            logging.error(f"Failed to crop image: {str(e)}")
            raise Exception(f"Image cropping failed: {str(e)}")
    
    def combine_to_pdf(self, image_paths: List[str], output_dir: str, filename: str) -> str:
        """Combine multiple images into a single PDF (Legacy version, no text)"""
        try:
            output_path = os.path.join(output_dir, f"{filename}.pdf")
            
            # Convert images to PDF
            temp_pdfs = []
            merger = PdfMerger()
            
            for i, image_path in enumerate(image_paths):
                if not os.path.exists(image_path):
                    logging.warning(f"Image not found: {image_path}")
                    continue
                
                # Open and convert image to RGB if necessary
                image = Image.open(image_path)
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                # Create temporary PDF for this image
                temp_pdf_path = os.path.join(output_dir, f"temp_{i}.pdf")
                image.save(temp_pdf_path, "PDF")
                temp_pdfs.append(temp_pdf_path)
                
                # Add to merger
                merger.append(temp_pdf_path)
            
            if not temp_pdfs:
                raise Exception("No valid images to combine")
            
            # Write combined PDF
            merger.write(output_path)
            merger.close()
            
            # Clean up temporary PDFs
            for temp_pdf in temp_pdfs:
                try:
                    os.remove(temp_pdf)
                except:
                    pass
            
            logging.info(f"Successfully created combined PDF (raw): {output_path}")
            return output_path
            
        except Exception as e:
            logging.error(f"Failed to combine images to PDF: {str(e)}")
            raise Exception(f"PDF combination failed: {str(e)}")

    def combine_to_pdf_with_details(self, image_paths: List[str], output_dir: str, filename: str, summary_data: List[Dict]) -> str:
        """Combine multiple images into a single PDF with AI insights using fpdf2"""
        if not FPDF_AVAILABLE:
            logging.warning("fpdf2 not available, falling back to basic PDF")
            return self.combine_to_pdf(image_paths, output_dir, filename)

        try:
            output_path = os.path.join(output_dir, f"{filename}.pdf")
            pdf = FPDF(orientation='L', unit='in', format='Letter')
            pdf.set_auto_page_break(auto=True, margin=0.5)

            for i, image_path in enumerate(image_paths):
                if not os.path.exists(image_path):
                    continue
                
                pdf.add_page()
                
                # Title
                pdf.set_font("helvetica", "B", 16)
                pdf.cell(0, 0.4, f"Tableau Dashboard Export Report", align="C", ln=1)
                pdf.ln(0.2)
                
                # Image on left
                img = Image.open(image_path)
                aspect = img.height / img.width
                img_w = 4.5
                img_h = img_w * aspect
                
                # Center image vertically if it's small, or just place it
                pdf.image(image_path, x=0.5, y=1.2, w=img_w)
                
                # Insights on right
                pdf.set_left_margin(5.5)
                pdf.set_y(1.2)
                
                # Get insights for this dashboard
                # We need to regenerate or pass them. 
                # Actually summary_data should have them if we generated them before? 
                # No, they are generated inside _add_dashboard_to_word.
                # Let's fix this by generating insights here too if needed, or better, 
                # ensure summary_data contains pre-generated insights.
                
                dashboard_name = summary_data[i].get("dashboard", "Dashboard")
                applied_filters = summary_data[i].get("applied_filters", {})
                filter_text = self._format_filters(applied_filters)

                if filter_text:
                    pdf.set_font("helvetica", "B", 10)
                    pdf.write(0.2, "Applied Filters: ")
                    pdf.set_font("helvetica", "", 10)
                    pdf.write(0.2, f"{filter_text}\n\n")

                # Add data source info (As of Date)
                datasources = summary_data[i].get("datasources", [])
                ds_text = self._format_datasource_info(datasources)
                if ds_text:
                    pdf.set_font("helvetica", "B", 10)
                    pdf.write(0.2, "Data Source: ")
                    pdf.set_font("helvetica", "", 10)
                    pdf.write(0.2, f"{ds_text}\n\n")

                csv_data = summary_data[i].get('csv_data', '') if summary_data else ''
                insights = self._generate_ai_insights(image_path, dashboard_name, csv_data=csv_data)
                
                pdf.set_font("helvetica", "B", 12)
                pdf.cell(0, 0.3, "AI Insights", ln=1)
                pdf.ln(0.1)
                
                pdf.set_font("helvetica", "", 10)
                for insight in insights:
                    # Skip the first item if it's the title (already handled or will be)
                    # For this format, the list will contain [Title, Bullet1, Bullet2, Bullet3]
                    # Actually, let's keep it simple and just draw bullets for all but the first.
                    is_title = (insight == insights[0])
                    
                    if not is_title:
                        pdf.set_font("helvetica", "B", 10)
                        pdf.write(0.2, "• ")
                        pdf.set_font("helvetica", "", 10)

                    # Handle bolding in PDF (markdown style **bold**)
                    if '**' in insight:
                        parts = insight.split('**')
                        for i, part in enumerate(parts):
                            if i % 2 == 1:
                                pdf.set_font("helvetica", "B", 10)
                                pdf.write(0.2, part)
                                pdf.set_font("helvetica", "", 10)
                            else:
                                pdf.write(0.2, part)
                        pdf.write(0.2, "\n\n")
                    else:
                        pdf.write(0.2, f"{insight}\n\n")
                
                pdf.set_left_margin(0.5) # Reset margin

            pdf.output(output_path)
            logging.info(f"Successfully created detailed PDF: {output_path}")
            return output_path
        except Exception as e:
            logging.error(f"Failed to create detailed PDF: {str(e)}")
            return self.combine_to_pdf(image_paths, output_dir, filename)

    # ── Blend360 theme palette (matched from reference slide) ────────────────
    # Background: very dark navy #060C18
    # Primary teal: #00C4CC  (KPI numbers, borders, rule lines)
    # White: #FFFFFF          (main title, logo)
    # Slate: #94A3B8          (body text, labels)
    # Card bg: #0D1528        (panel fill)
    # Footer bg: #040A12      (darker strip)
    _B360_BG        = RGBColor(0x06, 0x0C, 0x18) if PPTX_AVAILABLE else None
    _B360_TEAL      = RGBColor(0x00, 0xC4, 0xCC) if PPTX_AVAILABLE else None
    _B360_TEAL_DIM  = RGBColor(0x00, 0x6E, 0x76) if PPTX_AVAILABLE else None
    _B360_WHITE     = RGBColor(0xFF, 0xFF, 0xFF) if PPTX_AVAILABLE else None
    _B360_LIGHT     = RGBColor(0xB0, 0xBE, 0xCE) if PPTX_AVAILABLE else None
    _B360_CARD      = RGBColor(0x0D, 0x15, 0x28) if PPTX_AVAILABLE else None
    _B360_FOOTER    = RGBColor(0x04, 0x0A, 0x12) if PPTX_AVAILABLE else None

    @staticmethod
    def _b360_bg_xml(slide):
        """Set slide background to Blend360 dark navy."""
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = RGBColor(0x06, 0x0C, 0x18)

    @staticmethod
    def _b360_add_rect(slide, x, y, w, h, rgb):
        """Solid filled rectangle with no border line."""
        sh = slide.shapes.add_shape(1, PPTInches(x), PPTInches(y), PPTInches(w), PPTInches(h))
        sh.fill.solid()
        sh.fill.fore_color.rgb = rgb
        sh.line.fill.background()
        return sh

    @staticmethod
    def _b360_add_box(slide, x, y, w, h, fill_rgb, border_rgb, border_pt=1.5):
        """Rectangle with solid fill AND a coloured border line."""
        from pptx.util import Pt as _Pt
        sh = slide.shapes.add_shape(1, PPTInches(x), PPTInches(y), PPTInches(w), PPTInches(h))
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill_rgb
        sh.line.color.rgb = border_rgb
        sh.line.width = _Pt(border_pt)
        return sh

    @staticmethod
    def _b360_text(slide, x, y, w, h, text, size, rgb,
                   bold=False, italic=False, align=PP_ALIGN.LEFT,
                   face="Calibri", wrap=True, margin_in=0.0):
        """Add text box. Returns (txb, tf, first_paragraph)."""
        txb = slide.shapes.add_textbox(PPTInches(x), PPTInches(y), PPTInches(w), PPTInches(h))
        tf  = txb.text_frame
        tf.word_wrap = wrap
        m = Emu(int(margin_in * 914400))
        tf.margin_top = tf.margin_bottom = tf.margin_left = tf.margin_right = m
        p   = tf.paragraphs[0]
        p.alignment = align
        run = p.add_run()
        run.text           = text
        run.font.size      = PPTPt(size)
        run.font.color.rgb = rgb
        run.font.bold      = bold
        run.font.italic    = italic
        run.font.name      = face
        return txb, tf, p

    def _b360_header(self, slide, slide_w=13.33, dashboard_name=""):
        """Standard Blend360 header: thin top teal bar, logo, right label, rule."""
        # Very thin teal line at top edge (matches reference)
        self._b360_add_rect(slide, 0, 0, slide_w, 0.045, self._B360_TEAL)
        # BLEND360 logo text
        self._b360_text(slide, 0.38, 0.10, 3.8, 0.42,
                        "BLEND360", 17, self._B360_WHITE,
                        bold=True, face="Arial Black")
        # Right label
        self._b360_text(slide, slide_w - 4.5, 0.15, 4.3, 0.30,
                        "DATA & ANALYTICS PRACTICE", 8, self._B360_TEAL,
                        align=PP_ALIGN.RIGHT, face="Arial")
        # Horizontal teal rule below header
        self._b360_add_rect(slide, 0.38, 0.60, slide_w - 0.76, 0.025, self._B360_TEAL)
        # Dashboard context line (content slides only)
        if dashboard_name:
            self._b360_text(slide, 0.55, 0.68, 10.0, 0.28,
                            f"RETAIL  |  DATA & ANALYTICS  —  {dashboard_name.upper()}",
                            7.5, self._B360_TEAL, face="Arial")

    def _b360_footer(self, slide, slide_w=13.33, slide_h=7.5, page_num=None):
        """Blend360 footer: dark strip, thin teal rule, confidentiality text, page number."""
        fh = 0.30
        self._b360_add_rect(slide, 0, slide_h - fh, slide_w, fh, self._B360_FOOTER)
        self._b360_add_rect(slide, 0, slide_h - fh, slide_w, 0.022, self._B360_TEAL_DIM)
        self._b360_text(slide, 0.38, slide_h - fh + 0.04, 8, 0.22,
                        "Confidential  |  Blend360  |  Data & Analytics Practice",
                        7.5, self._B360_LIGHT)
        if page_num is not None:
            self._b360_text(slide, slide_w - 1.2, slide_h - fh + 0.04, 1.0, 0.22,
                            str(page_num), 8, self._B360_LIGHT,
                            align=PP_ALIGN.RIGHT)

    def combine_to_pptx_with_details(self, image_paths: List[str], output_dir: str, filename: str, summary_data: List[Dict]) -> str:
        """Combine multiple images into a Blend360-themed PowerPoint presentation with AI insights."""
        if not PPTX_AVAILABLE:
            raise Exception("python-pptx is not installed")

        try:
            output_path = os.path.join(output_dir, f"{filename}.pptx")
            prs = Presentation()
            SLIDE_W, SLIDE_H = 13.33, 7.5
            prs.slide_width  = PPTInches(SLIDE_W)
            prs.slide_height = PPTInches(SLIDE_H)

            blank_layout = prs.slide_layouts[6]  # fully blank

            # ── Title / cover slide ───────────────────────────────────────────
            title_slide = prs.slides.add_slide(blank_layout)
            self._b360_bg_xml(title_slide)

            # Left teal accent bar
            self._b360_add_rect(title_slide, 0, 0, 0.07, SLIDE_H, self._B360_TEAL)

            # Header
            self._b360_header(title_slide, SLIDE_W)

            # Main title — two lines, well separated
            self._b360_text(
                title_slide, 0.55, 1.55, 9.0, 0.95,
                "DASHBOARD INSIGHTS",
                46, self._B360_WHITE,
                bold=True, face="Arial Black", align=PP_ALIGN.LEFT
            )
            # Teal accent rule under title
            self._b360_add_rect(title_slide, 0.55, 2.55, 3.5, 0.04, self._B360_TEAL)
            # Subtitle — clearly below
            self._b360_text(
                title_slide, 0.55, 2.70, 9.0, 0.48,
                "Automated Tableau Analytics Report",
                18, self._B360_TEAL,
                face="Calibri"
            )
            # Sub-line
            self._b360_text(
                title_slide, 0.55, 3.22, 9.0, 0.32,
                "From snapshot to insight \u2014 powered by AI",
                11.5, self._B360_LIGHT,
                italic=True, face="Calibri"
            )

            # KPI stat boxes (bottom left)
            stat_boxes = [
                ("DASHBOARDS",  str(len(image_paths)), 30),
                ("AI INSIGHTS", "\u2713 INCLUDED",      16),
                ("GENERATED",   datetime.now().strftime("%b %d, %Y"), 14),
            ]
            box_x, box_y, box_w, box_h, gap = 0.55, 5.10, 3.4, 1.10, 0.18
            for label, value, val_size in stat_boxes:
                # Card bg with full teal border
                self._b360_add_box(title_slide, box_x, box_y, box_w, box_h,
                                   self._B360_CARD, self._B360_TEAL, border_pt=1.2)
                # Teal top bar on card
                self._b360_add_rect(title_slide, box_x, box_y, box_w, 0.048, self._B360_TEAL)
                # Value
                self._b360_text(
                    title_slide, box_x + 0.15, box_y + 0.12, box_w - 0.3, 0.58,
                    value,
                    val_size, self._B360_TEAL,
                    bold=True, face="Arial Black"
                )
                # Label
                self._b360_text(
                    title_slide, box_x + 0.15, box_y + 0.72, box_w - 0.3, 0.28,
                    label,
                    8.5, self._B360_LIGHT,
                    face="Arial"
                )
                box_x += box_w + gap

            # Decorative right panel — dark card with teal left border
            self._b360_add_rect(title_slide, 9.55, 1.0, 3.45, 5.8, self._B360_CARD)
            self._b360_add_rect(title_slide, 9.55, 1.0, 0.048, 5.8, self._B360_TEAL)
            self._b360_text(
                title_slide, 9.72, 1.18, 3.1, 0.38,
                "WHAT'S INSIDE",
                8.5, self._B360_TEAL, bold=True,
                face="Arial", align=PP_ALIGN.LEFT
            )
            self._b360_add_rect(title_slide, 9.72, 1.60, 2.8, 0.022, self._B360_TEAL_DIM)
            self._b360_text(
                title_slide, 9.72, 1.72, 3.1, 5.0,
                "Each slide in this report includes:\n\n"
                "\u2023  Cropped dashboard view\n\n"
                "\u2023  Applied filter context\n\n"
                "\u2023  Data source & refresh date\n\n"
                "\u2023  AI-generated deep analysis:\n"
                "     KPIs, anomalies, trends,\n"
                "     risks & recommendations",
                10, self._B360_LIGHT,
                face="Calibri", wrap=True, margin_in=0.0
            )

            self._b360_footer(title_slide, SLIDE_W, SLIDE_H)

            # ── Content slides — one per dashboard image ──────────────────────
            for idx, image_path in enumerate(image_paths):
                if not os.path.exists(image_path):
                    continue

                slide = prs.slides.add_slide(blank_layout)
                self._b360_bg_xml(slide)

                sd = summary_data[idx] if summary_data and idx < len(summary_data) else {}
                dashboard_name = sd.get("dashboard", f"Dashboard {idx + 1}")
                applied_filters = sd.get("applied_filters", {})
                datasources     = sd.get("datasources", [])
                csv_data        = sd.get("csv_data", "")

                # Left teal accent bar
                self._b360_add_rect(slide, 0, 0, 0.07, SLIDE_H, self._B360_TEAL)

                # Header
                self._b360_header(slide, SLIDE_W, dashboard_name)

                # ── Image panel (left, 0.35→8.5") ────────────────────────────
                IMG_X, IMG_Y     = 0.35, 1.15
                IMG_MAX_W        = 8.15
                IMG_MAX_H        = SLIDE_H - IMG_Y - 0.55

                try:
                    with Image.open(image_path) as img_obj:
                        iw, ih = img_obj.size
                    aspect = ih / iw
                    img_w  = IMG_MAX_W
                    img_h  = img_w * aspect
                    if img_h > IMG_MAX_H:
                        img_h = IMG_MAX_H
                        img_w = img_h / aspect
                    # Centre vertically in available space
                    img_y_off = IMG_Y + (IMG_MAX_H - img_h) / 2
                    slide.shapes.add_picture(
                        image_path,
                        PPTInches(IMG_X), PPTInches(img_y_off),
                        width=PPTInches(img_w), height=PPTInches(img_h)
                    )
                except Exception as img_err:
                    logging.warning(f"Could not add image to slide: {img_err}")

                # ── Right insights panel (8.65→13.0") ────────────────────────
                PNL_X, PNL_Y = 8.65, 1.15
                PNL_W, PNL_H = SLIDE_W - PNL_X - 0.33, SLIDE_H - PNL_Y - 0.55

                # Card background
                self._b360_add_rect(slide, PNL_X, PNL_Y, PNL_W, PNL_H, self._B360_CARD)
                self._b360_add_rect(slide, PNL_X, PNL_Y, PNL_W, 0.045, self._B360_TEAL)

                cur_y = PNL_Y + 0.18

                # "AI INSIGHTS" label
                self._b360_text(
                    slide, PNL_X + 0.18, cur_y, PNL_W - 0.36, 0.32,
                    "AI INSIGHTS",
                    10, self._B360_TEAL,
                    bold=True, face="Arial Black"
                )
                cur_y += 0.35

                # Divider
                self._b360_add_rect(slide, PNL_X + 0.18, cur_y, PNL_W - 0.36, 0.018, self._B360_TEAL_DIM)
                cur_y += 0.1

                # Filters
                filter_text = self._format_filters(applied_filters)
                ds_text     = self._format_datasource_info(datasources)

                if filter_text:
                    self._b360_text(
                        slide, PNL_X + 0.18, cur_y, PNL_W - 0.36, 0.22,
                        f"Filters: {filter_text}",
                        8, self._B360_LIGHT,
                        face="Calibri", wrap=True
                    )
                    cur_y += 0.25

                if ds_text:
                    self._b360_text(
                        slide, PNL_X + 0.18, cur_y, PNL_W - 0.36, 0.22,
                        f"Source: {ds_text}",
                        8, self._B360_LIGHT,
                        face="Calibri", wrap=True
                    )
                    cur_y += 0.28

                # Divider before insights
                self._b360_add_rect(slide, PNL_X + 0.18, cur_y, PNL_W - 0.36, 0.018, self._B360_TEAL_DIM)
                cur_y += 0.12

                # AI insights
                try:
                    insights = self._generate_ai_insights(image_path, dashboard_name, csv_data=csv_data)
                    logging.info(f"Generated {len(insights)} insights for PPTX slide {idx + 1}")
                except Exception as ai_e:
                    logging.error(f"AI insights failed for slide {idx + 1}: {ai_e}")
                    insights = ["AI insights unavailable"]

                remaining_h = PNL_H - (cur_y - PNL_Y) - 0.15

                # Build insight text in a single wrapped text box
                insight_lines = []
                for i_idx, ins in enumerate(insights):
                    clean = ins.replace("**", "").strip()
                    if not clean:
                        continue
                    if i_idx == 0:
                        insight_lines.append(("title", clean))
                    else:
                        insight_lines.append(("bullet", clean))

                # Render title
                if insight_lines and insight_lines[0][0] == "title":
                    title_text = insight_lines[0][1]
                    self._b360_text(
                        slide, PNL_X + 0.18, cur_y, PNL_W - 0.36, 0.38,
                        title_text,
                        9.5, self._B360_WHITE,
                        bold=True, face="Calibri", wrap=True
                    )
                    cur_y += 0.41

                # Render each bullet individually for clean spacing
                bullet_items = [(kind, t) for kind, t in insight_lines if kind == "bullet"]
                for b_idx, (_, b_text) in enumerate(bullet_items):
                    # Strip leading bold label (e.g. "**KPI Performance:**") for display
                    clean_b = b_text.replace("**", "").strip()
                    avail_h = (PNL_Y + PNL_H - 0.12) - cur_y
                    if avail_h < 0.22:
                        break  # no more room
                    # Estimate height: ~0.16in per line at 8.5pt, avg ~60 chars per line
                    est_lines = max(1, len(clean_b) // 55 + 1)
                    box_h = min(est_lines * 0.175 + 0.05, avail_h)
                    self._b360_text(
                        slide, PNL_X + 0.14, cur_y, PNL_W - 0.28, box_h,
                        clean_b,
                        8.5, self._B360_LIGHT,
                        face="Calibri", wrap=True
                    )
                    cur_y += box_h + 0.04
                    # Thin separator between bullets
                    if b_idx < len(bullet_items) - 1 and (PNL_Y + PNL_H - 0.12) - cur_y > 0.1:
                        self._b360_add_rect(slide, PNL_X + 0.14, cur_y, PNL_W - 0.28, 0.010, self._B360_TEAL_DIM)
                        cur_y += 0.04

                self._b360_footer(slide, SLIDE_W, SLIDE_H)

            prs.save(output_path)
            logging.info(f"Successfully created Blend360-themed PPTX: {output_path}")
            return output_path

        except Exception as e:
            logging.error(f"Failed to create PPTX: {str(e)}", exc_info=True)
            raise Exception(f"PPTX creation failed: {str(e)}")
    
    def combine_to_word(self, image_paths: List[str], output_dir: str, filename: str) -> str:
        """Combine multiple images into a single Word document"""
        try:
            output_path = os.path.join(output_dir, f"{filename}.docx")
            
            # Create new Word document
            doc = Document()
            doc.add_heading('Tableau Dashboard Export', 0)
            
            for i, image_path in enumerate(image_paths):
                if not os.path.exists(image_path):
                    logging.warning(f"Image not found: {image_path}")
                    continue
                
                # Add section heading
                doc.add_heading(f'Dashboard {i + 1}', level=1)
                
                # Add image to document
                # Calculate appropriate width (max 6 inches)
                image = Image.open(image_path)
                aspect_ratio = image.height / image.width
                width = min(6.0, image.width / 100)  # Convert pixels to inches roughly
                height = width * aspect_ratio
                
                doc.add_picture(image_path, width=Inches(width))
                
                # Add page break if not the last image
                if i < len(image_paths) - 1:
                    doc.add_page_break()
            
            # Save document
            doc.save(output_path)
            
            logging.info(f"Successfully created Word document: {output_path}")
            return output_path
            
        except Exception as e:
            logging.error(f"Failed to combine images to Word: {str(e)}")
            raise Exception(f"Word document creation failed: {str(e)}")
    
    def combine_to_word_with_details(self, image_paths: List[str], output_dir: str, filename: str, summary_data: List[Dict]) -> str:
        """Combine multiple images into a single Word document with detailed metadata using 2-column layout"""
        try:
            output_path = os.path.join(output_dir, f"{filename}.docx")
            
            # Create new Word document
            doc = Document()
            
            # Add main title
            title = doc.add_heading('Tableau Dashboard Export Report', 0)
            title.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            # Export Summary removed as per request
            
            # Process dashboards in pairs for same-page layout
            for i in range(0, len(image_paths), 2):
                # Add page heading for dashboard(s)
                # Headers removed as per request
                # if i + 1 < len(image_paths):
                #     page_title = f'Dashboards {i + 1} & {i + 2}'
                # else:
                #     page_title = f'Dashboard {i + 1}'
                
                # doc.add_heading(page_title, level=1)
                
                # First dashboard
                self._add_dashboard_to_word(doc, image_paths[i], summary_data[i], i + 1)
                
                # Second dashboard on same page (if exists)
                if i + 1 < len(image_paths):
                    # Add some spacing between dashboards
                    doc.add_paragraph()
                    self._add_dashboard_to_word(doc, image_paths[i + 1], summary_data[i + 1], i + 2)
                
                # Add page break if not the last pair
                if i + 2 < len(image_paths):
                    doc.add_page_break()
            
            # Save document
            doc.save(output_path)
            
            logging.info(f"Successfully created detailed Word document: {output_path}")
            return output_path
            
        except Exception as e:
            logging.error(f"Failed to combine images to Word with details: {str(e)}")
            raise Exception(f"Detailed Word document creation failed: {str(e)}")
    
    def _add_dashboard_to_word(self, doc, image_path: str, data: Dict, section_num: int):
        """Add a single dashboard to Word document with 2-column layout"""
        try:
            if not os.path.exists(image_path):
                logging.warning(f"Image not found: {image_path}")
                return
            
            # Create a table for 2-column layout
            table = doc.add_table(rows=1, cols=2)
            # Remove table borders
            # table.style = 'Table Grid'
            
            # Set column widths (50% each)
            for cell in table.rows[0].cells:
                cell.width = Inches(3.25)  # Half of 6.5 inch page width
            
            # Left column - Image
            left_cell = table.rows[0].cells[0]
            left_para = left_cell.paragraphs[0]
            
            # Add image to left cell
            image = Image.open(image_path)
            img_width = image.width
            img_height = image.height
            aspect_ratio = img_height / img_width
            
            # Set image width to fit in left column (3 inches max)
            img_width_inches = 3.0
            
            run = left_para.runs[0] if left_para.runs else left_para.add_run()
            run.add_picture(image_path, width=Inches(img_width_inches))
            
            # Right column - Metadata
            right_cell = table.rows[0].cells[1]
            right_para = right_cell.paragraphs[0]
            
            # Metadata and headers removed as per request. Only showing AI insights.
            
            # Add Applied Filters metadata
            applied_filters = data.get("applied_filters", {})
            filter_text = self._format_filters(applied_filters)
            
            if filter_text:
                p_filt = right_cell.add_paragraph()
                run_f_label = p_filt.add_run("Applied Filters: ")
                run_f_label.bold = True
                run_f_label.font.size = Pt(10)
                run_f_val = p_filt.add_run(filter_text)
                run_f_val.font.size = Pt(10)
                p_filt.paragraph_format.space_after = Pt(6)

            # Add Data Source info (As of Date)
            datasources = data.get("datasources", [])
            ds_text = self._format_datasource_info(datasources)
            if ds_text:
                p_ds = right_cell.add_paragraph()
                run_ds_label = p_ds.add_run("Data Source: ")
                run_ds_label.bold = True
                run_ds_label.font.size = Pt(10)
                run_ds_val = p_ds.add_run(ds_text)
                run_ds_val.font.size = Pt(10)
                p_ds.paragraph_format.space_after = Pt(12)

            # Generate and add AI insights if enabled
            if self.gemini_client or self.anthropic_client:
                try:
                    csv_data = data.get('csv_data', '')
                    schema_info = data.get('schema_info', '')
                    logging.info(f"Generating AI insights for dashboard {section_num} (CSV data: {len(csv_data)} chars, Schema info: {len(schema_info)} chars)...")
                    insights = self._generate_ai_insights(image_path, data.get("dashboard", f"Dashboard {section_num}"), csv_data=csv_data, schema_info=schema_info)
                    
                    for idx, insight in enumerate(insights):
                        is_title = (idx == 0)
                        p = right_cell.add_paragraph()
                        
                        if is_title:
                            run = p.add_run(insight)
                            run.bold = True
                            run.font.size = Pt(14)
                            p.paragraph_format.space_after = Pt(12)
                        else:
                            # Add bullet for non-title items
                            p.add_run('• ').bold = True
                            
                            if '**' in insight:
                                parts = insight.split('**')
                                for i, part in enumerate(parts):
                                    run = p.add_run(part)
                                    if i % 2 == 1: # Odd parts were between **
                                        run.bold = True
                            else:
                                p.add_run(insight)
                            
                            # Standard padding
                            p.paragraph_format.space_after = Pt(8)
                    
                    logging.info(f"Successfully added {len(insights)} insights to dashboard {section_num}")
                except Exception as ai_error:
                    logging.warning(f"Failed to generate AI insights for dashboard {section_num}: {ai_error}")
                    # Continue without insights - don't fail the entire document
            
            # Set vertical alignment for cells
            left_cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            right_cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            
            logging.info(f"Added dashboard {section_num} to Word document in 2-column layout")
            
        except Exception as img_error:
            logging.error(f"Failed to add dashboard {section_num}: {str(img_error)}")
            # Add error message instead
            error_para = doc.add_paragraph()
            error_para.add_run(f'[Error loading Dashboard {section_num}: {os.path.basename(image_path)}]').italic = True
    
    def create_thumbnail(self, image_path: str, max_width: int = 200, max_height: int = 120) -> str:
        """Create a thumbnail of an image"""
        try:
            image = Image.open(image_path)
            
            # Calculate thumbnail size maintaining aspect ratio
            image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            # Generate thumbnail filename
            base_name = os.path.splitext(os.path.basename(image_path))[0]
            thumb_path = os.path.join(os.path.dirname(image_path), f"{base_name}_thumb.png")
            
            # Save thumbnail
            image.save(thumb_path, "PNG")
            
            logging.info(f"Successfully created thumbnail: {thumb_path}")
            return thumb_path
            
        except Exception as e:
            logging.error(f"Failed to create thumbnail: {str(e)}")
            raise Exception(f"Thumbnail creation failed: {str(e)}")
    
    def cleanup_temp_files(self):
        """Clean up any temporary files created during processing"""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
        self.temp_files.clear()
    
    def _generate_ai_insights(self, image_path: str, dashboard_name: str, csv_data: str = '', schema_info: str = '') -> List[str]:
        """
        Generate executive AI insights combining the cropped dashboard image with the
        underlying CSV data.  When CSV data is present it is the PRIMARY source of
        truth for all numbers; the image provides visual / structural context only.
        """
        # Use configured provider
        if self.anthropic_client and (config.AI_PROVIDER == "anthropic" or not self.gemini_client):
            return self._generate_anthropic_insights(image_path, dashboard_name, csv_data, schema_info)
        
        if not self.gemini_client:
            return ["AI insights generation failed", "No AI provider configured."]
            
        try:
            pil_image = PILImage.open(image_path)
            has_data = bool(csv_data and csv_data.strip())
            has_schema = bool(schema_info and schema_info.strip())

            if has_data:
                schema_block = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DATA SOURCE / SCHEMA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{schema_info.strip()}
""" if has_schema else ''

                prompt = f"""You are a Chief Analytics Officer delivering a deep executive intelligence briefing.
You have TWO complementary inputs — the raw data is the PRIMARY truth for all numbers.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INPUT 1 — RAW DATA (primary source of truth)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{csv_data.strip()}
{schema_block}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INPUT 2 — DASHBOARD VISUALIZATION (attached image)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Use the image for: chart type, axis labels, color coding, groupings, visual spikes.
Do NOT read numbers from the image — use Input 1 for all figures.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ANALYSIS REQUIRED (all 5 dimensions — mandatory)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. KPI PERFORMANCE — compute totals, growth rates, averages; identify top & bottom performers with exact figures.
2. ANOMALY DETECTION — find statistical outliers, sudden drops/spikes, values deviating >15% from trend; explain the likely cause.
3. TREND ANALYSIS — identify directional momentum (accelerating / decelerating / reversal); quantify the trend slope where possible.
4. BUSINESS RISK — what is the single biggest risk this data reveals? Tie it to a specific number.
5. STRATEGIC RECOMMENDATION — what ONE concrete action should leadership take in the next 30 days? Be specific, not generic.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT (return exactly this, no extra text)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
<TITLE>
6-10 word strategic title capturing the single dominant insight
</TITLE>

<BULLET_1>
**KPI Performance:** [Top/bottom performers with exact numbers. Growth rate vs prior period. Which segment leads and by how much.] ≤ 60 words.
</BULLET_1>

<BULLET_2>
**Anomaly:** [Specific outlier or spike — name the exact value, when it occurred, how far it deviates from the norm, and probable cause.] ≤ 60 words.
</BULLET_2>

<BULLET_3>
**Trend:** [Direction and momentum — is performance accelerating or decelerating? Quantify. Highlight any inflection point visible in both data and chart.] ≤ 60 words.
</BULLET_3>

<BULLET_4>
**Risk:** [The biggest business risk this data exposes. Cite the specific metric and threshold that triggers concern. Consequences if unaddressed.] ≤ 60 words.
</BULLET_4>

<BULLET_5>
**Recommendation:** [One concrete, time-bound action for leadership. Reference the specific data point driving this urgency. What to do, who owns it, by when.] ≤ 60 words.
</BULLET_5>

TONE: Confident, decisive, zero filler words. Every sentence must contain at least one specific number or metric name."""

            else:
                # ── IMAGE-ONLY PROMPT (no CSV available) ────────────────────────
                prompt = """You are a Chief Analytics Officer delivering a deep executive intelligence briefing
from a Tableau dashboard screenshot.

ANALYSE ALL 5 DIMENSIONS:
1. KPI PERFORMANCE — read visible metrics; identify top and bottom performers with exact figures shown.
2. ANOMALY DETECTION — find any bar, line, or value that stands out dramatically from the rest; explain the likely cause.
3. TREND ANALYSIS — identify directional momentum visible in the chart; is it accelerating or decelerating?
4. BUSINESS RISK — what is the single biggest risk this dashboard reveals?
5. STRATEGIC RECOMMENDATION — one concrete action for leadership in the next 30 days.

OUTPUT FORMAT (return exactly this, no extra text):
<TITLE>
6-10 word strategic title capturing the dominant insight
</TITLE>

<BULLET_1>
**KPI Performance:** [Top/bottom performers with specific visible figures. Which metric leads and by how much.] ≤ 60 words.
</BULLET_1>

<BULLET_2>
**Anomaly:** [Specific outlier — name the exact value or bar, how far it deviates, probable cause.] ≤ 60 words.
</BULLET_2>

<BULLET_3>
**Trend:** [Direction and momentum visible in the chart. Any inflection point or reversal.] ≤ 60 words.
</BULLET_3>

<BULLET_4>
**Risk:** [Biggest business risk this dashboard exposes. Cite the specific metric driving the concern.] ≤ 60 words.
</BULLET_4>

<BULLET_5>
**Recommendation:** [One concrete, time-bound action for leadership based on what this dashboard shows.] ≤ 60 words.
</BULLET_5>

TONE: Confident, decisive, zero filler words."""

            # Send image AFTER the prompt so the model reads data first, uses
            # the image only for label/layout context.
            
            # Retry logic and Model Fallback for 429/404 errors
            # We prioritize GEMINI_MODEL from config, but will fallback if needed
            fallback_models = [GEMINI_MODEL, 'gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.0-flash']
            # Deduplicate while preserving order
            models_to_try = []
            for m in fallback_models:
                if m not in models_to_try:
                    models_to_try.append(m)
            
            logging.info(f"AI EXECUTION: Attempting insights using model sequence: {models_to_try}")
            print(f"\n[AI DEBUG] Models to try: {models_to_try}")
                    
            max_retries_per_model = 2  # Reduced from 5 — fast fail and move to next model
            retry_delay = 5            # Reduced from 10
            response = None
            last_error = Exception("All Gemini models failed")

            for model_name in models_to_try:
                for attempt in range(max_retries_per_model):
                    try:
                        logging.info(f"Attempting AI insights with model: {model_name} (Attempt {attempt+1}/{max_retries_per_model})")
                        response = self.gemini_client.models.generate_content(
                            model=model_name,
                            contents=[prompt, pil_image]
                        )
                        break # Success with this model!
                    except Exception as e:
                        last_error = e
                        error_msg = str(e).lower()

                        # Handle 404 (Model not found) - try next model immediately
                        if "404" in error_msg or "not_found" in error_msg:
                            logging.warning(f"Model {model_name} not found (404). Trying fallback...")
                            break # Break retry loop to try next model

                        # Handle 429 (Rate limit)
                        if ("429" in error_msg or "resource_exhausted" in error_msg):
                            if attempt < max_retries_per_model - 1:
                                wait_time = retry_delay * (attempt + 1)  # Fixed: was *2, now linear backoff
                                msg = f"Rate limit hit for {model_name}. Waiting {wait_time}s... (Attempt {attempt+1}/{max_retries_per_model})"
                                logging.warning(msg)
                                print(f"\n[AI INSIGHTS] {msg}")
                                time.sleep(wait_time)
                                continue
                            else:
                                logging.warning(f"Rate limit persisted for {model_name}. Trying fallback...")
                                break # Try next model

                        # Other errors - try next model
                        logging.error(f"Error with {model_name}: {str(e)}. Trying fallback...")
                        break
                
                if response:
                    break # Success!
                    
            if not response:
                error_summary = f"All Gemini models {models_to_try} failed. Last error: {str(last_error)}"
                logging.error(error_summary)
                raise Exception(error_summary)

            raw = response.text.strip()

            # ── Parse structured XML-like tags ────────────────────────────────
            import re
            def extract_tag(tag, text):
                m = re.search(rf'<{tag}>(.*?)</{tag}>', text, re.DOTALL)
                return m.group(1).strip() if m else None

            title   = extract_tag('TITLE',    raw)
            bullet1 = extract_tag('BULLET_1', raw)
            bullet2 = extract_tag('BULLET_2', raw)
            bullet3 = extract_tag('BULLET_3', raw)
            bullet4 = extract_tag('BULLET_4', raw)
            bullet5 = extract_tag('BULLET_5', raw)

            if title and bullet1:
                insights = [title]
                for b in (bullet1, bullet2, bullet3, bullet4, bullet5):
                    if b:
                        insights.append(b)
                return insights[:6]

            # ── Fallback: plain-line parsing (handles non-tagged responses) ───
            lines = [l.strip() for l in raw.split('\n') if l.strip()]
            insights = []
            if lines:
                insights.append(lines[0].lstrip('•-*#1234. ').strip())
                for line in lines[1:]:
                    clean = line.lstrip('•-*#1234. ').strip()
                    if clean:
                        insights.append(clean)

            return insights[:4] if insights else ["Insight Summary unavailable"]

        except Exception as e:
            logging.error(f"Failed to generate AI insights: {str(e)}")
            return ["AI insights generation failed", f"Error: {str(e)}", "Please check your Gemini API key and quota."]

    def _generate_anthropic_insights(self, image_path: str, dashboard_name: str, csv_data: str = '', schema_info: str = '') -> List[str]:
        """Generate insights using Anthropic Claude"""
        try:
            with open(image_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
            prompt = f"Analyze this dashboard: {dashboard_name}. Data: {csv_data}. Schema: {schema_info}. Provide 5 bullet points (KPI, Anomaly, Trend, Risk, Recommendation)."
            
            message = self.anthropic_client.messages.create(
                model=config.ANTHROPIC_MODEL,
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_data}},
                        {"type": "text", "text": prompt}
                    ]
                }]
            )
            return message.content[0].text.split('\n')
        except Exception as e:
            error_msg = str(e)
            logging.error(f"Anthropic insights failed: {error_msg}")
            # Identify specific errors
            if "Authentication" in error_msg or "401" in error_msg:
                return ["Anthropic Authentication Failed", "Please check your API key in config.py."]
            if "Resource" in error_msg or "429" in error_msg:
                return ["Claude Rate Limit Hit", "Your current tier allows 5 requests per minute. Please wait."]
            return ["Anthropic insights generation failed", f"Error: {error_msg[:100]}..."]

    def vision_classifier(self, image_path: str) -> str:
        """AI Vision: Identify the dashboard type and business context"""
        if not self.gemini_client:
            return "Classification Unavailable (AI Disabled)"
        
        try:
            pil_image = PILImage.open(image_path)
            prompt = "Analyze this Tableau dashboard image. Identify the primary industry (e.g., Sales, Finance, Supply Chain) and the intended audience (e.g., Executive, Operational). Return a single concise string like 'Executive Sales Dashboard'."
            
            response = self.gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[prompt, pil_image]
            )
            return response.text.strip()
        except Exception as e:
            logging.error(f"Vision Classifier failed: {e}")
            return "Unknown Dashboard Type"

    def vision_dashboard_analyze(self, image_path: str) -> List[str]:
        """AI Vision: Discover all worksheet names and visual components visible in the image"""
        if not self.gemini_client:
            return []
            
        try:
            pil_image = PILImage.open(image_path)
            prompt = """Analyze the attached Tableau dashboard image.
Extract the names of all individual worksheets, charts, or data tables visible in this dashboard.
Return ONLY a JSON list of strings. No other text.

Example Output:
["Sheet 1", "Product Sales", "Trend Line"]
"""
            response = self.gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[prompt, pil_image]
            )
            
            text = response.text.strip()
            # Try to extract JSON list
            if "[" in text and "]" in text:
                import json
                start = text.find("[")
                end = text.rfind("]") + 1
                try:
                    names = json.loads(text[start:end])
                    return list(set(names))
                except:
                    pass
            
            # Fallback to line-by-line if JSON fails
            lines = [l.strip().lstrip('•-1234. ') for l in text.split('\n') if l.strip()]
            return list(set(lines)) # Deduplicate
        except Exception as e:
            logging.error(f"Vision Dashboard Analyze failed: {e}")
            return []

    def vision_image_segment(self, image_path: str) -> Dict[str, Any]:
        """AI Vision: Segment the image into logical layout areas (Classic CV + AI)"""
        try:
            # Load with OpenCV for segmentation
            img = cv2.imread(image_path)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Simple thresholding to find boundaries
            _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            segments = []
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                if w > 50 and h > 50: # Filter noise
                    segments.append({'x': x, 'y': y, 'w': w, 'h': h})
            
            # Use AI to describe the overall layout
            layout_desc = "Standard Grid"
            if self.gemini_client:
                pil_image = PILImage.open(image_path)
                prompt = "Describe the layout of this dashboard in 10 words (e.g., 'Two-column layout with header and three charts below')."
                resp = self.gemini_client.models.generate_content(model=GEMINI_MODEL, contents=[prompt, pil_image])
                layout_desc = resp.text.strip()
                
            return {
                'segment_count': len(segments),
                'layout_description': layout_desc,
                'raw_segments': segments[:10] # Top 10 for info
            }
        except Exception as e:
            logging.error(f"Vision Image Segment failed: {e}")
            return {'error': str(e)}
