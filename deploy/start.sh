#!/bin/sh
# Arranque en producción:
#   1. Si el disco está vacío (máquina nueva), recupera la base de datos desde la copia.
#   2. Aplica las migraciones pendientes.
#   3. Arranca la app "dentro" de Litestream, que replica mientras la app viva.
set -eu

DB=/data/katiu.db

if [ -n "${LITESTREAM_BUCKET:-}" ]; then
  litestream restore -if-db-not-exists -if-replica-exists -config /etc/litestream.yml "$DB"
else
  echo "⚠️  LITESTREAM_BUCKET no definido: arrancando SIN copia de seguridad" >&2
fi

alembic upgrade head

APP="uvicorn katiu.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=*"
if [ -n "${LITESTREAM_BUCKET:-}" ]; then
  exec litestream replicate -config /etc/litestream.yml -exec "$APP"
else
  exec $APP
fi
