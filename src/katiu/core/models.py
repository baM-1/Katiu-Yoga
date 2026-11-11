"""Piezas comunes a todos los modelos."""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Los timestamps se guardan siempre en UTC; se muestran en Europe/Madrid."""
    return datetime.now(UTC)
