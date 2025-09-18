import pytesseract, logging, sys, os,shutil, argparse, json
from pathlib import Path
from PIL import Image
from .search_utils import chained_search, serial_number, folder_path, existing_files
from .image_utils import images, pdf_temporal_images, get_files_name
from .ocr_utils import fallback_table_extraction, comparing_tables
from multiprocessing import cpu_count, Pool   

def cleaning_images(image_name):
    if not Path(image_name).exists():
        logging.error(f"Image {image_name} does not exist.")
        return
    with Image.open(image_name) as img:
        umbrella = img.convert('L') 
        umbrella = umbrella.point(lambda x: 0 if x < 128 else 255)
        umbrella.save(image_name, 'PNG')

def setup_tesseract():
    """configurates tesseract path automatically based on the platform."""
    try:
        if sys.platform.startswith('win'):
            pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        else:
            pytesseract.pytesseract.tesseract_cmd = 'tesseract'
    except Exception as e:
        logging.warning(f"tesseract could not be configurated: {e}")

def parse_cli_args():
    """Parse the command line arguments. and return them along with all keywords."""
    parser = argparse.ArgumentParser(description='Image processing and data extraction tool.')
    parser.add_argument('-g', '--language', type=str, default='spa', help='Language for OCR processing (default: spa).')
    parser.add_argument('-l','--location', type=str, required=True, help="User's Directory. Some common directories are: Desktop,Documents, Downloads, Pictures, Music, Videos")
    parser.add_argument('-f', '--folder', type=str, required=True, help='Name of the folder containing files.')
    parser.add_argument('-e', '--excel', type=str, required=True, help='Name of the output Excel file.')
    parser.add_argument('-s', '--searching-serials', action='store_true', help='Enable serial number searching.')
    parser.add_argument('-x', '--extra_terms', type=str, default=None, help='Additional search terms to include, separated by commas.')
    parser.add_argument('-n', '--n_terms', type=int, default=0, required=True, help='Amount of terms thath might appear between the searched word and it\'s value')
    parser.add_argument('-v', '--devolution', action='store_true', help='Enable devolution mode to see the chain of terms found.')
    parser.add_argument('-q', '--quiet', action='store_true', help='Run in quiet mode (only errors will be shown).')
    all_keywords = load_keywords('keywords.json')
    doc_types = list(all_keywords.keys())
    parser.add_argument('-d', '--doc-type', type=str, required=True, choices=doc_types, help='The type of document to process (e.g., facturas, recibos).')
    args = parser.parse_args()
    return args, all_keywords

def load_keywords(file_name="keywords.json"):
    """
    Loads keywords from a JSON file and returns them as a dictionary.
    Compatible with both .py execution and PyInstaller .exe builds.
    """
    try:
        file_path = resource_path(file_name)
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f) 
    except Exception as e:
        logging.error(f"Error loading keywords from {file_name}: {e}")
        return {}
    
def resource_path(relative_path: str) -> str:
    """
    Get absolute path to resource, works for dev and for PyInstaller bundle.
    """
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def get_search_terms(args, all_keywords):
    """
    Build the list of search terms from the doc type and extra terms.
    - If JSON usa dict ({"nit": [...], "total": [...]}) → devuelve las keys.
    - If JSON usa lista (["nit", "total"]) → devuelve la lista tal cual.
    - Extra terms se agregan siempre al final.
    """
    if not isinstance(all_keywords, dict):
        logging.warning("all_keywords is not a dict; defaulting to empty dict.")
        all_keywords = {}

    doc_type = getattr(args, "doc_type", None)
    doc_patterns = all_keywords.get(doc_type, {})

    if isinstance(doc_patterns, dict):
        terms = list(doc_patterns.keys())
    elif isinstance(doc_patterns, list):
        terms = doc_patterns[:]  # copia directa
    else:
        terms = []

    print(f"Searching terms for '{doc_type}': {terms}")

    # Agregar extra terms desde CLI
    extra_terms_value = getattr(args, "extra_terms", None)
    if extra_terms_value:
        extra_terms_list = [term.strip() for term in extra_terms_value.split(",") if term.strip()]
        terms.extend(extra_terms_list)
        print(f"Final searching terms (from CLI): {terms}")

    return terms

def prepare_folder_and_files(location, folder):
    """
    Validates, creates the folder and retrieves image names.
    Returns the working folder path and a list of copied image paths.
    Raises FileNotFoundError if the folder does not exist or is empty.
    """
    parent_folder = folder_path(location, folder)
    parent_folder = existing_files(parent_folder)

    if parent_folder is None or not Path(parent_folder).exists():
        raise FileNotFoundError(f"Folder path {parent_folder} does not exist or could not be created, or is empty.")

    files_name = get_files_name(parent_folder)
    if not files_name:
        raise FileNotFoundError(f"No files found in folder {parent_folder}.")
    working_dir = parent_folder / "working_folder"
    working_dir.mkdir(exist_ok=True)
    copied_files = []
    for file in files_name:
        src = Path(parent_folder) / file
        dst = working_dir / file
        shutil.copy(src, dst)
        copied_files.append(dst)
    converted_files = images(working_dir)
    logging.info(f"Files to be processed: {converted_files}")
    return working_dir, converted_files

def paths_from_names(folder_path_, image_names):
    """Converts image names to full paths."""
    return [folder_path_ / image_name for image_name in image_names]

def extract_data_from_docs(image_names, texts, image_paths, searching_serial, terms, folder_path_, n, dev, patterns):
    """
    extract data from processed documents.
    - terms: list of keys to search for in the text.
    - patterns: dict with specific regex for those terms (e.g., all_keywords[doc_type]).
    """

    results = []
    for image_name, text, image_path in zip(image_names, texts, image_paths):
        serial = None
        if searching_serial:
            serial = serial_number(text, patterns=patterns)

        for term in terms:
            output = chained_search(term, text, n, dev, patterns=patterns)
            if dev:
                if output:
                    final_key, final_value = output[-1]
                    path_str = " -> ".join([f"{k}:{v}" for k, v in output])
                    results.append({
                        'Image': image_name,
                        'Serial': serial,
                        'Key': final_key.strip().lower(),
                        'Value': final_value,
                        'Path': path_str
                    })
            else:
                key, value = output
                if key and value:
                    results.append({
                        'Image': image_name,
                        'Serial': serial,
                        'Key': key.strip().lower(),
                        'Value': value
                    })
                    continue

            try:
                table_dict = fallback_table_extraction(folder_path_ / image_name)
                if not isinstance(table_dict, dict):
                    logging.warning(f"fallback_table_extraction returned non-dict for {image_name}, skipping tables.")
                    continue
            except Exception as e:
                logging.error(f"Error running fallback_table_extraction for {image_name}: {e}")
                continue

            for flavor in ["camelot_lattice", "camelot_stream", "tabula_lattice", "tabula_stream"]:
                tables_raw = table_dict.get(flavor, []) or []
                tables = comparing_tables(tables_raw)
                found = False

                for table in tables:
                    df = table.df if hasattr(table, 'df') else table
                    try:
                        for col in df.columns:
                            if term.lower() in str(col).lower():
                                for idx, row in df.iterrows():
                                    value = row[col]
                                    if value and not any(
                                        r['Image'] == image_name and r['Key'] == term.lower() and r['Value'] == value 
                                        for r in results
                                    ):
                                        results.append({
                                            'Image': image_name,
                                            'Serial': serial,
                                            'Key': term.lower(),
                                            'Value': value
                                        })
                                        found = True
                                if found:
                                    break
                        if found:
                            break
                    except Exception as e:
                        logging.debug(f"Error iterating columns for table in {image_name}: {e}")

                    try:
                        for idx, row in df.iterrows():
                            for cell in row:
                                if term.lower() in str(cell).lower() and not any(
                                    r['Image'] == image_name and r['Key'] == term.lower() and r['Value'] == cell 
                                    for r in results
                                ):
                                    results.append({
                                        'Image': image_name,
                                        'Serial': serial,
                                        'Key': term.lower(),
                                        'Value': cell
                                    })
                                    found = True
                                    break
                            if found:
                                break
                        if found:
                            break
                    except Exception as e:
                        logging.debug(f"Error iterating rows/cells for table in {image_name}: {e}")

                if found:
                    break

    return results


def delete_pdfs(folder_path):
    """
    Deletes all PDF files in the specified folder.
    """
    for file in os.listdir(folder_path):
        if file.lower().endswith('.pdf'):
            pdf_path = folder_path / file
            if pdf_path.exists():
                try:
                    pdf_path.unlink()
                    logging.info(f"PDF deleted: {pdf_path}")
                except Exception as e:
                    logging.error(f"Could not delete {pdf_path}: {e}")

def safe_cleanup(folder_path_, image_names):
    """cleans the temporary images created from PDFs."""
    try:
        if folder_path_ is not None and image_names:
            pdf_temporal_images(folder_path_, image_names)
            delete_pdfs(folder_path_)
            logging.info("Temporary images from PDFs have been deleted.")
    except Exception as e:
        logging.warning(f"Error during cleanup: {e}")



