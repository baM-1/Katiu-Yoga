# Changelog

Todos los cambios relevantes de este proyecto se documentan aquí.
Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) ·
Versionado: [SemVer](https://semver.org/lang/es/).

## [Sin publicar]

### Añadido (Fase 1: cimientos y datos limpios)
- Modelo de datos con SQLModel: planes, horario recurrente, clases, alumnos, asistencias, pagos,
  bonos y registro de recordatorios. Diagrama ER en `docs/DATA_MODEL.md` y ADR-0003.
- Catálogo de tarifas 2026: individual presencial y online, y grupal, con clase suelta y bonos de
  4 y 8 clases (60 días).
- `core/money.py` (céntimos y formato en euros), `core/db.py` (SQLite en modo WAL con claves
  foráneas activadas) y un repositorio base con repositorios por módulo.
- Migraciones con Alembic (esquema inicial) y un test que comprueba que coinciden con los modelos.
- `scripts/import_excel.py`: importación idempotente del Excel con limpieza de teléfonos
  (E.164), nombres, fechas en texto y filas corridas, más un informe de anomalías y un cuadre con
  RESUMEN_MENSUAL.
- 51 tests (reglas de limpieza, dinero, importación, idempotencia y migraciones) sobre un Excel
  ficticio.

### Corregido
- La lectura de CATALOGOS mezclaba sus dos tablas porque repiten la cabecera "Tipo_de_clase".

## Fase 0

### Añadido
- Fase 0: esqueleto del proyecto con uv y Python 3.13, organizado como monolito modular
  (`core`, `students`, `classes`, `attendance`, `payments`, `dashboard`, `reminders`).
- App FastAPI con la página "Hola Kat 🌊" y el endpoint `/salud`.
- Identidad visual de Katiu Yoga (ADR-0002): paleta oficial, logo y tipografías Newsreader + Inter,
  con modo oscuro "bosque de noche".
- Configuración con pydantic-settings y `.env.example`.
- Calidad: ruff (lint + formato), pyright, pytest y pre-commit, con un hook que bloquea
  Excel, CSV, bases de datos y `.env`.
- CI en GitHub Actions: lint, formato, tipos y tests en cada PR.
- Documentación: README, `docs/ARCHITECTURE.md`, ADR-0001 y ADR-0002.
