import re
from urllib.parse import urlsplit


def normalize_name(value: str) -> str:
    name = " ".join(value.strip().split())
    if not 2 <= len(name) <= 128:
        raise ValueError("Имя должно содержать от 2 до 128 символов")
    if sum(char.isalpha() for char in name) < 2 or not all(
        char.isalpha() or char in " -'’" for char in name
    ):
        raise ValueError("Имя может содержать только буквы, пробелы, дефис и апостроф")
    return name


def normalize_phone(value: str) -> str:
    phone = re.sub(r"[\s().-]", "", value.strip())
    if phone.startswith("00"):
        phone = f"+{phone[2:]}"
    if phone.startswith("8") and len(phone) == 11:
        phone = f"+7{phone[1:]}"
    elif phone.isdigit() and len(phone) == 10:
        phone = f"+7{phone}"
    elif phone.isdigit():
        phone = f"+{phone}"
    if not re.fullmatch(r"\+[1-9]\d{9,14}", phone):
        raise ValueError("Укажите корректный номер телефона, например +7 999 123-45-67")
    return phone


def normalize_email(value: str) -> str:
    """Приводит почту к единому виду и отсекает явно некорректные адреса."""
    email = value.strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("Укажите корректную почту, например name@example.com")
    return email


def normalize_zoom_url(value: str) -> str:
    """Проверяет ссылку Zoom перед сохранением в карточке встречи."""
    url = value.strip()
    if len(url) > 2048:
        raise ValueError("Ссылка Zoom слишком длинная")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Укажите полную Zoom-ссылку, начинающуюся с https://")
    return url
