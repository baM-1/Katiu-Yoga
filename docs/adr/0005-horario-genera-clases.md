# ADR-0005: El horario fijo genera las clases; las extra se crean a mano

- **Estado:** aceptada
- **Fecha:** 2026-11-11

## Contexto
En el Excel, Kat creaba cada clase a mano (`CLA-0001`…) y luego copiaba su ID. Su horario real
es de viernes a las 9:00 y a las 10:15, pero quiere poder abrir más franjas o una clase puntual.

## Decisión
- **`ScheduleSlot`** = franja semanal (día + hora + tipo + duración). Kat las gestiona en
  *Más → Horario*.
- **`generate_sessions()`** crea las clases de los próximos 14 días a partir de las franjas
  activas. Es **idempotente**: si una franja ya tiene su clase ese día, no la duplica. Se ejecuta
  al abrir "Hoy" y al guardar una franja, así que no hace falta un cron.
- **Pausar una franja** retira sus clases futuras **vacías**. Las que ya tienen gente se
  conservan.
- **Clase extra**: una `ClassSession` sin franja. Al crearla, la app lleva directamente a pasar
  lista.
- **Habituales**: la lista ordena primero a quien vino a esa misma franja (día de la semana +
  hora) en los últimos 120 días.

## Alternativas descartadas
- **Reglas de recurrencia (RRULE / iCal):** muy potentes, pero aquí sobran. "Cada viernes a
  las 9" cabe en dos columnas.
- **Cron nocturno que genere las clases:** otra pieza que vigilar. Generar al abrir "Hoy" cuesta
  milisegundos.

## Consecuencias
- ✅ Kat no crea nunca una clase normal, y pasar lista son 3 toques: Hoy → clase → alumno.
- ⚠️ Si se cambia el precio de una tarifa, las clases ya generadas conservan el precio anterior
  (es intencionado: ver ADR-0003). Afecta como mucho a 2 semanas.
