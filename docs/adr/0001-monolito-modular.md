# ADR-0001: Monolito modular con FastAPI + SQLite + HTMX

- **Estado:** aceptada
- **Fecha:** 2026-11-11

## Contexto
Una sola profesora y unas decenas de alumnos (37 en el Excel, 10 activos). El uso principal es
desde el móvil, justo al acabar la clase. Lalo quiere Python, HTML, SQL y CSS, y aprender buenas
prácticas. La app tiene que poder crecer sin reescribirse.

## Decisión
- **Monolito modular** por dominios, con capas `routes → service → repository`.
- **FastAPI + Jinja2 + HTMX:** HTML renderizado en el servidor, con interactividad sin un
  framework JS.
- **SQLite (WAL) + SQLModel + Alembic**, con el camino a PostgreSQL abierto.
- **CSS propio** con tokens y sin build step. **PWA** instalable.
- **uv** para gestionar Python y dependencias. **ruff**, **pyright** y **pytest** para la calidad.

## Alternativas descartadas
- **React/Next + API:** dos proyectos y un pipeline de build. Es excesivo aquí y aleja de
  Python/HTML/CSS.
- **Django:** muy válido, pero con más "magia". FastAPI enseña cada pieza por separado.
- **Seguir con Google Sheets + AppSheet:** rápido, pero no resuelve la usabilidad ni el diseño.
- **Microservicios:** coste operativo (red, despliegues, consistencia) sin ningún beneficio a
  esta escala.

## Consecuencias
- ✅ Un solo despliegue, barato y fácil de entender de punta a punta.
- ✅ La lógica de negocio se prueba sin servidor.
- ⚠️ SQLite necesita un volumen persistente y backups en el hosting (Fase 4).
- ⚠️ La interactividad muy compleja (offline total, arrastrar y soltar) costaría más con HTMX.
