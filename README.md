# PDF Scan Explorer - scan documents explorer and automation 
Preview and Rename Scan PDF Explorer  
A webbased document PDF explorer and automation. For easy view, rename and move scanned PDF files with the help of AI (if you want) 
  
## Background and Motivation:  
I was searching for a easy to use solution to get my letters and paper digital.  
Since I was searching for a solution for my unraid NAS, solutions like paperwork dont work as docker/in web or on many computer.  
Programs like Paperless and Papermerge are great but much to heavy with database etc.  
I like to keep my files in a normal folder structure to share and access them from every pc.  
Thats how PDF Scan Explorer started. As an lightwight easy to use web based application to make it easy to preview, rename and move scanned documents.  
  
## BETA Note:  
This program is very new and theres a lot to test. Please report issues to the issues tab on github.

## Functions:
* PDF OCR Autoscan will move known documents based on keywords
* Preview and Rename documents from a web browser
* AI based suggestion of Filename and Folder
* PDF Merge let you merge documents (1+1 and front and back pages)
* Split documents 
* Manual rename and move

## How it works:
1. Documents get scanned to a scan-folder 
2. These documents will be autoscanned and moved to the specific locations
3. Any files that are not recognized by autoscan will be moved to the subfolder "unknown" of the scan-folder
4. The Webbased PR PDF Explorer lists all documents of the "unknown" folder.

## How it looks like:

![Explorer](https://i.ibb.co/b723gYv/Explorer.jpg)
![OCR](https://i.ibb.co/JQb8Frf/OCR.jpg)
![UNRAID-PATH-EXAMPLES](https://i.ibb.co/vxC6WngQ/grafik.png)


# Install and run

## Run as docker

Example:  
` docker run -d --name='PRPDF' -p 80:80 -v '/mnt/user/Share':'/Archiv/':'rw' -v '/mnt/user/SCAN':'/source/static/pdf/':'rw' -v '/mnt/user/appdata/prpdf/':'/source/config':'rw' 'knex666/prpdf'`

* Note 1: use knex666/latest-dev for developer preview
* Note 2: remember to setup the network to map the port of your configuration ` -p 80:80` you can choose any port you want see config
* Note 3: besited a folder structure for documents in a folder you mount to /Archiv/ you can volume mount any directory you want to /Archiv/ to build you own virtual folder structure
` -v '/mnt/user/Files/Accounting':'/Archiv/Accounting':'rw'` etc.

## Run with python on linux
Note: Please ensure to run it from /source/ 
create a folder /Archiv for your files 
and a folder /source/static/pdf/ as location for you scanned pdfs
otherwise feel free to edit the sourcecode on vars.py etc.

* ` python3 -m pip install -r requirements.txt`
* ` sudo apt-get install tesseract-ocr poppler-utils` etc. (see Dockerfile)
* ` export Workdir=path to app folder
* ` python3 prpdf.py`

## Run as systemd service on Fedora
* ` clone to /opt/prpdf (or adapt path below)`
* ` sudo dnf install tesseract-tools tesseract-devel poppler`
* ` python3 -m pip install -r requirements.txt`
* Adapt Homepath in the following two commands (default /opt/prpdf) 
* ` adduser -M -r -s /usr/bin/nologin -d /opt/prpdf`
* ` chown prpdf:prpdf /opt/prpdf`
* Edit prpdf.service to reflect your WORKDIR (/opt/prpdf by default)
* ` cp prpdf.service /lib/systemd/system `
* ` systemctl enable --now prpdf`

# Configuration
A default config will be creating within the first start of PR PDF.
For Docker please mount the config folder to make it persistent.
An example: https://github.com/maschhoff/prpdf/blob/main/config/config.json

# Donate
If you like what you see please buy me a Pizza -> https://www.buymeacoffee.com/maschhoff 
Or please buy tobias a coffee -> https://www.buymeacoffee.com/tobiasgraeber

