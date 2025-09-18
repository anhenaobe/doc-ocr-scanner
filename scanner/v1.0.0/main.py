import sys, logging, re
from .excel_utils import save_results_if_any
from .general_utils import setup_tesseract, get_search_terms, prepare_folder_and_files, paths_from_names, safe_cleanup, extract_data_from_docs, parse_cli_args
from .ocr_utils import run_clean_and_ocr

#to install the program run: pyinstaller --onefile --add-data "keywords.json;." main.py

def log_config(level, log_file="scanner.log"):
    """
    Configures logging to log messages to both a file and the console.
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

def main():
    """
    Main function to run the scanner.
    Parses command line arguments, sets up Tesseract, prepares the folder and files,
    runs OCR on images, extracts data, and saves results to an Excel file.
    Handles exceptions and cleans up temporary files.
    """
    log_level = logging.ERROR if ("--quiet" in sys.argv or "-q" in sys.argv) else logging.INFO
    log_config(log_level)

    folder_path_ = None
    image_names = []

    try:
        args, all_keywords = parse_cli_args()
        all_keywords = normalize_keywords(all_keywords)
        setup_tesseract()

        terms = get_search_terms(args, all_keywords)
        patterns = all_keywords.get(args.doc_type, {})  

        folder_path_, image_names = prepare_folder_and_files(args.location, args.folder)
        image_paths = paths_from_names(folder_path_, image_names)

        texts = run_clean_and_ocr(image_paths, args.language)

        results = extract_data_from_docs(
            image_names, texts, image_paths,
            args.searching_serials, terms,
            folder_path_, n=args.n_terms, dev=args.devolution,
            patterns=patterns 
        )

        save_results_if_any(results, args.excel)

    except Exception as e:
        logging.error(f"Critical error in main: {e}", exc_info=True)
        sys.exit(1)

    finally:
        safe_cleanup(folder_path_, image_names)

def normalize_keywords(all_keywords):
    """
    Convierte listas de términos en dicts con regex simples.
    Ej: ["nit", "total"] → {"nit": [r"(?i)nit[:\s-]*(\S+)"], "total": [r"(?i)total[:\s-]*(\S+)"]}
    """
    normalized = {}
    for doc_type, patterns in all_keywords.items():
        if isinstance(patterns, list):
            # convertir cada string en un regex básico
            term_dict = {}
            for term in patterns:
                regex = rf"(?i){re.escape(term)}[:\s-]*(\S+)"
                term_dict[term.lower()] = [regex]
            normalized[doc_type] = term_dict
        elif isinstance(patterns, dict):
            normalized[doc_type] = patterns
        else:
            logging.warning(f"Doc type '{doc_type}' has invalid format: {type(patterns)}")
            normalized[doc_type] = {}
    return normalized


if __name__ == "__main__":
    main()