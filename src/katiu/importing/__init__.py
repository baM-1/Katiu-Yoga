"""Importación del Excel histórico (Google Sheets) a la base de datos.

- `cleaning.py`: reglas de limpieza puras (sin BD, sin archivos) → fáciles de testear.
- `excel.py`: lee las hojas del .xlsx como listas de diccionarios.
- `service.py`: orquesta la importación idempotente y produce el informe.
"""
