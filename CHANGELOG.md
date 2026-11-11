# Changelog

Todos los cambios relevantes de este proyecto se documentan aquí.
Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) ·
Versionado: [SemVer](https://semver.org/lang/es/).

## [Sin publicar]

### Añadido (Panel de Admin)
- **Panel de Admin** en `/admin`, solo para usuarios con `is_admin` (los demás ven un 404).
  Se llega desde Más → Panel de Admin. ADR-0007.
- **Usuarios:** alta, contraseña nueva, activar/desactivar. Nadie puede desactivarse a sí mismo
  y siempre queda un admin activo.
- **Registro de actividad** (`audit_events`, solo añadir): entradas y fallos, fichas, asistencia,
  cobros, horario, usuarios y exportaciones. Sin datos personales ni de salud.
- **Estado de la copia de seguridad** leyendo las métricas de Litestream (`127.0.0.1:9090`).
- **Exportar a Excel** (alumnos, clases, asistencias, pagos, bonos, tarifas, horario). Las notas
  de salud solo si se marcan.
- `scripts/make_admin.py` para dar acceso de admin desde la terminal del servidor.

### Añadido (primeras observaciones de Kat)
- **Editar ficha de alumno**: nombre, teléfono, email, fechas, ubicación, tarifa habitual,
  salud, notas, activo/inactivo y consentimiento de WhatsApp (guarda la fecha; se borra al
  retirarlo). Valida antes de guardar y conserva lo escrito si hay un error.
- **Manual de una hoja (A4)** para Kat en `docs/manual/` (HTML fuente + PDF).

### Cambiado (primeras observaciones de Kat)
- Textos sin surf: yoga y sánscrito con humor. La ola decorativa pasa a ser un divisor con la
  estrella del logo.
- Logo en SVG (nítido a cualquier tamaño).
- Service worker: estáticos con *stale-while-revalidate* y versión `katiu-v2`, para que los
  cambios de diseño lleguen al móvil sin reinstalar.

### Añadido (piloto)
- **Despliegue en Fly.io** (París): `Dockerfile` multietapa sin datos ni secretos, `fly.toml`
  con health check en `/salud` y apagado automático. ADR-0006.
- **Copia continua con Litestream** a Cloudflare R2 (UE) y restauración automática al arrancar
  en un disco vacío (`deploy/start.sh`).
- **Despliegue continuo** con GitHub Actions cuando la CI pasa en `main` (requiere
  `FLY_API_TOKEN`).
- Guía paso a paso en `docs/DEPLOY.md`.

### Cambiado (piloto)
- SQLite espera hasta 5 s al candado (`busy_timeout`) para convivir con Litestream.

### Cambiado
- Tarifa especial **Grupo Reggio · clase suelta (21 €)** como plan activo. El resto de clases
  grupales siguen a 30 €.

### Añadido (Fase 2: pasar lista en 3 toques)
- **Login** con argon2id, sesión en una cookie firmada (30 días), CSRF en todos los POST, límite
  de 5 intentos cada 15 minutos y cabeceras de seguridad (CSP estricta, HSTS en producción).
  ADR-0004.
- **Hoy**: las clases del día y las próximas, generadas solas a partir del horario fijo.
- **Pasar lista**: un toque marca "vino", otro marca "pagado" (en efectivo por defecto),
  habituales de la franja primero, buscador instantáneo, alta rápida sin salir de la pantalla y
  totales en vivo (cobrado y pendiente).
- **Alumnos**: lista con buscador, ficha (datos, salud protegida, saldo, historial) y botón de
  WhatsApp.
- **Más → Horario**: añadir o pausar clases fijas y crear clases extra puntuales. ADR-0005.
- **Contraseña**: cambiarla desde la app.
- **PWA instalable**: manifest, service worker (estáticos en caché, páginas con la red primero,
  aviso sin conexión) e iconos.
- Paleta **"Marea turquesa"** con tokens de marca y roles, modo oscuro "mar de noche",
  componentes documentados en `docs/DESIGN_SYSTEM.md` y página `/_estilo`.
- Scripts `bootstrap.py` (tarifas, horario de viernes a las 9:00 y a las 10:15, y usuario) y
  `seed_demo.py` (datos ficticios).
- 85 tests.


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
