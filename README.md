# Katiu Yoga 🌊

Mini app web para que Kat lleve a sus alumnos, las asistencias, los cobros y los recordatorios
**desde el móvil y sin volver a copiar un ID**. Sustituye a la hoja de Google Sheets
`Katiu_Yoga_CONTROL`.

> Estado: **Fase 2 (pasar lista en 3 toques)**. Ver el [roadmap](#fases) y el [CHANGELOG](CHANGELOG.md).

## Arrancar en local

Necesitas [uv](https://docs.astral.sh/uv/) (instala Python 3.13 por ti).

```bash
uv sync                      # crea .venv e instala dependencias exactas (uv.lock)
cp .env.example .env         # configuración local
uv run pre-commit install    # activa los checks antes de cada commit
uv run python scripts/bootstrap.py --email tu@email.com   # BD + tarifas + horario + usuario
uv run fastapi dev           # http://127.0.0.1:8000
```

### Probar con datos ficticios
```bash
KATIU_DATABASE_URL=sqlite:///data/demo.db uv run python scripts/seed_demo.py
KATIU_DATABASE_URL=sqlite:///data/demo.db uv run fastapi dev   # demo@katiu.local / demo-olas
```

## Comandos del día a día

| Qué | Comando |
|---|---|
| Tests | `uv run pytest` |
| Lint | `uv run ruff check .` |
| Formato | `uv run ruff format .` |
| Tipos | `uv run pyright` |
| Importar el Excel | `uv run python scripts/import_excel.py` (idempotente; informe en `data/import_report.md`) |
| Nueva migración | `uv run alembic revision --autogenerate -m "qué cambia"` |
| Todo lo del CI | `uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest` |

## Datos personales (RGPD)

El Excel original va en `data/raw/` y la base de datos en `data/katiu.db`. **Ninguno de los dos
entra en git**: lo impiden `.gitignore` y un hook de pre-commit. Los tests y las capturas usan
siempre datos ficticios.

## Estructura

```
src/katiu/
├── main.py          # crea la app y monta los módulos
├── core/            # config, db, seguridad, plantillas, dinero
├── students/        # cada módulo de dominio tiene:
├── classes/         #   routes.py     → HTTP (HTML/HTMX)
├── attendance/      #   service.py    → reglas de negocio
├── payments/        #   repository.py → consultas a la BD
├── dashboard/
├── reminders/
├── accounts/        # usuarios y login
├── settings/        # menú Más, horario y contraseña
├── importing/       # importación del Excel
├── templates/       # base.html y parciales compartidos
└── static/          # css (tokens), iconos, PWA
```

Por qué está organizada así: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) y
[ADR-0001](docs/adr/0001-monolito-modular.md).

## Fases

0. Arranque: repo, herramientas, CI, "Hola Kat". ✓
1. Cimientos y datos limpios: modelo, migraciones, importación del Excel. ✓
2. **Pasar lista en 3 toques:** login, diseño Marea turquesa, Hoy, Pasar lista, Alumnos, PWA. ← *aquí*
3. Dinero y panorama: saldos, pagos, dashboard, exportación.
4. Recordatorios y despliegue.
