# doc-ocr-scanner

Tool for automatically extracting data from images and PDFs to Excel.  
Converts scanned documents (invoices, receipts, etc.) into processable tables.

## Features
- OCR using Tesseract.
- Image cleaning and preprocessing with OpenCV.
- Support for PDF documents and images (JPG, PNG, TIFF, etc.).
- Table extraction using Camelot and Tabula.
- Direct export to Excel (.xlsx).

## Instalation
Clone the repository:
```bash
git clone https://github.com/TU-USUARIO/scanner_working_ver.git
cd scanner_working_ver
```

Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage
Execution example:
```bash
python -m scanner_working_ver.main -l . -f test -e salida -n 1 -q -s -d facturas
```

Main parameters:
- `-l` → Base directory (e.g., Desktop, Downloads, etc.)
- `-f` → Folder containing the documents to be processed
- `-e` → Name of the output Excel file
- `-d` → Document type (invoices, receipts, etc.)
- `-s` → Enables serial number search
- `-q` → Quiet mode
- `-n` → Number of context terms

## Compilation to executable
```bash
pyinstaller --onefile --add-data "keywords.json;." main.py
```

## Licence
Restrictive (ver archivo LICENSE)
