# ADR-0006: Piloto en Fly.io (Madrid) con SQLite + Litestream

- **Estado:** aceptada
- **Fecha:** 2026-11-11
- **Sustituye en parte a:** D3 ("local hasta la Fase 4"). Lalo elige adelantar un piloto para
  que Kat pase lista de verdad antes de construir la Fase 3.

## Contexto
La app guarda datos de salud: tienen que quedarse en la UE y no perderse nunca. La usan una o
dos personas, unas pocas veces por semana. Queremos coste mínimo y cero mantenimiento.

## Opciones
1. **Fly.io + volumen + Litestream → R2.** Máquina en Madrid, se apaga sola, SQLite tal cual,
   copia continua fuera de Fly.
2. **Render/Railway + PostgreSQL gestionado.** Más caro (≥ 7 €/mes por la BD) y obliga a
   migrar de SQLite sin necesitarlo.
3. **VPS propio (Hetzner).** Barato, pero hay que mantener el sistema operativo, el
   cortafuegos y los certificados.

## Decisión
Opción 1. La imagen Docker arranca con `deploy/start.sh`: restaura desde R2 si el disco está
vacío, aplica migraciones y arranca uvicorn dentro de `litestream replicate`. HTTPS lo pone Fly.
Los secretos solo viven en `fly secrets`. El despliegue continuo va por GitHub Actions cuando
existe `FLY_API_TOKEN`.

## Consecuencias
- ✅ 2-4 €/mes, datos en la UE (Fly `mad` + R2 con jurisdicción UE), restauración automática.
- ✅ El código no cambia: misma SQLite que en local (se añade `busy_timeout` para convivir con
  Litestream).
- ⚠️ Una sola máquina: si Fly cae, la app cae (aceptable para un piloto).
- ⚠️ Primera visita tras un rato sin uso: ~2 s de arranque en frío.
- 🔁 Revisar si algún día hay varias profesoras escribiendo a la vez: entonces, PostgreSQL.
