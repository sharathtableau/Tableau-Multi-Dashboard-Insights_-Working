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
    logging.info(f"AI CONFIG: Primary Model={GEMINI_MODEL}, Provider={getattr(config, 'AI_PROVIDER', 'gemini')}")
except ImportError:
    import os
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    GEMINI_MODEL = "gemini-2.0-flash"
    ENABLE_AI_INSIGHTS = False
    logging.warning("config.py not found or incomplete. Using fallbacks.")

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
