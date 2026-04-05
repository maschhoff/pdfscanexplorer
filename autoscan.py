import os
import pytesseract
import ocrmypdf
from PIL import Image
import PyPDF2
from PyPDF2.errors import DependencyError
from datetime import datetime, date
import logging
import time
import threading
import shutil
import random
from concurrent.futures import ProcessPoolExecutor, as_completed
import shutil as sh

import settings
import status
from vars import *

# Dynamisches Laden der gesamten Config
def get_config():
    return settings.loadConfig()

# Initiales Logging-Setup (nicht dynamisch, da das Logging-Modul sich nicht zur Laufzeit neu konfigurieren lässt)
initial_config = get_config()
log_level = logging.DEBUG if initial_config.get("debug", "off") == "on" else logging.INFO
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("autosorter.log"),
        logging.StreamHandler()
    ]
)

# Verify dependencies (optional)
logging.debug(f"jbig2enc found: {sh.which('jbig2enc') is not None}")
logging.debug(f"qpdf found: {sh.which('qpdf') is not None}")

# Verzeichnisse sicherstellen
for d in [archiv_dir, temp_dir, unknown_dir]:
    os.makedirs(d, exist_ok=True)

# Pfad sicher zusammenbauen
def safe_join(base_path, filename):
    clean_name = os.path.basename(filename)
    return os.path.join(base_path, clean_name)

# Dateiname für unbekannte Dateien erzeugen
def generate_unknown_filename(original_filename):
    config = get_config()
    basename, _ = os.path.splitext(original_filename)
    newname = basename

    if config.get("append_date", True):
        file_path = safe_join(pdf_dir, original_filename)
        filedatum = date.fromtimestamp(os.path.getmtime(file_path)).strftime('%d-%m-%Y')
        newname += f" - {filedatum}"

    if config.get("append_random", True):
        newname += f" - {random.randint(1111, 9999)}"

    return newname + ".pdf"

# Datei in den Unknown-Ordner verschieben
def move_to_unknown(pdf_file):
    try:
        src_path = safe_join(pdf_dir, pdf_file)
        newname = generate_unknown_filename(pdf_file)
        dst_path = os.path.join(unknown_dir, newname)

        logging.debug(f"Resolved unknown_dir: {unknown_dir}, Newname: {newname}")
        logging.info(f"MOVE (to unknown ({unknown_dir})) {src_path} to {dst_path}")
        shutil.move(src_path, dst_path)
    except Exception as e:
        logging.error(f"Failed to move file to unknown: {pdf_file} - {e}")

# OCR-Verarbeitung
def safe_ocrpdf(file_path, save_path):
    config = get_config()
    lang = config.get("lang", "deu")
    ocr_opts = config.get("ocr_options", {})
    ocr_mode = ocr_opts.get("ocr_mode", "skip_text")
    temp_output = save_path + ".tmp"

    try:
        logging.info(f"Running OCRmyPDF on: {file_path} (mode: {ocr_mode})")
        
        # Only one of these three may be True
        force_ocr = ocr_mode == "force_ocr" # Always OCR, even if text is present
        skip_text = ocr_mode == "skip_text" # OCR only for pages without text
        redo_ocr = ocr_mode == "redo_ocr"   # Replace existing OCR (if machine-readable-results are poor)

        ocrmypdf.ocr(
            file_path,
            temp_output,
            language=lang,
            rotate_pages=ocr_opts.get("rotate_pages", True),
            deskew=ocr_opts.get("deskew", True),
            optimize=ocr_opts.get("optimize", 1),
            jobs=ocr_opts.get("jobs", 1),
            force_ocr=force_ocr,
            skip_text=skip_text,
            redo_ocr=redo_ocr
        )

        if not os.path.exists(temp_output) or os.path.getsize(temp_output) < 1024:
            raise ValueError("OCR output file is empty or too small – skipping overwrite.")

        shutil.move(temp_output, save_path)
        logging.debug(f"OCR successful for {file_path}, replaced with new version.")

    except Exception as e:
        logging.error(f"OCRmyPDF failed or invalid output for {file_path}: {e}")
        if os.path.exists(temp_output):
            os.remove(temp_output)
        raise

# OCR-Wrapper
def ocr(folder, pdf_file):
    config = get_config()
    lang = config.get("lang", "deu")
    force_ocr = config.get("force_ocr", False)

    logging.info(f"Checking for OCR need in: {pdf_file}")
    if not pdf_file.endswith(".pdf"):
        logging.warning(f"Unsupported file type for OCR: {pdf_file}")
        return None

    source = safe_join(folder, pdf_file)

    try:
        if not force_ocr:
            with open(source, "rb") as pdf_file_obj:
                reader = PyPDF2.PdfReader(pdf_file_obj)

                if not reader.pages:
                    raise ValueError("PDF has no pages or is malformed.")

                first_page = reader.pages[0]
                extracted_text = first_page.extract_text()

                if extracted_text and extracted_text.strip():
                    logging.info(f"OCR skipped for {pdf_file} – text already exists")
                    return extracted_text
                else:
                    logging.info(f"No text found in {pdf_file} – proceeding with OCR")
        else:
            logging.info(f"OCR forced for {pdf_file} due to config (force_ocr=true)")

        # OCR durchführen
        safe_ocrpdf(source, source)

        with open(source, "rb") as pdf_file_obj:
            reader = PyPDF2.PdfReader(pdf_file_obj)
            if not reader.pages:
                raise ValueError("PDF has no pages after OCR – possibly invalid output.")
            first_page = reader.pages[0]
            final_text = first_page.extract_text()
            if final_text and final_text.strip():
                logging.info(f"OCR completed successfully for {pdf_file}")
            else:
                logging.warning(f"OCR ran but no text extracted for {pdf_file}")
            return final_text

    except DependencyError as dep_err:
        logging.error(f"PyCryptodome is required for AES decryption in {pdf_file}: {dep_err}")
        return None
    except Exception as e:
        logging.exception(f"OCR failed for {source}: {e}")
        return None

# Sortierfunktion anhand des Textinhalts
def sort(pdf_file, text):
    config = get_config()
    index = config["index"]
    debug = config.get("debug", "off")

    if debug == "on":
        logging.debug(f"EXTRACTED TEXT from {pdf_file}:\n{text}")

    for archiv_item in index:
        try:
            folder, filename = archiv_item.split(";")
            if not folder.strip() or not filename.strip():
                logging.error(f"Invalid index entry '{archiv_item}' – skipping file {pdf_file}")
                continue
        except ValueError:
            logging.error(f"Invalid index format: {archiv_item}")
            continue

        count = sum(1 for keyword in index[archiv_item] if keyword in text)

        if count >= len(index[archiv_item]):
            # folder is already an absolute path (e.g. /Archiv/Rechnungen)
            # safe_join would strip everything but the last component via basename,
            # so use the path directly and only sanitize whitespace.
            full_folder_path = folder.strip()
            os.makedirs(full_folder_path, exist_ok=True)

            file_date = date.fromtimestamp(os.path.getmtime(safe_join(pdf_dir, pdf_file))).strftime('%d_%m_%Y')
            new_filename = f"{filename}_{file_date}_{random.randint(1111,9999)}.pdf"

            src_path = safe_join(pdf_dir, pdf_file)
            dst_path = safe_join(full_folder_path, new_filename)

            try:
                logging.info(f"MOVE (sorting) {src_path} to {dst_path}")
                shutil.move(src_path, dst_path)
                return True
            except Exception as e:
                logging.error(f"Error moving file {pdf_file} to archive: {e}")
                return False

    return False  # Kein Treffer im Index

# Einzelne PDF-Datei verarbeiten
def process_pdf(pdf_file):
    try:
        text = ocr(pdf_dir, pdf_file)
        if not text:
            raise ValueError("No OCR text extracted")

        sorted_successfully = sort(pdf_file, text)
        if not sorted_successfully:
            logging.info(f"No matching index found – moving to unknown: {pdf_file}")
            move_to_unknown(pdf_file)

    except Exception as e:
        logging.warning(f"Processing failed for {pdf_file}: {e}")
        move_to_unknown(pdf_file)

# Hauptverarbeitung
def run():
    logging.info("Running OCR and sorting process")

    pdf_files = [
        f for f in os.listdir(pdf_dir)
        if f.lower().endswith(".pdf") and os.path.isfile(safe_join(pdf_dir, f))
    ]

    with ProcessPoolExecutor(max_workers=os.cpu_count() or 4) as executor:
        futures = {executor.submit(process_pdf, f): f for f in pdf_files}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logging.error(f"Unhandled exception in OCR process: {e}")

    for f in os.listdir(temp_dir):
        path = safe_join(temp_dir, f)
        if os.path.isfile(path):
            try:
                os.remove(path)
            except Exception as e:
                logging.warning(f"Could not delete temp file {f}: {e}")

    config = get_config()
    moved_files = any(os.path.isfile(os.path.join(unknown_dir, f)) for f in os.listdir(unknown_dir))
    status.set_update_needed(bool(moved_files and config.get("enable_update_flag", True)))

# Hintergrund-Thread für Cronjob
cron_lock = threading.Lock()
cron_running = False

def autoscan_cron():
    global cron_running
    with cron_lock:
        if cron_running:
            logging.info("Cronjob already running, skipping.")
            return
        cron_running = True

    try:
        while True:
            config = get_config()
            updatetime = float(config.get("updatetime", 60))

            logging.info(f"STARTING CRONJOB Interval: {updatetime} - Time: {datetime.now()}")
            try:
                run()
            except Exception as e:
                logging.exception("Exception in autoscan_cron run loop")
            time.sleep(updatetime)
    finally:
        cron_running = False

# Cronjob-Thread starten
th = threading.Thread(target=autoscan_cron, daemon=True)
th.start()
