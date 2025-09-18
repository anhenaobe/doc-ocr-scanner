import re
import logging
import os
from pathlib import Path

def searching(search_term, text, patterns=None, return_all = False):
    """
    search for a term in the text, if the term have been found, returns the term and the respective key
    """

    if patterns and search_term.lower() in patterns:
        regex_list = patterns[search_term.lower()]
        results = []
        for regex in regex_list:
            matches = re.findall(regex, text, re.IGNORECASE | re.DOTALL)
            if matches:
                if return_all:
                    results.extend(matches)
                else:
                    return (search_term, matches[0].strip())
        if results:
            return results
        
    first_match = re.search(re.escape(search_term), text, re.IGNORECASE)
    if not first_match:
        logging.info(f"Term '{search_term}' not found in text.")
        return (None, None)

    sep_chars = r"[\s:=-]*"
    pattern = rf"{re.escape(first_match.group(0))}{sep_chars}(.{{0,100}})"
    after_term = re.search(pattern, text, re.IGNORECASE | re.DOTALL)

    if after_term:
        snippet = after_term.group(1)

        number_regex = r"(?:[-+]?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?)"
        alnum_regex = r"\b([A-Za-z0-9]+)\b"
        word_regex  = r"([a-zA-Z]+)"

        for regex in [number_regex, alnum_regex, word_regex]:
            match = re.search(regex, snippet)
            if match:
                return (first_match.group(0), match.group(0))

    return (first_match.group(0), None)

def date_finder(text, term):
    """
    Finds dates near the given term in text.
    Supports dd/mm/yyyy, yyyy-mm-dd, dd-mm-yy, etc.
    """
    term_escaped = re.escape(term)
    date_regex = rf"{term_escaped}[\s:=-]*" \
                 r"(\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}|\d{{4}}[/-]\d{{1,2}}[/-]\d{{1,2}})"

    match = re.search(date_regex, text, re.IGNORECASE)
    if match:
        return match.group(1)
    return None

def serial_number(text, patterns=None, return_all=False):
    """
    Extracts a serial number from the text if the user requires it
    """
    serial_words = [
        "número de serie", "nº de serie", "no. de serie", "num. de serie",
        "serie", "serial", "serial number", "id", "código", "código único",
        "clave", "clave única", "referencia", "referencia única", "folio",
        "número de folio", "comprobante", "número de comprobante",
        "ticket", "número de ticket", "factura", "número de factura",
        "recibo", "número de recibo", "orden", "número de orden",
        "pedido", "número de pedido", "documento", "número de documento",
        "contrato", "número de contrato", "expediente", "registro",
        "número de registro", "id único", "identificación", "identificador",
        "s/n", "sn", "unique id", "unique code",
        "reference", "reference number", "ref",
        "folio number", "voucher", "voucher number",
        "ticket number", "invoice", "invoice number",
        "receipt", "receipt number", "order", "order number",
        "purchase order", "po number", "document number",
        "contract number", "file", "file number",
        "record", "registration number", "unique identifier"
    ]

    results = []

    if patterns and "serial" in patterns:
        for regex in patterns["serial"]:
            matches = re.findall(regex, text, re.IGNORECASE)
            if matches:
                if return_all:
                    results.extend(matches)
                else:
                    return matches[0]
        if results:
            return results

    serial_words = [
        "número de serie", "nº de serie", "no. de serie", "num. de serie",
        "serie", "serial", "serial number", "id", "código", "folio", "factura",
        "ticket", "recibo", "orden", "pedido", "documento", "contrato",
        "expediente", "registro", "unique id", "reference"
    ]

    for serial in serial_words:
        serial_term_escaped = re.escape(serial)
        serial_regex = rf"(?i){serial_term_escaped}\s*[:\-#]?\s*([A-Z0-9\-\/]+)"
        matches = re.findall(serial_regex, text, re.IGNORECASE)
        if matches:
            if return_all:
                results.extend(matches)
            else:
                return matches[0]

    return results if results else None

def normalize_number(num_str):
    """
    Normalizes a numeric string by removing spaces and converting commas to dots.
    Returns a float if possible, otherwise returns the original string.
    """
    num_str = num_str.replace(' ', '')
    if ',' in num_str and '.' in num_str:
        num_str = num_str.replace(',', '')
    elif ',' in num_str:
        num_str = num_str.replace(',', '.')
    try:
        return float(num_str)
    except ValueError:
        return num_str

def final_dict(results):
    """
    Aggregates results by key. Uses normalize_number to clean numeric strings.
    - Sums numeric values.
    - Collects unique non-numeric values in lists.
    """
    summed_values = {}
    string_values = {}

    for result in results:
        key = result.get('Key')
        value = result.get('Value')
        if key is None or value is None:
            continue

        normalized = normalize_number(str(value))

        if isinstance(normalized, float):
            summed_values[key] = summed_values.get(key, 0.0) + normalized
        else:
            if key not in string_values:
                string_values[key] = set()
            string_values[key].add(normalized)

    string_values = {k: list(v) for k, v in string_values.items()}
    return summed_values, string_values

def folder_path(parent_folder, folder_name):
    """
    Returns the full path to a folder located in the user's chosen directory.
    If running in Codespaces, uses /workspaces/Projects as base.
    Creates the folder if it does not exist.
    """
    if os.environ.get("CODESPACES") or "codespace" in str(Path.home()):
        base_path = Path("/workspaces/Projects")
    else:
        user_home = Path.home()
        base_path = user_home / parent_folder if not Path(parent_folder).is_absolute() else Path(parent_folder)
    folder_path = base_path / folder_name
    if not folder_path.exists():
        logging.info(f"Folder {folder_path} does not exist. Creating it.")
        try:
            folder_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logging.error(f"Error creating folder '{folder_path}': {e}")
            return None
    return folder_path

def existing_files(folder_path):
    """
    Checks if the folder contains any files. Returns the folder path if files exist, otherwise None.
    """
    content = os.listdir(folder_path)
    if content:
        logging.info(f"Files found in folder: {folder_path}")
        return folder_path
    else:
        logging.warning(f"No files found in folder: {folder_path}")
        print(f"No files found in folder: {folder_path}. Please add images or PDFs and try again.")
        return None

def normalize_text(text):
    """
    Normalizes text by stripping leading/trailing spaces, converting to lowercase,
    and replacing multiple spaces with a single space.
    """
    text = text.strip().lower()
    text = re.sub(r'\s+', ' ', text)
    return text

def chained_search(initial_term, text, n, dev, patterns=None): 
    current_term = initial_term
    current_value = None
    chain = []

    if n == 0:
        return searching(current_term, text, patterns=patterns, return_all=False)

    for i in range(n):
        term, value = searching(current_term, text, patterns=patterns, return_all=False)
        if not term or not value:
            break
        current_term = value
        current_value = value
        chain.append((term, value))

    if dev:
        return chain
    return (initial_term, current_value) if current_value else (None, None)

