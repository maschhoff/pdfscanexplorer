# ai_local_text.py
import json
import os
from openai import OpenAI
import settings
from PyPDF2 import PdfReader  # pip install PyPDF2

config = settings.loadConfig()
API_KEY = config.get("openai_api_key", "")
client = OpenAI(api_key=API_KEY)

def extract_text_from_pdf(path: str, max_chars: int = 15000) -> str:
    reader = PdfReader(path)
    text_parts = []
    for page in reader.pages:
        text = page.extract_text() or ""
        text_parts.append(text)
        # Stop early if very large
        if sum(len(p) for p in text_parts) > max_chars:
            break
    return "\n".join(text_parts)[:max_chars]

def categorize_document(file_path: str, ordner_liste: list[str]):
    if(API_KEY==""):
        raise ValueError("Kein API Key vorhanden!")
    pdf_text = extract_text_from_pdf(file_path)
    if not pdf_text.strip():
        raise ValueError("Keine extrahierbaren Textinhalte in der PDF.")

    # Baue Prompt — sende reinen Text (kein file-objekt)
    system_prompt = (
        "Du bist ein intelligentes Dokumentenverwaltungssystem. "
        "Lies den folgende Text (aus einer PDF) und gib ausschließlich ein JSON-Objekt im Format "
        "{\"Ordner\": \"<Ordnername>\", \"Datei\": \"<NeuerDateiname.pdf>\"} zurück."
    )

    user_text = (
        f"Liste der möglichen Ordner:\n{chr(10).join(ordner_liste)}\n\n"
        "Analysiere den folgenden Auszug aus der PDF und bestimme den passenden Ordner und Dateinamen.\n\n"
        "BEGIN PDF TEXT\n" + pdf_text + "\nEND PDF TEXT"
    )

    # Verwende chat.completions (kein file)
    response = client.chat.completions.create(
        model="gpt-5",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ],
    )

    raw = response.choices[0].message.content.strip()
    # Versuche JSON zu parsen
    try:
        parsed = json.loads(raw)
    except Exception:
        # Fallback: gib Raw zurück, damit du siehst, was das Modell ausgegeben hat
        return {"raw": raw}
    return parsed

# Beispiel
# ordner = ["Rechnungen", "Versicherung", "Steuer", "Privat"]
# print(categorize_document_local_text("rechnung.pdf", ordner))
