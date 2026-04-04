import os
import glob
import random
import json
import logging
from datetime import datetime, date
from logging.handlers import TimedRotatingFileHandler
from flask import Flask, render_template, request, redirect, jsonify, session, send_file
import settings
import autoscan
import imap_scanner
import merge
import splitpages
import status
import shutil
from vars import *
import ai

app = Flask(__name__)
app.secret_key = 'L6^uzJZ6En5EJs'


# Homepage - List PDFs and show preview
@app.route('/')
def index():
    pdf = loadFiles()
    if pdf:
        search = pdf[0]
    else:
        search = {"name": ""}
    return render_template(
        'explorer.html', 
        liste=pdf, 
        preview=search['name'], 
        subdirhtml=subdirhtml, 
        folders=loadArchivFolder(),
        iterator=0,
        selected_folder=unknown_dir
    )


# Form submission on homepage (file rename/move)
@app.route('/', methods=['POST'])
def my_form_post():
    config = settings.loadConfig()
    
    newid = request.form['pdf']
    oldid = request.form['oldpdf']
    folder = request.form['folder']
    iterator = request.form['inputiterator']

    sortCol = request.form.get("sortCol", type=int, default=2)
    sortDir = request.form.get("sortDir", default="desc")
    searchTerm = request.form.get("searchTerm", default="")

    append_date = config.get("append_date", True)
    append_random = config.get("append_random", True)

    session['selected_folder'] = request.form.get("folder", unknown_dir)
    selected_folder = session.get("selected_folder", unknown_dir) #/static/pdf/unknown/

    fileneu = newid
    if append_date:
        filedatum = date.fromtimestamp(os.path.getmtime(os.path.join(unknown_dir, oldid))).strftime('%d-%m-%Y')
        fileneu += " - " + filedatum
    if append_random:
        fileneu += " - " + str(random.randint(1111, 9999))
    fileneu += ".pdf"

    message = ""
    file_moved = False

    if newid != "":
        if folder != "unknown":
            shutil.move(os.path.join(unknown_dir, oldid), os.path.join(folder, fileneu))
            message = "Success: File '" + fileneu + "' moved"
            file_moved = True
        else:
            shutil.move(os.path.join(unknown_dir, oldid), os.path.join(unknown_dir, fileneu))
            message = "Success: Title changed to:" + fileneu

    pdf = loadFiles()

    if file_moved:
        def sort_key(item):
            if sortCol == 0:
                return item['name']
            elif sortCol == 1:
                return item['size']
            else:
                return item['date']

        pdf_sorted = sorted(pdf, key=sort_key, reverse=(sortDir == "desc"))
        new_preview = pdf_sorted[0]['name'] if pdf_sorted else ""
        iterator = 0
    else:
        new_preview = fileneu

    return render_template(
        'explorer.html',
        message=message,
        liste=pdf,
        preview=new_preview,
        subdirhtml=subdirhtml,
        folders=loadArchivFolder(),
        iterator=iterator,
        sort_column=sortCol,
        sort_direction=sortDir,
        search_term=searchTerm,
        selected_folder=selected_folder
    )


# Merge PDF page(s) selection page
@app.route('/merge')
def domerge():
    pdf = loadFiles()
    return render_template('merge.html', files=pdf)

@app.route('/merge', methods=['POST'])
def domergepost():
    file1 = request.form['file1']
    file2 = request.form['file2']
    option = request.form['option']
    filename = request.form['pdf']

    if "merge" in option:
        message = merge.pdf_merge_file(os.path.join(unknown_dir, file1), os.path.join(unknown_dir, file2), filename)
    else:
        message = merge.pdf_adf(os.path.join(unknown_dir, file1), os.path.join(unknown_dir, file2), filename)

    pdf = loadFiles()
    return render_template('explorer.html', liste=pdf, message=message, subdirhtml=subdirhtml, folders=loadArchivFolder(), iterator=0)


# Split PDF page(s) selection page
@app.route('/split')
def dosplit():
    pdf = loadFiles()
    return render_template('split.html', files=pdf)

@app.route('/split', methods=['POST'])
def dosplitpost():
    file1 = request.form['file1']
    page = int(request.form['page'])
    logging.info(f"Split Page after: {page}")

    splitpages.split_pdf(os.path.join(unknown_dir, file1), page)

    pdf = loadFiles()
    return render_template('explorer.html', liste=pdf, message="", subdirhtml=subdirhtml, folders=loadArchivFolder(), iterator=0)


# Try AI to get folder and filename
@app.route('/ai/<string:id>')
def aisug(id):
    pdf = loadFiles()
    try:
        result=ai.categorize_document(unknown_dir+id,loadArchivFolder())
        return render_template('explorer.html', liste=pdf, preview=id, message="", subdirhtml=subdirhtml, folders=loadArchivFolder(), iterator=0, selected_folder=result["Ordner"], sugg_filename=result["Datei"])
    except Exception as e:
        logging.error(f"An exception occurred in AI {e}")
        return render_template('explorer.html', liste=pdf, preview=id, message=f"Error {e}", subdirhtml=subdirhtml, folders=loadArchivFolder(), iterator=0)
    
# Trigger autoscan manually
@app.route('/autoscan')
def doautoscan():
    try:
        autoscan.run()
        global subdirhtml
        subdirhtml = ""
        listdirs(archiv_dir)
    except Exception as e:
        logging.error(f"An exception occurred {e}")

    pdf = loadFiles()
    search = pdf[0] if pdf else {"name": ""}
    return render_template('explorer.html', liste=pdf, preview=search['name'], subdirhtml=subdirhtml, folders=loadArchivFolder(), iterator=0)


# Delete file
@app.route('/delete/<string:id>')
def dodelete(id):
    os.remove(os.path.join(unknown_dir, id))
    return redirect('/')


# Rotate PDF pages
@app.route('/rotate/<string:id>')
def dorotate(id):
    splitpages.rotate_pages(os.path.join(unknown_dir, id))

    rotated_name = id.replace(".pdf", "_rotated.pdf")

    sortCol = 2
    sortDir = "desc"
    searchTerm = ""

    message = f"File '{rotated_name}' successfully rotated."

    pdf = loadFiles()

    def sort_key(item):
        if sortCol == 0:
            return item['name']
        elif sortCol == 1:
            return item['size']
        else:
            return item['date']

    pdf_sorted = sorted(pdf, key=sort_key, reverse=(sortDir == "desc"))

    iterator = 0
    for i, item in enumerate(pdf_sorted):
        if item['name'] == rotated_name:
            iterator = i
            break

    return render_template(
        'explorer.html',
        message=message,
        liste=pdf_sorted,
        preview=rotated_name,
        subdirhtml=subdirhtml,
        folders=loadArchivFolder(),
        iterator=iterator,
        sort_column=sortCol,
        sort_direction=sortDir,
        search_term=searchTerm
    )


# OCR page display
@app.route('/<string:id>')
def doocr(id):
    return render_template('magic.html', preview=id, subdirhtml=subdirhtml, folders=loadArchivFolder(), pdf=id)


# Autoscan rule save
@app.route('/magic', methods=['POST'])
def autoscan_rule():
    newid = request.form['pdf']
    folder = request.form['folder']
    keywords = request.form['keywords']

    keyw_array = [k.strip() for k in keywords.split(",")]
    key = folder + ";" + newid

    config = settings.loadConfig()
    config["index"].update({key: keyw_array})
    settings.writeJsonConfig(config)

    pdf = loadFiles()
    return render_template('explorer.html', liste=pdf, subdirhtml=subdirhtml, folders=loadArchivFolder(), iterator=0, message="Autoscan rule saved")


# Settings view
@app.route('/settings')
def setting():
    config_raw = settings.getConfigRaw()
    return render_template('settings.html', config=settings.loadConfig(), config_raw=config_raw.read())


# Save settings
@app.route('/settings', methods=['POST'])
def setting_save():
    global config
    config = settings.loadConfig()
    
    config_raw = request.form['hiddenconfig']
    logging.info(f"Config: {config_raw}")

    if not config_raw:
        config_raw = settings.getConfigRaw()
        return render_template('settings.html', config=config, config_raw=config_raw.read())

    try:
        json.loads(config_raw)
        settings.writeConfig(config_raw)
        config = settings.loadConfig()
        return render_template('settings.html', config=config, config_raw=config_raw, message="Config saved, please restart!")
    except Exception as e:
        logging.error(e)
        return render_template('settings.html', config=config, config_raw=config_raw, message="JSON error")


# Check if update is needed (for front-end polling)
@app.route("/check_update", methods=["GET", "POST"])
def check_update():
    update = status.get_update_needed()
    response = jsonify({"update": update})
    response.headers["Cache-Control"] = "no-store"  # Cache verhindern
    return response

# Reset the update flag
@app.route("/reset_update_flag", methods=["GET", "POST"])
def reset_update_flag():
    status.set_update_needed(False)
    response = jsonify({"update": status.get_update_needed()})
    response.headers["Cache-Control"] = "no-store"
    return response

# Set the update flag
@app.route("/set_update_flag", methods=["GET", "POST"])
def set_update_flag():
    status.set_update_needed(True)
    response = jsonify({"update": status.get_update_needed()})
    response.headers["Cache-Control"] = "no-store"
    return response


## UPLOAD ##

# Erlaubte Dateiendungen
ALLOWED_EXTENSIONS = {"pdf", "pdfx"}

def allowed_file(filename):
    """Prüft, ob die Datei eine erlaubte Endung hat."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/upload", methods=["POST"])
def upload_file():
    # Prüfen, ob eine Datei im Request enthalten ist
    if "file" not in request.files:
        return jsonify({"error": "Keine Datei im Request gefunden."}), 400

    file = request.files["file"]

    # Prüfen, ob eine Datei ausgewählt wurde
    if file.filename == "":
        return jsonify({"error": "Keine Datei ausgewählt."}), 400

    # Prüfen, ob Dateiendung erlaubt ist
    if file and allowed_file(file.filename):
        filepath = os.path.join(pdf_dir, file.filename)
        file.save(filepath)
        return redirect('/autoscan')
        """
        return jsonify({
            "message": "Datei erfolgreich hochgeladen.",
            "filename": file.filename,
            "path": filepath
        }), 200
        """
    else:
        return jsonify({"error": "Dateityp nicht erlaubt."}), 400
    

# File Explorer: browse archive folders
@app.route('/fileexplorer')
def fileexplorer():
    return render_template('fileexplorer.html', subdirhtml=subdirhtml)


# File Explorer: list PDFs in a given archive folder (AJAX endpoint)
@app.route('/api/files')
def api_files():
    folder = request.args.get('folder', '')
    if not folder:
        return jsonify([])

    real_archiv = os.path.realpath(archiv_dir)
    real_folder = os.path.realpath(folder)

    if not real_folder.startswith(real_archiv):
        return jsonify({'error': 'Access denied'}), 403

    if not os.path.isdir(real_folder):
        return jsonify([])

    rel_base = os.path.relpath(real_folder, real_archiv)

    result = []
    for fname in sorted(os.listdir(real_folder)):
        if fname.lower().endswith('.pdf') and os.path.isfile(os.path.join(real_folder, fname)):
            fpath = os.path.join(real_folder, fname)
            rel_path = os.path.join(rel_base, fname) if rel_base != '.' else fname
            result.append({
                'name': fname,
                'size': f'{os.path.getsize(fpath) / 1_000_000:.2f} MB',
                'date': datetime.fromtimestamp(os.path.getmtime(fpath)).strftime('%Y-%m-%d %H:%M:%S'),
                'url': '/archive/' + rel_path.replace(os.sep, '/'),
            })
    return jsonify(result)


# Serve archive PDF files for preview
@app.route('/archive/<path:filepath>')
def serve_archive_file(filepath):
    real_archiv = os.path.realpath(archiv_dir)
    safe_path = os.path.realpath(os.path.join(archiv_dir, filepath))
    if not safe_path.startswith(real_archiv):
        return 'Access denied', 403
    if not os.path.isfile(safe_path):
        return 'File not found', 404
    return send_file(safe_path, mimetype='application/pdf')


# Trigger IMAP scan manually
@app.route('/imap_scan')
def do_imap_scan():
    try:
        count = imap_scanner.scan_imap()
        msg = f"IMAP scan complete: {count} PDF(s) imported."
    except Exception as e:
        logging.error(f"IMAP scan error: {e}")
        msg = f"IMAP scan error: {e}"

    global subdirhtml
    subdirhtml = ""
    listdirs(archiv_dir)

    pdf = loadFiles()
    search = pdf[0] if pdf else {"name": ""}
    return render_template('explorer.html', liste=pdf, preview=search['name'],
                           subdirhtml=subdirhtml, folders=loadArchivFolder(),
                           iterator=0, message=msg)


# Subdirectories list & HTML generation for folder tree
subdirs = [archiv_dir]
subdirhtml = ""

def listdirs(rootdir):
    global subdirhtml
    for it in os.scandir(rootdir):
        if it.is_dir():
            subdirs.append(it.path)
            subdirhtml += f"""
            <li><i class="fas fa-angle-right rotate"></i>
            <span><i class="far fa-folder-open ic-w mx-1"></i><a href="javascript:void(0)" onClick="selectfolder('{it.path}');">{it.name}</a></span>
            <ul class="nested">
            """
            listdirs(it.path)
            subdirhtml += "</ul></li>"

print('Creating Directory Map... that can take some time')
listdirs(archiv_dir)


# Load list of archive folders
def loadArchivFolder():
    return subdirs


# Load list of PDFs from unknown_dir with metadata
def loadFiles():
    res = []
    if os.path.exists(unknown_dir):
        files = glob.glob(os.path.join(unknown_dir, "*.pdf"))
        for file in files:
            filer = {
                "name": os.path.basename(file),
                "size": f"{os.path.getsize(file) / 1_000_000:.2f} MB",
                "date": datetime.fromtimestamp(os.path.getmtime(file)).strftime('%Y-%m-%d %H:%M:%S')
            }
            res.append(filer)
    return res


if __name__ == '__main__':
    work_dir = os.environ.get('WORKDIR', '.')

    logfile_path = os.path.join(work_dir, 'config', 'server.log')

    file_handler = TimedRotatingFileHandler(
        logfile_path,
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

    logging.basicConfig(
        level=logging.INFO,
        handlers=[file_handler, stream_handler],
        force=True
    )

    config = settings.loadConfig()
    debug = config.get("debug", False)

    logging.info(f"Start PR PDF Server from {work_dir}...")
    print(f"Start PR PDF Server from {work_dir}...")
    print("""
     (\__/)  .-  -.)
     /0 0 `./    .'
    (O__,   \   (
      / .  . )  .
      |-| '-' \  )
      (   _(   ).'
    °....~....$

      PR PDF
    """)

    app.run(host='0.0.0.0', port=config.get("port", 80), debug=debug)
