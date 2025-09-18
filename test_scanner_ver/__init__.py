# scanner/__init__.py

from .main import main
from .ocr_utils import fallback_table_extraction, comparing_tables
from .image_utils import img_to_pdf
from .excel_utils import save_multiple_to_excel

__all__ = [
    "main",
    "fallback_table_extraction",
    "comparing_tables",
    "img_to_pdf",
    "save_multiple_to_excel",
]
