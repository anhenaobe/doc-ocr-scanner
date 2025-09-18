import pytesseract, logging, cv2
from PIL import Image
import numpy as np
from functools import partial
from multiprocessing import Pool
from .image_utils import multiprocesing_, img_to_pdf
import pandas as pd
import hashlib
import re
from pathlib import Path


def open_cv_image_process(image_path):
    '''opens an image with open cv and processes it with gray scale, binarization and denoising'''
    try:    
        img = cv2.imread(str(image_path))
        if img is None:
            logging.error(f"Image could not be loaded: {image_path}")
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        binarized = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 10)
        denoised = cv2.fastNlMeansDenoising(binarized, h=10, templateWindowSize=7, searchWindowSize=21)
        return denoised
    except Exception as e:
        logging.error(f"Error processing image {image_path}: {e}")
        return None

def detect_skew_and_lines(image):
    """ Detects skew and lines in the image using Canny edge detection and Hough Transform. """
    edges = cv2.Canny(image, 100, 200)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
    if lines is None:
        return 0 
    angles = []
    for rho, theta in lines[:,0]:
        angle = (theta * 180 / np.pi) - 90
        angles.append(angle)
    median_angle = np.median(angles)
    return median_angle

def rotate_image(image, angle):
    """ Rotates the image by the given angle. """
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, 
                             borderMode=cv2.BORDER_REPLICATE)
    return rotated

def process_image(image_path, language):
    """
    opens an image, processes it with OpenCV, detects skew and corrects it,
    then runs OCR using Tesseract and returns the extracted text in lowercase.
    """
    if not image_path.exists():
        logging.error(f"Image {image_path} does not exist.")
        return ""
    if not image_path.is_file():
        logging.error(f"Image {image_path} is not a file.")
        return ""
    pipline = open_cv_image_process(image_path)
    if pipline is None:
        return ""
    skew_angle = detect_skew_and_lines(pipline)
    open_cv_image = pipline
    if abs(skew_angle) > 1:
        open_cv_image = rotate_image(pipline, skew_angle)
    try:
        pil_image = Image.fromarray(open_cv_image)
        text = pytesseract.image_to_string(pil_image, lang=language)
        return text.lower().strip()
    except pytesseract.TesseractError:
        logging.error(f"Error processing image {image_path} with Tesseract.")
        return ""
    except Exception as e:
        logging.error(f"Error converting image {image_path} to PIL Image: {e}")
        return ""


def fallback_table_extraction(image_path):
    """
    Return a dictionary with table extraction results using different "flavors":
      {
        "camelot_lattice": [...],
        "camelot_stream": [...],
        "tabula_lattice": [...],
        "tabula_stream": [...]
      }

    Guarantees:
    - Always returns a dict with the four keys, each containing a list (possibly empty).
    - If the input is an image, it will be converted to PDF via img_to_pdf().
    - If the PDF is detected as scanned (image-only), Camelot is skipped.
    - Any internal failure returns empty lists instead of None.
    """
    searching_files_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif')

    tables_camelot_lattice, tables_camelot_stream = [], []
    tables_tabula_lattice, tables_tabula_stream = [], []
    pdf_path = None

    try:
        image_path = Path(image_path)
        if image_path.suffix.lower() in searching_files_extensions:
            img_to_pdf(image_path, str(image_path.with_suffix('.pdf')))
            pdf_path = image_path.with_suffix('.pdf')
        elif image_path.suffix.lower() == '.pdf':
            pdf_path = image_path
        else:
            logging.warning("Unsupported file type for fallback_table_extraction: %s", image_path)
            return {
                "camelot_lattice": [],
                "camelot_stream": [],
                "tabula_lattice": [],
                "tabula_stream": []
            }
    except Exception as e:
        logging.error("Error converting %s to PDF: %s", image_path, e)
        return {
            "camelot_lattice": [],
            "camelot_stream": [],
            "tabula_lattice": [],
            "tabula_stream": []
        }
    try:
        scanned = is_scanned_pdf(pdf_path)
    except Exception as e:
        logging.warning("is_scanned_pdf failed for %s: %s", pdf_path, e)
        scanned = False
    if not scanned:
        try:
            import camelot
            tables_camelot_lattice = camelot.read_pdf(str(pdf_path), pages='all', flavor='lattice') or []
            tables_camelot_stream  = camelot.read_pdf(str(pdf_path), pages='all', flavor='stream')  or []
        except Exception as e:
            logging.error("Error extracting tables with Camelot for %s: %s", pdf_path, e)
            tables_camelot_lattice, tables_camelot_stream = [], []
    else:
        logging.info("%s appears to be scanned (image-only); skipping Camelot.", pdf_path.name)

    # 4) Always try Tabula (returns list of DataFrames)
    try:
        import tabula
        tables_tabula_lattice = tabula.read_pdf(str(pdf_path), pages='all', multiple_tables=True, lattice=True) or []
        tables_tabula_stream  = tabula.read_pdf(str(pdf_path), pages='all', multiple_tables=True, stream=True)  or []
    except Exception as e:
        logging.error("Error extracting tables with Tabula for %s: %s", pdf_path, e)
        tables_tabula_lattice, tables_tabula_stream = [], []

    return {
        "camelot_lattice": tables_camelot_lattice,
        "camelot_stream": tables_camelot_stream,
        "tabula_lattice": tables_tabula_lattice,
        "tabula_stream": tables_tabula_stream
    }

def _normalize_dataframe_for_signature(df):
    """
    Normalize a DataFrame to a compact representation used to generate a signature.
    - Convert all values to str, strip repeated whitespace and lowercase.
    - Limit to the first N rows to keep signature creation fast and memory-friendly.
    """
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(df)
    df = df.fillna('').astype(str)
    df = df.applymap(lambda x: re.sub(r'\s+', ' ', x).strip().lower())
    N = 8  # sample rows to build the signature (trade-off between speed and uniqueness)
    df_small = df.head(N)
    return df_small

def comparing_tables(tables_list):
    """
    Receive a list of tables (Camelot Table objects or pandas.DataFrame objects).
    Return a list of unique tables (keeping original object types).
    - Handles None or empty input by returning [].
    - Uses a compact signature (columns + first N rows) to detect duplicates efficiently.
    """
    if not tables_list:
        return []

    unique_tables = []
    seen_signatures = set()

    for table in tables_list:
        try:
            df = table.df if hasattr(table, 'df') else table
            df_norm = _normalize_dataframe_for_signature(df)
            columns_sig = tuple(map(lambda c: str(c).strip().lower(), df_norm.columns.tolist()))
            rows_sig = tuple(tuple(row) for row in df_norm.values.tolist())
            signature = (columns_sig, rows_sig)
            sig_hash = hashlib.md5(repr(signature).encode('utf-8')).hexdigest()
        except Exception as e:
            logging.debug("Normalization/signature failed for a table: %s", e)
            sig_hash = hashlib.md5(repr(table).encode('utf-8')).hexdigest()

        if sig_hash not in seen_signatures:
            seen_signatures.add(sig_hash)
            unique_tables.append(table)

    return unique_tables

def run_clean_and_ocr(image_paths, language):
    """
    runs image cleaning and OCR processing.
    Returns a list of texts extracted from the images.
    Uses multiprocessing for efficiency.
    """
    try:
        multiprocesing_(image_paths, process_image)
    except Exception as e:
        logging.warning(f"Error during cleaning_images multiprocessing: {e}")
    process_image_with_lang = partial(process_image, language=language)
    texts = multiprocesing_(image_paths, process_image_with_lang)
    return texts

def is_scanned_pdf(pdf_path):
    """
    Verifes if a PDF is scanned by checking if it contains text.
    Returns True if the PDF is scanned (i.e., contains no text), otherwise False.
    Uses PyMuPDF to extract text from the first page.
    """
    try:
        import fitz  
        pdf_path = str(pdf_path)  
        doc = fitz.open(pdf_path)
        text = doc[0].get_text("text").strip()
        doc.close()
        return len(text) == 0
    except Exception as e:
        logging.warning(f"Pdf could not be analized: {e}")
        return False  