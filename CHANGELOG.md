# Changelog

Todos los cambios relevantes de este proyecto se documentan aquí.
Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) ·
Versionado: [SemVer](https://semver.org/lang/es/).

## [Sin publicar]

### Añadido
- Fase 0: esqueleto del proyecto con uv y Python 3.13, organizado como monolito modular
  (`core`, `students`, `classes`, `attendance`, `payments`, `dashboard`, `reminders`).
- App FastAPI con la página "Hola Kat 🌊" y el endpoint `/salud`.
- Primeros tokens de diseño "Boho Surf" (claro y modo oscuro "atardecer").
- Configuración con pydantic-settings y `.env.example`.
- Calidad: ruff (lint + formato), pyright, pytest y pre-commit, con un hook que bloquea
  Excel, CSV, bases de datos y `.env`.
- CI en GitHub Actions: lint, formato, tipos y tests en cada PR.
- Documentación: README, `docs/ARCHITECTURE.md` y ADR-0001.
