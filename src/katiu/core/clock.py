"""La hora "de Kat": todo lo que dependa de "hoy" pasa por aquí (y los tests lo pueden fijar)."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from katiu.core.config import get_settings


def tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def now() -> datetime:
    return datetime.now(tz())


def today() -> date:
    return now().date()
