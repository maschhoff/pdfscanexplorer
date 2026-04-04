import imaplib
import email
import email.header
import os
import logging
import time
import threading
import re

import settings
import status
from vars import unknown_dir


def get_imap_config():
    return settings.loadConfig().get("imap", {})


def decode_header_value(value):
    """Decode potentially encoded email header value."""
    parts = email.header.decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def sanitize_filename(filename):
    """Remove or replace unsafe characters from filename."""
    filename = decode_header_value(filename)
    filename = re.sub(r'[^\w\s\-.]', '_', filename)
    filename = filename.strip()
    if not filename:
        filename = "attachment"
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    return filename


def unique_path(directory, filename):
    """Return a unique file path by appending a counter if the file already exists."""
    base, ext = os.path.splitext(filename)
    candidate = os.path.join(directory, filename)
    counter = 1
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{base}_{counter}{ext}")
        counter += 1
    return candidate


def scan_imap():
    """
    Connect to the configured IMAP mailbox, download PDF attachments from
    unseen emails directly into the unknown folder for manual review.
    Returns the number of PDF files downloaded.
    """
    imap_config = get_imap_config()

    if not imap_config.get("enabled", False):
        logging.info("IMAP scanning is disabled in config")
        return 0

    host = imap_config.get("host", "")
    port = int(imap_config.get("port", 993))
    use_ssl = imap_config.get("ssl", True)
    username = imap_config.get("username", "")
    password = imap_config.get("password", "")
    folder = imap_config.get("folder", "INBOX")
    processed_folder = imap_config.get("processed_folder", "")
    delete_after = imap_config.get("delete_after_import", False)

    if not host or not username or not password:
        logging.error("IMAP config incomplete: host, username and password are required")
        return 0

    downloaded = 0

    try:
        logging.info(f"IMAP: Connecting to {host}:{port} (SSL={use_ssl})")
        if use_ssl:
            mail = imaplib.IMAP4_SSL(host, port)
        else:
            mail = imaplib.IMAP4(host, port)

        mail.login(username, password)
        status, _ = mail.select(folder)
        if status != "OK":
            logging.error(f"IMAP: Could not select folder '{folder}'")
            mail.logout()
            return 0

        status, messages = mail.search(None, "UNSEEN")
        if status != "OK":
            logging.error("IMAP: Search for unseen messages failed")
            mail.logout()
            return 0

        email_ids = [eid for eid in messages[0].split() if eid]
        logging.info(f"IMAP: Found {len(email_ids)} unseen message(s)")

        for email_id in email_ids:
            try:
                status, msg_data = mail.fetch(email_id, "(RFC822)")
                if status != "OK" or not msg_data or msg_data[0] is None:
                    continue

                msg = email.message_from_bytes(msg_data[0][1])
                has_pdf = False

                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = part.get_content_disposition() or ""
                    filename = part.get_filename()

                    is_pdf = (
                        content_type == "application/pdf"
                        or (
                            "attachment" in content_disposition
                            and filename
                            and filename.lower().endswith(".pdf")
                        )
                    )

                    if not is_pdf or not filename:
                        continue

                    safe_name = sanitize_filename(filename)
                    dest_path = unique_path(unknown_dir, safe_name)

                    payload = part.get_payload(decode=True)
                    if not payload:
                        logging.warning(f"IMAP: Empty payload for attachment '{filename}', skipping")
                        continue

                    with open(dest_path, "wb") as f:
                        f.write(payload)

                    logging.info(f"IMAP: Saved attachment '{safe_name}' to {dest_path}")
                    has_pdf = True
                    downloaded += 1

                if has_pdf:
                    if delete_after:
                        mail.store(email_id, "+FLAGS", "\\Deleted")
                    else:
                        if processed_folder:
                            try:
                                mail.copy(email_id, processed_folder)
                            except Exception as copy_err:
                                logging.warning(f"IMAP: Could not copy to '{processed_folder}': {copy_err}")
                        mail.store(email_id, "+FLAGS", "\\Seen")

            except Exception as e:
                logging.error(f"IMAP: Error processing message {email_id}: {e}")

        if delete_after:
            mail.expunge()

        mail.logout()

    except Exception as e:
        logging.error(f"IMAP: Connection error: {e}")
        return 0

    if downloaded > 0:
        logging.info(f"IMAP: Downloaded {downloaded} PDF(s) to unknown folder")
        status.set_update_needed(True)

    return downloaded


def _imap_cron():
    """Background thread that periodically scans the IMAP mailbox."""
    while True:
        imap_config = get_imap_config()
        interval = float(imap_config.get("scan_interval", 300))

        if imap_config.get("enabled", False):
            try:
                count = scan_imap()
                if count:
                    logging.info(f"IMAP cron: processed {count} PDF(s)")
            except Exception as e:
                logging.exception(f"IMAP cron error: {e}")

        time.sleep(interval)


# Start background thread on module import
_imap_thread = threading.Thread(target=_imap_cron, daemon=True)
_imap_thread.start()
