# Despliegue (piloto en Fly.io)

La app vive en **Fly.io, región París** (`cdg`, la UE más cercana: Fly ya no ofrece Madrid). SQLite está en un disco persistente y
**Litestream** copia cada cambio a **Cloudflare R2** (jurisdicción UE). Por qué así: ver
[ADR-0006](adr/0006-despliegue-fly-litestream.md).

```
móvil de Kat ──HTTPS──▶ Fly.io (París) ─── uvicorn + FastAPI
                                │
                                ├── /data/katiu.db  (disco de 1 GB)
                                └── Litestream ──▶ R2 (copia continua, 30 días)
```

Coste aproximado: 2-4 €/mes (la máquina se apaga sola cuando nadie la usa). R2: gratis
hasta 10 GB.

## 0. Antes de empezar (una vez)

- Cuenta en https://fly.io y en https://dash.cloudflare.com (las dos piden tarjeta).
- En el Mac: `brew install flyctl` y después `fly auth login`.
- El Excel real en `data/raw/Katiu_Yoga_CONTROL.xlsx` (no va a git).

## 1. Bucket de copias en Cloudflare R2

1. R2 → **Create bucket** → nombre `katiu-backups`, **Jurisdiction: European Union**.
2. R2 → **Manage API tokens** → **Create API token** → permiso *Object Read & Write*, solo
   para `katiu-backups`.
3. Apunta: *Access Key ID*, *Secret Access Key* y el endpoint de la UE, que tiene esta forma:
   `https://<ACCOUNT_ID>.eu.r2.cloudflarestorage.com`.

## 2. Crear la app en Fly

Desde la carpeta del repo:

```bash
fly apps create katiu-yoga          # si el nombre está cogido, elige otro y cámbialo en fly.toml
fly volumes create katiu_data --region cdg --size 1 --app katiu-yoga   # responde "y" al aviso
fly secrets set --app katiu-yoga \
  KATIU_SECRET_KEY="$(openssl rand -hex 32)" \
  LITESTREAM_BUCKET=katiu-backups \
  LITESTREAM_ENDPOINT="https://<ACCOUNT_ID>.eu.r2.cloudflarestorage.com" \
  LITESTREAM_ACCESS_KEY_ID="<access key>" \
  LITESTREAM_SECRET_ACCESS_KEY="<secret>"
fly deploy
```

Comprueba: `curl https://katiu-yoga.fly.dev/salud` → `{"estado":"ok"}`.

> El aviso de Fly sobre "un solo volumen" es esperado: la redundancia la da Litestream.

## 3. Cargar los datos reales (una vez)

```bash
# Subir el Excel a la carpeta temporal de la máquina (se borra al reiniciar)
fly ssh sftp shell --app katiu-yoga
» put data/raw/Katiu_Yoga_CONTROL.xlsx /tmp/control.xlsx
» exit

# Entrar en la máquina
fly ssh console --app katiu-yoga
$ python scripts/import_excel.py /tmp/control.xlsx --report /tmp/informe.md
$ python scripts/bootstrap.py --email <email de Kat> --nombre Kat   # pide la contraseña
$ rm /tmp/control.xlsx /tmp/informe.md
$ exit
```

El orden importa: primero el Excel (trae alumnos y precios históricos) y después
`bootstrap.py` (horario de viernes y usuario). Los dos son idempotentes.

## 4. En el móvil de Kat

1. Abrir `https://katiu-yoga.fly.dev` en Safari (o Chrome en Android) y entrar.
2. Compartir → **Añadir a pantalla de inicio**. Desde ahí se abre como una app.
3. Recomendado: que Kat cambie la contraseña en **Más → Contraseña**.

## 5. Despliegue automático (opcional, recomendado)

```bash
fly tokens create deploy --app katiu-yoga --expiry 8760h
```

Pega el token en GitHub → *Settings → Secrets and variables → Actions* → `FLY_API_TOKEN`.
Desde entonces, cada merge a `main` con la CI en verde se despliega solo
(`.github/workflows/deploy.yml`).

## Copias de seguridad

- **Ver qué copias hay:**
  `fly ssh console -C "litestream snapshots -config /etc/litestream.yml /data/katiu.db"`
- **Restaurar en una máquina nueva:** no hay que hacer nada. Si el disco está vacío, el
  arranque (`deploy/start.sh`) recupera la base de datos desde R2 antes de abrir la app.
- **Bajarte una copia al Mac** (en local, con Litestream instalado y las mismas variables):
  `litestream restore -config deploy/litestream.yml -o backups/katiu.db /data/katiu.db`

## Si algo va mal

| Síntoma | Qué mirar |
|---|---|
| La app no arranca | `fly logs --app katiu-yoga` |
| "LITESTREAM_BUCKET no definido" en los logs | Faltan los secretos del paso 2 |
| Se cerró la sesión de Kat tras un despliegue | Se cambió `KATIU_SECRET_KEY`; no cambiarla salvo filtración |
