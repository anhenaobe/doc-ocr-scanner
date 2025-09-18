from PIL import Image
from pathlib import Path
from pdf2image import convert_from_path
from multiprocessing import Pool, cpu_count
import logging
import os
from reportlab.pdfgen import canvas

def pdf_temporal_images(folder_path, image_names):
    """
    Deletes temporary images created from PDFs.
    Removes images named with '_page_1.png' or containing '_page_' in their names.
    """
    for image_name in image_names:
        if image_name.endswith('_page_1.png') or '_page_' in image_name:
            image_path = folder_path / image_name
            if image_path.exists():
                try:
                    image_path.unlink()
                    logging.info(f"Temporary image deleted: {image_path}")
                except Exception as e:
                    logging.error(f"Could not delete {image_path}: {e}")

def images(folder_path, pdf_password=None):
    """
    Converts PDFs to images and returns a list of image file names in the folder.
    If a PDF is password-protected, prompts the user for the password.
    """
    file_names = get_files_name(folder_path)
    image_names = []
    for file in file_names:
        if file.lower().endswith('.pdf'):
            pdf_path = folder_path / file
            try:
                pdf_images = convert_from_path(pdf_path, userpw=pdf_password)
                for i, image in enumerate(pdf_images):
                    file_path_obj = Path(file)
                    image_name = f"{file_path_obj.stem}_page_{i + 1}.png"
                    image.save(folder_path / image_name, 'PNG')
                    image_names.append(image_name)
            except Exception as e:
                if "incorrect password" in str(e).lower() or "password required" in str(e).lower():
                    logging.warning(f"PDF {pdf_path} is password-protected.")
                    import getpass
                    pdf_password = getpass.getpass(prompt=f"Enter password for {file}: ")
                    try:
                        pdf_images = convert_from_path(pdf_path, userpw=pdf_password)
                        for i, image in enumerate(pdf_images):
                            file_path_obj = Path(file)
                            image_name = f"{file_path_obj.stem}_page_{i + 1}.png"
                            image.save(folder_path / image_name, 'PNG')
                            image_names.append(image_name)
                    except Exception as e2:
                        logging.error(f"Error converting {pdf_path} with provided password: {e2}")
                else:
                    logging.error(f"Error converting {pdf_path} to images: {e}")
        else:
            image_names.append(file)
    seen_names = set(image_names)
    return list(seen_names)

def img_to_pdf(image_path, output_path):
    """ Converts an image to a PDF file.
    image_path: Path to the input image.
    output_path: Path to save the output PDF.
    """
    if image_path.exists():
        with Image.open(image_path) as img:
            img_width, img_height = img.size

        c = canvas.Canvas(output_path, pagesize=(img_width, img_height))
        c.drawImage(image_path, 0, 0, width=img_width, height=img_height)
        c.save()
    else:
        logging.error(f"Image {image_path} does not exist. Cannot convert to PDF.")
        raise FileNotFoundError(f"Image {image_path} does not exist.")
    logging.info(f"Converted {image_path} to PDF: {output_path}")

def get_files_name(folder_path):
    """
    Returns a list of image and PDF file names in the specified folder.
    """
    searching_files_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif', '.pdf'}
    files_names = []
    try:
        for filename in os.listdir(folder_path):
            ext = Path(filename).suffix.lower()
            if ext in searching_files_extensions:
                files_names.append(filename)
        return files_names
    except FileNotFoundError as e:
        logging.error("Folder not found: %s", e)
        return []
    except PermissionError as e:
        logging.error("Permission denied: %s", e)
        return []
    except Exception as e:
        logging.error("Other error: %s", e)
        return []

def multiprocesing_(image_paths, function):
    """
    Applies the given function to each image path using multiprocessing.
    Returns a list of results.
    """
    with Pool(processes=cpu_count()) as pool:
        results = pool.map(function, image_paths)
    return results

