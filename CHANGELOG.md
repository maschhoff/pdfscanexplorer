## [v1.0.1] - 2025-11-16 / 📦 Changelog – New Features & Improvements

### New Features

- Upload a file manually in the WebUI
  Click the + sign to start
  Endpoint /upload
- OpenAI API Integration for Filename and Folder suggestion.
  Enable by setting the "openai_api_key in the config file / settings
  Endpoint /ai

## [v1.0.0] - 2025-07-25 / 📦 Changelog – New Features & Improvements

### New Features

- Automatic frontend refresh when new files appear in `/unknown`  
  Enabled via the setting `enable_update_flag`  
  ➤ Endpoint: `/check_update`  
  _Closes #22_ of https://github.com/maschhoff/prpdf/issues

- Integrated PDF.JS Canvas Viewer for consistent, cross-browser PDF rendering  
  Works on mobile and replaces Firefox’s native viewer.

- Auto-navigation to the next file after one has been sorted or moved.

- Auto-scroll into view when a file is renamed.

- Highlight of the currently selected file, including support via "Show next file" button.

- Reworked settings/config dialog  
  Pretty-printed JSON for improved readability and editing.

- PDF download button now opens in a new tab or window.

- Fixed 180° rotation logic for PDFs.

- Folder view and explorer improved  
  Includes visual updates and fixed `selectedFolder` handling  
  _Closes #17_ of https://github.com/maschhoff/prpdf/issues

- Search filters, sort order, and view state now persist even after renaming, saving, or moving files.

- Improved regex to support special characters and umlauts in filenames.

- Improved error logging with basic 7-day log rotation.

- CSS and style enhancements (`main.css`).

- NoneType error fix: folders are now ignored during autoscan  
  Only files are processed  
  _Closes #3_ of https://github.com/maschhoff/prpdf/issues

- Better autoscan/OCR UX  
  Reorganized input fields and added functional descriptions.

- Autoscan job scheduling improved to prevent overlapping runs  
  Respects `updatetime` config setting.

- New config options added:
  - `"append_date": true` – Append file date to filename
  - `"append_random": true` – Append random number to filename

- View column in file list is now non-sortable to prevent layout issues.

### 🐞 Bug Fixes & Maintenance

- Numerous bug fixes  
- 🧹 Code cleanup and formatting  
- 🔧 General stability improvements
