# ai.py — AI folder/filename suggestion, multi-provider
import json
import re
import settings
from PyPDF2 import PdfReader  # pip install PyPDF2

SYSTEM_PROMPT = (
    "Du bist ein intelligentes Dokumentenverwaltungssystem. "
    "Lies den folgende Text (aus einer PDF) und gib ausschließlich ein JSON-Objekt im Format "
    "{\"Ordner\": \"<Ordnername>\", \"Datei\": \"<NeuerDateiname.pdf>\"} zurück. "
    "Gib nur das reine JSON-Objekt zurück, ohne Markdown-Codeblock und ohne weiteren Text."
)


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


def _build_user_text(ordner_liste: list[str], pdf_text: str) -> str:
    return (
        f"Liste der möglichen Ordner:\n{chr(10).join(ordner_liste)}\n\n"
        "Analysiere den folgenden Auszug aus der PDF und bestimme den passenden Ordner und Dateinamen.\n\n"
        "BEGIN PDF TEXT\n" + pdf_text + "\nEND PDF TEXT"
    )


def _parse_response(raw: str):
    raw = raw.strip()
    # Models sometimes wrap the JSON in a markdown code fence despite instructions not to.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", raw, re.DOTALL)
    if fence:
        raw = fence.group(1).strip()
    try:
        return json.loads(raw)
    except Exception:
        # Fallback: gib Raw zurück, damit du siehst, was das Modell ausgegeben hat
        return {"raw": raw}


def _call_openai_compatible(api_key: str, model: str, base_url: str | None, system_prompt: str, user_text: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
    )
    return response.choices[0].message.content.strip()


def _call_gemini(api_key: str, model: str, system_prompt: str, user_text: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    gen_model = genai.GenerativeModel(model, system_instruction=system_prompt)
    response = gen_model.generate_content(user_text)
    return response.text.strip()


def _call_anthropic(api_key: str, model: str, system_prompt: str, user_text: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": user_text}],
    )
    return response.content[0].text.strip()


def categorize_document(file_path: str, ordner_liste: list[str]):
    config = settings.loadConfig()
    ai_cfg = config.get("ai", {}) or {}
    provider = ai_cfg.get("provider") or "openai"

    pdf_text = extract_text_from_pdf(file_path)
    if not pdf_text.strip():
        raise ValueError("Keine extrahierbaren Textinhalte in der PDF.")
    user_text = _build_user_text(ordner_liste, pdf_text)

    if provider == "openai":
        cfg = ai_cfg.get("openai", {}) or {}
        api_key = cfg.get("api_key", "")
        if not api_key:
            raise ValueError("No API Key set!")
        raw = _call_openai_compatible(api_key, cfg.get("model") or "gpt-5", None, SYSTEM_PROMPT, user_text)

    elif provider == "deepseek":
        cfg = ai_cfg.get("deepseek", {}) or {}
        api_key = cfg.get("api_key", "")
        if not api_key:
            raise ValueError("No API Key set!")
        raw = _call_openai_compatible(
            api_key, cfg.get("model") or "deepseek-chat", "https://api.deepseek.com", SYSTEM_PROMPT, user_text
        )

    elif provider == "ollama":
        cfg = ai_cfg.get("ollama", {}) or {}
        host = (cfg.get("host") or "http://localhost:11434").rstrip("/")
        raw = _call_openai_compatible(
            "ollama", cfg.get("model") or "llama3.1", host + "/v1", SYSTEM_PROMPT, user_text
        )

    elif provider == "gemini":
        cfg = ai_cfg.get("gemini", {}) or {}
        api_key = cfg.get("api_key", "")
        if not api_key:
            raise ValueError("No API Key set!")
        raw = _call_gemini(api_key, cfg.get("model") or "gemini-2.5-flash", SYSTEM_PROMPT, user_text)

    elif provider == "anthropic":
        cfg = ai_cfg.get("anthropic", {}) or {}
        api_key = cfg.get("api_key", "")
        if not api_key:
            raise ValueError("No API Key set!")
        raw = _call_anthropic(api_key, cfg.get("model") or "claude-sonnet-4-5", SYSTEM_PROMPT, user_text)

    else:
        raise ValueError(f"Unknown AI provider: {provider}")

    return _parse_response(raw)
