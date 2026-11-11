"""Pequeñas utilidades de texto para la interfaz."""

from urllib.parse import quote


def initials(full_name: str) -> str:
    """ "Ana María López" → "AL" · "Oscar" → "OS"."""
    parts = [p for p in full_name.split() if p[:1].isalpha()]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def first_name(full_name: str) -> str:
    return full_name.split()[0] if full_name.strip() else full_name


def whatsapp_url(phone_e164: str | None, text: str = "") -> str | None:
    """Enlace wa.me que abre WhatsApp con el mensaje escrito (Kat solo pulsa "enviar")."""
    if not phone_e164:
        return None
    url = f"https://wa.me/{phone_e164.lstrip('+')}"
    return f"{url}?text={quote(text)}" if text else url
